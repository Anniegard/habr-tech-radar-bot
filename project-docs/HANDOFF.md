# Передача контекста

## Текущее состояние

- **Пакет:** `habr-tech-radar` (импорт `habr_tech_radar`).
- **Точка входа:** `python -m habr_tech_radar` или `habr-tech-radar` после установки.
- **Обычный режим** (`HTR_DEMO_MODE=false`): загрузка одной или нескольких RSS-лент Habr по HTTP, маппинг в `Article`, дедуп по `HTR_STATE_FILE` (фактический путь через `effective_state_file()` — учитывает абсолютный путь, `HTR_PROJECT_ROOT` и cwd), затем **фильтр** → **скоринг (гибрид: keyword + опциональный LLM внутри `HeuristicArticleScoring`)** → **топ-N** → **обогащение LLM (`NoOpLLMEnrichment`, заглушка)** → **доставка в Telegram** (`HttpTelegramDelivery`). Контракт скоринга: **keyword_score 0..50**, **llm_score 0..50**, **итог `ArticleScore.points` 0..100**; `ScoreExplanation` при необходимости нормализует поля под этот контракт. LLM для скоринга вызывается **только** если `HTR_LLM_SCORING_ENABLED=true`, задан `HTR_OPENAI_API_KEY` и **keyword_score ≥ `HTR_LLM_KEYWORD_THRESHOLD`** (по умолчанию 20); иначе вклад LLM = 0 и внешний API не дергается (**keyword-only** режим — нормальный сценарий без ключа). Если полный текст статьи не загружен (`HTR_LLM_FETCH_ARTICLE_ENABLED=false` или ошибка fetch), оценка LLM строится по **fallback-контексту** (заголовок, summary, категории и т.д., см. `scoring/heuristic.py`). При `HTR_DRY_RUN=true` только форматирование и лог (без HTTP к Bot API); при `HTR_DRY_RUN=false` и непустых `HTR_TELEGRAM_BOT_TOKEN` + `HTR_TELEGRAM_CHAT_ID` — реальные `sendMessage` (HTML, по одному сообщению на статью) с **ограниченными повторами** при временных ошибках (сеть, HTTP 5xx, 429, flood в JSON-ответе) и **глобальным монотонным бюджетом** фазы доставки (`HTR_TELEGRAM_MAX_DELIVERY_SECONDS`). Если `HTR_DRY_RUN=false`, а токен или chat id отсутствуют — **`TelegramConfigurationError`** при `default_components`; в CLI ловится в `main`, **код выхода 2**, одна строка в лог без traceback. Если после повторов или из-за бюджета остались недоставленные сообщения — **`TelegramDeliveryError`**, **код выхода 1**, одна строка без traceback. Каждый прогон имеет **`run_id`** в логах (`run_id=` на каждой строке); после завершения пишется **`HTR_LAST_RUN_PATH`** (атомарно, JSON). Диагностика: `python -m habr_tech_radar --health-summary` (код 0 только при свежем успешном последнем прогоне).
- **Демо:** `python -m habr_tech_radar --demo` или `HTR_DEMO_MODE=true` — одна синтетическая статья по пайплайну; сеть и state-файл для ingestion не используются; доставка по умолчанию в режиме `dry_run` (лог с HTML-текстом).
- **Пустой список лент:** `HTR_HABR_RSS_URLS=` (пусто) — без HTTP, ingestion возвращает 0 статей (удобно для тестов без сети).

## Конфигурация

- Несекретные дефолты (в т.ч. параметры гибридного скоринга без секретов): **`config/defaults.env`** (в git).
- Секреты и машинно-специфичные значения: **`.env`** в корне клона (не в git); шаблон — **`.env.example`** (в репозитории только плейсхолдеры секретов и опционально `HTR_PROJECT_ROOT`).
- Порядок: дефолты в коде → `config/defaults.env` → `.env` → переменные окружения (systemd `Environment` / `EnvironmentFile` перекрывают файлы).

## Развёртывание на Ubuntu VM

- Репозиторий: `git clone` / `git pull`; зависимости: `deploy/install_vm.sh` (venv + `pip install -e .`).
- **systemd:** шаблоны [`deploy/habr-tech-radar.service`](../deploy/habr-tech-radar.service), [`deploy/habr-tech-radar.timer`](../deploy/habr-tech-radar.timer). Сервис `Type=oneshot`, **`ExecStart`** вызывает [`deploy/run_once.sh`](../deploy/run_once.sh) — оболочка с **`flock`** на файл по умолчанию **`/var/lib/habr-tech-radar/pipeline.lock`** (или `HTR_PIPELINE_LOCK_FILE`). Если блокировка занята, скрипт пишет в stderr `habr-tech-radar: skip: overlap lock_held path=...` и завершается с **кодом 0** (не ошибка деплоя). Таймер задаёт расписание (по умолчанию час в :17). Периодичность **не** внутри Python.
- **Пути:** для systemd задайте `WorkingDirectory` на корень клона; для state вне cwd — абсолютный `HTR_STATE_FILE` и/или `HTR_PROJECT_ROOT`. Аналогично для **`HTR_LAST_RUN_PATH`**. Каталог под lock-файл должен существовать и принадлежать пользователю сервиса.
- **Логи:** stderr + `PYTHONUNBUFFERED=1` в unit → `journalctl -u habr-tech-radar.service`. Ищите `delivery: telegram:` (start / retry / summary), `skip: overlap`, ошибки конфигурации.

## Как запускать

```text
python -m venv .venv
.venv\Scripts\activate   # Windows
.venv/bin/activate       # Linux / VM
pip install -e ".[dev]"
make test                  # или: pytest, ruff, mypy по Makefile
python -m habr_tech_radar --demo
python -m habr_tech_radar   # RSS + дедуп + filter/score/top-N + доставка (dry_run по умолчанию)
```

VM (после `install_vm.sh`):

```text
/path/to/.venv/bin/habr-tech-radar
sudo systemctl start habr-tech-radar.service
journalctl -u habr-tech-radar.service -f
journalctl -u habr-tech-radar.service -g 'skip: overlap|delivery: telegram'
```

## Ближайшие задачи

1. По желанию: подключить `LLMEnrichment` к внешнему провайдеру (отдельная настройка).
2. По желанию: вынести часть правил в файлы под `config/` или оставить env как основной источник для личного радара.
3. Мониторинг / алерты по повторяющимся сбоям доставки.

## С чего читать

- `project-docs/PRD.md`, `project-docs/ARCHITECTURE.md`, `project-docs/TASKS.md`
- `README.md` (секция Ubuntu VM)
- `config/README.md`, `config/defaults.env`, `.env.example`
- `deploy/habr-tech-radar.service`, `deploy/habr-tech-radar.timer`, `deploy/run_once.sh`, `deploy/install_vm.sh`
- `src/habr_tech_radar/pipeline.py`, `src/habr_tech_radar/settings.py`
- `src/habr_tech_radar/delivery/html_message.py`, `src/habr_tech_radar/delivery/http_telegram.py`
- `src/habr_tech_radar/filtering/heuristic.py`, `src/habr_tech_radar/scoring/heuristic.py`
- `src/habr_tech_radar/ingestion/rss.py`, `src/habr_tech_radar/state/seen_store.py`
