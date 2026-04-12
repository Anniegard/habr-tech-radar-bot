from __future__ import annotations

import json
import logging
import os
import tempfile
from collections.abc import Iterable
from pathlib import Path

logger = logging.getLogger(__name__)


class SeenArticleStore:
    """Persist seen article IDs in a JSON file for deduplication across runs."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._seen: set[str] = set()
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = self._path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, UnicodeDecodeError) as e:
            logger.warning(
                "seen store: could not read %s (%s), starting with empty state",
                self._path,
                e,
            )
            return
        except json.JSONDecodeError as e:
            logger.warning(
                "seen store: corrupted JSON in %s (%s), starting with empty state",
                self._path,
                e,
            )
            return

        ids = data.get("seen_ids")
        if not isinstance(ids, list):
            logger.warning("seen store: invalid 'seen_ids' in %s, starting empty", self._path)
            return
        self._seen = {str(x) for x in ids if str(x)}

    def is_seen(self, article_id: str) -> bool:
        return article_id in self._seen

    def mark_seen(self, ids: Iterable[str]) -> None:
        self._seen.update(ids)

    def save(self) -> None:
        """Write current state to disk (atomic replace). Creates parent dirs if needed."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"seen_ids": sorted(self._seen)}
        fd, tmp_name = tempfile.mkstemp(
            prefix=".seen_",
            suffix=".tmp",
            dir=self._path.parent,
        )
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self._path)
        except OSError:
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                pass
            raise
