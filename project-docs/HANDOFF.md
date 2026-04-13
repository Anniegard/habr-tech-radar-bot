# Передача контекста

## Текущее состояние

- **Пакет:** `habr-tech-radar` (импорт `habr_tech_radar`).
- **Точка входа:** `python -m habr_tech_radar` или `habr-tech-radar` после установки.
- **Конфигурация:** `HTR_*` через env и `.env`. Опционально **пресет** JSON [`config/default_radar.json`](../config/default_radar.json): при `HTR_PRESET_ENABLED=true` (по умолчанию) подмешиваются include-листы и `max_selected`, если соответствующие поля **не заданы** в `.env`. Для демо (`--demo` / `HTR_DEMO_MODE`) пресет не применяется.
- **Обычный режим** (`HTR_DEMO_MODE=false`): RSS по HTTP, нормализация URL и стабильный `id` (`habr:article:<n>`), дедуп по `HTR_STATE_FILE`, **фильтр** → **скоринг** → **топ-N** → no-op LLM → **Telegram** (`HttpTelegramDelivery`): при `HTR_DRY_RUN=true` только форматирование и лог (без HTTP к Bot API); при `HTR_DRY_RUN=false` и непустых `HTR_TELEGRAM_BOT_TOKEN` + `HTR_TELEGRAM_CHAT_ID` — реальные `sendMessage` с ретраями, фазовым бюджетом и опционально **дневным лимитом** (`HTR_MAX_TELEGRAM_MESSAGES_PER_DAY`, state в `delivery_budget.json` рядом с seen или `HTR_DELIVERY_BUDGET_FILE`). Ошибка конфигурации Telegram → **код 2**; неполная доставка → **код 1**. Логи с **`run_id=`**; в конце **`run summary:`**; атомарный **`HTR_LAST_RUN_PATH`** с метриками RSS/фильтра/доставки.
- **Демо:** `python -m habr_tech_radar --demo` или `HTR_DEMO_MODE=true` — одна синтетическая статья; сеть и state для ingestion не используются.
- **Пустой список лент:** `HTR_HABR_RSS_URLS=` — без HTTP, ingestion возвращает 0 статей.

## Развёртывание на Ubuntu VM

- Репозиторий: `git clone` / `git pull`; зависимости: `deploy/install_vm.sh` (venv + `pip install -e .`).
- Конфиг: `.env` в корне клона (или `EnvironmentFile` в systemd); шаблон — `.env.example`.
- **systemd:** шаблоны [`deploy/habr-tech-radar.service`](../deploy/habr-tech-radar.service), [`deploy/habr-tech-radar.timer`](../deploy/habr-tech-radar.timer). Сервис `Type=oneshot`, **`ExecStart`** — [`deploy/run_once.sh`](../deploy/run_once.sh) с **`flock`**. Таймер — расписание вне Python.
- **Пути:** `WorkingDirectory` на корень клона; для state вне cwd — абсолютный `HTR_STATE_FILE` и/или `HTR_PROJECT_ROOT`. Аналогично **`HTR_LAST_RUN_PATH`** и при необходимости **`HTR_DELIVERY_BUDGET_FILE`**.

## Как запускать

```text
python -m venv .venv
.venv/bin/activate
pip install -e ".[dev]"
make check
python -m habr_tech_radar --demo
python -m habr_tech_radar
```

VM: `journalctl -u habr-tech-radar.service -f`; health: `python -m habr_tech_radar --health-summary`.

## Ближайшие задачи

1. По желанию: `LLMEnrichment` с реальным провайдером (отдельный scope).
2. Мониторинг / алерты по повторяющимся сбоям доставки.

## С чего читать

- `project-docs/PRD.md`, `project-docs/ARCHITECTURE.md`, `project-docs/TASKS.md`
- `README.md`, `config/default_radar.json`, `.env.example`
- `src/habr_tech_radar/pipeline.py`, `src/habr_tech_radar/settings.py`, `src/habr_tech_radar/main.py`
