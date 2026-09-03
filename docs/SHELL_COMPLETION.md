# Shell Tab-Completion

`leetnotes` is built with [Click](https://click.palletsprojects.com/), which supports shell tab-completion out of the box for Bash, Zsh, and Fish.

Once `leetnotes` is installed on your PATH (e.g. via `pip install .`, `uv tool install .`, or inside your virtual environment), you can generate completions for your shell.

## 1. Fish

```fish
_LEETNOTES_COMPLETE=fish_source leetnotes > ~/.config/fish/completions/leetnotes.fish
```

Fish autoloads this by filename — nothing else to add to `config.fish`.

## 2. Bash

Add to `~/.bashrc`:

```bash
eval "$(_LEETNOTES_COMPLETE=bash_source leetnotes)"
```

## 3. Zsh

Add to `~/.zshrc`:

```zsh
eval "$(_LEETNOTES_COMPLETE=zsh_source leetnotes)"
```

## Using Completion

```bash
leetnotes <TAB>                 # -> notes  problems
leetnotes problems <TAB>        # -> count  data  delete  list  recent  render  show
leetnotes notes prefill --<TAB> # -> --all  --regenerate  --limit  --max-failures  --rate-limit/--no-rate-limit
```
