# Floor plan → 3D model

3D model and renders made from the ground-floor plan in the project DXF
(113751 Ada 28 Parsel), using the heights from the section sheet.

## Output (`output/`)
| File | What it is |
|---|---|
| `house.glb` | 3D model. Opens in Blender, Windows 3D Viewer, https://gltf-viewer.donmccurdy.com |
| `house.obj` | Same model as OBJ (FreeCAD, SketchUp, 3ds Max…) |
| `render_front_southwest.png` | Entrance side |
| `render_veranda_northwest.png` | Covered veranda |
| `render_aerial_southeast.png` | Aerial view |
| `render_interior_cutaway.png` | Roof removed, rooms and furniture |
| `freecad_parts/` | One OBJ per material, used by `freecad_import.FCMacro` |
| `model_info.json` | Key dimensions |

## What was taken from the drawing
- Walls: layer `DUVAR`. Columns: `KOLON`.
- Doors and windows: found from the gaps between wall ends, sized from the `K:…/210` and `P:…/…` labels.
- Stairs: `MERDİVEN M`. Furniture: the bed, sofa, chair and sanitary blocks.
- Heights (from KESİTLER): ground ±0.00, floor +0.60, window head +2.80, eave +3.50,
  hip roof with 40 % slope and 90 cm overhang (ridge ≈ +6.05).

## Open it in FreeCAD
1. In FreeCAD: **Macro → Macros…**, set *User macros location* to this `floorplan3d` folder.
2. Select `freecad_import.FCMacro` and click **Execute**.
3. The house loads as coloured parts (walls, roof, glass, furniture…) and is saved as
   `output/house.FCStd`. Hide the `Roof` and `Slab` objects (Space bar) to look inside.

For pictures from FreeCAD: **Tools → Save picture…**.
You can also just **File → Import** `output/house.obj` (single grey mesh).

## Rebuild from the DXF
```
pip install ezdxf shapely trimesh mapbox_earcut numpy scipy
python build_model.py plan.dxf output
```
This regenerates `house.glb`, `house.obj` and `output/freecad_parts/` (used by the FreeCAD macro).

Optional, only for new rendered images: install Blender 4.2+ and run
`blender -b -P render.py -- output 96`.
