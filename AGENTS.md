## Agent skills

### Implementation prerequisites

Before implementing any ticket:

1. Ask the user whether to implement the ticket on a dedicated branch or directly on `main`. Wait for an explicit choice before creating a branch or changing code. Recommend a dedicated branch named `codex/issue-<number>-<slug>`; if the user chooses `main`, verify that `main` is checked out before implementation.
2. Verify GitHub CLI inside the sandbox with `gh --version`, `gh auth status`, and repository access. If authentication or repository access fails because the sandbox cannot read GitHub CLI configuration, Windows Credential Manager, the system keyring, or the network, request controlled elevated permission and rerun the same read-only validation once outside the sandbox. Treat a successful elevated validation as authenticated; do not ask the user to log in again. Only stop before changing code and ask the user to install, authenticate, or repair GitHub CLI when `gh` is missing or the elevated validation also fails. The user owns this setup; do not substitute a temporary CLI or token workaround, copy credentials into the repository, or weaken the sandbox globally.
3. Verify the Conda environment with `conda run -n agent python --version`. Run all Python, backend, test, migration, and project-script commands in the `agent` environment, preferably via `conda run -n agent ...`; do not use the base, global, or another Python environment.
4. Install any new Python package into `agent`. When it is a project dependency, also update the repository's dependency declaration in the same change. If Conda or the `agent` environment is unavailable, stop and ask the user to create or repair it.

Frontend tools may use the repository's Node.js installation, but Python invoked by frontend or build scripts must still resolve to the `agent` environment.

### Issue tracker

Issues for this repository are tracked with GitHub Issues. See `docs/agents/issue-tracker.md`.

### Triage labels

Triage uses the five default canonical labels. See `docs/agents/triage-labels.md`.

### Domain docs

This repository uses the single-context domain documentation layout. See `docs/agents/domain.md`.
