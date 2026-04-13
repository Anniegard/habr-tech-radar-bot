# Product requirements (Stage 1)

## Problem

Staying aware of relevant Habr articles without manual scrolling. The product surfaces higher-signal posts using deterministic rules, scores them, optionally ranks top-N, and notifies via Telegram. It is **not** an auto-commenting or social bot.

## Stage 1 (this repository) — implemented

- **Ingestion:** RSS over HTTP (stdlib), resilient parsing, stable article ids for Habr URLs, deduplication across feeds and runs (`SeenArticleStore`).
- **Filtering:** Env-driven and preset-assisted substring include/exclude on title, summary, and RSS categories.
- **Scoring:** Integer heuristic scoring with strong / technical / include tiers, hubs, recency, negative penalties; structured `ScoreExplanation`.
- **Selection:** Top-N per run with tie-breaks.
- **Delivery:** Telegram Bot API `sendMessage` (HTML), dry-run mode, retries and phase budget, optional daily send cap (UTC).
- **Operations:** `last_run.json` snapshot, `--health-summary`, structured logging with `run_id` and end-of-run summary line.
- **LLM:** `NoOpLLMEnrichment` by default; optional provider can plug in behind the same interface (not required for Stage 1).

## Out of scope here

- **Stage 2**: Private workflow to draft comments on selected articles.
- Mandatory OpenAI or other LLM provider (keys may exist for future use only).
- Docker/Kubernetes/hosted platform; in-process scheduling (use systemd timer on the VM).

## Success criteria

- Runnable Python 3.12 package with typed settings, logging, full Stage 1 pipeline, tests (ruff, mypy, pytest, pre-commit), and CI workflow.
- Clear module boundaries (`ingestion` → `filtering` → `scoring` → `selection` → `llm` → `delivery`).
- Documentation and Cursor rules so a developer or agent can continue without guessing intent.
