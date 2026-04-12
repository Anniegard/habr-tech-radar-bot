# Передача контекста

## Текущее состояние

- **Пакет:** `habr-tech-radar` (импорт `habr_tech_radar`).
- **Точка входа:** `python -m habr_tech_radar` или `habr-tech-radar` после установки.
- **Обычный режим** (`HTR_DEMO_MODE=false`): загрузка одной или нескольких RSS-лент Habr по HTTP, маппинг в `Article`, фильтрация по уже виденным `id` в файле `HTR_STATE_FILE` (по умолчанию `.habr_tech_radar_seen.json`), сохранение новых id после успешного разбора.
- **Демо:** `python -m habr_tech_radar --demo` или `HTR_DEMO_MODE=true` — одна синтетическая статья по пайплайну; сеть и state-файл для ingestion не используются; delivery только в лог.
- **Пустой список лент:** `HTR_HABR_RSS_URLS=` (пусто) — без HTTP, ingestion возвращает 0 статей (удобно для тестов без сети).

## Как запускать

```text
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -e ".[dev]"
make test                  # или: pytest, ruff, mypy по Makefile
python -m habr_tech_radar --demo
python -m habr_tech_radar   # RSS + дедуп (нужен интернет)
```

## Ближайшие задачи

1. Реальный **`TelegramDelivery`** с bot token + chat ID и учётом `dry_run` (при `true` — не отправлять).
2. **`ArticleFilter`** / **`ArticleScoring`** с правилами в `config/` вместо заглушек.
3. По желанию: планировщик / периодический запуск; при росте состояния — рассмотреть SQLite.

## С чего читать

- `project-docs/PRD.md`, `project-docs/ARCHITECTURE.md`, `project-docs/TASKS.md`
- `src/habr_tech_radar/pipeline.py`, `src/habr_tech_radar/settings.py`
- `src/habr_tech_radar/ingestion/rss.py`, `src/habr_tech_radar/state/seen_store.py`
