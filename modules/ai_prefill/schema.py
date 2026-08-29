from pydantic import BaseModel, Field


class PrefillContent(BaseModel):
    """AI-generated draft content mapping onto the notes template's prefillable
    sections (see resources/templates/leetcode_notes_plain.md.j2). This is the
    schema handed to the AI provider and validated against on the way back."""

    problem_summary: str = ""
    core_idea: list[str] = Field(default_factory=list)
    # Loop invariant, split into the four parts of the classic
    # initialization/maintenance/termination argument — see the
    # "invariant_*" FIELD GUIDANCE blocks in system_prompt.txt.
    # invariant_statement is a single sentence; the other three are each up
    # to 5 short bullets (not paragraphs) explaining that part.
    invariant_statement: str = ""
    invariant_initialization: list[str] = Field(default_factory=list)
    invariant_maintenance: list[str] = Field(default_factory=list)
    invariant_termination: list[str] = Field(default_factory=list)
    trap: list[str] = Field(default_factory=list)
    recognition_clue: list[str] = Field(default_factory=list)
    complexity_time: str = ""
    complexity_space: str = ""
