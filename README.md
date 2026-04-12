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
deploy/                # systemd unit templates + install_vm.sh for Ubuntu VM
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

## Ubuntu VM (git, venv, systemd)

Приложение остаётся **одноразовым** (один запуск — один проход пайплайна). Периодический запуск делается **снаружи** через **systemd timer** (не APScheduler и не циклы в Python).

### Требования на сервере

- Ubuntu (или совместимый systemd), **Python 3.12**. Если в дистрибутиве нет 3.12, используйте [deadsnakes](https://launchpad.net/~deadsnakes/+archive/ubuntu/ppa) или официальные пакеты вашей версии ОС.
- Пользователь Unix **не root** для запуска сервиса (в шаблонах ниже пример `htrbot`).

### Клонирование и обновление

```bash
sudo useradd -r -m -s /bin/bash htrbot   # или свой пользователь
sudo -u htrbot -i
cd ~
git clone https://github.com/YOUR_ORG/habr-tech-radar-bot.git
cd habr-tech-radar-bot
# обновления:
git pull origin main
```

### Виртуальное окружение и зависимости

Из корня репозитория:

```bash
chmod +x deploy/install_vm.sh
./deploy/install_vm.sh
# с dev-зависимостями (отладка на VM): ./deploy/install_vm.sh --dev
```

Скрипт создаёт `.venv`, ставит пакет в editable-режиме (`pip install -e .`) и печатает пути. Секреты в скрипт **не** вшиты.

### Конфигурация `.env`

```bash
cp .env.example .env
chmod 600 .env
nano .env   # или редактор по вкусу
```

Заполните как минимум режим и Telegram (для боя): `HTR_DRY_RUN`, `HTR_TELEGRAM_BOT_TOKEN`, `HTR_TELEGRAM_CHAT_ID`. Для **просмотра без отправки** оставьте `HTR_DRY_RUN=true` — HTTP к Telegram не выполняется, сообщения пишутся в лог как «would send».

Для постоянного state-файла вне домашнего каталога задайте абсолютный `HTR_STATE_FILE` (и при необходимости `HTR_PROJECT_ROOT` — см. `.env.example`). Создайте каталог и выставьте владельца под пользователя сервиса:

```bash
sudo mkdir -p /var/lib/htrbot/habr-tech-radar
sudo chown -R htrbot:htrbot /var/lib/htrbot
```

### systemd: service + timer

1. Отредактируйте пути в [`deploy/habr-tech-radar.service`](deploy/habr-tech-radar.service) и [`deploy/habr-tech-radar.timer`](deploy/habr-tech-radar.timer): `User`, `Group`, `WorkingDirectory`, `EnvironmentFile`, при необходимости `Documentation=`. `ExecStart` указывает на [`deploy/run_once.sh`](deploy/run_once.sh) — оболочка с **`flock`**, чтобы **не было двух одновременных** запусков по таймеру.
2. Создайте каталог под **файл блокировки** (по умолчанию **`/var/lib/habr-tech-radar/`** для `pipeline.lock`) и отдайте владельцу сервисного пользователя (см. комментарии в unit и вывод `install_vm.sh --install-systemd`).
3. Установите юниты и включите таймер (сначала venv от обычного пользователя — см. выше; копирование в `/etc` — от root):

```bash
chmod +x deploy/run_once.sh
sudo /path/to/habr-tech-radar-bot/deploy/install_vm.sh --install-systemd
# или вручную:
sudo install -m 0644 deploy/habr-tech-radar.service /etc/systemd/system/
sudo install -m 0644 deploy/habr-tech-radar.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now habr-tech-radar.timer
```

**Перекрытие запусков:** если предыдущий прогон ещё держит блокировку, новый старт **не падает**: в stderr будет строка вида `habr-tech-radar: skip: overlap lock_held path=...`, код выхода **0** (в `journalctl` это не выглядит как поломка деплоя). Путь к lock можно переопределить переменной **`HTR_PIPELINE_LOCK_FILE`** в unit-файле (`Environment=`).

Таймер по умолчанию: **каждый час в :17** (см. `OnCalendar` в unit). `RandomizedDelaySec` слегка размазывает старт.

**Повторы Telegram:** при временных сбоях сети, HTTP **5xx** и **429** `sendMessage` повторяется ограниченное число раз с паузой (см. `HTR_TELEGRAM_SEND_MAX_ATTEMPTS`, `HTR_TELEGRAM_RETRY_BASE_SECONDS` в `.env.example`). Повторы **не продолжаются за пределами** общего монотонного бюджета фазы доставки: `HTR_TELEGRAM_MAX_DELIVERY_SECONDS` (по умолчанию 240 с). В логах: `delivery: telegram: start|retry|summary`, без URL с токеном.

**Снимок последнего прогона:** после каждого запуска пишется атомарно JSON в `HTR_LAST_RUN_PATH` (по умолчанию `.runtime/last_run.json` в рабочем каталоге; на VM удобно абсолютный путь, например под `/var/lib/...`). Для быстрой проверки по SSH: `python -m habr_tech_radar --health-summary` (код **0** только если последний прогон был **success**, файл свежий по `HTR_HEALTH_MAX_AGE_MINUTES`). Строки лога содержат **`run_id=`** на каждой записи (корреляция этапов в `journalctl`).

### Управление и логи

```bash
sudo systemctl start habr-tech-radar.service      # разовый запуск вручную
sudo systemctl status habr-tech-radar.timer
sudo systemctl list-timers habr-tech-radar.timer
journalctl -u habr-tech-radar.service -f
journalctl -u habr-tech-radar.service -n 200 --no-pager
# полезные фильтры:
journalctl -u habr-tech-radar.service -g 'skip: overlap|delivery: telegram|TelegramConfigurationError'
```

В unit задано `PYTHONUNBUFFERED=1`, чтобы строки лога сразу попадали в journal. Строки **`delivery: telegram:`** дают режим (`dry_run` / `live`), бюджет, число отобранных статей, повторы и итог `sent` / `failed` / `skipped_due_budget` / `remaining_budget_s`.

### Ручной запуск для отладки

```bash
cd /path/to/habr-tech-radar-bot
source .venv/bin/activate
set -a; source .env; set +a   # если не полагаетесь на pydantic .env
python -m habr_tech_radar
```

Коды выхода основного прогона: **0** — успех; **2** — нет токена/chat id при `HTR_DRY_RUN=false` (`TelegramConfigurationError`, одна строка в логе); **1** — неполная доставка (`TelegramDeliveryError`: остались `failed`, исчерпан глобальный бюджет доставки с `skipped_due_budget`, и т.п.). Пропуск из‑за **flock** даёт код **0** и строку `skip: overlap` в логе.

Коды **`--health-summary`**: **0** — последний `last_run.json` есть, парсится, `status=success`, возраст в пределах `HTR_HEALTH_MAX_AGE_MINUTES`; **1** — файл отсутствует, битый, устаревший или статус не success; **2** — некорректные настройки (`Settings`).

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
| (ops)              | `python -m habr_tech_radar --health-summary` |


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
- `HTR_STATE_FILE` — путь к JSON-файлу с уже виденными `id` статей; по умолчанию `.habr_tech_radar_seen.json` относительно текущей рабочей директории (для systemd задайте `WorkingDirectory` в корень клона или используйте абсолютный путь). Повторный запуск с тем же фидом обычно не дублирует статьи.
- `HTR_PROJECT_ROOT` — если задан, **относительный** `HTR_STATE_FILE` резолвится от этого каталога (удобно, когда cwd не совпадает с каталогом данных).
- `HTR_RSS_FETCH_TIMEOUT_SECONDS` — таймаут HTTP на каждый RSS-запрос (по умолчанию `30`).
- `HTR_TELEGRAM_BOT_TOKEN`, `HTR_TELEGRAM_CHAT_ID` — для **живой** доставки при `HTR_DRY_RUN=false` (оба непустые). Бот: [@BotFather](https://t.me/BotFather); **chat id** — ваш user id или id группы (удобно узнать через [@userinfobot](https://t.me/userinfobot) или аналоги). При `HTR_DRY_RUN=true` можно оставить пустыми.
- `HTR_TELEGRAM_SEND_MAX_ATTEMPTS`, `HTR_TELEGRAM_RETRY_BASE_SECONDS` — лимит попыток `sendMessage` на статью и базовая задержка для backoff (см. `.env.example`).
- `HTR_TELEGRAM_MAX_DELIVERY_SECONDS` — общий лимит времени (монотонные секунды) на всю фазу доставки в Telegram; по умолчанию `240`.
- `HTR_TELEGRAM_FORMAT_MODE` — `prod` (компактные сообщения по умолчанию) или `debug` (полный разбор score и сигналов).
- `HTR_LAST_RUN_PATH` — путь к JSON последнего прогона (атомарная запись); по умолчанию `.runtime/last_run.json` (относительный путь резолвится как `HTR_STATE_FILE`, см. `HTR_PROJECT_ROOT`).
- `HTR_HEALTH_MAX_AGE_MINUTES` — для `--health-summary`: максимальный возраст `finished_at_utc` в минутах, чтобы считать прогон «свежим»; по умолчанию `180`.
- `HTR_PIPELINE_LOCK_FILE` — путь к файлу блокировки для [`deploy/run_once.sh`](deploy/run_once.sh) (обычно задаётся в systemd, не в `.env`).
- `HTR_OPENAI_API_KEY` — зарезервировано под будущий `LLMEnrichment` (пока не используется).

### Фильтрация и скоринг (эвристики)

Правила задаются через `HTR_` (см. `.env.example`). Строки ключевых слов и хабов — **через запятую или пробел**; сопоставление **без учёта регистра**, по **подстроке** в заголовке, кратком тексте (`summary`) и строках категорий RSS (`metadata["categories"]`).

- **Исключения (`HTR_EXCLUDE_*`)**: если сработало — статья **сразу отбрасывается** и не попадает в скоринг.
- **Включения (`HTR_INCLUDE_*`)**: если оба списка (`INCLUDE_KEYWORDS` и `INCLUDE_HUBS`) **пусты** — режим **пермиссивный** (действуют только исключения). Если хотя бы один список непустой — статья проходит фильтр, если есть совпадение **хотя бы по одному** ключевому слову **или** хабу (логика **ИЛИ**).
- **Скоринг**: целочисленные очки с **уровнями сигналов** (приоритет: strong → technical → include): встроенные списки `HTR_SCORE_STRONG_KEYWORDS` и `HTR_SCORE_TECHNICAL_KEYWORDS` (или пустые строки, чтобы отключить встроенные дефолты), обычные include-ключи и хабы, бонус за появление сигнала в **заголовке**, линейный **бонус свежести** (по умолчанию меньше, чем раньше: `HTR_SCORE_WEIGHT_RECENCY_MAX`, опционально жёсткий потолок `HTR_SCORE_RECENCY_MAX_POINTS` вместо него), **штрафы** за совпадения из `HTR_SCORE_NEGATIVE_KEYWORDS` (`HTR_SCORE_WEIGHT_PENALTY_PER_HIT` за каждое совпадение). Итоговые очки не уходят ниже нуля. Веса: `HTR_SCORE_WEIGHT_STRONG_KEYWORD`, `HTR_SCORE_WEIGHT_TECHNICAL_SIGNAL`, `HTR_SCORE_WEIGHT_INCLUDE_KEYWORD`, остальные — см. `.env.example`. У каждой оценки — `ScoreExplanation` (совпадения по группам, `breakdown`, краткое `selection_summary`).
- **Ранжирование**: сортировка по убыванию очков; при равенстве — **новее по дате**, затем по `id` для стабильности. В выдачу попадает не больше **`HTR_MAX_SELECTED_ARTICLES`** (по умолчанию `20`).

### Режим RSS и дедупликация

В обычном режиме (`HTR_DEMO_MODE=false`) приложение загружает указанные RSS-ленты по HTTP, парсит записи в модель `Article`, отбрасывает элементы с уже известными `id` (файл `HTR_STATE_FILE`) и возвращает в пайплайн только **новые** статьи. После успешного разбора новые `id` дописываются в JSON. Если процесс упал до сохранения, при следующем запуске часть статей может снова попасть в выдачу.

## Запуск

- **Обычный режим** (RSS, нужен интернет): `python -m habr_tech_radar` — новые статьи из ленты (минус уже сохранённые id), затем фильтр → скоринг → топ-N → доставка (по умолчанию `HTR_DRY_RUN=true`: HTML-сообщения в лог, без Telegram HTTP).
- **Демо-пайплайн** (одна фейковая статья, без сети): `python -m habr_tech_radar --demo` или `HTR_DEMO_MODE=true` — доставка ведёт себя как при `dry_run`: форматированный текст в логе.

После установки пакета: консольная команда `habr-tech-radar`.

### Сообщение в Telegram (HTML)

Одна статья — одно сообщение. Режим задаётся **`HTR_TELEGRAM_FORMAT_MODE`**:

- **`prod`** (по умолчанию): короткое user-facing сообщение — заголовок, score, дата публикации (UTC), строка «Почему выбрано» из сигналов, укороченный summary, **ссылка без `utm_*` / `fbclid` / `gclid`** в query.
- **`debug`**: полная диагностика — совпадения по группам (strong / technical / include / hubs / negative), разбивка очков по компонентам, заметки (`reasons`), полный summary.

Текст строится в [`format_radar_item_html`](src/habr_tech_radar/delivery/html_message.py) (`parse_mode=HTML`). Пользовательский контент экранируется; длинные тексты обрезаются до лимита Telegram (~4096 символов) с пометкой «truncated».

### Реальная отправка

1. Установите `HTR_TELEGRAM_BOT_TOKEN` и `HTR_TELEGRAM_CHAT_ID`.
2. Установите `HTR_DRY_RUN=false`.
3. Запустите пайплайн (например `python -m habr_tech_radar`). Если `HTR_DRY_RUN=false`, а токен или chat id пустые, приложение завершится с **кодом выхода 2** и одной строкой ошибки в логе (fail-fast, без traceback). Если после повторов остались ошибки доставки — **код 1** и краткое сообщение без traceback.

## Работа с агентами (Cursor)

1. Перед крупными изменениями прочитать `project-docs/PRD.md`, `ARCHITECTURE.md`, `TASKS.md`.
2. Соблюдать `.cursor/rules/` (сначала доки, границы задачи, обновление handoff).
3. После существенной работы обновить `TASKS.md`, `SESSION_LOG.md`, `HANDOFF.md`.

## Следующие шаги по разработке

По мотивам `project-docs/TASKS.md`:

1. По желанию — **LLM enrichment** за существующим интерфейсом (`OpenAI` и др.).
2. По желанию — вынести часть правил в `config/`; при росте состояния — SQLite вместо JSON.
3. Мониторинг / алерты по повторяющимся `failed` в логах доставки.

## License

MIT (см. `pyproject.toml`).