from __future__ import annotations

from habr_tech_radar.pipeline import default_components, run_pipeline


def test_pipeline_demo_produces_one_item() -> None:
    components = default_components(demo_mode=True)
    items = run_pipeline(components)
    assert len(items) == 1
    assert items[0].score.article.id == "demo-1"


def test_pipeline_no_demo_empty() -> None:
    components = default_components(demo_mode=False)
    items = run_pipeline(components)
    assert items == []
