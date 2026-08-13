"""Archive the aggregate shape of the production `knowledge_gaps` table.

The paper reports that gap logging deduplicated some hundreds of retrieval misses into
some tens of distinct gaps, and the Lessons section argues from that ratio. Those two
numbers were the only ones in the paper that no archived file could support: they were
read off the production table once and written down, so nothing could recompute them,
a reader could not check them, and because the table keeps growing, anyone querying it
later would get different numbers and conclude the paper was wrong. This pins them.

Read-only, deliberately. It issues one SELECT and writes nothing back: a live product
is not worth touching for a number that a read answers completely.

**It stores counts only, never the `question` column.** Those rows are whatever the
deployed agent failed to answer, which includes real user traffic, and the paper states
that no real-user conversation was used. Aggregates keep that true; question text would
not.

It also resolves an ambiguity the repository cannot: `_record_gap` inserts without
setting `hit_count`, so the total number of misses is `SUM(hit_count)` if the column
defaults to 1 but `SUM(hit_count) + COUNT(*)` if it defaults to 0, and the table's DDL
is not in the backend repo. `min_hit_count` in the output answers it, and both readings
are recorded so the paper can quote the right one.

    ../.venv-agent/bin/python archive_gap_table.py            # print, then write
    ../.venv-agent/bin/python archive_gap_table.py --dry-run   # print only
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT
ARCHIVE = HERE / "archived_runs"
BACKEND_ENV = HERE.parent.parent / "kokun-backend" / ".env"
OUT = ARCHIVE / "knowledge_gaps_snapshot.json"


def _credentials() -> tuple[str, str]:
    """Read Supabase credentials from the backend's .env without importing it."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if url and key:
        return url, key
    if not BACKEND_ENV.exists():
        raise SystemExit(f"no SUPABASE_URL/SUPABASE_KEY in the environment and no {BACKEND_ENV}")
    found: dict[str, str] = {}
    for line in BACKEND_ENV.read_text().splitlines():
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.strip() in ("SUPABASE_URL", "SUPABASE_KEY"):
            found[k.strip()] = v.strip().strip("'\"")
    try:
        return found["SUPABASE_URL"], found["SUPABASE_KEY"]
    except KeyError as e:
        raise SystemExit(f"{BACKEND_ENV} has no {e.args[0]}")


def fetch() -> dict:
    from supabase import create_client

    url, key = _credentials()
    client = create_client(url, key)
    # Only the two columns the aggregates need. Never `question`.
    rows = (client.table("knowledge_gaps")
            .select("hit_count,last_seen_at")
            .execute().data or [])
    if not rows:
        raise SystemExit("knowledge_gaps returned no rows; refusing to archive an empty snapshot")

    counts = [int(r.get("hit_count") or 0) for r in rows]
    seen = sorted(str(r["last_seen_at"]) for r in rows if r.get("last_seen_at"))
    distinct, total = len(counts), sum(counts)
    return {
        "queried_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ"),
        "table": "knowledge_gaps",
        "dedup_threshold": 0.85,
        "distinct_gaps": distinct,
        "sum_hit_count": total,
        "min_hit_count": min(counts),
        "max_hit_count": max(counts),
        # Which of these the paper should quote depends on the column default, and
        # min_hit_count settles it: 1 means every insert already counted its own miss.
        "total_misses_if_default_1": total,
        "total_misses_if_default_0": total + distinct,
        "total_misses": total if min(counts) >= 1 else total + distinct,
        "default_inferred": 1 if min(counts) >= 1 else 0,
        "last_seen_range": [seen[0], seen[-1]] if seen else None,
        "note": ("Counts only; the question column is never read or stored, because "
                 "these rows include production traffic and the paper reports that no "
                 "real-user conversation was used."),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="print without writing")
    args = ap.parse_args()

    snap = fetch()
    ratio = snap["total_misses"] / snap["distinct_gaps"]
    print(f"knowledge_gaps as of {snap['queried_at']}")
    print(f"  distinct gaps        {snap['distinct_gaps']}")
    print(f"  total misses         {snap['total_misses']}"
          f"   (hit_count default inferred as {snap['default_inferred']})")
    print(f"  ratio                {ratio:.1f}x")
    print(f"  hit_count range      {snap['min_hit_count']}..{snap['max_hit_count']}")
    if snap["default_inferred"] == 0:
        print("  NOTE: the paper's figure needs +distinct_gaps; it undercounted by "
              f"{snap['distinct_gaps']}")
    if args.dry_run:
        print("\n--dry-run: nothing written")
        return
    ARCHIVE.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(snap, indent=2) + "\n")
    print(f"\nwrote {OUT.relative_to(HERE)}")
    print("  next: quote these in the paper with the date, and add a verifier check")


if __name__ == "__main__":
    main()
