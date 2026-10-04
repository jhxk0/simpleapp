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
| `model_info.json` | Key dimensions |

## What was taken from the drawing
- Walls: layer `DUVAR`. Columns: `KOLON`.
- Doors and windows: found from the gaps between wall ends, sized from the `K:…/210` and `P:…/…` labels.
- Stairs: `MERDİVEN M`. Furniture: the bed, sofa, chair and sanitary blocks.
- Heights (from KESİTLER): ground ±0.00, floor +0.60, window head +2.80, eave +3.50,
  hip roof with 40 % slope and 90 cm overhang (ridge ≈ +6.05).

## Rebuild
```
pip install ezdxf shapely trimesh mapbox_earcut scipy bpy
python3 build_model.py plan.dxf output
python3 render.py output 96
```
