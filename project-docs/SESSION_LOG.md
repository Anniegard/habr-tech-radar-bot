# Журнал сессий

*Одна короткая запись на сессию (человек или агент).*

## 2026-04-12 — Bootstrap

- Создан пакет Python 3.12 в src-layout, tooling (Ruff, mypy, pytest, pre-commit), заглушка пайплайна, тесты, project-docs, правила Cursor, README.
- Запуск по умолчанию — заглушки (без сети). Демо: `HTR_DEMO_MODE=1` или `--demo`.

**Дальше:** реализовать Habr ingestion за `HabrIngestion` (RSS), персистенцию виденных id.
