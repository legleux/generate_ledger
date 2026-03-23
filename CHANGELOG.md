# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 2026-03-23

### Changed

- CLI: `gen ledger` and `gen auto` no longer require double subcommand name (was `gen ledger ledger`)
- Amendments: `develop` profile auto-fetches amendment list from GitHub; `release` profile queries mainnet RPC
- All imports standardized to `from generate_ledger.*` (`gl` alias remains as a dev-only convenience)
- Removed bundled `amendments_develop.json`; renamed `amendments_release.json` to `amendments_mainnet.json`
- Dead CLI files removed (`cli/__init__.py`, `cli/compose.py`); `auto.py` renamed to `click_builder.py`
- Backend tiers: `fast` dependency group is no longer included in `dev` by default

### Added

- Project description added to `pyproject.toml`
- Complexity reporting (complexipy, radon) added to CI
- Conventional commits enforced via pre-commit hook
- GPU tests skip gracefully when CUDA is not available

### Removed

- Unused dependencies removed: `httpx`, `platformdirs`
- `complexipy` moved from runtime to dev dependency group
