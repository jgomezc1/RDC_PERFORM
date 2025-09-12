# ARTIFACTS — Vibecoding Quick Samples

This document provides **small, copy‑pasteable samples** of each JSON artifact emitted by *My_Perform3D*.
Use it during AI vibecoding sessions to ground responses in the **current schema and shape** of the data.

> **Source of truth**: the real files in `out/` (or this session's uploads). These samples are **truncated** for readability.
> Always treat **tags** and **node references** as contracts across artifacts.

## Invariants (must hold)
- Every `i_node`/`j_node` referenced in `beams.json` and `columns.json` **exists** in `nodes.json`.
- All `tag` values across `nodes.json` are **unique**.
- Any diaphragm `master` and `slaves` are existing node tags from `nodes.json`.
- `supports.json.applied[].node` refers to an existing node tag.
- Segment semantics in `beams.json` / `columns.json`: `rigid_i` → `deformable` → `rigid_j` when rigid offsets are present.
- Transform tags (`transf_tag`) referenced in elements are defined where required in the pipeline.

---
## story_graph.json

Top-to-bottom story order, elevations, and per-story active points (subset).

```json
{
  "story_order_top_to_bottom": [
    "11_P6",
    "08_P5",
    "07_P5_m155"
  ],
  "story_elev": {
    "11_P6": 14.775000000000002,
    "08_P5": 13.300000000000002,
    "07_P5_m155": 11.750000000000002
  },
  "active_points": {
    "11_P6": [
      {
        "id": "34",
        "x": 45.55,
        "y": 27.45,
        "z": 14.775000000000002,
        "explicit_z": false,
        "diaphragm": "D1",
        "springprop": null
      },
      {
        "id": "795",
        "x": 53.3,
        "y": 20.75,
        "z": 14.775000000000002,
        "explicit_z": false,
        "diaphragm": "D1",
        "springprop": null
      },
      {
        "id": "827",
        "x": 53.05,
        "y": 27.45,
        "z": 14.775000000000002,
        "explicit_z": false,
        "diaphragm": "D1",
        "springprop": null
      },
      {
        "id": "847",
        "x": 69.95,
        "y": 27.45,
        "z": 14.775000000000002,
        "explicit_z": false,
        "diaphragm": "D1",
        "springprop": null
      },
      {
        "id": "20",
        "x": 61.0,
        "y": 11.0,
        "z": 14.775000000000002,
        "explicit_z": false,
        "diaphragm": "D1",
        "springprop": null
      }
    ]
  }
}
```

## nodes.json

`nodes[]` registry with coordinates, story, and kind. (First 10 entries).

```json
{
  "nodes": [
    {
      "tag": 1,
      "x": 60.99065201754386,
      "y": 20.960964912280705,
      "z": 14.775000000000002,
      "story": "11_P6",
      "story_index": 0,
      "kind": "diaphragm_master"
    },
    {
      "tag": 2,
      "x": 59.4406245631068,
      "y": 22.26067961165048,
      "z": 13.300000000000002,
      "story": "08_P5",
      "story_index": 1,
      "kind": "diaphragm_master"
    },
    {
      "tag": 3,
      "x": 62.04204545454548,
      "y": 13.297727272727274,
      "z": 11.750000000000002,
      "story": "07_P5_m155",
      "story_index": 2,
      "kind": "diaphragm_master"
    },
    {
      "tag": 4,
      "x": 59.4406245631068,
      "y": 22.26067961165048,
      "z": 10.200000000000001,
      "story": "04_P4",
      "story_index": 3,
      "kind": "diaphragm_master"
    },
    {
      "tag": 5,
      "x": 62.04204545454548,
      "y": 13.297727272727274,
      "z": 8.65,
      "story": "05_P4_m155",
      "story_index": 4,
      "kind": "diaphragm_master"
    },
    {
      "tag": 6,
      "x": 59.4406245631068,
      "y": 22.26067961165048,
      "z": 7.1000000000000005,
      "story": "04_P3",
      "story_index": 5,
      "kind": "diaphragm_master"
    },
    {
      "tag": 7,
      "x": 62.04204545454548,
      "y": 13.297727272727274,
      "z": 5.4,
      "story": "03_P3_m170",
      "story_index": 6,
      "kind": "diaphragm_master"
    },
    {
      "tag": 8,
      "x": 58.184068804347866,
      "y": 22.314673913043475,
      "z": 3.7,
      "story": "02_P2",
      "story_index": 7,
      "kind": "diaphragm_master"
    },
    {
      "tag": 9,
      "x": 62.04204545454548,
      "y": 13.297727272727274,
      "z": 2.0,
      "story": "01_P2_m170",
      "story_index": 8,
      "kind": "diaphragm_master"
    },
    {
      "tag": 12000,
      "x": 53.09851,
      "y": 26.15,
      "z": 14.775000000000002,
      "story": "11_P6",
      "story_index": 0,
      "kind": "grid",
      "source_point_id": "12"
    }
  ]
}
```

## diaphragms.json

One diaphragm record with truncated `slaves[]` list.

```json
{
  "diaphragms": [
    {
      "story": "11_P6",
      "master": 1,
      "slaves": [
        12000,
        14000,
        15000,
        16000,
        17000,
        18000,
        20000,
        34000,
        36000,
        37000,
        38000,
        39000
      ],
      "mass": {
        "M": 81515.31250000001,
        "Izz": 8151531.250000002,
        "A": 326.0612500000001,
        "t": 0.1,
        "rho": 2500.0,
        "applied": true
      },
      "fix": {
        "ux": 0,
        "uy": 0,
        "uz": 1,
        "rx": 1,
        "ry": 1,
        "rz": 0,
        "applied": true
      }
    }
  ]
}
```

## beams.json

Beam **segments** after rigid-end splitting when present. (First 5 entries).

```json
{
  "beams": [
    {
      "tag": 871107618,
      "segment": "rigid_i",
      "parent_line": "B408",
      "story": "11_P6",
      "line": "B408",
      "i_node": 792000,
      "j_node": 1547118906,
      "i_coords": [
        68.8,
        27.45,
        14.775000000000002
      ],
      "j_coords": null,
      "section": "V40X55",
      "transf_tag": 1871107618,
      "A": 200000.0,
      "E": 25000000000.0,
      "G": 10416666666.666668,
      "J": 16666.666666666668,
      "Iy": 4166.666666666667,
      "Iz": 2666.6666666666674,
      "length_off_i": 0.4,
      "length_off_j": 0.0
    },
    {
      "tag": 565314628,
      "segment": "deformable",
      "parent_line": "B408",
      "story": "11_P6",
      "line": "B408",
      "i_node": 1547118906,
      "j_node": 847000,
      "i_coords": [
        68.8,
        27.45,
        14.775000000000002
      ],
      "j_coords": [
        69.95,
        27.45,
        14.775000000000002
      ],
      "section": "V40X55",
      "transf_tag": 1565314628,
      "A": 0.2,
      "E": 25000000000.0,
      "G": 10416666666.666668,
      "J": 0.016666666666666666,
      "Iy": 0.004166666666666667,
      "Iz": 0.0026666666666666674,
      "length_off_i": 0.4,
      "length_off_j": 0.0
    },
    {
      "tag": 735417077,
      "segment": "rigid_i",
      "parent_line": "B409",
      "story": "11_P6",
      "line": "B409",
      "i_node": 786000,
      "j_node": 1606501140,
      "i_coords": [
        68.8,
        20.75,
        14.775000000000002
      ],
      "j_coords": null,
      "section": "V40X55",
      "transf_tag": 1735417077,
      "A": 200000.0,
      "E": 25000000000.0,
      "G": 10416666666.666668,
      "J": 16666.666666666668,
      "Iy": 4166.666666666667,
      "Iz": 2666.6666666666674,
      "length_off_i": 0.2,
      "length_off_j": 0.0
    },
    {
      "tag": 125218473,
      "segment": "deformable",
      "parent_line": "B409",
      "story": "11_P6",
      "line": "B409",
      "i_node": 1606501140,
      "j_node": 851000,
      "i_coords": [
        68.8,
        20.75,
        14.775000000000002
      ],
      "j_coords": [
        69.95,
        20.75,
        14.775000000000002
      ],
      "section": "V40X55",
      "transf_tag": 1125218473,
      "A": 0.2,
      "E": 25000000000.0,
      "G": 10416666666.666668,
      "J": 0.016666666666666666,
      "Iy": 0.004166666666666667,
      "Iz": 0.0026666666666666674,
      "length_off_i": 0.2,
      "length_off_j": 0.0
    },
    {
      "tag": 731822639,
      "segment": "rigid_i",
      "parent_line": "B410",
      "story": "11_P6",
      "line": "B410",
      "i_node": 780000,
      "j_node": 2025550686,
      "i_coords": [
        68.8,
        16.175,
        14.775000000000002
      ],
      "j_coords": null,
      "section": "V40X55",
      "transf_tag": 1731822639,
      "A": 200000.0,
      "E": 25000000000.0,
      "G": 10416666666.666668,
      "J": 16666.666666666668,
      "Iy": 4166.666666666667,
      "Iz": 2666.6666666666674,
      "length_off_i": 0.2,
      "length_off_j": 0.0
    }
  ]
}
```

## columns.json

Column **segments** after rigid-end splitting when present. (First 5 entries).

```json
{
  "columns": [
    {
      "tag": 342376417,
      "segment": "rigid_i",
      "parent_line": "C1032",
      "story": "11_P6",
      "i_node": 20002,
      "j_node": 1860458314,
      "section": "C50x80C",
      "transf_tag": 1442376417,
      "A": 160000.00000000003,
      "E": 25000000000.0,
      "G": 10416666666.666668,
      "J": 8533.333333333336,
      "Iy": 2133.333333333334,
      "Iz": 2133.333333333334,
      "length_off_i": 0.275,
      "length_off_j": 0.275
    },
    {
      "tag": 105534426,
      "segment": "deformable",
      "parent_line": "C1032",
      "story": "11_P6",
      "i_node": 1860458314,
      "j_node": 1851532825,
      "section": "C50x80C",
      "transf_tag": 1205534426,
      "A": 0.16000000000000003,
      "E": 25000000000.0,
      "G": 10416666666.666668,
      "J": 0.008533333333333335,
      "Iy": 0.002133333333333334,
      "Iz": 0.002133333333333334,
      "length_off_i": 0.275,
      "length_off_j": 0.275
    },
    {
      "tag": 461407362,
      "segment": "rigid_j",
      "parent_line": "C1032",
      "story": "11_P6",
      "i_node": 1851532825,
      "j_node": 20000,
      "section": "C50x80C",
      "transf_tag": 1561407362,
      "A": 160000.00000000003,
      "E": 25000000000.0,
      "G": 10416666666.666668,
      "J": 8533.333333333336,
      "Iy": 2133.333333333334,
      "Iz": 2133.333333333334,
      "length_off_i": 0.275,
      "length_off_j": 0.275
    },
    {
      "tag": 192174111,
      "segment": "rigid_i",
      "parent_line": "C44",
      "story": "11_P6",
      "i_node": 40001,
      "j_node": 1705001494,
      "section": "C50x80C",
      "transf_tag": 1292174111,
      "A": 160000.00000000003,
      "E": 25000000000.0,
      "G": 10416666666.666668,
      "J": 8533.333333333336,
      "Iy": 2133.333333333334,
      "Iz": 2133.333333333334,
      "length_off_i": 0.275,
      "length_off_j": 0.275
    },
    {
      "tag": 230283439,
      "segment": "deformable",
      "parent_line": "C44",
      "story": "11_P6",
      "i_node": 1705001494,
      "j_node": 1931490505,
      "section": "C50x80C",
      "transf_tag": 1330283439,
      "A": 0.16000000000000003,
      "E": 25000000000.0,
      "G": 10416666666.666668,
      "J": 0.008533333333333335,
      "Iy": 0.002133333333333334,
      "Iz": 0.002133333333333334,
      "length_off_i": 0.275,
      "length_off_j": 0.275
    }
  ]
}
```

## supports.json

Boundary condition masks per node (1=fixed, 0=free). (First 10 entries).

```json
{
  "version": 1,
  "applied": [
    {
      "node": 36009,
      "mask": [
        1,
        1,
        1,
        1,
        1,
        1
      ]
    },
    {
      "node": 795009,
      "mask": [
        1,
        1,
        1,
        1,
        1,
        1
      ]
    },
    {
      "node": 794009,
      "mask": [
        1,
        1,
        1,
        1,
        1,
        1
      ]
    },
    {
      "node": 34009,
      "mask": [
        1,
        1,
        1,
        1,
        1,
        1
      ]
    },
    {
      "node": 827009,
      "mask": [
        1,
        1,
        1,
        1,
        1,
        1
      ]
    },
    {
      "node": 791009,
      "mask": [
        1,
        1,
        1,
        1,
        1,
        1
      ]
    },
    {
      "node": 56009,
      "mask": [
        1,
        1,
        1,
        1,
        1,
        1
      ]
    },
    {
      "node": 15009,
      "mask": [
        1,
        1,
        1,
        1,
        1,
        1
      ]
    },
    {
      "node": 1384009,
      "mask": [
        1,
        1,
        1,
        1,
        1,
        1
      ]
    },
    {
      "node": 792009,
      "mask": [
        1,
        1,
        1,
        1,
        1,
        1
      ]
    }
  ]
}
```

## _intermediate_nodes.json

Interface nodes created at rigid-end split boundaries. (First 10 entries).

```json
{
  "nodes": [
    {
      "tag": 1860458314,
      "x": 61.0,
      "y": 11.0,
      "z": 12.025000000000002,
      "story": "07_P5_m155",
      "story_index": 2,
      "kind": "rigid_interface",
      "source": "interface(20002,20000,I)"
    },
    {
      "tag": 1851532825,
      "x": 61.0,
      "y": 11.0,
      "z": 14.500000000000002,
      "story": "11_P6",
      "story_index": 0,
      "kind": "rigid_interface",
      "source": "interface(20002,20000,J)"
    },
    {
      "tag": 1705001494,
      "x": 61.0,
      "y": 16.175,
      "z": 13.575000000000003,
      "story": "08_P5",
      "story_index": 1,
      "kind": "rigid_interface",
      "source": "interface(40001,40000,I)"
    },
    {
      "tag": 1931490505,
      "x": 61.0,
      "y": 16.175,
      "z": 14.500000000000002,
      "story": "11_P6",
      "story_index": 0,
      "kind": "rigid_interface",
      "source": "interface(40001,40000,J)"
    },
    {
      "tag": 1857118050,
      "x": 61.0,
      "y": 20.75,
      "z": 13.575000000000003,
      "story": "08_P5",
      "story_index": 1,
      "kind": "rigid_interface",
      "source": "interface(41001,41000,I)"
    },
    {
      "tag": 1539421479,
      "x": 61.0,
      "y": 20.75,
      "z": 14.500000000000002,
      "story": "11_P6",
      "story_index": 0,
      "kind": "rigid_interface",
      "source": "interface(41001,41000,J)"
    },
    {
      "tag": 1679980716,
      "x": 68.8,
      "y": 16.175,
      "z": 13.575000000000003,
      "story": "08_P5",
      "story_index": 1,
      "kind": "rigid_interface",
      "source": "interface(780001,780000,I)"
    },
    {
      "tag": 1775962271,
      "x": 68.8,
      "y": 16.175,
      "z": 14.500000000000002,
      "story": "11_P6",
      "story_index": 0,
      "kind": "rigid_interface",
      "source": "interface(780001,780000,J)"
    },
    {
      "tag": 1900135920,
      "x": 68.8,
      "y": 20.75,
      "z": 13.575000000000003,
      "story": "08_P5",
      "story_index": 1,
      "kind": "rigid_interface",
      "source": "interface(786001,786000,I)"
    },
    {
      "tag": 2095455861,
      "x": 68.8,
      "y": 20.75,
      "z": 14.500000000000002,
      "story": "11_P6",
      "story_index": 0,
      "kind": "rigid_interface",
      "source": "interface(786001,786000,J)"
    }
  ]
}
```

## parsed_raw.json

Raw ETABS-derived structures used by the parser (subset of `stories` and `points`).

```json
{
  "stories": [
    {
      "name": "11_P6",
      "height": 1.475,
      "elev": null,
      "similar_to": null,
      "masterstory": null
    },
    {
      "name": "08_P5",
      "height": 1.55,
      "elev": null,
      "similar_to": "04_P3",
      "masterstory": null
    },
    {
      "name": "07_P5_m155",
      "height": 1.55,
      "elev": null,
      "similar_to": "03_P3_m170",
      "masterstory": null
    }
  ],
  "points": {
    "221": {
      "x": 46.9,
      "y": 27.45,
      "third": null,
      "has_three": false
    },
    "225": {
      "x": 47.95,
      "y": 27.45,
      "third": null,
      "has_three": false
    },
    "229": {
      "x": 49.0,
      "y": 27.45,
      "third": null,
      "has_three": false
    },
    "233": {
      "x": 50.05,
      "y": 27.45,
      "third": null,
      "has_three": false
    },
    "237": {
      "x": 51.1,
      "y": 27.45,
      "third": null,
      "has_three": false
    }
  }
}
```
