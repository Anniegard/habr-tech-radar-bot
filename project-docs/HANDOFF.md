# Передача контекста

## Текущее состояние

- **Пакет:** `habr-tech-radar` (импорт `habr_tech_radar`).
- **Точка входа:** `python -m habr_tech_radar` или `habr-tech-radar` после установки.
- **Обычный режим** (`HTR_DEMO_MODE=false`): загрузка одной или нескольких RSS-лент Habr по HTTP, маппинг в `Article`, дедуп по `HTR_STATE_FILE` (фактический путь через `effective_state_file()` — учитывает абсолютный путь, `HTR_PROJECT_ROOT` и cwd), затем **фильтр** → **скоринг** → **топ-N** → no-op LLM → **доставка в Telegram** (`HttpTelegramDelivery`): при `HTR_DRY_RUN=true` только форматирование и лог «would send» (без HTTP к Bot API); при `HTR_DRY_RUN=false` и непустых `HTR_TELEGRAM_BOT_TOKEN` + `HTR_TELEGRAM_CHAT_ID` — реальные `sendMessage` (HTML, по одному сообщению на статью). Если `HTR_DRY_RUN=false`, а токен или chat id отсутствуют — **`TelegramConfigurationError`** при `default_components`; в CLI ловится в `main`, **код выхода 2**, одна строка в лог без traceback.
- **Демо:** `python -m habr_tech_radar --demo` или `HTR_DEMO_MODE=true` — одна синтетическая статья по пайплайну; сеть и state-файл для ingestion не используются; доставка по умолчанию в режиме `dry_run` (лог с HTML-текстом).
- **Пустой список лент:** `HTR_HABR_RSS_URLS=` (пусто) — без HTTP, ingestion возвращает 0 статей (удобно для тестов без сети).

## Развёртывание на Ubuntu VM

- Репозиторий: `git clone` / `git pull`; зависимости: `deploy/install_vm.sh` (venv + `pip install -e .`).
- Конфиг: `.env` в корне клона (или `EnvironmentFile` в systemd); шаблон переменных — `.env.example` в репозитории.
- **systemd:** шаблоны [`deploy/habr-tech-radar.service`](../deploy/habr-tech-radar.service), [`deploy/habr-tech-radar.timer`](../deploy/habr-tech-radar.timer). Сервис `Type=oneshot`, таймер задаёт расписание (по умолчанию час в :17). Периодичность **не** внутри Python.
- **Пути:** для systemd задайте `WorkingDirectory` на корень клона; для state вне cwd — абсолютный `HTR_STATE_FILE` и/или `HTR_PROJECT_ROOT`.
- **Логи:** stderr + `PYTHONUNBUFFERED=1` в unit → `journalctl -u habr-tech-radar.service`.
- **Перекрытие запусков:** systemd не гарантирует mutex; при длинных прогонах увеличить интервал таймера или опционально обернуть `ExecStart` в `flock` (см. комментарии в timer unit).

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
```

## Ближайшие задачи

1. По желанию: `LLMEnrichment` с OpenAI (за интерфейсом, через env) — **этап отдельного scope**.
2. По желанию: вынести часть правил в `config/` или оставить env как основной источник для личного радара.
3. Операционно: retry Telegram, `flock` при необходимости, мониторинг.

## С чего читать

- `project-docs/PRD.md`, `project-docs/ARCHITECTURE.md`, `project-docs/TASKS.md`
- `README.md` (секция Ubuntu VM)
- `deploy/habr-tech-radar.service`, `deploy/habr-tech-radar.timer`, `deploy/install_vm.sh`
- `src/habr_tech_radar/pipeline.py`, `src/habr_tech_radar/settings.py`
- `src/habr_tech_radar/delivery/html_message.py`, `src/habr_tech_radar/delivery/http_telegram.py`
- `src/habr_tech_radar/filtering/heuristic.py`, `src/habr_tech_radar/scoring/heuristic.py`
- `src/habr_tech_radar/ingestion/rss.py`, `src/habr_tech_radar/state/seen_store.py`
