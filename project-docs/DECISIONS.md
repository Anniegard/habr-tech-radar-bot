# Architecture decisions

## ADR-001: Python 3.12 and src layout

**Context:** Small open-source pet project, one primary maintainer.

**Decision:** Require Python 3.12, package under `src/habr_tech_radar/`.

**Consequences:** Clear imports in tests via `pythonpath`; standard setuptools discovery.

---

## ADR-002: pydantic-settings and env prefix `HTR_`

**Context:** Typed configuration without a custom parser.

**Decision:** `Settings` with `env_prefix="HTR_"` and optional `.env`.

**Consequences:** Documented variables; secrets optional for stub runs.

---

## ADR-003: Protocol + stub services

**Context:** Real integrations come later; local runs must be safe.

**Decision:** `typing.Protocol` per boundary; default wiring uses stubs and log-only delivery.

**Consequences:** Easy to swap implementations; no framework lock-in.

---

## ADR-004: No Docker or CI in MVP foundation

**Context:** Week-one velocity and simplicity.

**Decision:** venv + Makefile only; no CI in initial commit.

**Consequences:** Contributors run checks locally (`make test`, `pre-commit`).