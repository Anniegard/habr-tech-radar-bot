# Product requirements (MVP foundation)

## Problem

Staying aware of relevant Habr articles without manual scrolling. The product surfaces high-signal posts, scores them, and notifies via Telegram.

## Scope (this repository)

- Monitor new Habr articles (RSS).
- Filter to interesting items (configurable rules).
- Score relevance: **stage-1 hybrid** — deterministic keyword/heuristic signals (**0..50**) plus **optional** OpenAI-assisted scoring (**0..50**) when enabled and above a keyword threshold; final rank uses **`ArticleScore.points` (0..100)**. Without a key or below threshold, scoring stays **keyword-only**.
- Deliver selected items to Telegram (Bot API).
- **Post-rank LLM enrichment** (`LLMEnrichment`) is wired as a **no-op** by default; connecting a provider for summaries/tags is optional future work (not part of stage-1 scoring).

## Out of scope here

- Full hosted production platform as a managed service (this repo targets self-hosted runs).
- Docker, CI/CD, Kubernetes as required infrastructure for the app itself.
- Stage-2 features: private comment generation, auto-commenting on Habr, or other social automation beyond RSS → filter → score → Telegram notify.

## Week-1 success criteria

- Runnable Python package with typed settings, logging, pipeline, and tests.
- Clear module boundaries (`ingestion` → `filtering` → `scoring` → `llm` → `delivery`).
- Documentation so a developer can continue without guessing intent.
