# Architecture

## Pipeline

```mermaid
flowchart LR
  ingest[ingestion]
  filt[filtering]
  score[scoring]
  llm[llm]
  del[delivery]
  ingest --> filt --> score --> llm --> del
```



- **ingestion**: Fetch or parse new articles (`HabrIngestion` protocol). **Demo:** `StubHabrIngestion` (synthetic article). **Normal:** `RssHabrIngestion` + JSON `SeenArticleStore` for cross-run dedup.
- **filtering**: Reduce candidates (`ArticleFilter`; stub pass-through).
- **scoring**: Rank or score (`ArticleScoring`; stub fixed score).
- **llm**: Optional enrichment (`LLMEnrichment`; `NoOpLLMEnrichment`).
- **delivery**: Notify (`TelegramDelivery`; `LogOnlyTelegramDelivery` logs only).

## Code map


| Path                              | Role                                                   |
| --------------------------------- | ------------------------------------------------------ |
| `src/habr_tech_radar/settings.py` | `pydantic-settings`, env prefix `HTR_`                 |
| `src/habr_tech_radar/pipeline.py` | `run_pipeline`, `default_components`                   |
| `src/habr_tech_radar/state/`      | `SeenArticleStore` (seen article IDs JSON file)        |
| `src/habr_tech_radar/models/`     | `Article`, `FilterResult`, `ArticleScore`, `RadarItem` |
| `config/`                         | Reserved for future rules files (not read yet)         |


## Design choices

- **Protocols** for service boundaries; **stub** implementations where integrations are not ready yet.
- **RSS HTTP** in normal mode (`RssHabrIngestion`); **no network** in demo mode or when `HTR_HABR_RSS_URLS` is empty.
- **Demo mode** (`HTR_DEMO_MODE` or `--demo`) injects one synthetic article for pipeline testing.

