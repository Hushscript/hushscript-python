"""Fails when the mutmut score is below 80 (spec 13.2)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

FLOOR = 80.0


def main(stats: str) -> int:
    data = json.loads(Path(stats).read_text(encoding="utf-8"))
    killed = data["killed"]
    judged = killed + data["survived"] + data.get("timeout", 0) + data.get("suspicious", 0)
    score = 100.0 * killed / judged if judged else 100.0
    print(f"mutation score {score:.1f}% ({killed} killed of {judged}, floor {FLOOR})")
    return 0 if score >= FLOOR else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
