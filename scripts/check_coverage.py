"""Fails unless line coverage is at least 90 and branch coverage at least 85 (spec 13.2).

coverage.py's own `fail_under` is a single combined number, so the two floors are checked here
from the JSON report.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

LINES_FLOOR = 90.0
BRANCHES_FLOOR = 85.0


def main(report: str) -> int:
    totals = json.loads(Path(report).read_text(encoding="utf-8"))["totals"]
    lines = 100.0 * totals["covered_lines"] / totals["num_statements"]
    branches = 100.0 * totals["covered_branches"] / totals["num_branches"]
    print(f"coverage: lines {lines:.1f}% (floor {LINES_FLOOR})")
    print(f"coverage: branches {branches:.1f}% (floor {BRANCHES_FLOOR})")
    if lines < LINES_FLOOR or branches < BRANCHES_FLOOR:
        print("coverage is below the floor", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
