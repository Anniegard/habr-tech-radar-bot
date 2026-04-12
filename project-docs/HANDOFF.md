# Передача контекста

## Текущее состояние

- **Пакет:** `habr-tech-radar` (импорт `habr_tech_radar`).
- **Точка входа:** `python -m habr_tech_radar` или `habr-tech-radar` после установки.
- **Обычный режим** (`HTR_DEMO_MODE=false`): загрузка одной или нескольких RSS-лент Habr по HTTP, маппинг в `Article`, дедуп по `HTR_STATE_FILE`, затем **фильтр** (`HeuristicArticleFilter`) → **скоринг** (`HeuristicArticleScoring`, целые очки и `ScoreExplanation`) → **топ-N** (`HTR_MAX_SELECTED_ARTICLES`) → no-op LLM → **доставка в Telegram** (`HttpTelegramDelivery`): при `HTR_DRY_RUN=true` только форматирование и лог «would send» (без HTTP к Bot API); при `HTR_DRY_RUN=false` и непустых `HTR_TELEGRAM_BOT_TOKEN` + `HTR_TELEGRAM_CHAT_ID` — реальные `sendMessage` (HTML, по одному сообщению на статью). Если `HTR_DRY_RUN=false`, а токен или chat id отсутствуют — **ошибка при `default_components`** (`TelegramConfigurationError`), без молчаливого fallback.
- **Демо:** `python -m habr_tech_radar --demo` или `HTR_DEMO_MODE=true` — одна синтетическая статья по пайплайну; сеть и state-файл для ingestion не используются; доставка по умолчанию в режиме `dry_run` (лог с HTML-текстом).
- **Пустой список лент:** `HTR_HABR_RSS_URLS=` (пусто) — без HTTP, ingestion возвращает 0 статей (удобно для тестов без сети).

## Как запускать

```text
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -e ".[dev]"
make test                  # или: pytest, ruff, mypy по Makefile
python -m habr_tech_radar --demo
python -m habr_tech_radar   # RSS + дедуп + filter/score/top-N + доставка (dry_run по умолчанию)
```

## Ближайшие задачи

1. Планировщик / периодический запуск (вне процесса приложения: cron, systemd, CI и т.д.).
2. По желанию: `LLMEnrichment` с OpenAI (за интерфейсом, через env) — **этап отдельного scope**.
3. По желанию: вынести часть правил в `config/` или оставить env как основной источник для личного радара.

## С чего читать

- `project-docs/PRD.md`, `project-docs/ARCHITECTURE.md`, `project-docs/TASKS.md`
- `src/habr_tech_radar/pipeline.py`, `src/habr_tech_radar/settings.py`
- `src/habr_tech_radar/delivery/html_message.py`, `src/habr_tech_radar/delivery/http_telegram.py`
- `src/habr_tech_radar/filtering/heuristic.py`, `src/habr_tech_radar/scoring/heuristic.py`, `src/habr_tech_radar/selection.py`
- `src/habr_tech_radar/ingestion/rss.py`, `src/habr_tech_radar/state/seen_store.py`
