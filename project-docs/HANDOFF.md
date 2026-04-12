# Передача контекста

## Текущее состояние

- **Пакет:** `habr-tech-radar` (импорт `habr_tech_radar`).
- **Точка входа:** `python -m habr_tech_radar` или `habr-tech-radar` после установки.
- **По умолчанию:** заглушка ingestion не возвращает статей; **нет** вызовов внешних API.
- **Демо:** `python -m habr_tech_radar --demo` или `HTR_DEMO_MODE=true` — одна синтетическая статья по пайплайну; delivery только в лог.

## Как запускать

```text
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -e ".[dev]"
make test                  # или: pytest, ruff, mypy по Makefile
python -m habr_tech_radar --demo
```

## Ближайшие задачи

1. Заменить `StubHabrIngestion` на RSS (или официальный API, если используете): получать записи, маппить в `Article`.
2. Добавить персистенцию последнего виденного id статьи / временной метки (достаточно простого JSON-файла).
3. Набросать реальный `TelegramDelivery` с учётом `dry_run` (при true — не отправлять).

## С чего читать

- `project-docs/PRD.md`, `project-docs/ARCHITECTURE.md`, `project-docs/TASKS.md`
- `src/habr_tech_radar/pipeline.py`, `src/habr_tech_radar/settings.py`

