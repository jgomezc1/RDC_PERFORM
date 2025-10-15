# Glossary

**Story Index** — 0 at top story; increases downward. Encoded in node tag (`tag % 1000`).
**Active Points/Lines** — The points/lines present on a story slice after ETABS parsing.
**Rigid Diaphragm** — MPC tying all story nodes to a master node (free in-plane DOF, fixed out-of-plane).
**Rigid End Zone** — ETABS longitudinal offsets (`LENGTHOFFI/J`) handled via OpenSees `geomTransf -jntOffset` parameter, allowing exact rigid behavior without element splitting.
**Explicit Model** — `out/explicit_model.py` built from artifacts, runnable without ETABS.
