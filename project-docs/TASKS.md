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

## Дальше

- `TelegramDelivery` с bot token + chat ID; учёт `dry_run`; формат сообщений из `ScoreExplanation`
- По желанию: `LLMEnrichment` с OpenAI (за интерфейсом, через env)
- Планировщик / одноразовый режим CLI

## Этап 2 (не начинать в этом репо без явного scope)

- Workflow черновиков комментариев к выбранным статьям
