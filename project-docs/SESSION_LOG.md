# Журнал сессий

*Одна короткая запись на сессию.*

## 2026-04-12 — Bootstrap

- Создан пакет Python 3.12 в src-layout, tooling (Ruff, mypy, pytest, pre-commit), заглушка пайплайна, тесты, project-docs, README.
- Запуск по умолчанию — заглушки (без сети). Демо: `HTR_DEMO_MODE=1` или `--demo`.

**Дальше:** реализовать Habr ingestion за `HabrIngestion` (RSS), персистенцию виденных id.

## 2026-04-12 — Filter, scoring, ranking (env-driven)

- Модели: `ScoreExplanation`, `ArticleScore.points` (int) вместо нормализованного float.
- `HeuristicArticleFilter` / `HeuristicArticleScoring`, `selection.select_top_scored`, интеграция в `run_pipeline` после скоринга.
- Env: `HTR_INCLUDE_KEYWORDS`, `HTR_EXCLUDE_KEYWORDS`, `HTR_INCLUDE_HUBS`, `HTR_EXCLUDE_HUBS` (строки со списками через запятую/пробел), `HTR_MAX_SELECTED_ARTICLES`, веса `HTR_SCORE_*`.
- Тесты: фильтр include/exclude, скоринг (title/hub/recency), топ-N и тай-брейки, парсинг списков в настройках.

**Дальше:** реальный `TelegramDelivery` поверх отранжированных `RadarItem`.

## 2026-04-12 — Telegram HTTP delivery (Stage 1)

- `HttpTelegramDelivery` + `format_radar_item_html` (HTML, экранирование, лимит длины); `HTR_DRY_RUN` строго отключает HTTP к Telegram; live-режим требует оба `HTR_TELEGRAM_*`; fail-fast в `default_components` при `dry_run=false` без учётных данных.
- Тесты в `tests/test_delivery_telegram.py`; документация и `.env.example` обновлены.

**Дальше:** планировщик; опционально LLM за интерфейсом.

## 2026-04-12 — RSS ingestion + dedup

- Реализованы `RssHabrIngestion` (stdlib HTTP + XML RSS 2.0) и `SeenArticleStore` (JSON-файл с `seen_ids`, восстановление при битом файле, атомарная запись).
- `default_components(settings)`: демо → `StubHabrIngestion`; иначе RSS + дедуп. Новые env: `HTR_HABR_RSS_URLS`, `HTR_STATE_FILE`, `HTR_RSS_FETCH_TIMEOUT_SECONDS`.
- Тесты: парсинг RSS из фикстуры, два запуска с одним фидом (второй пустой), битый state-файл, пайплайн демо / пустой список URL.

**Дальше:** реальный `TelegramDelivery` и/или правила `ArticleFilter` / scoring.

## 2026-04-12 — Ubuntu VM и systemd timer

- Добавлены `deploy/habr-tech-radar.service` (oneshot), `deploy/habr-tech-radar.timer` (расписание вне Python), `deploy/install_vm.sh` (venv + опциональная установка unit-файлов от root).
- Настройки: `HTR_PROJECT_ROOT`, функция `effective_state_file()` для резолва `HTR_STATE_FILE`; `SeenArticleStore` использует итоговый путь.
- `main`: перехват `TelegramConfigurationError`, код выхода 2; тесты в `tests/test_paths.py`.
- Обновлены README, HANDOFF, TASKS, `.env.example`, CHANGELOG.

**Дальше:** LLM за интерфейсом; операционные улучшения (retry, flock) по необходимости.

## 2026-04-12 — Операционное ужесточение (flock + retry Telegram)

- `deploy/run_once.sh` + `flock`: путь блокировки по умолчанию `/var/lib/habr-tech-radar/pipeline.lock`, переменная `HTR_PIPELINE_LOCK_FILE`; при занятом lock — stderr `skip: overlap`, exit 0. Unit `ExecStart` переведён на wrapper.
- `HttpTelegramDelivery`: повторы при временных сбоях (сеть, 5xx, 429, flood в JSON), экспоненциальный backoff с потолком; без повторов на явные клиентские/конфигурационные ошибки; логи `delivery: telegram: start|retry|summary`; `TelegramDeliveryError` → `main` exit 1.
- Env: `HTR_TELEGRAM_SEND_MAX_ATTEMPTS`, `HTR_TELEGRAM_RETRY_BASE_SECONDS`. Тесты в `tests/test_delivery_telegram.py`, `tests/test_paths.py`. Документация и CHANGELOG обновлены.

**Дальше:** мониторинг; LLM за интерфейсом; опционально retry RSS.

## 2026-04-13 — Публичная чистка и layered config

- Убраны служебные IDE-файлы; README и project-docs без лишнего внутреннего контекста; верх README переписан на русский.
- Добавлен отслеживаемый `config/defaults.env`, загрузка в `Settings`: `defaults.env` затем `.env`; упрощён `.env.example`; обновлены `deploy/install_vm.sh`, CHANGELOG, HANDOFF, TASKS.
