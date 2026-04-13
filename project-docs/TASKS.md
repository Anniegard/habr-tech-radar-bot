# Бэклог задач

## Сделано (bootstrap)

- Структура репозитория, `pyproject.toml`, Ruff, mypy, pytest, pre-commit, Makefile
- Настройки, логирование, модели, протоколы, заглушка пайплайна, тесты

## Сделано (Stage 1 slice)

- Ingestion Habr по **RSS** (`RssHabrIngestion`): реальные записи `Article`, устойчивость к битым элементам и сетевым ошибкам
- Персистенция виденных **id** в **JSON** (`SeenArticleStore`, `HTR_STATE_FILE`), дедуп между запусками
- Демо-режим без изменений: `StubHabrIngestion` + синтетическая статья

## Сделано (Stage 1 — filter / score / rank)

- `HeuristicArticleFilter`: include/exclude по ключевым словам и хабам (подстроки, casefold), пермиссивный режим без include-правил, OR между keyword и hub при гейтинге
- `HeuristicArticleScoring`: целочисленные веса, бонус за заголовок, свежесть по дате; `ScoreExplanation` + разбивка очков
- `select_top_scored`: топ-N, тай-брейк по дате и `id`; `HTR_MAX_SELECTED_ARTICLES`
- Настройки и `.env.example` для списков и весов; тесты на фильтр, скоринг, ранжирование, парсинг списков в настройках

## Сделано (Stage 1 — Telegram delivery)

- `HttpTelegramDelivery`: Telegram Bot API `sendMessage` по HTTP (stdlib), `parse_mode=HTML`, одно сообщение на `RadarItem`
- `format_radar_item_html`: экранирование, `ScoreExplanation`, время публикации, обрезка до ~4096 символов
- `HTR_DRY_RUN`: при `true` нет внешних вызовов Telegram; при `false` без токена/chat id — fail-fast в `default_components`
- Тесты: форматирование, dry_run без сети, форма POST, wiring, экранирование

## Сделано (VM / systemd slice)

- Каталог `deploy/`: `habr-tech-radar.service` (oneshot), `habr-tech-radar.timer`, `install_vm.sh`
- `HTR_PROJECT_ROOT` и `effective_state_file()` для предсказуемого пути к JSON state на VM
- CLI: `TelegramConfigurationError` → код выхода 2, одна строка в лог
- Документация: README (Ubuntu VM), HANDOFF, `.env.example`

## Сделано (операционное ужесточение VM)

- `deploy/run_once.sh`: `flock` на `HTR_PIPELINE_LOCK_FILE` (по умолчанию `/var/lib/habr-tech-radar/pipeline.lock`), при занятой блокировке — лог `skip: overlap`, код выхода 0
- `HttpTelegramDelivery`: ограниченные повторы `sendMessage` (сеть, 5xx, 429, flood в JSON), backoff, логи `start` / `retry` / `summary`; `TelegramDeliveryError` → CLI код 1
- Тесты на политику повторов и `main` exit 1; обновлены README, HANDOFF, CHANGELOG, SESSION_LOG, `.env.example`

## Сделано (публичная чистка и layered config)

- Убраны служебные IDE-файлы и лишний внутренний контекст из публичных текстов
- `config/defaults.env` + загрузка слоями; упрощён `.env.example`; обновлены README, deploy, project-docs

## Дальше

- По желанию: `LLMEnrichment` с внешним провайдером (за интерфейсом, через env)
- Мониторинг / алерты по доставке; по желанию — отдельные retry для RSS
