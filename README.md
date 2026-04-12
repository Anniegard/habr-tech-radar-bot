# Habr Tech Radar Bot

Personal **tech radar**: monitor new Habr articles, filter interesting ones, score them, and deliver selected items to Telegram. This repository is **Stage 1**: real **RSS ingestion** with JSON-backed deduplication, plus stub filtering/scoring and log-only delivery—**not** full Telegram or OpenAI integrations yet.

## Цель MVP (этап 1)

Небольшой типизированный пакет на Python:

- Конфигурация через переменные окружения (префикс `HTR_`) и опционально `.env`
- **Пайплайн**: RSS ingestion (не демо) → filtering → scoring → LLM (no-op) → delivery (только лог)
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

Скопируйте `.env.example` в `.env`, если нужны нестандартные значения (для демо-режима без сети `.env` не обязателен).

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
- `HTR_HABR_RSS_URLS` — один или несколько URL RSS (через запятую или пробел). По умолчанию лента русскоязычных статей Habr. Пустое значение отключает запросы (для тестов/CI).
- `HTR_STATE_FILE` — путь к JSON-файлу с уже виденными `id` статей; по умолчанию `.habr_tech_radar_seen.json` в текущей директории. Повторный запуск с тем же фидом обычно не дублирует статьи.
- `HTR_RSS_FETCH_TIMEOUT_SECONDS` — таймаут HTTP на каждый RSS-запрос (по умолчанию `30`).
- `HTR_TELEGRAM_BOT_TOKEN`, `HTR_TELEGRAM_CHAT_ID`, `HTR_OPENAI_API_KEY` — опционально; доставка и LLM пока не подключены к внешним сервисам.

### Режим RSS и дедупликация

В обычном режиме (`HTR_DEMO_MODE=false`) приложение загружает указанные RSS-ленты по HTTP, парсит записи в модель `Article`, отбрасывает элементы с уже известными `id` (файл `HTR_STATE_FILE`) и возвращает в пайплайн только **новые** статьи. После успешного разбора новые `id` дописываются в JSON. Если процесс упал до сохранения, при следующем запуске часть статей может снова попасть в выдачу.

## Запуск

- **Обычный режим** (RSS, нужен интернет): `python -m habr_tech_radar` — статьи из ленты минус уже сохранённые id.
- **Демо-пайплайн** (одна фейковая статья, без сети): `python -m habr_tech_radar --demo` или `HTR_DEMO_MODE=true`

После установки пакета: консольная команда `habr-tech-radar`.

## Работа с агентами (Cursor)

1. Перед крупными изменениями прочитать `project-docs/PRD.md`, `ARCHITECTURE.md`, `TASKS.md`.
2. Соблюдать `.cursor/rules/` (сначала доки, границы задачи, обновление handoff).
3. После существенной работы обновить `TASKS.md`, `SESSION_LOG.md`, `HANDOFF.md`.

## Следующие шаги по разработке

По мотивам `project-docs/TASKS.md`:

1. Реальный **`TelegramDelivery`** с token + chat id; учитывать `dry_run`.
2. Замена заглушек **filtering** и **scoring** настраиваемыми правилами в `config/`.
3. По желанию — **LLM enrichment** за существующим интерфейсом; при необходимости — SQLite вместо JSON для состояния.

## License

MIT (см. `pyproject.toml`).