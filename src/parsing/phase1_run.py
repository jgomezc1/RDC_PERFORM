"""
CLI entrypoint for Phase 1.
Usage:
    python -m src.parsing.phase1_run
    OR from project root: python src/parsing/phase1_run.py
Outputs:
    out/parsed_raw.json
    out/story_graph.json
    out/story_table.csv
    out/point_matrix.csv
"""
import json
import sys
from pathlib import Path
import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import E2K_PATH, OUT_DIR
from src.parsing.e2k_parser import parse_e2k
from src.parsing.story_builder import build_story_graph


def main():
    text = Path(E2K_PATH).read_text(encoding="utf-8", errors="ignore")
    raw = parse_e2k(text)

    # Tag the artifacts version so downstream tools can gate new fields safely.
    # Bump when we add or change top-level Phase-1 structures.
    raw["_artifacts_version"] = "1.1"  # 1.1 introduces LENGTHOFFI/J and OFFSET{X,Y,Z}{I,J} in line_assigns

    story = build_story_graph(raw)

    # Write compact JSON (easier to diff; no giant .py files)
    (OUT_DIR / "parsed_raw.json").write_text(
        json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (OUT_DIR / "story_graph.json").write_text(
        json.dumps(story, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # CSV sanity: stories
    rows = [{
        "story": s["name"],
        "height": s["height"],
        "elev_explicit": s["elev"],
        "elev_computed": story["story_elev"].get(s["name"]),
    } for s in raw["stories"]]
    pd.DataFrame(rows).to_csv(OUT_DIR / "story_table.csv", index=False)

    # CSV sanity: point vs story activation
    story_order = story["story_order_top_to_bottom"]
    pt_to_stories = {}
    for a in raw["point_assigns"]:
        pt_to_stories.setdefault(a["point"], set()).add(a["story"])
    matrix = []
    for pid in sorted(raw["points"].keys(), key=lambda x: (len(x), x)):
        row = {"point": pid}
        assigned = pt_to_stories.get(pid, set())
        for s in story_order:
            row[s] = 1 if s in assigned else 0
        matrix.append(row)
    pd.DataFrame(matrix).to_csv(OUT_DIR / "point_matrix.csv", index=False)

    print("Phase 1 complete.")
    print(f"  - {OUT_DIR/'parsed_raw.json'}")
    print(f"  - {OUT_DIR/'story_graph.json'}")
    print(f"  - {OUT_DIR/'story_table.csv'}")
    print(f"  - {OUT_DIR/'point_matrix.csv'}")


if __name__ == "__main__":
    main()

