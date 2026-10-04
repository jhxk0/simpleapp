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
1. Build the 3D model (any Python 3.9+):
   ```
   pip install ezdxf shapely trimesh mapbox_earcut numpy
   python build_model.py plan.dxf output
   ```
2. Render the images with Blender 4.2 or newer (https://www.blender.org/download/):
   ```
   blender -b -P render.py -- output 96
   ```
   On Windows, if `blender` isn't on your PATH, use the full path, e.g.
   `"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe" -b -P render.py -- output 96`.
   (`pip install bpy` only works on Python 3.11, so running inside Blender is simpler.)
