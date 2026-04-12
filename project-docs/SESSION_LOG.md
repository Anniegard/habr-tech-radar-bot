# Журнал сессий

*Одна короткая запись на сессию (человек или агент).*

## 2026-04-12 — Bootstrap

- Создан пакет Python 3.12 в src-layout, tooling (Ruff, mypy, pytest, pre-commit), заглушка пайплайна, тесты, project-docs, правила Cursor, README.
- Запуск по умолчанию — заглушки (без сети). Демо: `HTR_DEMO_MODE=1` или `--demo`.

**Дальше:** реализовать Habr ingestion за `HabrIngestion` (RSS), персистенцию виденных id.

## 2026-04-12 — RSS ingestion + dedup

- Реализованы `RssHabrIngestion` (stdlib HTTP + XML RSS 2.0) и `SeenArticleStore` (JSON-файл с `seen_ids`, восстановление при битом файле, атомарная запись).
- `default_components(settings)`: демо → `StubHabrIngestion`; иначе RSS + дедуп. Новые env: `HTR_HABR_RSS_URLS`, `HTR_STATE_FILE`, `HTR_RSS_FETCH_TIMEOUT_SECONDS`.
- Тесты: парсинг RSS из фикстуры, два запуска с одним фидом (второй пустой), битый state-файл, пайплайн демо / пустой список URL.

**Дальше:** реальный `TelegramDelivery` и/или правила `ArticleFilter` / scoring.
