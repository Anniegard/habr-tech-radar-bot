from __future__ import annotations

from pathlib import Path

from habr_tech_radar.state.seen_store import SeenArticleStore


def test_seen_store_corrupted_file_recovers_empty_and_save_restores(tmp_path: Path) -> None:
    path = tmp_path / "seen.json"
    path.write_text("{not valid json", encoding="utf-8")
    store = SeenArticleStore(path)
    assert not store.is_seen("a")
    store.mark_seen(["a", "b"])
    store.save()
    store2 = SeenArticleStore(path)
    assert store2.is_seen("a")
    assert store2.is_seen("b")


def test_seen_store_missing_file_starts_empty(tmp_path: Path) -> None:
    path = tmp_path / "missing.json"
    s = SeenArticleStore(path)
    assert not s.is_seen("x")
