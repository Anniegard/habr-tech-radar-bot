# Roadmap

## Near term

1. Habr ingestion (RSS), deduplication, last-seen state (JSON file).
2. Filtering: hubs, keywords, blocklists; optional richer config under `config/`.
3. Scoring: heuristics first; optional additional signals later.
4. Telegram: send messages with title, link, score; respect `dry_run`.
5. Scheduling: systemd timer or cron (keep scheduling outside the Python process).

## Non-goals

- Multi-user product as a service, mandatory web UI, Kubernetes-by-default.
