# Changelog

## [Unreleased]

### 2026-04-12

- Развёртывание на Ubuntu VM: каталог `deploy/` с шаблонами `habr-tech-radar.service` (oneshot), `habr-tech-radar.timer`, скрипт `deploy/install_vm.sh` (venv, `pip install -e .`, опциональное копирование unit-файлов в `/etc/systemd/system/`). Документация в README и `project-docs/HANDOFF.md`.
- Конфигурация путей: `HTR_PROJECT_ROOT`, функция `effective_state_file()` для резолва относительного `HTR_STATE_FILE`; интеграция в пайплайн (`SeenArticleStore`).
- CLI: при ошибке конфигурации Telegram в живом режиме — код выхода 2 и одна строка в лог (`TelegramConfigurationError` в `main`); тесты в `tests/test_paths.py`.
- `.env.example`: дополнены комментарии для VM, плейсхолдеры Telegram, примеры `HTR_STATE_FILE` / `HTR_PROJECT_ROOT`.
- Telegram: `HttpTelegramDelivery` (stdlib HTTP JSON `sendMessage`), HTML-сообщения из `RadarItem` / `ScoreExplanation` (`format_radar_item_html`), строгий `HTR_DRY_RUN` (без сети при `true`), fail-fast при `HTR_DRY_RUN=false` без токена и chat id; тесты и обновление README / project-docs / `.env.example`.
- Bootstrap: Python 3.12, src-layout, tooling (Ruff, mypy, pytest, pre-commit), stub pipeline, tests, project-docs, Cursor rules.
- Документация: README и часть `project-docs` на русском; правило `boss-brief-ru.mdc`.
- RSS ingestion (`RssHabrIngestion`, stdlib HTTP/XML) и дедупликация между запусками через JSON `SeenArticleStore`; настройки `HTR_HABR_RSS_URLS`, `HTR_STATE_FILE`, `HTR_RSS_FETCH_TIMEOUT_SECONDS`; демо-режим без изменений.
- Эвристический фильтр и скоринг по env (`HTR_INCLUDE_*`, `HTR_EXCLUDE_*`, веса `HTR_SCORE_*`), модель `ScoreExplanation`, отбор топ-N (`HTR_MAX_SELECTED_ARTICLES`), тесты и обновление документации.

