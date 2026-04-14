# Habr Tech Radar Bot

**Личный tech radar для Habr:** мониторинг новых статей по RSS, фильтрация «шума», эвристический скоринг и доставка **топ-N** подходящих материалов в **Telegram**. Один процесс = один проход пайплайна; периодический запуск настраивается снаружи (например **systemd timer**).

**Кому полезно:** тем, кто не хочет вручную пролистывать всю ленту, но хочет получать отобранные статьи по своим ключевым словам и хабам.

**Что внутри:** Python 3.12, загрузка RSS, дедупликация по JSON, фильтр и гибридный скоринг (keyword + опциональный LLM) через переменные окружения, отправка в Telegram Bot API (`sendMessage`, HTML). Обогащение после ранжирования (`llm.enrich`) остаётся заглушкой.

## Быстрый старт (локально)

```bash
git clone https://github.com/YOUR_ORG/habr-tech-radar-bot.git
cd habr-tech-radar-bot
python3.12 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m pre_commit install   # опционально
```

Для демо без сети: `python -m habr_tech_radar --demo`.

Для обычного прогона с RSS несекретные параметры уже заданы в **[config/defaults.env](config/defaults.env)**. Создайте **`.env`** только если нужны секреты или свои значения:

```bash
cp .env.example .env
chmod 600 .env
# Минимум для реальной отправки в Telegram: HTR_TELEGRAM_BOT_TOKEN, HTR_TELEGRAM_CHAT_ID, HTR_DRY_RUN=false
```

Порядок загрузки: **дефолты в коде** → **config/defaults.env** → **`.env`** → **переменные окружения** (в т.ч. из systemd; окружение сильнее файлов).

## Структура репозитория

```text
src/habr_tech_radar/   # Пакет: настройки, пайплайн, модели, сервисы
tests/                 # Pytest
deploy/                # systemd, install_vm.sh, run_once.sh (flock)
config/                # defaults.env (несекретные дефолты), README
project-docs/          # PRD, архитектура, задачи, handoff
scripts/               # Зарезервировано под вспомогательные скрипты
```

## Требования

- **Python 3.12** (`requires-python` в `pyproject.toml`)
- Виртуальное окружение (рекомендуется)

## Локальная установка (Windows PowerShell)

```powershell
cd habr-tech-radar-bot
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pre_commit install
```

## Ubuntu VM (git, venv, systemd)

Приложение **одноразовое**: один запуск выполняет один проход. Расписание задаёт **таймер systemd**, а не цикл в Python.

### На сервере

- Ubuntu (или совместимый systemd), **Python 3.12**. Если пакета нет в репозитории дистрибутива — [deadsnakes](https://launchpad.net/~deadsnakes/+archive/ubuntu/ppa) или пакеты вашей ОС.
- Отдельный Unix-пользователь **не root** для сервиса (в примерах ниже — `htrbot`).

### Клонирование

```bash
sudo useradd -r -m -s /bin/bash htrbot
sudo -u htrbot -i
cd ~
git clone https://github.com/YOUR_ORG/habr-tech-radar-bot.git
cd habr-tech-radar-bot
git pull origin main
```

### Зависимости

```bash
chmod +x deploy/install_vm.sh
./deploy/install_vm.sh
# с dev-зависимостями: ./deploy/install_vm.sh --dev
```

Скрипт создаёт `.venv`, ставит пакет в editable-режиме. Секреты в скрипт не вшиваются.

### Конфигурация

В репозитории уже есть **config/defaults.env** (несекретные значения). Создайте в корне клона **`.env`** для токена Telegram, chat id и при необходимости путей на сервере:

```bash
cp .env.example .env
chmod 600 .env
```

**systemd** подхватывает тот же `.env` через `EnvironmentFile` в `[deploy/habr-tech-radar.service](deploy/habr-tech-radar.service)` (путь поправьте под свой клон). Относительные пути в настройках резолвятся от `WorkingDirectory` (корень клона) или от `HTR_PROJECT_ROOT`.

Для state вне домашнего каталога задайте абсолютные `HTR_STATE_FILE` / `HTR_LAST_RUN_PATH` и создайте каталоги:

```bash
sudo mkdir -p /var/lib/htrbot/habr-tech-radar
sudo chown -R htrbot:htrbot /var/lib/htrbot
```

### systemd: service + timer

1. Отредактируйте пути в `[deploy/habr-tech-radar.service](deploy/habr-tech-radar.service)` и `[deploy/habr-tech-radar.timer](deploy/habr-tech-radar.timer)`: `User`, `Group`, `WorkingDirectory`, `EnvironmentFile`. `ExecStart` → `[deploy/run_once.sh](deploy/run_once.sh)` (**flock**, без параллельных запусков).
2. Каталог для lock-файла (по умолчанию `/var/lib/habr-tech-radar/`) — см. комментарии в unit и вывод `install_vm.sh --install-systemd`.
3. Установка юнитов:

```bash
chmod +x deploy/run_once.sh
sudo /path/to/habr-tech-radar-bot/deploy/install_vm.sh --install-systemd
# или вручную:
sudo install -m 0644 deploy/habr-tech-radar.service /etc/systemd/system/
sudo install -m 0644 deploy/habr-tech-radar.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now habr-tech-radar.timer
```

**Перекрытие запусков:** если предыдущий прогон держит блокировку, новый пишет в stderr `habr-tech-radar: skip: overlap lock_held path=...`, код выхода **0**. Lock: переменная **`HTR_PIPELINE_LOCK_FILE`** в unit.

Таймер по умолчанию: **каждый час в :17** (`OnCalendar` в timer).

**Повторы Telegram:** временные сбои сети, HTTP **5xx**, **429** — ограниченные повторы `sendMessage` (см. `HTR_TELEGRAM_SEND_MAX_ATTEMPTS`, `HTR_TELEGRAM_RETRY_BASE_SECONDS` в `[config/defaults.env](config/defaults.env)`). Общий бюджет фазы доставки: `HTR_TELEGRAM_MAX_DELIVERY_SECONDS`. Логи: `delivery: telegram: start|retry|summary`.

**Снимок прогона:** атомарно JSON в `HTR_LAST_RUN_PATH`. Проверка: `python -m habr_tech_radar --health-summary` (код **0** только при свежем успешном прогоне по `HTR_HEALTH_MAX_AGE_MINUTES`). В логах на каждой строке есть `run_id=`.

### Управление и логи

```bash
sudo systemctl start habr-tech-radar.service
sudo systemctl status habr-tech-radar.timer
journalctl -u habr-tech-radar.service -f
journalctl -u habr-tech-radar.service -g 'skip: overlap|delivery: telegram|TelegramConfigurationError'
```

### Ручной запуск

```bash
cd /path/to/habr-tech-radar-bot
source .venv/bin/activate
python -m habr_tech_radar
```

Коды выхода основного прогона: **0** — успех; **2** — нет токена/chat id при `HTR_DRY_RUN=false`; **1** — частичная доставка (`TelegramDeliveryError`). Пропуск из‑за flock — **0**, строка `skip: overlap`.

`--health-summary`: **0** / **1** / **2** — см. выше.

## Команды (Make)


| Command            | Описание                     |
| ------------------ | ---------------------------- |
| `make install`     | Установка в editable-режиме  |
| `make install-dev` | Dev-зависимости + pre-commit |
| `make lint`        | `ruff check`                 |
| `make format`      | `ruff format`                |
| `make typecheck`   | `mypy src tests`             |
| `make test`        | `pytest`                     |
| `make run`         | `python -m habr_tech_radar`  |


Без Make: `python -m pytest`, `python -m ruff check .`, `python -m mypy src`, и т.д.

## Переменные окружения

Префикс **`HTR_`**. Несекретные значения по умолчанию — в **[config/defaults.env](config/defaults.env)**. Шаблон для `.env` — **[.env.example](.env.example)**.

Кратко:

- `HTR_DRY_RUN` — по умолчанию `true`: без HTTP к Telegram; лог «would send».
- `HTR_DEMO_MODE` / `--demo` — одна синтетическая статья, без сети.
- `HTR_HABR_RSS_URLS` — RSS URL (пусто = без HTTP, удобно для тестов). Дефолтная лента задаётся в коде; для переопределения из `.env` используйте **JSON-массив**, например `HTR_HABR_RSS_URLS=["https://habr.com/ru/rss/all/"]`.
- `HTR_STATE_FILE`, `HTR_PROJECT_ROOT`, `HTR_LAST_RUN_PATH` — пути к state и снимку прогона.
- `HTR_TELEGRAM_*` — токен, chat id, формат сообщений, retry, бюджет доставки.
- `HTR_PIPELINE_LOCK_FILE` — для `[deploy/run_once.sh](deploy/run_once.sh)`.
- `HTR_LLM_SCORING_ENABLED`, `HTR_LLM_KEYWORD_THRESHOLD` — гибридный скоринг stage-1: keyword score **0..50**, LLM score **0..50**, итог **0..100** (максимумы не настраиваются).
- `HTR_LLM_FETCH_ARTICLE_ENABLED`, `HTR_LLM_FETCH_ARTICLE_TIMEOUT_SECONDS`, `HTR_LLM_MAX_ARTICLE_CHARS`, `HTR_LLM_MAX_SUMMARY_CHARS`, `HTR_LLM_REQUEST_TIMEOUT_SECONDS`, `HTR_LLM_MODEL` — параметры LLM-оценки и подготовки контента.

Длинные лексиконы для скоринга (`HTR_SCORE_*_KEYWORDS`) по умолчанию заданы в коде; при необходимости переопределите в `.env` или окружении.

### Фильтрация и скоринг

Списки ключевых слов и хабов — строки с разделителями запятая/пробел; совпадение по **подстроке**, без учёта регистра.

- **Исключения (`HTR_EXCLUDE_*`)** — статья отбрасывается до скоринга.
- **Включения** — если оба списка include пусты, режим пермиссивный (только exclude). Иначе нужно совпадение по keyword **или** hub (OR).
- **Скоринг (stage-1 гибрид):** keyword score `0..50` (детерминированные сигналы: strong / technical / include, хабы, заголовок, свежесть, штрафы) + optional LLM score `0..50`; итоговый `ArticleScore.points` = `0..100`.
- LLM-вклад вычисляется **только** при `HTR_LLM_SCORING_ENABLED=true`, наличии `HTR_OPENAI_API_KEY` и `keyword_score >= HTR_LLM_KEYWORD_THRESHOLD` (по умолчанию `20`); иначе `llm_score=0` и внешний API не вызывается (это нормальный keyword-only режим).
- Если полный текст статьи не загружается или `HTR_LLM_FETCH_ARTICLE_ENABLED=false`, LLM оценивает по контексту из заголовка, summary, категорий и автора.

Подробнее модель данных и поток — `[project-docs/ARCHITECTURE.md](project-docs/ARCHITECTURE.md)`.

### Сообщения в Telegram (HTML)

Режимы `HTR_TELEGRAM_FORMAT_MODE`: **`prod`** (компактно) или **`debug`** (полный разбор). Форматирование: [`format_radar_item_html`](src/habr_tech_radar/delivery/html_message.py).

### Реальная отправка

1. `HTR_TELEGRAM_BOT_TOKEN`, `HTR_TELEGRAM_CHAT_ID`
2. `HTR_DRY_RUN=false`
3. `python -m habr_tech_radar`

## Для контрибьюторов

Перед крупными изменениями имеет смысл просмотреть `[project-docs/PRD.md](project-docs/PRD.md)`, `[project-docs/ARCHITECTURE.md](project-docs/ARCHITECTURE.md)`, `[project-docs/TASKS.md](project-docs/TASKS.md)`.

## Возможные улучшения (не обязательно)

- Опциональное обогащение через существующий интерфейс LLM (отдельная настройка и провайдер).
- Вынести часть правил в файлы под `config/`; при росте данных — SQLite вместо JSON state.
- Алерты по повторяющимся ошибкам доставки.

## License

MIT (см. `pyproject.toml`).