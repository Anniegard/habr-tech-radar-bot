# Product requirements (MVP foundation)

## Problem

Staying aware of relevant Habr articles without manual scrolling. The product should surface high-signal posts, score them, and notify via Telegram.

## Stage 1 (this repository)

- Monitor new Habr articles (implementation TBD: RSS/API).
- Filter to interesting items (rules TBD).
- Score relevance (heuristics and/or signals TBD).
- Deliver selected items to Telegram (bot/API TBD).
- Optional LLM enrichment behind an interface (no real provider in scaffold).

## Out of scope here

- **Stage 2**: Private workflow to draft comments on selected articles.
- Full production integrations in the initial commit (no real Habr/Telegram/OpenAI calls).
- Docker, CI/CD, Kubernetes, hosted infra.

## Week-1 success criteria

- Runnable Python package with typed settings, logging, stub pipeline, and tests.
- Clear module boundaries (`ingestion` → `filtering` → `scoring` → `llm` → `delivery`).
- Documentation and Cursor rules so a developer or agent can continue without guessing intent.