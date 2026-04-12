# Roadmap

## Stage 1 (near term)

1. Habr ingestion (RSS or API), deduplication, last-seen state (file or SQLite).
2. Filtering: hubs, keywords, blocklist; load optional config from `config/`.
3. Scoring: simple heuristics first; optional LLM-assisted signals later.
4. Telegram: send messages with title, link, score; respect `dry_run`.
5. Scheduling: cron/Task Scheduler or a tiny loop (keep boring).

## Stage 2 (later)

- Comment-draft generation workflow for a subset of articles (private; not part of this scaffold).

## Non-goals

- Multi-user product, web UI (unless you explicitly add it), Kubernetes.