"""Generate deterministic, original simulation results without a web server."""
from __future__ import annotations
import json
from pathlib import Path
from robotics.simulation import RobotCell


def main():
    cell = RobotCell(seed=13)
    cell.run()
    while cell.pick_count < 12 and cell.elapsed < 240:
        cell.step(0.08)
    if cell.pick_count != 12:
        raise RuntimeError(f"Incomplete run: {cell.pick_count}/12 sorted")
    result = {
        "experiment": "12 sequential boxes, fixed random seed 13",
        "units": {"time": "simulation seconds"},
        "sorted": cell.pick_count,
        "counts": cell.counts,
        "elapsed_simulation_seconds": round(cell.elapsed, 2),
        "controller_state_at_completion": cell.phase,
        "note": "Idealized deterministic simulation, not physical robot performance",
    }
    path = Path(__file__).resolve().parent / "results" / "demo_summary.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
