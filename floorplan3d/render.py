"""Render house.glb with Blender.

Usage (any OS, with Blender installed):
    blender -b -P render.py -- <out_dir> [samples]
or, on Python 3.11 with `pip install bpy`:
    python render.py <out_dir> [samples]
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
out = Path(args[0]).resolve()
samples = int(args[1]) if len(args) > 1 else 64

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(out / "house.glb"))

MATS = {  # name: (base color, roughness, extra)
    "wall": ((0.93, 0.90, 0.84), 0.85, {}), "column": ((0.93, 0.90, 0.84), 0.85, {}),
    "slab": ((0.88, 0.86, 0.82), 0.8, {}), "roof": ((0.62, 0.25, 0.15), 0.7, {}),
    "fascia": ((0.30, 0.18, 0.10), 0.6, {}), "platform": ((0.78, 0.75, 0.70), 0.9, {}),
    "stairs": ((0.78, 0.75, 0.70), 0.9, {}), "floor": ((0.72, 0.56, 0.38), 0.5, {}),
    "glass": ((0.75, 0.88, 0.95), 0.03, {"Transmission Weight": 1.0, "IOR": 1.45}),
    "frame": ((0.08, 0.08, 0.09), 0.4, {}), "door": ((0.50, 0.32, 0.18), 0.5, {}),
    "railing": ((0.06, 0.06, 0.06), 0.35, {"Metallic": 0.8}),
    "ground": ((0.42, 0.55, 0.30), 1.0, {}), "bed": ((0.92, 0.92, 0.95), 0.9, {}),
    "sofa": ((0.45, 0.52, 0.60), 0.9, {}), "wood": ((0.55, 0.38, 0.24), 0.55, {}),
    "sanitary": ((0.97, 0.97, 0.97), 0.15, {}), "counter": ((0.15, 0.15, 0.16), 0.4, {}),
}
objs = {}
for ob in bpy.context.scene.objects:
    if ob.type != "MESH":
        continue
    key = ob.name.split(".")[0]
    objs[key] = ob
    col, rough, extra = MATS.get(key, ((0.8, 0.8, 0.8), 0.8, {}))
    m = bpy.data.materials.new(key)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*(c ** 2.2 for c in col), 1)  # sRGB -> linear
    bsdf.inputs["Roughness"].default_value = rough
    for k, v in extra.items():
        bsdf.inputs[k].default_value = v
    ob.data.materials.clear()
    ob.data.materials.append(m)
    for p in ob.data.polygons:
        p.use_smooth = False

scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = samples
scene.cycles.use_denoising = True
scene.render.resolution_x, scene.render.resolution_y = 1600, 1000
scene.view_settings.view_transform = "AgX"
scene.view_settings.look = "AgX - Medium High Contrast"
scene.view_settings.exposure = -0.3

world = bpy.data.worlds.new("w")
scene.world = world
world.use_nodes = True
nt = world.node_tree
sky = nt.nodes.new("ShaderNodeTexSky")
try:
    sky.sky_type = "NISHITA"
except TypeError:
    pass
sky.sun_elevation = math.radians(35)
sky.sun_rotation = math.radians(210)
bg = nt.nodes["Background"]
bg.inputs["Strength"].default_value = 0.12
nt.links.new(sky.outputs["Color"], bg.inputs["Color"])

sun_data = bpy.data.lights.new("sun", "SUN")
sun_data.energy = 2.6
sun_data.angle = math.radians(1.5)
sun = bpy.data.objects.new("sun", sun_data)
scene.collection.objects.link(sun)
sun.rotation_euler = (math.radians(50), 0, math.radians(210))

cam_data = bpy.data.cameras.new("cam")
cam = bpy.data.objects.new("cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam


def shoot(name, loc, target, lens=28, hide=()):
    for k in hide:
        if k in objs:
            objs[k].hide_render = True
    cam.location = Vector(loc)
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    cam_data.lens = lens
    scene.render.filepath = str(out / f"{name}.png")
    bpy.ops.render.render(write_still=True)
    for k in hide:
        if k in objs:
            objs[k].hide_render = False
    print("rendered", name)


# Glb is Y-up -> Blender imports as Z-up; plan north = +Y, south (entrance) = -Y.
shoot("render_front_southwest", (-14, -19, 5.5), (0, -1, 2.2), lens=30)
shoot("render_veranda_northwest", (-15, 17, 4.5), (-1, 3, 1.8), lens=30)
shoot("render_aerial_southeast", (17, -20, 15), (0, 0, 2), lens=32)
shoot("render_interior_cutaway", (9, -15, 22), (0, 0.5, 0), lens=34, hide=("roof", "slab", "fascia"))
