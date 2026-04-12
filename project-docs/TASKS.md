# Бэклог задач

## Сделано (bootstrap)

- Структура репозитория, `pyproject.toml`, Ruff, mypy, pytest, pre-commit, Makefile
- Настройки, логирование, модели, протоколы, заглушка пайплайна, тесты

## Сделано (Stage 1 slice)

- Ingestion Habr по **RSS** (`RssHabrIngestion`): реальные записи `Article`, устойчивость к битым элементам и сетевым ошибкам
- Персистенция виденных **id** в **JSON** (`SeenArticleStore`, `HTR_STATE_FILE`), дедуп между запусками
- Демо-режим без изменений: `StubHabrIngestion` + синтетическая статья

## Дальше

- Реализация `ArticleFilter` с настраиваемыми правилами (`config/`)
- Реализация `ArticleScoring` не как заглушка (веса, хабы, ключевые слова)
- `TelegramDelivery` с bot token + chat ID; учёт `dry_run`
- По желанию: `LLMEnrichment` с OpenAI (за интерфейсом, через env)
- Планировщик / одноразовый режим CLI

## Этап 2 (не начинать в этом репо без явного scope)

- Workflow черновиков комментариев к выбранным статьям
