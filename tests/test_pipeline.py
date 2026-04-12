from __future__ import annotations

from habr_tech_radar.pipeline import default_components, run_pipeline
from habr_tech_radar.settings import Settings


def test_pipeline_demo_produces_one_item() -> None:
    components = default_components(
        Settings(
            demo_mode=True,
            include_keywords="",
            include_hubs="",
            exclude_keywords="",
            exclude_hubs="",
        )
    )
    result = run_pipeline(components)
    assert len(result.items) == 1
    assert result.items[0].score.article.id == "demo-1"


def test_pipeline_no_demo_no_rss_urls_empty() -> None:
    components = default_components(Settings(demo_mode=False, habr_rss_urls=[]))
    result = run_pipeline(components)
    assert result.items == []
