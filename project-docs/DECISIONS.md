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

---

## ADR-005: Hybrid scoring contract (50 / 50 / 100) and LLM gating

**Context:** Stage-1 personal radar needs a clear, debuggable score with an optional semantic signal without mandatory API cost.

**Decision:** Keyword/heuristic contribution is capped at **50**; LLM contribution is capped at **50**; **`ArticleScore.points`** is the sum, capped at **100**. Call OpenAI for scoring only when **`HTR_LLM_SCORING_ENABLED`**, **`HTR_OPENAI_API_KEY`** is set, and **keyword score ≥ `HTR_LLM_KEYWORD_THRESHOLD`** (default **20**). If full-article fetch is disabled or fails, build LLM input from **fallback context** (title, summary, categories, etc.). **`ScoreExplanation`** normalizes stored breakdown fields to the same bounds when constructed from external data.

**Consequences:** Predictable ranking; keyword-only mode remains first-class; no LLM spend on low-signal items.