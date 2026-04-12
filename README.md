# Habr Tech Radar Bot

Personal **tech radar**: monitor new Habr articles, filter interesting ones, score them, and deliver selected items to Telegram. This repository is **Stage 1**: real **RSS ingestion** with JSON-backed deduplication, **config-driven** substring filtering and integer scoring, ranking with a per-run cap, and **Telegram delivery** via the Bot API (`sendMessage`, HTML). **OpenAI / LLM enrichment** is not wired yet.

## Цель MVP (этап 1)

Небольшой типизированный пакет на Python:

- Конфигурация через переменные окружения (префикс `HTR_`) и опционально `.env`
- **Пайплайн**: RSS ingestion (не демо) → filtering → scoring → top-N → LLM (no-op) → **Telegram** (`HttpTelegramDelivery`: сухой прогон или реальная отправка)
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
- `HTR_DRY_RUN` — по умолчанию `true`: сообщения **форматируются** и пишутся в лог как «would send», **без** HTTP к Telegram. Для реальной отправки задайте `false` и токен + chat id.
- `HTR_DEMO_MODE` — при `true` ingestion возвращает одну синтетическую статью (без сети)
- `HTR_HABR_RSS_URLS` — один или несколько URL RSS (через запятую или пробел). По умолчанию лента русскоязычных статей Habr. Пустое значение отключает запросы (для тестов/CI).
- `HTR_STATE_FILE` — путь к JSON-файлу с уже виденными `id` статей; по умолчанию `.habr_tech_radar_seen.json` в текущей директории. Повторный запуск с тем же фидом обычно не дублирует статьи.
- `HTR_RSS_FETCH_TIMEOUT_SECONDS` — таймаут HTTP на каждый RSS-запрос (по умолчанию `30`).
- `HTR_TELEGRAM_BOT_TOKEN`, `HTR_TELEGRAM_CHAT_ID` — для **живой** доставки при `HTR_DRY_RUN=false` (оба непустые). Бот: [@BotFather](https://t.me/BotFather); **chat id** — ваш user id или id группы (удобно узнать через [@userinfobot](https://t.me/userinfobot) или аналоги). При `HTR_DRY_RUN=true` можно оставить пустыми.
- `HTR_OPENAI_API_KEY` — зарезервировано под будущий `LLMEnrichment` (пока не используется).

### Фильтрация и скоринг (эвристики)

Правила задаются через `HTR_` (см. `.env.example`). Строки ключевых слов и хабов — **через запятую или пробел**; сопоставление **без учёта регистра**, по **подстроке** в заголовке, кратком тексте (`summary`) и строках категорий RSS (`metadata["categories"]`).

- **Исключения (`HTR_EXCLUDE_*`)**: если сработало — статья **сразу отбрасывается** и не попадает в скоринг.
- **Включения (`HTR_INCLUDE_*`)**: если оба списка (`INCLUDE_KEYWORDS` и `INCLUDE_HUBS`) **пусты** — режим **пермиссивный** (действуют только исключения). Если хотя бы один список непустой — статья проходит фильтр, если есть совпадение **хотя бы по одному** ключевому слову **или** хабу (логика **ИЛИ**).
- **Скоринг**: целочисленные очки за совпадения include-ключей и хабов, бонус за ключ в **заголовке**, линейный **бонус свежести** по дате публикации. Веса настраиваются (`HTR_SCORE_WEIGHT_*`, окно свежести `HTR_SCORE_RECENCY_WINDOW_DAYS`). У каждой оценки есть структура `ScoreExplanation` (совпадения и разбивка по компонентам) — удобно для отладки и будущего Telegram.
- **Ранжирование**: сортировка по убыванию очков; при равенстве — **новее по дате**, затем по `id` для стабильности. В выдачу попадает не больше **`HTR_MAX_SELECTED_ARTICLES`** (по умолчанию `20`).

### Режим RSS и дедупликация

В обычном режиме (`HTR_DEMO_MODE=false`) приложение загружает указанные RSS-ленты по HTTP, парсит записи в модель `Article`, отбрасывает элементы с уже известными `id` (файл `HTR_STATE_FILE`) и возвращает в пайплайн только **новые** статьи. После успешного разбора новые `id` дописываются в JSON. Если процесс упал до сохранения, при следующем запуске часть статей может снова попасть в выдачу.

## Запуск

- **Обычный режим** (RSS, нужен интернет): `python -m habr_tech_radar` — новые статьи из ленты (минус уже сохранённые id), затем фильтр → скоринг → топ-N → доставка (по умолчанию `HTR_DRY_RUN=true`: HTML-сообщения в лог, без Telegram HTTP).
- **Демо-пайплайн** (одна фейковая статья, без сети): `python -m habr_tech_radar --demo` или `HTR_DEMO_MODE=true` — доставка ведёт себя как при `dry_run`: форматированный текст в логе.

После установки пакета: консольная команда `habr-tech-radar`.

### Сообщение в Telegram (HTML)

Одна статья — одно сообщение. Текст строится в [`format_radar_item_html`](src/habr_tech_radar/delivery/html_message.py): заголовок, очки, время публикации (UTC), ссылка (`parse_mode=HTML`), кратко **почему такой score** (совпадения include, разбивка по компонентам из `ScoreExplanation`), при необходимости summary. Пользовательский контент экранируется; длинные тексты обрезаются до лимита Telegram (~4096 символов) с пометкой «truncated».

### Реальная отправка

1. Установите `HTR_TELEGRAM_BOT_TOKEN` и `HTR_TELEGRAM_CHAT_ID`.
2. Установите `HTR_DRY_RUN=false`.
3. Запустите пайплайн (например `python -m habr_tech_radar`). Если `HTR_DRY_RUN=false`, а токен или chat id пустые, приложение завершится с ошибкой конфигурации при сборке компонентов (fail-fast).

## Работа с агентами (Cursor)

1. Перед крупными изменениями прочитать `project-docs/PRD.md`, `ARCHITECTURE.md`, `TASKS.md`.
2. Соблюдать `.cursor/rules/` (сначала доки, границы задачи, обновление handoff).
3. После существенной работы обновить `TASKS.md`, `SESSION_LOG.md`, `HANDOFF.md`.

## Следующие шаги по разработке

По мотивам `project-docs/TASKS.md`:

1. Планировщик / периодический запуск (cron, systemd, GitHub Actions и т.д.).
2. По желанию — **LLM enrichment** за существующим интерфейсом (`OpenAI` и др.).
3. По желанию — вынести часть правил в `config/`; при росте состояния — SQLite вместо JSON.

## License

MIT (см. `pyproject.toml`).