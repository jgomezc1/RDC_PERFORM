# -*- coding: utf-8 -*-
"""
Streamlit viewer for ETABS->OpenSees models.

Workflow:
  1) Upload a Python model file that exposes build_model(stage='...').
  2) Choose a build stage (Nodes only / Nodes+Columns / Nodes+Columns+Beams).
  3) Choose a view filter (Columns only / Beams only / Nodes + Beams / Columns + Beams).
  4) Build and visualize. Story filtering is available if ./out/story_graph.json exists.

Visualization:
- Optional visualization of Rigid Diaphragm Master Nodes (centroid nodes)
  read from ./out/diaphragms.json written by the translator during build.
- Boundary Conditions overlay (from ./out/supports.json) with per-DOF toggles.
  BCs at the Master nodes, if any, are excluded from the overlay.
"""

import streamlit as st
import os
import importlib.util
import sys
import tempfile
import json
import datetime
from typing import Dict, Tuple, List, Any
from openseespy.opensees import (
    wipe, getNodeTags, nodeCoord, getEleTags, eleNodes
)

APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(APP_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)
try:
    os.chdir(PROJECT_ROOT)
except Exception:
    pass

# Plotting utilities
import view_utils_App as vu


# Enhanced verification module
try:
    from model_verification_app import add_verification_tab, verify_joint_offsets, run_modal_analysis
    VERIFICATION_AVAILABLE = True
except ImportError:
    VERIFICATION_AVAILABLE = False

# Structural validation module
try:
    from structural_validation_app import run_structural_validation, display_validation_results
    STRUCTURAL_VALIDATION_AVAILABLE = True
except ImportError:
    STRUCTURAL_VALIDATION_AVAILABLE = False


# -----------------------
# Helpers
# -----------------------
def load_module_from_path(mod_name: str, file_path: str):
    """Dynamically load a module from a file path."""
    spec = importlib.util.spec_from_file_location(mod_name, file_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader, f"Cannot load module from {file_path}"
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module

def collect_nodes() -> Dict[int, Tuple[float, float, float]]:
    """Return {node_tag: (x, y, z)} from the current OpenSees domain."""
    try:
        node_tags = getNodeTags()
    except Exception:
        return {}
    return {int(tag): tuple(nodeCoord(int(tag))) for tag in node_tags}

def collect_elements() -> Dict[int, Tuple[int, int]]:
    """Return {ele_tag: (i, j)} for all 2-node elements."""
    results: Dict[int, Tuple[int, int]] = {}
    try:
        ele_tags = getEleTags()
    except Exception:
        return results
    for et in ele_tags:
        try:
            ni, nj = eleNodes(int(et))
            results[int(et)] = (int(ni), int(nj))
        except Exception:
            continue
    return results

def summarize_elements(nodes: Dict[int, Tuple[float, float, float]],
                       elements: Dict[int, Tuple[int, int]]) -> Dict[str, int]:
    x_dir = y_dir = z_dir = others = 0
    for _, (ni, nj) in elements.items():
        if ni not in nodes or nj not in nodes:
            others += 1
            continue
        xi, yi, zi = nodes[ni]
        xj, yj, zj = nodes[nj]
        dx, dy, dz = abs(xj - xi), abs(yj - yi), abs(zj - zi)
        mx = max(dx, dy, dz)
        if mx == dx and mx > 0:
            x_dir += 1
        elif mx == dy and mx > 0:
            y_dir += 1
        elif mx == dz and mx > 0:
            z_dir += 1
        else:
            others += 1
    return {"X": x_dir, "Y": y_dir, "Z": z_dir, "Other": others}

def filter_elements_by_orientation(nodes: Dict[int, Tuple[float, float, float]],
                                   elements: Dict[int, Tuple[int, int]],
                                   mode: str) -> Dict[int, Tuple[int, int]]:
    if mode == "columns_beams":
        return elements
    out: Dict[int, Tuple[int, int]] = {}
    for tag, (ni, nj) in elements.items():
        if ni not in nodes or nj not in nodes:
            continue
        xi, yi, zi = nodes[ni]
        xj, yj, zj = nodes[nj]
        dx, dy, dz = abs(xj - xi), abs(yj - yi), abs(zj - zi)
        mx = max(dx, dy, dz)
        is_column = (mx == dz and mx > 0)
        if mode == "columns_only" and is_column:
            out[tag] = (ni, nj)
        elif mode in ("beams_only", "nodes_beams") and (mx == dx or mx == dy) and mx > 0:
            out[tag] = (ni, nj)
    return out

def load_story_meta(path: str = "out/story_graph.json"):
    """Return (story_names_top_to_bottom, story_elev_map) if available, else ([], {})."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        names = [str(s) for s in data.get("story_order_top_to_bottom", [])]
        elevs = {str(k): float(v) for k, v in data.get("story_elev", {}).items()}
        return names, elevs
    except Exception:
        return [], {}

def _near(z: float, Z: float, tol: float) -> bool:
    return abs(z - Z) <= tol

def filter_by_stories_any(nodes, elements, story_names, story_elev, tol=1e-9):
    wantedZ = [story_elev[s] for s in story_names if s in story_elev]
    if not wantedZ:
        return elements
    out = {}
    for tag, (ni, nj) in elements.items():
        if ni not in nodes or nj not in nodes:
            continue
        zi = nodes[ni][2]; zj = nodes[nj][2]
        if any(_near(zi, Zs, tol) or _near(zj, Zs, tol) for Zs in wantedZ):
            out[tag] = (ni, nj)
    return out

def filter_by_story_range(nodes, elements, story_start, story_end, story_elev, tol=1e-9):
    if story_start not in story_elev or story_end not in story_elev:
        return elements
    z1, z2 = story_elev[story_start], story_elev[story_end]
    zmin, zmax = (z1, z2) if z1 <= z2 else (z2, z1)
    zmin -= tol; zmax += tol
    out = {}
    for tag, (ni, nj) in elements.items():
        if ni not in nodes or nj not in nodes:
            continue
        zi = nodes[ni][2]; zj = nodes[nj][2]
        if (zmin <= zi <= zmax) or (zmin <= zj <= zmax):
            out[tag] = (ni, nj)
    return out

def load_diaphragms_meta(path: str = "out/diaphragms.json") -> List[int]:
    """Return list of diaphragm master-node tags if file exists, else []."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        masters = [int(rec["master"]) for rec in data.get("diaphragms", []) if "master" in rec]
        return masters
    except Exception:
        return []

def load_supports_meta(path: str = "out/supports.json") -> Dict[int, Tuple[int, int, int, int, int, int]]:
    """
    Return {node_tag: (UX, UY, UZ, RX, RY, RZ)} from out/supports.json if present.
    Excludes ground nodes (tag > 9000000) which are rendered as spring markers instead.
    If missing/invalid, returns {}.
    """
    try:
        import os
        if not os.path.exists(path):
            print(f"[load_supports_meta] File not found: {path} (cwd={os.getcwd()})")
            return {}
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        out: Dict[int, Tuple[int, int, int, int, int, int]] = {}
        ground_nodes_skipped = 0
        for rec in data.get("applied", []):
            n = int(rec.get("node"))

            # Skip ground nodes - they should be rendered as spring markers, not BC markers
            if n > 9000000:
                ground_nodes_skipped += 1
                continue

            mask = tuple(int(v) for v in rec.get("mask", []))
            if len(mask) == 6:
                out[n] = mask  # type: ignore[assignment]
        print(f"[load_supports_meta] Loaded {len(out)} structural supports from {path}")
        if ground_nodes_skipped > 0:
            print(f"[load_supports_meta] Skipped {ground_nodes_skipped} ground nodes (will render as springs)")
        return out
    except Exception as e:
        print(f"[load_supports_meta] Error loading supports: {e}")
        import traceback
        traceback.print_exc()
        return {}


def load_springs_meta(path: str = "out/spring_grounds.json") -> Dict[int, Dict[str, Any]]:
    """
    Return {structural_node_tag: {ground_tag, spring_type, ...}} for nodes with springs.
    If missing/invalid, returns {}.
    """
    try:
        import os
        if not os.path.exists(path):
            print(f"[load_springs_meta] File not found: {path}")
            return {}
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        out: Dict[int, Dict[str, Any]] = {}
        for ground_node in data.get("ground_nodes", []):
            structural_tag = int(ground_node.get("structural_node"))
            ground_tag = int(ground_node.get("tag"))
            story = ground_node.get("story", "")

            out[structural_tag] = {
                "ground_tag": ground_tag,
                "story": story,
                "kind": ground_node.get("kind", "spring_ground")
            }

        print(f"[load_springs_meta] Loaded {len(out)} nodes with springs from {path}")
        return out
    except Exception as e:
        print(f"[load_springs_meta] Error loading springs: {e}")
        import traceback
        traceback.print_exc()
        return {}


# -----------------------
# UI
# -----------------------
st.set_page_config(layout="wide", page_title="ETABS → OpenSees Viewer")

c1, c2, c3 = st.columns([1, 4, 1])

with c1:
    st.image("company_logo.png", width=120)

with c2:
    st.title("R&DC Nonlinear Time History Analysis")
    st.subheader("Powered by OpenSeesPy")

with c3:
    st.image("company_logo.png", width=120)

st.write(
    "Upload a **model script** (e.g., `MODEL_translated.py`), choose a build stage, "
    "and visualize the resulting OpenSees domain."
)

with st.sidebar:
    st.header("Build Controls")

    # Model source selection
    model_source = st.radio(
        "Model Source",
        ["Use built-in MODEL_translator", "Upload custom model file"],
        index=0
    )

    uploaded_file = None
    if model_source == "Upload custom model file":
        uploaded_file = st.file_uploader(
            "1) Upload `kosmos_translated.py` (or similar)",
            type=["py"],
            accept_multiple_files=False
        )

    stage_choice = st.selectbox(
        "2) Build Stage",
        ["Nodes only", "Nodes + Columns", "Nodes + Columns + Beams"],
        index=2
    )
    stage_param = {"Nodes only": "nodes", "Nodes + Columns": "columns", "Nodes + Columns + Beams": "all"}[stage_choice]

    view_choice = st.selectbox(
        "3) View Filter",
        ["Columns only", "Beams only", "Nodes + Beams", "Columns + Beams"],
        index=3
    )
    view_param = {
        "Columns only": "columns_only",
        "Beams only": "beams_only",
        "Nodes + Beams": "nodes_beams",
        "Columns + Beams": "columns_beams",
    }[view_choice]

    plot_height = st.slider("4) Plot Height (px)", min_value=500, max_value=1200, value=800, step=50)
    show_axes_grid = st.checkbox("5) Show reference axes/grid", value=True)

    # Show nodes toggle — default OFF for beams/columns-only views
    default_show_nodes = (view_param == "nodes_beams") or (stage_param == "nodes")
    show_nodes = st.checkbox("6) Show nodes (markers)", value=default_show_nodes)

    # Toggle local longitudinal axes (i -> j)
    show_local_axes = st.checkbox("7) Show local longitudinal axes (i → j)", value=False)

    # Diaphragm Master Nodes toggle (independent of regular nodes)
    show_master_nodes = st.checkbox("8) Show diaphragm master nodes", value=True)

    # NEW: Boundary Conditions overlay controls
    st.markdown("---")
    st.subheader("Boundary Conditions")
    show_supports = st.checkbox("Show boundary-condition overlay", value=True)
    c1, c2 = st.columns(2)
    with c1:
        bc_size = st.slider("Symbol size", min_value=0.05, max_value=1.00, value=0.25, step=0.05)
    with c2:
        st.caption("Per-DOF (1 = fixed)")
        dof_UX = st.checkbox("UX", value=True)
        dof_UY = st.checkbox("UY", value=True)
        dof_UZ = st.checkbox("UZ", value=True)
        dof_RX = st.checkbox("RX", value=True)
        dof_RY = st.checkbox("RY", value=True)
        dof_RZ = st.checkbox("RZ", value=True)

    # Springs overlay controls
    st.markdown("---")
    st.subheader("Spring Markers")
    show_springs = st.checkbox("Show spring markers (SSI nodes)", value=True)
    spring_size = st.slider("Spring marker size", min_value=5, max_value=20, value=10, step=1)

    # Build Controls
    st.markdown("---")

    st.caption("Tip: build in stages and filter the view to diagnose issues.")

    build_btn = st.button("Build & Visualize Model", use_container_width=True, type="primary")

# -----------------------
# Build & visualize
# -----------------------
if build_btn:
    # Debug: Print model source selection
    print(f"[DEBUG] model_source = '{model_source}'")
    print(f"[DEBUG] uploaded_file = {uploaded_file}")

    # Check if we have a model source
    if model_source == "Upload custom model file" and not uploaded_file:
        st.error("Please upload a Python model file first.")
    else:
        try:
            wipe()

            if model_source == "Use built-in MODEL_translator":
                # Use the built-in MODEL_translator directly
                # Force reload to ensure we get the latest code (not cached)
                import sys
                import importlib

                # Remove cached modules
                modules_to_reload = [
                    'src.orchestration.MODEL_translator',
                    'src.model_building.nodes',
                    'src.model_building.supports',
                    'src.model_building.springs',
                    'src.model_building.diaphragms',
                    'src.model_building.columns',
                    'src.model_building.beams',
                    'src.model_building.emit_nodes',
                ]
                for mod_name in modules_to_reload:
                    if mod_name in sys.modules:
                        importlib.reload(sys.modules[mod_name])

                from src.orchestration.MODEL_translator import build_model
                print(f"[Viewer] ✅ Building model using built-in MODEL_translator with stage={stage_param}")
                st.info(f"Building with built-in MODEL_translator (stage={stage_param})")
                build_model(stage=stage_param)
            else:
                # Load and execute uploaded file
                print(f"[Viewer] ⚠️ Building model from uploaded file: {uploaded_file.name if uploaded_file else 'None'}")
                st.info(f"Building from uploaded file: {uploaded_file.name if uploaded_file else 'None'}")
                with tempfile.NamedTemporaryFile(delete=False, suffix=".py") as tmp:
                    tmp.write(uploaded_file.getvalue())
                    model_script_path = tmp.name

                user_model_module = load_module_from_path("user_model", model_script_path)
                user_model_module.build_model(stage=stage_param)

            nodes = collect_nodes()
            all_elements = collect_elements()

            # DIAGNOSTIC: Check node z-range
            if nodes:
                z_coords = [coord[2] for coord in nodes.values()]
                z_min, z_max = min(z_coords), max(z_coords)
                print(f"[DIAGNOSTIC] Collected {len(nodes)} nodes, Z range: [{z_min:.3f}, {z_max:.3f}]")
                nodes_below_10 = sum(1 for z in z_coords if z < 10.0)
                print(f"[DIAGNOSTIC] Nodes below z=10.00: {nodes_below_10}")

            elements = filter_elements_by_orientation(nodes, all_elements, view_param)

            # Load master nodes metadata written by diaphragms.py (if present)
            master_nodes = load_diaphragms_meta()

            # Load BC metadata (supports) if present
            supports_by_node = load_supports_meta()

            # Load spring metadata if present
            springs_by_node = load_springs_meta()

            st.session_state.model_built = True
            st.session_state.nodes = nodes
            st.session_state.elements_all = elements
            st.session_state.plot_height = plot_height
            st.session_state.show_axes_grid = show_axes_grid
            st.session_state.show_nodes = show_nodes
            st.session_state.show_local_axes = show_local_axes
            st.session_state.show_master_nodes = show_master_nodes
            st.session_state.master_nodes = master_nodes

            # Persist supports overlay state
            st.session_state.show_supports = show_supports
            st.session_state.supports_by_node = supports_by_node
            st.session_state.bc_size = bc_size
            st.session_state.bc_dofs = {
                "UX": bool(dof_UX),
                "UY": bool(dof_UY),
                "UZ": bool(dof_UZ),
                "RX": bool(dof_RX),
                "RY": bool(dof_RY),
                "RZ": bool(dof_RZ),
            }

            # Persist springs overlay state
            st.session_state.show_springs = show_springs
            st.session_state.springs_by_node = springs_by_node
            st.session_state.spring_size = spring_size

            # Clear any previous test results since we've moved to unified validation
            st.session_state.test_results = None

            st.success("Model built successfully. Use story filters below if needed.")
        except Exception as e:
            st.exception(e)
            st.session_state.model_built = False

# Initialize state
if "model_built" not in st.session_state:
    st.session_state.model_built = False
for key, default in [
    ("nodes", {}), ("elements_all", {}), ("plot_height", 800),
    ("show_axes_grid", True), ("show_nodes", True), ("show_local_axes", False),
    ("show_master_nodes", True), ("master_nodes", []),
    # supports defaults
    ("show_supports", True), ("supports_by_node", {}), ("bc_size", 0.25),
    ("bc_dofs", {"UX": True, "UY": True, "UZ": True, "RX": True, "RY": True, "RZ": True}),
    # springs defaults
    ("show_springs", True), ("springs_by_node", {}), ("spring_size", 10),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# -----------------------
# Story Filter Panel (post-build)
# -----------------------
names, elevs = load_story_meta()
st.subheader("Story Filter")
if not st.session_state.model_built:
    st.info("Build a model to enable story filtering.")
    st.session_state.elements = {}
else:
    if not names:
        st.caption("No `out/story_graph.json` detected — story-based filtering is unavailable.")
        st.session_state.elements = st.session_state.elements_all.copy()
    else:
        mode = st.radio(
            "Mode",
            ["All stories", "Select specific stories", "Select range (contiguous)"],
            index=0,
            horizontal=True
        )

        elements = st.session_state.elements_all.copy()
        if mode == "All stories":
            pass
        elif mode == "Select specific stories":
            selection = st.multiselect(
                "Pick one or more stories (top to bottom)",
                options=names,
                default=[],
                help="Keeps members that touch ANY of the selected story planes."
            )
            if selection:
                elements = filter_by_stories_any(st.session_state.nodes, elements, selection, elevs, tol=1e-9)
                st.caption(f"Active: {', '.join(selection)}")
            else:
                st.caption("No stories selected → showing all.")
        else:
            c1, c2 = st.columns(2)
            with c1:
                start_story = st.selectbox("Start story", options=names, index=0)
            with c2:
                end_story = st.selectbox("End story", options=names, index=len(names)-1)
            elements = filter_by_story_range(st.session_state.nodes, elements, start_story, end_story, elevs, tol=1e-9)
            st.caption(f"Active range: {start_story} ↔ {end_story}")

        st.session_state.elements = elements


# -----------------------
# Visualization + Summary
# -----------------------
st.subheader("3D Interactive View")
if st.session_state.model_built:
    # If the user selected "Nodes only" stage, force nodes on (safety)
    force_nodes_on = (stage_param == "nodes")
    show_nodes_effective = True if force_nodes_on else bool(st.session_state.show_nodes)

    view_options = {
        "show_axes": st.session_state.show_axes_grid,
        "show_grid": st.session_state.show_axes_grid,
        "show_nodes": show_nodes_effective,
        "show_local_axes": bool(st.session_state.show_local_axes),
        "local_axis_frac": 0.25,
        "show_master_nodes": bool(st.session_state.show_master_nodes),
        "master_nodes": st.session_state.master_nodes,
        "master_node_size": 10,
        "node_size": 3,
        "beam_thickness": 2,
        "column_thickness": 3,
        # NEW: supports overlay
        "show_supports": bool(st.session_state.show_supports),
        "supports_by_node": st.session_state.supports_by_node,
        "supports_dofs": st.session_state.bc_dofs,
        "supports_size": float(st.session_state.bc_size),
        "supports_exclude": set(st.session_state.master_nodes or []),  # <-- exclude masters explicitly
        # Springs overlay
        "show_springs": bool(st.session_state.show_springs),
        "springs_by_node": st.session_state.springs_by_node,
        "springs_size": int(st.session_state.spring_size),
    }
    elems = st.session_state.elements if "elements" in st.session_state else st.session_state.elements_all
    fig = vu.create_interactive_plot(
        nodes=st.session_state.nodes,
        elements=elems,
        options=view_options
    )
    try:
        fig.update_layout(height=st.session_state.plot_height, margin=dict(l=0, r=0, t=30, b=0))
    except Exception:
        pass
    st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False})
else:
    st.info("Upload a model script and click **Build & Visualize Model**.")

st.subheader("Model Summary")
if st.session_state.model_built:
    elems = st.session_state.elements if "elements" in st.session_state else st.session_state.elements_all
    st.write(f"**Nodes:** {len(st.session_state.nodes)}")
    st.write(f"**Elements (after filters):** {len(elems)}")
    if st.session_state.master_nodes:
        st.write(f"**Diaphragm Masters:** {len(st.session_state.master_nodes)}")
    # Show number of BC nodes (excluding masters)
    if st.session_state.supports_by_node:
        masters = set(st.session_state.master_nodes or [])
        bc_nodes = [n for n in st.session_state.supports_by_node.keys() if n not in masters]
        st.write(f"**Boundary-Conditioned Nodes (excluding masters):** {len(bc_nodes)}")
    if st.session_state.nodes and elems:
        summary = summarize_elements(st.session_state.nodes, elems)
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("Beams (X-dir)", summary["X"])
        with m2:
            st.metric("Beams (Y-dir)", summary["Y"])
        with m3:
            st.metric("Columns (Z-dir)", summary["Z"])
        with m4:
            st.metric("Other", summary["Other"])
else:
    st.write("—")

# -----------------------
# Enhanced Verification Features
# -----------------------
if st.session_state.model_built and VERIFICATION_AVAILABLE:
    st.markdown("---")
    st.header("🔬 Advanced Verification")

    # Create tabs for different verification types
    verification_tabs = st.tabs(["🔷 Geometric Validation", "🌊 Dynamic Analysis", "🏗️ Structural Integrity", "⚡ Quick Diagnostics"])

    with verification_tabs[0]:
        # Geometric Validation Tab
        st.subheader("🔷 Geometric Validation")
        st.markdown("Verify model geometry, connectivity, and joint offsets.")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("##### 🔧 Joint Offset Analysis")
            if st.button("Analyze Joint Offsets", key="analyze_offsets", use_container_width=True):
                with st.spinner("Analyzing joint offsets..."):
                    offset_results = verify_joint_offsets()

                    # Store results in session state
                    st.session_state.offset_verification = offset_results

        with col2:
            st.markdown("##### 🔗 Connectivity Check")
            if st.button("Check Connectivity", use_container_width=True, key="check_conn_geo"):
                with st.spinner("Loading model and checking connectivity..."):
                    try:
                        # Load explicit model first
                        explicit_path = os.path.join("out", "explicit_model.py")
                        if not os.path.exists(explicit_path):
                            st.error("Explicit model not found - ensure the model has been generated")
                        else:
                            # Load and build the model
                            spec = importlib.util.spec_from_file_location("model", explicit_path)
                            model_module = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(model_module)
                            model_module.build_model()

                            from openseespy.opensees import getNodeTags, getEleTags, eleNodes
                            node_tags = getNodeTags()
                            ele_tags = getEleTags()

                            # Check for disconnected nodes
                            connected_nodes = set()
                            for etag in ele_tags:
                                try:
                                    nodes = eleNodes(etag)
                                    connected_nodes.update(nodes)
                                except:
                                    pass

                            disconnected = len(node_tags) - len(connected_nodes)

                            if disconnected > 0:
                                st.warning(f"⚠️ {disconnected} nodes have no connections")
                            else:
                                st.success("✅ All nodes are connected")

                            st.info(f"Total: {len(node_tags)} nodes, {len(ele_tags)} elements")
                    except Exception as e:
                        st.error(f"Check failed: {e}")

        # Display results if available
        if hasattr(st.session_state, 'offset_verification'):
            results = st.session_state.offset_verification

            # Summary metrics
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                beam_pct = (results["beams"]["with_offsets"] / results["beams"]["total"] * 100) if results["beams"]["total"] > 0 else 0
                st.metric(
                    "Beams with Offsets",
                    f"{results['beams']['with_offsets']}/{results['beams']['total']}",
                    f"{beam_pct:.1f}%"
                )

            with col2:
                st.metric(
                    "Max Beam Offset",
                    f"{results['beams']['max_offset']:.3f} m"
                )

            with col3:
                col_pct = (results["columns"]["with_offsets"] / results["columns"]["total"] * 100) if results["columns"]["total"] > 0 else 0
                st.metric(
                    "Columns with Offsets",
                    f"{results['columns']['with_offsets']}/{results['columns']['total']}",
                    f"{col_pct:.1f}%"
                )

            with col4:
                st.metric(
                    "Max Column Offset",
                    f"{results['columns']['max_offset']:.3f} m"
                )

            # Validation status
            if results["validation"]["passed"]:
                st.success("✅ All joint offset validations passed")
            else:
                st.error("❌ Issues detected:")
                for issue in results["validation"]["issues"]:
                    st.warning(f"• {issue}")

            # Show details if elements with offsets exist
            if results["beams"]["details"] or results["columns"]["details"]:
                with st.expander("View Detailed Offset Information"):
                    if results["beams"]["details"]:
                        st.write("**Beams with significant offsets:**")
                        for beam in results["beams"]["details"][:5]:  # Show first 5
                            st.caption(f"Beam {beam['tag']} ({beam['line']}): Rigid ends = {beam['rigid_end_i']:.3f}m / {beam['rigid_end_j']:.3f}m")

                    if results["columns"]["details"]:
                        st.write("**Columns with significant offsets:**")
                        for col in results["columns"]["details"][:5]:  # Show first 5
                            st.caption(f"Column {col['tag']} ({col['line']}): Total offset = {col['magnitude']:.3f}m")

    with verification_tabs[1]:
        # Dynamic Analysis Tab
        st.subheader("🌊 Dynamic Analysis")
        st.markdown("Analyze modal properties and compare with ETABS results.")

        st.markdown("##### 📊 Modal Period Analysis")

        # Add warning and fix button for constraint issues
        if hasattr(st.session_state, 'modal_results') and st.session_state.modal_results:
            results = st.session_state.modal_results
            if results.get("success") and results.get("periods"):
                T1 = results["periods"][0] if results["periods"] else float('inf')
                if T1 > 100:  # Unrealistic period suggests constraint issues
                    st.error("⚠️ Detected unrealistic periods - likely constraint handler issue")
                    if st.button("🔧 Rebuild Model with Correct Constraints", key="fix_constraints"):
                        try:
                            # Force rebuild with explicit model
                            explicit_path = os.path.join("out", "explicit_model.py")
                            if os.path.exists(explicit_path):
                                from openseespy.opensees import wipe
                                wipe()

                                # Load and execute the corrected explicit model
                                spec = importlib.util.spec_from_file_location("corrected_model", explicit_path)
                                corrected_model = importlib.util.module_from_spec(spec)
                                spec.loader.exec_module(corrected_model)
                                corrected_model.build_model()

                                st.success("✅ Model rebuilt with correct constraints - try modal analysis again")
                                # Clear cached modal results
                                if hasattr(st.session_state, 'modal_results'):
                                    del st.session_state.modal_results
                            else:
                                st.error("Explicit model file not found")
                        except Exception as e:
                            st.error(f"Failed to rebuild model: {e}")

        col1, col2 = st.columns([2, 1])
        with col1:
            num_modes = st.slider("Number of modes", 3, 12, 6, key="num_modes")
        with col2:
            run_modal = st.button("Run Analysis", type="primary", key="run_modal")

        if run_modal:
            with st.spinner(f"Running eigenvalue analysis for {num_modes} modes..."):
                modal_results = run_modal_analysis(num_modes)
                st.session_state.modal_results = modal_results

        # Display results if available
        if hasattr(st.session_state, 'modal_results'):
            results = st.session_state.modal_results

            if results.get("success"):
                st.success("✅ Modal analysis completed")

                # Summary metrics
                col1, col2, col3 = st.columns(3)

                with col1:
                    if results["periods"] and results["periods"][0] < float('inf'):
                        st.metric("T₁ (Fundamental Period)", f"{results['periods'][0]:.3f} s")

                with col2:
                    if results["frequencies"] and results["frequencies"][0] > 0:
                        st.metric("f₁ (Fundamental Frequency)", f"{results['frequencies'][0]:.3f} Hz")

                with col3:
                    if len(results["periods"]) > 0:
                        st.metric("Modes Converged", len(results["periods"]))

                # Modal properties table
                if results["periods"]:
                    import pandas as pd
                    modal_df = pd.DataFrame({
                        "Mode": range(1, len(results["periods"]) + 1),
                        "Period (s)": [f"{p:.4f}" if p < float('inf') else "∞" for p in results["periods"]],
                        "Frequency (Hz)": [f"{f:.3f}" if f > 0 else "0" for f in results["frequencies"]]
                    })
                    st.dataframe(modal_df, hide_index=True, use_container_width=True)

                # Engineering checks
                if results["periods"] and results["periods"][0] < float('inf'):
                    T1 = results["periods"][0]
                    if 0.1 <= T1 <= 5.0:
                        st.info(f"ℹ️ Fundamental period T₁ = {T1:.3f}s is within typical range (0.1-5.0s)")
                    else:
                        st.warning(f"⚠️ Fundamental period T₁ = {T1:.3f}s is outside typical range")
            else:
                st.error(f"❌ Modal analysis failed: {results.get('error', 'Unknown error')}")
                st.info("Check that the model is properly constrained and has mass assigned")

    with verification_tabs[2]:
        # Structural Integrity Tab
        st.subheader("🏗️ Structural Integrity")
        st.markdown("Comprehensive validation of structural properties and ETABS consistency.")

        if STRUCTURAL_VALIDATION_AVAILABLE:
            st.markdown("""
            This comprehensive validation suite ensures the OpenSees model accurately
            represents the original ETABS model by checking:
            - **Geometric Fidelity**: Node/element counts, connectivity
            - **Mass Distribution**: Rigid diaphragm mass assignment
            - **Section Properties**: Beam and column properties
            - **Lateral Load Path**: Structural integrity under lateral loads
            - **Dynamic Properties**: Modal periods comparison
            """)

            # Configuration for ETABS periods
            with st.expander("⚙️ Configuration", expanded=False):
                st.subheader("Optional: ETABS Modal Periods")
                st.info("Enter ETABS modal periods for comparison (optional)")

                etabs_input = st.text_input(
                    "ETABS Periods (comma-separated, in seconds)",
                    placeholder="e.g., 0.245, 0.178, 0.156, 0.089, 0.067, 0.054",
                    help="Enter the modal periods from ETABS analysis for comparison",
                    key="etabs_periods_structural"
                )

                etabs_periods = None
                if etabs_input:
                    try:
                        etabs_periods = [float(x.strip()) for x in etabs_input.split(",")]
                        st.success(f"Loaded {len(etabs_periods)} ETABS periods for comparison")
                    except:
                        st.error("Invalid format - please enter comma-separated numbers")

            # Run validation button
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button("🔬 Run Structural Validation", type="primary", use_container_width=True, key="run_structural_validation_main"):
                    with st.spinner("Running comprehensive structural validation..."):
                        results = run_structural_validation(etabs_periods)

                        # Store results in session state
                        st.session_state.structural_validation_results = results
                        st.session_state.validation_timestamp = datetime.datetime.now()

            # Debug file generation
            st.markdown("---")
            st.markdown("##### 🔧 Debug Tools")

            # Check if explicit model exists
            explicit_exists = os.path.exists("out/explicit_model.py")

            if not explicit_exists:
                st.warning("⚠️ No explicit model found. Generate it first to enable debug file creation.")
                if st.button("🔨 Generate Explicit Model", use_container_width=True, key="gen_explicit_main", help="Creates explicit_model.py from current artifacts"):
                    with st.spinner("Generating explicit model..."):
                        try:
                            from structural_validation_app import generate_explicit_model_file
                            success = generate_explicit_model_file()
                            if success:
                                st.success("✅ Explicit model generated successfully!")
                                st.rerun()
                            else:
                                st.error("❌ Failed to generate explicit model. Ensure model artifacts exist.")
                        except ImportError:
                            st.error("Explicit model generation not available")

            if explicit_exists and st.button("📄 Generate Lateral Load Debug File", use_container_width=True, key="gen_debug_main", help="Creates standalone Python file for debugging"):
                try:
                    from structural_validation_app import generate_lateral_load_debug_file
                    debug_content = generate_lateral_load_debug_file(etabs_periods)
                    if debug_content:
                        st.success("Debug file generated successfully!")
                        st.download_button(
                            label="📥 Download lateral_load_debug.py",
                            data=debug_content,
                            file_name="lateral_load_debug.py",
                            mime="text/x-python",
                            key="download_debug_main"
                        )
                    else:
                        st.error("Failed to generate debug file")
                except ImportError:
                    st.error("Debug file generation not available")

            # Display results if available
            if hasattr(st.session_state, 'structural_validation_results'):
                st.divider()

                # Show timestamp
                if hasattr(st.session_state, 'validation_timestamp'):
                    st.caption(f"Last run: {st.session_state.validation_timestamp.strftime('%Y-%m-%d %H:%M:%S')}")

                # Display results using the imported function
                display_validation_results(st.session_state.structural_validation_results)
        else:
            st.warning("⚠️ Structural validation module not available. Please ensure structural_validation.py and structural_validation_app.py are present.")

    # Quick Diagnostics Tab
    with verification_tabs[3]:
        st.subheader("⚡ Quick Diagnostics")
        st.markdown("Fast checks for mass assignment, transforms, and basic model diagnostics.")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("##### 📊 Mass Assignment Check")
            if st.button("Check Mass Assignment", use_container_width=True, key="check_mass_diag"):
                with st.spinner("Loading model and checking mass assignment..."):
                    # Check mass assignment in the model
                    try:
                        from model_verification_app import check_mass_assignment
                        mass_results = check_mass_assignment()

                        if "error" in mass_results:
                            st.error(f"Check failed: {mass_results['error']}")
                        else:
                            if mass_results["success"]:
                                st.success(f"✅ Mass at {mass_results['nodes_with_mass']} nodes")
                                st.info(f"Total mass: {mass_results['total_mass']:.1f} kg")

                                # Show mass by elevation
                                if "mass_by_elevation" in mass_results:
                                    with st.expander("Mass Distribution by Elevation"):
                                        for z, data in sorted(mass_results["mass_by_elevation"].items()):
                                            st.caption(f"Z={z:.3f}m: {data['count']} nodes, {data['total_mass']:.1f} kg")
                            else:
                                st.error("❌ Mass assignment issues:")
                                for issue in mass_results["issues"]:
                                    st.warning(f"• {issue}")

                    except Exception as e:
                        st.error(f"Check failed: {e}")

        with col2:
            st.markdown("##### 🔧 Transform Verification")
            if st.button("Verify Transforms", use_container_width=True, key="check_trans_diag"):
                # Check if all elements have valid transforms
                try:
                    beams_data = load_json_artifact("beams.json") if 'load_json_artifact' in dir() else {}
                    columns_data = load_json_artifact("columns.json") if 'load_json_artifact' in dir() else {}

                    total_elements = len(beams_data.get("beams", [])) + len(columns_data.get("columns", []))

                    if total_elements > 0:
                        st.success(f"✅ {total_elements} elements with transforms")
                    else:
                        st.warning("No element data found")

                except Exception as e:
                    st.error(f"Check failed: {e}")

        # Detailed diagnostics in full width
        st.markdown("##### 🔍 Comprehensive Diagnostics")
        if st.button("Run Detailed Diagnostics", use_container_width=True, key="run_diagnostics_main"):
            # Run comprehensive model diagnostics
            st.info("📋 Running comprehensive model diagnostics...")

            # Check basic model info
            try:
                from openseespy.opensees import getNodeTags, getEleTags
                nodes = len(getNodeTags())
                elements = len(getEleTags())

                st.success(f"✅ Model: {nodes} nodes, {elements} elements")

                # Check constraints
                diaphragm_file = os.path.join("out", "diaphragms.json")
                if os.path.exists(diaphragm_file):
                    with open(diaphragm_file, 'r') as f:
                        d_data = json.load(f)
                        num_diaphragms = len(d_data.get("diaphragms", []))
                        if num_diaphragms > 0:
                            st.info(f"ℹ️ {num_diaphragms} rigid diaphragms detected")
                            st.warning("⚠️ Ensure constraints('Transformation') is set for modal analysis")

                # Check supports
                supports_file = os.path.join("out", "supports.json")
                if os.path.exists(supports_file):
                    with open(supports_file, 'r') as f:
                        s_data = json.load(f)
                        num_supports = len(s_data.get("applied", []))
                        st.success(f"✅ {num_supports} boundary conditions applied")

            except Exception as e:
                st.error(f"Diagnostics failed: {e}")

def load_json_artifact(filename: str):
    """Helper to load JSON artifacts"""
    import json
    filepath = os.path.join("out", filename)
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return json.load(f)
    return {}
