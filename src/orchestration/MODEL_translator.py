# -*- coding: utf-8 -*-
"""
MODEL_translator.py
Builds the OpenSees model for visualization inside the Streamlit app.

Staged build supported via build_model(stage=...):
  - 'nodes'            : nodes + point restraints + rigid diaphragms (+ nodes.json)
  - 'columns'          : nodes + restraints + diaphragms + columns (+ nodes.json)
  - 'beams' or 'all'   : nodes + restraints + diaphragms + columns + beams (+ nodes.json)

Change log:
- 2025-08-25: Build order updated to define supports BEFORE diaphragms so that
  diaphragms.py can read out/supports.json and skip stories with supports.
- 2025-08-25: Emit nodes.json after diaphragms creation (includes grid + masters).
"""
from __future__ import annotations

from openseespy.opensees import wipe, model

from src.model_building.nodes import define_nodes
from src.model_building.supports import define_point_restraints_from_e2k
from src.model_building.springs import define_spring_supports
from src.model_building.diaphragms import define_rigid_diaphragms
from src.model_building.columns import define_columns
from src.model_building.beams import define_beams
from src.model_building.emit_nodes import emit_nodes_json

# Default artifacts directory for emit_nodes_json; fall back to "out"
try:
    from config import OUT_DIR as _DEFAULT_OUT
except Exception:
    _DEFAULT_OUT = "out"


def build_model(stage: str = "all") -> None:
    """
    Build the OpenSees model according to the requested stage.

    Order (supports and springs before diaphragms, then emit nodes.json):
      1) Nodes
      2) Point restraints (supports)        -> out/supports.json
      3) Spring supports (zeroLength elems)
      4) Rigid diaphragms (uses supports)   -> out/diaphragms.json
      5) Emit nodes.json (grid + masters)   -> out/nodes.json
      6) Columns                            -> out/columns.json
      7) Beams (if stage in {'all','beams'})-> out/beams.json
    """
    wipe()
    # 3D, 6-DOF nodes (UX, UY, UZ, RX, RY, RZ)
    model("basic", "-ndm", 3, "-ndf", 6)

    # 1) Nodes
    print("[MODEL_translator] Step 1: Creating nodes...")
    from openseespy.opensees import getNodeTags as _check_nodes
    define_nodes()
    nodes_after_define = len(_check_nodes())
    print(f"[MODEL_translator] After define_nodes(): {nodes_after_define} nodes in domain")

    # 2) Point restraints (from ETABS POINTASSIGN ... RESTRAINT)
    print("[MODEL_translator] Step 2: Applying point restraints...")
    define_point_restraints_from_e2k()
    nodes_after_restraints = len(_check_nodes())
    print(f"[MODEL_translator] After restraints: {nodes_after_restraints} nodes in domain")

    # 3) Spring supports (from ETABS POINTASSIGN ... SPRINGPROP)
    print("[MODEL_translator] Step 3: Defining spring supports...")
    define_spring_supports(verbose=False)
    nodes_after_springs = len(_check_nodes())
    print(f"[MODEL_translator] After springs: {nodes_after_springs} nodes in domain")

    # 4) Diaphragms (creates centroid masters and ties slaves; masters are fixed in UZ,RX,RY)
    print("[MODEL_translator] Step 4: Defining rigid diaphragms...")
    define_rigid_diaphragms()
    nodes_after_diaphragms = len(_check_nodes())
    print(f"[MODEL_translator] After diaphragms: {nodes_after_diaphragms} nodes in domain")

    # 5) Emit nodes.json (includes masters; requires story_graph.json + diaphragms.json)
    print("[MODEL_translator] Step 5: Emitting nodes.json...")
    emit_nodes_json(_DEFAULT_OUT)
    nodes_after_emit = len(_check_nodes())
    print(f"[MODEL_translator] After emit_nodes: {nodes_after_emit} nodes in domain")

    if stage.lower() == "nodes":
        print("[MODEL] Built NODES + RESTRAINTS + SPRINGS + DIAPHRAGMS + NODES.JSON.")
        return

    # 6) Elements
    define_columns()

    # 7) Beams if requested/all
    if stage.lower() in ("all", "beams"):
        define_beams()

    print(f"[MODEL] Model built with stage={stage} (nodes.json emitted).")


if __name__ == "__main__":
    build_model()
