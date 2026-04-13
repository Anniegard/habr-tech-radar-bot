# Product requirements (MVP foundation)

## Problem

Staying aware of relevant Habr articles without manual scrolling. The product surfaces high-signal posts, scores them, and notifies via Telegram.

## Scope (this repository)

- Monitor new Habr articles (RSS).
- Filter to interesting items (configurable rules).
- Score relevance (heuristics).
- Deliver selected items to Telegram (Bot API).
- LLM enrichment is modeled in the pipeline but not connected to an external provider.

## Out of scope here

- Full hosted production platform as a managed service (this repo targets self-hosted runs).
- Docker, CI/CD, Kubernetes as required infrastructure for the app itself.

## Week-1 success criteria

- Runnable Python package with typed settings, logging, pipeline, and tests.
- Clear module boundaries (`ingestion` → `filtering` → `scoring` → `llm` → `delivery`).
- Documentation so a developer can continue without guessing intent.
