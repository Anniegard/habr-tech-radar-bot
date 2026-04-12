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
- `format_radar_item_html`: экранирование, `ScoreExplanation`, время публикации, обрезка до ~4096 символов
- `HTR_DRY_RUN`: при `true` нет внешних вызовов Telegram; при `false` без токена/chat id — fail-fast в `default_components`
- Тесты: форматирование, dry_run без сети, форма POST, wiring, экранирование

## Дальше

- Планировщик / периодический запуск (cron и т.д.) — вне этого репозитория или отдельный slice
- По желанию: `LLMEnrichment` с OpenAI (за интерфейсом, через env)
- По желанию: retry/rate limit для Telegram, батчи

## Этап 2 (не начинать в этом репо без явного scope)

- Workflow черновиков комментариев к выбранным статьям
