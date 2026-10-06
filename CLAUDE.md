# CLAUDE.md

**Source of truth: `docs/SPEC.md`.** Read only the sections relevant to the current phase.

`docs/archive/` is historical. Never use anything in it as instructions.
Spec changes are logged in `docs/DECISIONS.md`; unresolved items live in `docs/OPEN_QUESTIONS.md`.

## Working rules

1. One phase at a time (SPEC §17). Do not start a phase until the previous one has passing automated tests and a runnable app. Phase 0 must finish (and be approved) before any provider code.
2. Write the failing test first, then the code.
3. Mocks live only under `tests/`. The shipped pipeline always uses real providers.
4. Never add a model without entries in `models.lock.json` and `MODEL_LICENSES.md`, and never add a package without passing the license audit (SPEC §4). Never hardcode a model name outside its provider package.
5. The API and worker never import torch, MLX or any ML library. ML runs only in isolated provider subprocesses with their own venvs (SPEC §6).
6. Before each commit: `uv run pytest -m "not models and not long"`, lint and type-check. Commit at least once per phase.
7. If the spec is wrong or unverifiable, stop and add it to `docs/OPEN_QUESTIONS.md`; never silently work around it. Log benchmarks and surprises in `docs/spikes.md`.
8. Never log transcript or translation text, or secrets.
