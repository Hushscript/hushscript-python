"""Fails when the mutmut score is below 80 (spec 13.2)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

FLOOR = 80.0


def main(stats: str) -> int:
    data = json.loads(Path(stats).read_text(encoding="utf-8"))
    killed = data["killed"]
    statuses = sum(count for status, count in data.items() if status != "total")
    judged = max(data.get("total", 0), statuses)
    score = 100.0 * killed / judged if judged else 0.0
    print(f"mutation score {score:.1f}% ({killed} killed of {judged}, floor {FLOOR})")
    return 0 if score >= FLOOR else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
