# Habr Tech Radar Bot

Personal **tech radar**: monitor new Habr articles, filter interesting ones, score them, and deliver selected items to Telegram. This repository contains the **open MVP foundation** only—stubs and interfaces—not full Habr, Telegram, or OpenAI integrations.

## Цель MVP (этап 1)

Небольшой типизированный пакет на Python:

- Конфигурация через переменные окружения (префикс `HTR_`) и опционально `.env`
- **Заглушка пайплайна**: ingestion → filtering → scoring → LLM (no-op) → delivery (только лог)
- Тесты и инструменты разработки (Ruff, mypy, pytest, pre-commit)
- Документация для людей и агентов

**Этап 2** (черновики комментариев к статьям) здесь явно не делаем.

## Repository layout

```text
src/habr_tech_radar/   # Application package (settings, pipeline, models, services)
tests/                 # Pytest suite
scripts/               # Optional future CLI helpers
config/                # Reserved for future rules (YAML/JSON)
project-docs/          # PRD, architecture, tasks, handoff, decisions
.cursor/rules/         # Cursor agent rules
```

## Требования

- **Python 3.12** (см. `requires-python` в `pyproject.toml`)
- Виртуальное окружение (рекомендуется)

## Локальная установка

```powershell
cd "Habr Tech Radar Bot"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pre_commit install
```

Скопируйте `.env.example` в `.env`, если нужны нестандартные значения (для заглушек не обязательно).

## Команды

Если доступен **GNU Make** (Git Bash, WSL или `make` в PATH):


| Command            | Описание                           |
| ------------------ | ---------------------------------- |
| `make install`     | Установка в editable-режиме        |
| `make install-dev` | Dev-зависимости + pre-commit hooks |
| `make lint`        | `ruff check`                       |
| `make format`      | `ruff format`                      |
| `make typecheck`   | `mypy src tests`                   |
| `make test`        | `pytest`                           |
| `make precommit`   | `pre-commit run --all-files`       |
| `make run`         | `python -m habr_tech_radar`        |


Без Make — те же инструменты через `python -m`, например:

```text
python -m pytest
python -m ruff check src tests
python -m mypy src tests
python -m habr_tech_radar
```

## Переменные окружения

Префикс `**HTR_**`. Список — в `[.env.example](.env.example)`.

Важное:

- `HTR_LOG_LEVEL` — по умолчанию `INFO`
- `HTR_DRY_RUN` — по умолчанию `true` (зарезервировано под будущее отключение побочных эффектов)
- `HTR_DEMO_MODE` — при `true` ingestion возвращает одну синтетическую статью (без сети)
- `HTR_TELEGRAM_BOT_TOKEN`, `HTR_TELEGRAM_CHAT_ID`, `HTR_OPENAI_API_KEY` — опционально; заглушки их не используют

## Запуск

- **По умолчанию** (нет статей, без сети): `python -m habr_tech_radar`
- **Демо-пайплайн** (одна фейковая статья): `python -m habr_tech_radar --demo` или `HTR_DEMO_MODE=true`

После установки пакета: консольная команда `habr-tech-radar`.

## Работа с агентами (Cursor)

1. Перед крупными изменениями прочитать `project-docs/PRD.md`, `ARCHITECTURE.md`, `TASKS.md`.
2. Соблюдать `.cursor/rules/` (сначала доки, границы задачи, обновление handoff).
3. После существенной работы обновить `TASKS.md`, `SESSION_LOG.md`, `HANDOFF.md`.

## Следующие шаги по разработке

По мотивам `project-docs/TASKS.md`:

1. Реальный **Habr ingestion** (RSS/API) за интерфейсом `HabrIngestion`.
2. **Хранение** последних виденных id статей (файл или SQLite).
3. Замена заглушек **filtering** и **scoring** настраиваемыми правилами в `config/`.
4. **Telegram**-доставка с token + chat id; учитывать `dry_run`.
5. По желанию — **LLM enrichment** за существующим интерфейсом.

## License

MIT (см. `pyproject.toml`).