# generate_ledger aka LedgerTools

## Project Layout

    src/generate_ledger/
      __init__.py
      cli.py                # <- tiny entrypoint: just sets up Click + registers commands
      commands/             # <- Click command functions (thin), one file per topic
        __init__.py
        config.py           # config subcommands: edit/show/validate/init
        run.py              # run/start/stop/etc.
      services/             # <- REAL business lives here
        __init__.py
        config_service.py   # load/merge/validate config (no Click imports)
        runner.py           # core runtime logic
      models/
        __init__.py
        config.py           # pydantic schemas
      utils/
        __init__.py
        paths.py            # platformdirs helpers, path resolution
        editor.py           # pick/launch editor
    src/gl (just a shim for convenience)

## Pushing to PyPi
To manually push to pypi:




To push to test.pypi with uv

[[tool.uv.index]]
name = "testpypi"
url = "https://test.pypi.org/simple/"
publish-url = "https://test.pypi.org/legacy/"
explicit = true

## TODOs
- [ ] Add a pre-commit check to enforce using gl as imports. something along the lines of
```
    grep -R --line-number -E '^\s*import\s+generate_ledger\b|^\s*from\s+generate_ledger\b' src \
      | grep -v '/generate_ledger/__init__\.py' && {
        echo "Use 'import gl' inside the codebase."; exit 1;
```
