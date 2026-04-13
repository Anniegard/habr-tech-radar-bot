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
- Настройки и `.env.example` для списков и весов; тесты на фильтр, скоринг, ранжирование, парсинг списков

## Сделано (Stage 1 — Telegram delivery)

- `HttpTelegramDelivery`: Telegram Bot API `sendMessage` по HTTP (stdlib), `parse_mode=HTML`, одно сообщение на `RadarItem`
- `format_radar_item_html`: экранирование, `ScoreExplanation`, время публикации, обрезка до ~4096 символов по code points
- `HTR_DRY_RUN`: при `true` нет внешних вызовов Telegram; при `false` без токена/chat id — fail-fast в `default_components`
- Тесты: форматирование, dry_run без сети, форма POST, wiring, экранирование

## Сделано (VM / systemd slice)

- Каталог `deploy/`: `habr-tech-radar.service` (oneshot), `habr-tech-radar.timer`, `install_vm.sh`
- `HTR_PROJECT_ROOT` и `effective_state_file()` для предсказуемого пути к JSON state на VM
- CLI: `TelegramConfigurationError` → код выхода 2, одна строка в лог
- Документация: README (Ubuntu VM), HANDOFF, `.env.example`

## Сделано (операционное ужесточение VM)

- `deploy/run_once.sh`: `flock` на `HTR_PIPELINE_LOCK_FILE` (по умолчанию `/var/lib/habr-tech-radar/pipeline.lock`), при занятой блокировке — лог `skip: overlap`, код выхода 0
- `HttpTelegramDelivery`: ограниченные повторы `sendMessage` (сеть, 5xx, 429, flood в JSON-ответе), backoff, логи `start` / `retry` / `summary`; `TelegramDeliveryError` → CLI код 1
- Тесты на политику повторов и `main` exit 1; обновлены README, HANDOFF, CHANGELOG, SESSION_LOG, `.env.example`

## Сделано (Stage 1 production polish)

- Пресет `config/default_radar.json` + `HTR_PRESET_*`, merge только для полей не из env; дефолтный техрадар (include OR-gate), top-N 7 в коде
- Нормализация URL/id для Habr, дедуп между фидами, сводка ingestion по фидам, расширенный `last_run.json` и строка `run summary:`
- Дневной лимит реальных отправок Telegram (`HTR_MAX_TELEGRAM_MESSAGES_PER_DAY`) + `delivery_budget.json`
- CI GitHub Actions (`ruff`, `mypy`, `pytest`); `make check`
- Документация: README, PRD, ARCHITECTURE, troubleshooting, dry-run / prod примеры

## Дальше

- По желанию: `LLMEnrichment` с OpenAI (за интерфейсом, через env)
- Мониторинг / алерты по доставке; по желанию — отдельные retry для RSS

## Этап 2 (не начинать в этом репо без явного scope)

- Workflow черновиков комментариев к выбранным статьям
