# Contributing to APK-JTM

## Current maintenance model

APK-JTM is currently maintained by a single person, committing directly to `main`. There's no branch-per-feature or PR ceremony for the maintainer — this is a deliberate choice for a solo project, not an oversight.

If you're an **external contributor**, please use the process below rather than pushing directly.

## Reporting bugs or requesting features

Use the issue templates — **Bug report** or **Feature request** — when opening a new issue. They ask for the details that speed up triage (APK-JTM version, OS, steps to reproduce, etc).

Found a security vulnerability? See [SECURITY.md](SECURITY.md) instead — please don't open a public issue for those.

## Submitting a code change

1. Fork the repo and create a branch off `main` (e.g. `fix-upload-cleanup`, `add-pdf-export`).
2. Make your change. Keep commits focused — one logical change per commit, with a clear message explaining *why* the change is needed, not just what it does.
3. Run the test suite before opening a PR:
   ```
   pip install -r requirements.txt -r requirements-dev.txt
   pytest
   ```
4. Open a pull request against `main`. CI (GitHub Actions) runs the test suite automatically — it needs to pass before the PR can be merged.
5. Update [CHANGELOG.md](CHANGELOG.md) under an `[Unreleased]` heading if your change is user-facing (new feature, fix, or behaviour change). Version bumps and tagging are handled by the maintainer at release time.

## Code style

- No unnecessary abstractions — a bug fix doesn't need a refactor, a one-off script doesn't need a class hierarchy.
- Comments explain *why*, not *what* — well-named functions and variables should make the "what" obvious.
- New logic in the pure/testable modules (`extractor.py`, `apkid_client.py`, `quark_client.py`, `model_tier.py`, `paths.py`, the diff functions in `server.py`) should come with test coverage in `tests/`.

## Licence

APK-JTM is [GPL v3](LICENSE). By submitting a contribution, you agree it will be distributed under the same licence.
