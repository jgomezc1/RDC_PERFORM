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
from typing import Dict, Tuple, List, Any
from openseespy.opensees import (
    wipe, getNodeTags, nodeCoord, getEleTags, eleNodes
)

APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)
try:
    os.chdir(APP_DIR)
except Exception:
    pass

# Plotting utilities
import view_utils_App as vu

# Model testing framework
try:
    from opensees_model_tests import OpenSeesModelTester
    TESTING_AVAILABLE = True
except ImportError:
    TESTING_AVAILABLE = False


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

def load_story_meta(path: str = os.path.join(APP_DIR, "out", "story_graph.json")):
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

def load_diaphragms_meta(path: str = os.path.join(APP_DIR, "out", "diaphragms.json")) -> List[int]:
    """Return list of diaphragm master-node tags if file exists, else []."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        masters = [int(rec["master"]) for rec in data.get("diaphragms", []) if "master" in rec]
        return masters
    except Exception:
        return []

def load_supports_meta(path: str = os.path.join(APP_DIR, "out", "supports.json")) -> Dict[int, Tuple[int, int, int, int, int, int]]:
    """
    Return {node_tag: (UX, UY, UZ, RX, RY, RZ)} from out/supports.json if present.
    If missing/invalid, returns {}.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        out: Dict[int, Tuple[int, int, int, int, int, int]] = {}
        for rec in data.get("applied", []):
            n = int(rec.get("node"))
            mask = tuple(int(v) for v in rec.get("mask", []))
            if len(mask) == 6:
                out[n] = mask  # type: ignore[assignment]
        return out
    except Exception:
        return {}

def run_model_tests(test_categories: List[str]) -> Dict[str, Any]:
    """Run selected model test categories and return results."""
    if not TESTING_AVAILABLE:
        return {}

    try:
        tester = OpenSeesModelTester()

        # Map category names to test methods
        category_map = {
            "Model Integrity": tester.test_model_integrity,
            "Geometric Validation": tester.test_geometric_validation,
            "Structural Validation": tester.test_structural_validation,
            "ETABS Consistency": tester.test_etabs_consistency
        }

        results = {}
        for category in test_categories:
            if category in category_map:
                with st.spinner(f"Running {category} tests..."):
                    results[category.lower().replace(" ", "_")] = category_map[category]()

        return results
    except Exception as e:
        st.error(f"Error running tests: {str(e)}")
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

    # NEW: Model Testing Controls
    st.markdown("---")
    st.subheader("Model Testing")
    if not TESTING_AVAILABLE:
        st.warning("⚠️ Model testing framework not available (OpenSeesPy import issue)")
        enable_testing = False
        test_categories = []
    else:
        enable_testing = st.checkbox("Enable model validation tests", value=True)
        if enable_testing:
            test_categories = st.multiselect(
                "Select test categories to run",
                options=["Model Integrity", "Geometric Validation", "Structural Validation", "ETABS Consistency"],
                default=["Model Integrity", "Geometric Validation"],
                help="Choose which test suites to run after model build"
            )
        else:
            test_categories = []

    st.caption("Tip: build in stages and filter the view to diagnose issues.")

    build_btn = st.button("Build & Visualize Model", use_container_width=True, type="primary")

# -----------------------
# Build & visualize
# -----------------------
if build_btn:
    if not uploaded_file:
        st.error("Please upload a Python model file first.")
    else:
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".py") as tmp:
                tmp.write(uploaded_file.getvalue())
                model_script_path = tmp.name

            wipe()
            user_model_module = load_module_from_path("user_model", model_script_path)
            user_model_module.build_model(stage=stage_param)

            nodes = collect_nodes()
            all_elements = collect_elements()

            elements = filter_elements_by_orientation(nodes, all_elements, view_param)

            # Load master nodes metadata written by diaphragms.py (if present)
            master_nodes = load_diaphragms_meta()

            # Load BC metadata (supports) if present
            supports_by_node = load_supports_meta()

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

            # Run model tests if enabled
            if enable_testing and test_categories and TESTING_AVAILABLE:
                st.session_state.test_results = run_model_tests(test_categories)
            else:
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
# Model Test Results
# -----------------------
if hasattr(st.session_state, 'test_results') and st.session_state.test_results:
    st.subheader("🧪 Model Validation Results")

    # Calculate overall statistics
    all_suites = st.session_state.test_results.values()
    total_tests = sum(suite.total_tests for suite in all_suites)
    total_passed = sum(suite.passed_tests for suite in all_suites)
    overall_success = (total_passed / total_tests * 100) if total_tests > 0 else 0

    # Overall summary
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Tests", total_tests)
    with col2:
        st.metric("Passed", total_passed, delta=f"{overall_success:.1f}%")
    with col3:
        st.metric("Failed", total_tests - total_passed)

    # Test suite results
    for suite_key, suite in st.session_state.test_results.items():
        with st.expander(f"{suite.name} ({suite.passed_tests}/{suite.total_tests} passed)",
                        expanded=(suite.failed_tests > 0)):  # Expand if there are failures

            # Suite summary
            if suite.success_rate == 100:
                st.success(f"✅ All {suite.total_tests} tests passed!")
            elif suite.success_rate >= 80:
                st.warning(f"⚠️ {suite.passed_tests}/{suite.total_tests} tests passed ({suite.success_rate:.1f}%)")
            else:
                st.error(f"❌ Only {suite.passed_tests}/{suite.total_tests} tests passed ({suite.success_rate:.1f}%)")

            # Individual test results
            for result in suite.results:
                if result.passed:
                    st.success(f"✅ **{result.name}**: {result.message}")
                else:
                    if result.severity == "CRITICAL":
                        st.error(f"🚨 **{result.name}**: {result.message}")
                    elif result.severity == "ERROR":
                        st.error(f"❌ **{result.name}**: {result.message}")
                    elif result.severity == "WARNING":
                        st.warning(f"⚠️ **{result.name}**: {result.message}")
                    else:
                        st.info(f"ℹ️ **{result.name}**: {result.message}")

                # Show details if available
                if result.details:
                    st.caption("📋 Details:")
                    st.json(result.details)

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
