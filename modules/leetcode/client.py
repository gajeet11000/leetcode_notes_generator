import hashlib
import time
from typing import ClassVar

import requests
import structlog
from urllib3.util import Retry

from modules.leetcode.auth_cache import (
    clear_auth_cache,
    load_auth_cache,
    save_auth_cache,
)
from modules.leetcode.rate_limiting import JitteredLimiterAdapter
from modules.leetcode.settings import leetcode_settings

logger = structlog.get_logger(__name__)


class LeetCodeAuthenticationError(RuntimeError):
    """Raised when LEETCODE_SESSION/LEETCODE_CSRF_TOKEN look invalid or
    expired — see LeetCodeClient.ensure_authenticated. LeetCode's GraphQL API
    doesn't reject a bad session with an HTTP error or a GraphQL 'errors'
    entry; user-scoped fields (submissions, solved list, ...) just silently
    resolve to null/empty instead, which would otherwise only surface much
    later as a confusing crash deep in parsing code (e.g. len(None))."""


class LeetCodeClient:
    _AUTH_ERROR_MESSAGE = (
        "LeetCode says you're not signed in — LEETCODE_SESSION/LEETCODE_CSRF_TOKEN "
        "in .env look invalid or expired. Copy fresh values from an authenticated "
        "browser session and try again."
    )

    def __init__(self, settings=leetcode_settings):
        self.settings = settings
        self.session = requests.Session()
        self.graphql_url = f"{self.settings.BASE_URL}/graphql"
        self._authenticated: bool | None = None

        self._setup_session()

    def _credential_hash(self) -> str:
        """One-way hash of the current SESSION+CSRF_TOKEN — identifies
        *which* credentials a cached authentication result belongs to,
        without ever writing the raw secrets to disk."""
        raw = f"{self.settings.SESSION}:{self.settings.CSRF_TOKEN}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _probe_signed_in(self) -> bool:
        """The actual network call: asks LeetCode directly whether the
        current session is signed in."""
        query = "query globalData { userStatus { isSignedIn } }"
        try:
            response = self.session.post(self.graphql_url, json={"query": query})
            response.raise_for_status()
            result = response.json()
        except requests.exceptions.RequestException:
            logger.exception("authentication_check_failed")
            raise
        return bool(
            ((result.get("data") or {}).get("userStatus") or {}).get("isSignedIn")
        )

    def ensure_authenticated(self, force: bool = False) -> None:
        """Verifies LEETCODE_SESSION/CSRF_TOKEN are actually valid before a
        user-scoped request goes out.

        Three layers of caching, cheapest first (skipped entirely when
        force=True — used for a reactive re-check after an already-suspicious
        result, see get_solved_questions/get_recent_ac_submissions/
        LeetCodeSyncManager.populate_submission_code):
        1. In-memory, per client instance — a batch run only ever pays for
           one real check no matter how many slugs it processes.
        2. On-disk (see auth_cache.py) — a fresh CLI process (a new client
           instance) skips the check too, as long as SESSION/CSRF_TOKEN
           haven't changed (credential hash still matches) and the cached
           result isn't older than AUTH_CHECK_TTL_SECONDS. The TTL exists
           because a session can go stale on LeetCode's side without the
           .env values themselves ever changing — trusting a hash match
           forever would silently miss exactly that case.
        3. Otherwise: an actual network check, whose result updates both
           caches — success refreshes the on-disk record (resets the TTL
           clock); failure clears it, so a later, separate CLI invocation
           within the old TTL window doesn't keep trusting a now-known-stale
           record either.

        Raises LeetCodeAuthenticationError if LeetCode says we're not signed in.
        """
        if not force:
            if self._authenticated is not None:
                if not self._authenticated:
                    raise LeetCodeAuthenticationError(self._AUTH_ERROR_MESSAGE)
                return

            cached = load_auth_cache()
            if cached and cached.get("credential_hash") == self._credential_hash():
                age = time.time() - cached.get("verified_at", 0)
                if age < self.settings.AUTH_CHECK_TTL_SECONDS:
                    self._authenticated = True
                    logger.info(
                        "authentication_check_skipped",
                        reason="cached_and_fresh",
                        age_seconds=round(age),
                    )
                    return

        signed_in = self._probe_signed_in()
        self._authenticated = signed_in
        if signed_in:
            save_auth_cache(self._credential_hash(), time.time())
        else:
            clear_auth_cache()
        logger.info("authentication_check_completed", signed_in=signed_in, forced=force)
        if not signed_in:
            raise LeetCodeAuthenticationError(self._AUTH_ERROR_MESSAGE)

    def _setup_session(self):
        # 1. Automatic Retries on HTTP 429 (Too Many Requests) or Server Errors (5xx)
        retries = Retry(
            total=3,  # Total number of retries
            backoff_factor=2,  # Exponential backoff: 2s, 4s, 8s
            status_forcelist=[429, 500, 502, 503, 504],
            raise_on_status=False,
        )

        # 2. Rate Limiting Adapter, plus jitter — see rate_limiting.py for why.
        rate_limiter = JitteredLimiterAdapter(
            per_second=self.settings.REQUESTS_PER_SECOND,
            max_retries=retries,
        )

        # Mount the rate limiter and retries on all HTTP/HTTPS endpoints
        self.session.mount("https://", rate_limiter)
        self.session.mount("http://", rate_limiter)

        logger.info(
            "http_session_configured",
            requests_per_second=self.settings.REQUESTS_PER_SECOND,
            jitter_range=rate_limiter.jitter_range,
            max_retries=retries.total,
        )

        # Configure Headers and Cookies
        self.session.headers.update(
            {
                "X-CSRFToken": self.settings.CSRF_TOKEN,
                "Content-Type": "application/json",
                "Referer": str(self.settings.BASE_URL),
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
            }
        )
        self.session.cookies.set(
            "LEETCODE_SESSION",
            self.settings.SESSION,
            domain="leetcode.com",
        )
        self.session.cookies.set(
            "csrftoken",
            self.settings.CSRF_TOKEN,
            domain="leetcode.com",
        )

    _DIFFICULTY_LEVELS: ClassVar[dict[int, str]] = {
        0: "Unknown",
        1: "Easy",
        2: "Medium",
        3: "Hard",
    }

    def get_solved_questions(self) -> list[dict]:
        """Fetches all solved problems ('ac' status) from the REST API endpoint.

        The same response already carries id/title/difficulty for every
        problem (not just slug), at no extra request cost — pulling those
        out here lets callers (e.g. the CLI picker) label a slug that's
        solved on LeetCode but not yet fetched locally, without a per-slug
        GraphQL round trip.
        """
        self.ensure_authenticated()

        url = self.settings.ENDPOINT_ALL_PROBLEMS
        logger.info("solved_questions_request_started", url=url)

        try:
            response = self.session.get(url)
            response.raise_for_status()
        except Exception:
            logger.exception("solved_questions_request_failed", url=url)
            raise

        data = response.json()
        raw_pairs = data.get("stat_status_pairs", [])

        solved_problems = []

        for pair in raw_pairs:
            if pair.get("status") != "ac":
                continue
            stat = pair.get("stat") or {}
            solved_problems.append(
                {
                    "slug": stat.get("question__title_slug"),
                    "id": stat.get("frontend_question_id"),
                    "title": stat.get("question__title"),
                    "difficulty": self._DIFFICULTY_LEVELS.get(
                        (pair.get("difficulty") or {}).get("level", 0)
                    ),
                }
            )

        if not solved_problems:
            # Coming back with zero solved problems is essentially always a
            # dead session rather than reality (see LeetCodeSyncManager —
            # this endpoint is the source of truth for "solved" in the first
            # place). Force a live, uncached re-check to get a definitive
            # answer rather than silently trusting "zero solved" — a
            # genuinely brand-new account still comes through fine, since
            # this only raises if LeetCode itself confirms we're logged out.
            logger.warning(
                "solved_questions_empty_result", action="forcing_auth_recheck"
            )
            self.ensure_authenticated(force=True)

        logger.info(
            "solved_questions_request_succeeded",
            solved_count=len(solved_problems),
        )
        return solved_problems

    def get_question_details(self, slug: str) -> dict:
        """Queries LeetCode's GraphQL API to get comprehensive metadata for a specific problem."""
        log = logger.bind(slug=slug)
        query = """
        query selectQuestion($titleSlug: String!) {
          question(titleSlug: $titleSlug) {
            content
            questionFrontendId
            title
            titleSlug
            difficulty
            categoryTitle
            topicTags {
              name
              slug
            }
          }
        }
        """

        payload = {"query": query, "variables": {"titleSlug": slug}}

        log.info("question_details_request_started")
        try:
            response = self.session.post(self.graphql_url, json=payload)
            response.raise_for_status()
        except Exception:
            log.exception("question_details_request_failed")
            raise

        result = response.json()
        if "errors" in result:
            log.error("question_details_request_failed", errors=result["errors"])
            raise RuntimeError(f"GraphQL Error: {result['errors']}")

        question = (result.get("data") or {}).get("question")
        if not question:
            log.warning("question_details_not_found")
        else:
            log.info("question_details_request_succeeded", title=question.get("title"))

        return result

    def get_submission_list(self, slug: str, limit: int = 20) -> dict:
        """Queries LeetCode GraphQL to retrieve the submission history for a given problem."""
        self.ensure_authenticated()
        log = logger.bind(slug=slug)
        query = """
        query submissionList($questionSlug: String!, $limit: Int, $offset: Int) {
          questionSubmissionList(
            questionSlug: $questionSlug
            limit: $limit
            offset: $offset
          ) {
            submissions {
              id
              statusDisplay
              lang
              timestamp
            }
          }
        }
        """

        payload = {
            "query": query,
            "variables": {
                "questionSlug": slug,
                "limit": limit,
                "offset": 0,
            },
        }

        log.info("submission_list_request_started", limit=limit)
        try:
            response = self.session.post(self.graphql_url, json=payload)
            response.raise_for_status()
        except Exception:
            log.exception("submission_list_request_failed")
            raise

        result = response.json()
        if "errors" in result:
            log.error("submission_list_request_failed", errors=result["errors"])
            raise RuntimeError(f"GraphQL Error: {result['errors']}")

        submissions = (
            (result.get("data") or {}).get("questionSubmissionList") or {}
        ).get("submissions") or []
        log.info("submission_list_request_succeeded", submission_count=len(submissions))

        return result

    def get_recent_ac_submissions(
        self, username: str | None = None, limit: int = 20
    ) -> dict:
        """Queries LeetCode GraphQL for a user's most recent accepted submissions.

        Uses `username` if given, otherwise falls back to `LEETCODE_USERNAME`
        from settings. Raises ValueError if neither is available.
        """
        self.ensure_authenticated()

        target_username = username or self.settings.USERNAME
        if not target_username:
            raise ValueError(
                "No LeetCode username available — pass one explicitly or set LEETCODE_USERNAME."
            )

        log = logger.bind(username=target_username)
        query = """
        query recentAcSubmissions($username: String!, $limit: Int!) {
          recentAcSubmissionList(username: $username, limit: $limit) {
            title
            titleSlug
            timestamp
          }
        }
        """

        payload = {
            "query": query,
            "variables": {"username": target_username, "limit": limit},
        }

        log.info("recent_ac_submissions_request_started", limit=limit)
        try:
            response = self.session.post(self.graphql_url, json=payload)
            response.raise_for_status()
        except Exception:
            log.exception("recent_ac_submissions_request_failed")
            raise

        result = response.json()
        if "errors" in result:
            log.error("recent_ac_submissions_request_failed", errors=result["errors"])
            raise RuntimeError(f"GraphQL Error: {result['errors']}")

        submissions = (result.get("data") or {}).get("recentAcSubmissionList") or []
        if not submissions:
            # Same reasoning as get_solved_questions: a live re-check costs
            # nothing when this is a genuinely quiet period (no false
            # positive — it only raises if LeetCode confirms we're logged
            # out), but catches a dead session that would otherwise look
            # identical to "nothing recent to report".
            log.warning(
                "recent_ac_submissions_empty_result", action="forcing_auth_recheck"
            )
            self.ensure_authenticated(force=True)
        log.info(
            "recent_ac_submissions_request_succeeded", submission_count=len(submissions)
        )

        return result

    def get_submission_details(self, submission_id: int) -> dict:
        """Queries LeetCode GraphQL to get full details and source code for a specific submission ID."""
        self.ensure_authenticated()
        log = logger.bind(submission_id=submission_id)
        query = """
        query submissionDetails($submissionId: Int!) {
          submissionDetails(submissionId: $submissionId) {
            id
            code
            timestamp
            statusCode
            lang {
              name
              verboseName
            }
            runtimeDisplay
            memoryDisplay
          }
        }
        """

        payload = {
            "query": query,
            "variables": {"submissionId": int(submission_id)},
        }

        log.info("submission_details_request_started")
        try:
            response = self.session.post(self.graphql_url, json=payload)
            response.raise_for_status()
        except Exception:
            log.exception("submission_details_request_failed")
            raise

        result = response.json()
        if "errors" in result:
            log.error("submission_details_request_failed", errors=result["errors"])
            raise RuntimeError(f"GraphQL Error: {result['errors']}")

        log.info("submission_details_request_succeeded")
        return result
