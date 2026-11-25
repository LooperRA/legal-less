"""Batch runner: analyse every judgment file in a directory, one JSON result per case.

The runner is resumable (results keyed by SHA-256 of the input) and never fetches anything
from the network: judgments must be supplied by the operator in ``--input-dir``.
"""
from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
from pathlib import Path

from .llm import JSONModel
from .ratio import analyse_judgment

SUFFIXES = {".md", ".txt", ".html", ".htm", ".json"}


def run_batch(input_dir: str | Path, out_dir: str | Path, llm: JSONModel, *, workers: int = 2,
              limit: int | None = None, force: bool = False) -> dict[str, int]:
    src = Path(input_dir)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in src.iterdir() if p.suffix.lower() in SUFFIXES)
    if limit:
        files = files[:limit]
    stats = {"total": len(files), "done": 0, "skipped": 0, "failed": 0}
    log = (out / "run_log.jsonl").open("a", encoding="utf-8")

    def one(path: Path) -> tuple[str, str]:
        raw = path.read_text(encoding="utf-8")
        digest = sha256(raw.encode("utf-8")).hexdigest()
        target = out / f"{path.stem}.json"
        if target.exists() and not force:
            try:
                if json.loads(target.read_text(encoding="utf-8"))["provenance"]["sha256"] == digest:
                    return path.name, "skipped"
            except Exception:
                pass
        started = time.time()
        result = analyse_judgment(raw, llm, source_description=f"operator-supplied file {path.name}")
        target.write_text(result.to_json(), encoding="utf-8")
        log.write(json.dumps({"file": path.name, "citation": result.neutral_citation, "items": len(result.items),
                              "combos": len(result.combos), "true_ratios": len(result.true_ratios),
                              "seconds": round(time.time() - started, 1)}) + "\n")
        log.flush()
        return path.name, "done"

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(one, f): f for f in files}
        for fut in as_completed(futures):
            f = futures[fut]
            try:
                _, status = fut.result()
                stats[status] += 1
            except Exception as exc:  # keep going; record the failure
                stats["failed"] += 1
                log.write(json.dumps({"file": f.name, "error": str(exc)[:500]}) + "\n")
                log.flush()
            print(f"[batch] {sum(stats[k] for k in ('done', 'skipped', 'failed'))}/{stats['total']} "
                  f"{f.name} {stats}", file=sys.stderr, flush=True)
    log.close()
    return stats
