"""Speed-run video of the enclosure modelling, built from the FreeCAD step snapshots (Blender 5, Workbench)."""
import bpy, json, math, os
from mathutils import Vector, Euler

S = 0.01                                     # 1 mm = 0.01 Blender units
ST = "/work/housing/steps"
meta = json.load(open(f"{ST}/steps.json"))
steps = meta["steps"]
TOP = meta["top"]

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = 24

# ------------------------------------------------------------------ timing
DUR = {0: 66, 13: 48, 14: 48, 15: 78, 16: 48}
starts, f = [], 0
for i in range(len(steps)):
    starts.append(f); f += DUR.get(i, 42)
ASSEMBLE = f;            f += 40           # parts drop into place
ORBIT = f;               f += 54           # closed box orbit
EXPLODE = f;             f += 30           # explode again
END = f;                 f += 72           # end card on exploded view
TOTAL = f
sc.frame_start, sc.frame_end = 0, TOTAL - 1
HL = 20                                    # highlight frames at the start of each step

# ------------------------------------------------------------------ materials
def mat(name, rgba):
    m = bpy.data.materials.new(name); m.diffuse_color = rgba; return m
M = dict(base=mat("base", (0.23, 0.25, 0.28, 1)), lid=mat("lid", (0.84, 0.85, 0.87, 1)),
         add=mat("add", (1.0, 0.45, 0.08, 1)), rem=mat("rem", (0.95, 0.15, 0.1, 1)),
         lightpipes=mat("lp", (0.75, 0.88, 1.0, 1)), gasket=mat("gasket", (0.04, 0.04, 0.04, 1)),
         glands=mat("glands", (0.10, 0.10, 0.11, 1)), screws=mat("screws", (0.72, 0.72, 0.74, 1)),
         sketch=mat("sketch", (0.05, 0.35, 0.95, 1)), pcbline=mat("pcbline", (0.1, 0.65, 0.25, 1)),
         grid=mat("grid", (0.70, 0.73, 0.78, 1)), relay=mat("relay", (0.05, 0.07, 0.2, 1)))

def load(path, name, material):
    bpy.ops.wm.stl_import(filepath=path, global_scale=S)
    o = bpy.context.selected_objects[0]; o.name = name
    o.data.materials.clear(); o.data.materials.append(material)
    o.hide_render = True; o.keyframe_insert("hide_render", frame=0)
    return o

def show(o, f0, f1):
    """visible on frames [f0, f1)"""
    o.hide_render = False; o.keyframe_insert("hide_render", frame=f0)
    o.hide_render = True; o.keyframe_insert("hide_render", frame=f1)

def constant(o):
    ad = o.animation_data
    if ad and ad.action:
        try:
            for fc in ad.action.fcurves:
                for k in fc.keyframe_points: k.interpolation = "CONSTANT"
        except AttributeError:
            pass

# lid pose per step: raised above the base, or flipped beside it to show the underside
RAISED = (Vector((0, 0, 0.42)), Euler((0, 0, 0)))
FLIPPED = (Vector((0, 1.78, TOP * S)), Euler((math.pi, 0, 0)))
LIDPOSE = {8: RAISED, 9: RAISED, 10: RAISED, 11: FLIPPED, 12: FLIPPED, 13: FLIPPED, 14: RAISED, 15: (Vector((0, 0, 0.75)), Euler()),}

def pose(o, p):
    o.location = p[0]; o.rotation_euler = p[1]

# ------------------------------------------------------------------ grid floor
bpy.ops.mesh.primitive_grid_add(x_subdivisions=36, y_subdivisions=36, size=7.2, location=(0.44, 0.31, -0.026))
g = bpy.context.object; g.name = "grid"
w = g.modifiers.new("wf", "WIREFRAME"); w.thickness = 0.003
g.data.materials.append(M["grid"])

# ------------------------------------------------------------------ step 0: sketch lines drawn on the floor plane
sk = steps[0]["sketch"]
for k, pl in enumerate(sk):
    cu = bpy.data.curves.new(f"sk{k}", "CURVE"); cu.dimensions = "3D"; cu.bevel_depth = 0.0035
    sp = cu.splines.new("POLY"); sp.points.add(len(pl) - 1)
    for p, c in zip(sp.points, pl): p.co = (c[0] * S, c[1] * S, -0.02 + 0.0005 * k, 1)
    o = bpy.data.objects.new(f"sketch{k}", cu); sc.collection.objects.link(o)
    cu.materials.append(M["pcbline"] if k >= len(sk) - 4 else M["sketch"])
    a0 = starts[0] + 4 + k * 2.2
    cu.bevel_factor_end = 0; cu.keyframe_insert("bevel_factor_end", frame=a0)
    cu.bevel_factor_end = 1; cu.keyframe_insert("bevel_factor_end", frame=a0 + 6)
    show(o, 0, starts[2]); constant(o)

# ------------------------------------------------------------------ per-step geometry
for i, s in enumerate(steps):
    if i == 0 or i == 16: continue
    f0, f1 = starts[i], starts[i + 1] if i + 1 < len(steps) else ASSEMBLE
    d = f"{ST}/{i:02d}"
    for part in ("base", "lid"):
        if part not in s["parts"]: continue
        cur = load(f"{d}/{part}.stl", f"s{i}_{part}", M[part])
        diff = s["diff"]
        objs = [cur]
        if part + "_add" in diff:
            prev = load(f"{ST}/{i - 1:02d}/{part}.stl", f"s{i}_{part}_prev", M[part]) if os.path.exists(f"{ST}/{i - 1:02d}/{part}.stl") else None
            add = load(f"{d}/{part}_add.stl", f"s{i}_{part}_add", M["add"])
            # grow the new feature from its centre
            bpy.context.view_layer.objects.active = add
            bpy.ops.object.select_all(action="DESELECT"); add.select_set(True)
            bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
            s0 = add.scale.copy()
            add.scale = s0 * 0.02; add.keyframe_insert("scale", frame=f0)
            add.scale = s0; add.keyframe_insert("scale", frame=f0 + 9)
            show(add, f0, f0 + HL); show(cur, f0 + HL, f1)
            if prev: show(prev, f0, f0 + HL); objs.append(prev)
            objs.append(add)
        elif part + "_rem" in diff:
            rem = load(f"{d}/{part}_rem.stl", f"s{i}_{part}_rem", M["rem"])
            bpy.context.view_layer.objects.active = rem
            bpy.ops.object.select_all(action="DESELECT"); rem.select_set(True)
            bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
            s0 = rem.scale.copy()
            rem.scale = s0; rem.keyframe_insert("scale", frame=f0 + 6)
            rem.scale = s0 * 0.01; rem.keyframe_insert("scale", frame=f0 + HL)
            show(rem, f0, f0 + HL); show(cur, f0, f1)
            objs.append(rem)
        else:
            show(cur, f0, f1)
        if part == "lid" and i in LIDPOSE:
            for o in objs:
                loc0 = o.location.copy()          # origin_set may have moved the origin; keep the offset
                if o.rotation_euler.x == 0 and LIDPOSE[i][1].x != 0:
                    # flip about the world X axis: compose with the lid pose
                    mw = o.matrix_world.copy()
                    from mathutils import Matrix
                    T = Matrix.Translation(LIDPOSE[i][0]) @ LIDPOSE[i][1].to_matrix().to_4x4()
                    o.matrix_world = T @ mw
                else:
                    o.location = loc0 + LIDPOSE[i][0]
        for o in objs: constant(o) if o.name.endswith(("_prev",)) or o is cur else None

# ------------------------------------------------------------------ PCB (populated board from the KiCad GLB)
bpy.ops.import_scene.gltf(filepath="/work/anim/board.glb")
pcb = bpy.data.objects["Node_0"]; pcb.name = "PCB"
pcb.scale = (10, 10, 10)
REST = Vector((0.4825, 0.31, 0.06))
bpy.ops.mesh.primitive_cube_add(size=1, location=(31.1 * S, (62 - 49.8) * S, (6 + 1.6 + 7.65) * S))
relay = bpy.context.object; relay.scale = (20.5 * S, 10.1 * S, 15.3 * S); relay.data.materials.append(M["relay"])
relay.parent = pcb; relay.matrix_parent_inverse = pcb.matrix_world.inverted()
pcb.location = REST + Vector((0, 0, 0.9))
f15 = starts[15]
pcb.keyframe_insert("location", frame=0)
pcb.keyframe_insert("location", frame=f15 + 4)
pcb.location = REST; pcb.keyframe_insert("location", frame=f15 + 24)
pcb.keyframe_insert("location", frame=ORBIT - 1)
pcb_objs = [pcb] + [c for c in pcb.children_recursive]
for o in pcb_objs:
    o.hide_render = True; o.keyframe_insert("hide_render", frame=0)
    o.hide_render = False; o.keyframe_insert("hide_render", frame=f15)

# ------------------------------------------------------------------ final assembly (step 16 meshes)
d16 = f"{ST}/16"
fin = {}
for part in ("base", "lid", "lightpipes", "gasket", "glands", "screws"):
    o = load(f"{d16}/{part}.stl", f"final_{part}", M[part])
    o.hide_render = False; o.keyframe_insert("hide_render", frame=starts[16])
    fin[part] = o
EXP = dict(base=Vector((0, 0, 0)), gasket=Vector((0, 0, 0.30)), lightpipes=Vector((0, 0, 0.42)),
           lid=Vector((0, 0, 0.62)), screws=Vector((0, 0, 0.95)), glands=Vector((-0.38, 0, 0)))
PCB_EXP = REST + Vector((0, 0, 0.14))
def set_exploded(frame, k):
    for p, o in fin.items():
        o.location = EXP[p] * k; o.keyframe_insert("location", frame=frame)
    pcb.location = REST.lerp(PCB_EXP, k); pcb.keyframe_insert("location", frame=frame)
s16 = starts[16]
set_exploded(s16, 1.6); set_exploded(s16 + 18, 1.0)     # parts arrive exploded
set_exploded(ASSEMBLE, 1.0); set_exploded(ASSEMBLE + 34, 0.0)
set_exploded(EXPLODE, 0.0); set_exploded(EXPLODE + 26, 1.0)
set_exploded(TOTAL, 1.0)

# ------------------------------------------------------------------ camera: continuous orbit with per-step focus
C = Vector((0.44, 0.31, 0.12))
FOCUS = {  # target, distance, elevation(deg)
    "top": (C + Vector((0, 0, -0.1)), 3.1, 70), None: (C, 2.25, 33), "rim": (Vector((0.95, 0.62, 0.22)), 0.95, 35),
    "left": (Vector((-0.24, 0.31, 0.12)), 1.25, 18), "lid": (C + Vector((0, 0, 0.42)), 2.3, 30),
    "lid_under": (Vector((0.44, 1.78 - 0.31, 0.08)), 2.0, 52), "button": (Vector((0.81, 1.78 - 0.1875, 0.1)), 0.95, 50),
    "pcb": (C, 1.9, 42), "final": (C + Vector((0, 0, 0.25)), 2.7, 28),
}
def focus_at(fr):
    cur = None
    for i, s in enumerate(steps):
        if fr >= starts[i]: cur = s.get("focus")
    if fr >= ASSEMBLE: cur = "final"
    return cur
target = bpy.data.objects.new("target", None); sc.collection.objects.link(target)
cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera")); sc.collection.objects.link(cam)
cam.data.lens = 40; cam.data.clip_start = 0.01; sc.camera = cam
tc = cam.constraints.new("TRACK_TO"); tc.target = target; tc.track_axis = "TRACK_NEGATIVE_Z"; tc.up_axis = "UP_Y"
state = None
for fr in range(0, TOTAL + 1, 2):
    tgt, dist, el = FOCUS[focus_at(fr)]
    if state is None: state = [tgt.copy(), dist, el]
    k = 0.16                                       # exponential smoothing toward the shot
    state[0] = state[0].lerp(tgt, k); state[1] += (dist - state[1]) * k; state[2] += (el - state[2]) * k
    az = math.radians(-60 + fr * 0.33)            # slow orbit
    e = math.radians(state[2])
    cam.location = state[0] + Vector((math.cos(az) * math.cos(e), math.sin(az) * math.cos(e), math.sin(e))) * state[1]
    target.location = state[0]
    cam.keyframe_insert("location", frame=fr); target.keyframe_insert("location", frame=fr)

# ------------------------------------------------------------------ render settings (CAD viewport look)
sc.render.engine = "BLENDER_WORKBENCH"
sh = sc.display.shading
sh.light = "STUDIO"; sh.color_type = "MATERIAL"; sh.show_cavity = True; sh.cavity_type = "BOTH"
sh.show_object_outline = True; sh.object_outline_color = (0.03, 0.03, 0.04)
sh.show_shadows = True; sh.shadow_intensity = 0.3; sh.show_specular_highlight = True
sc.display.render_aa = "8"
world = bpy.data.worlds.new("w"); sc.world = world; world.color = (0.80, 0.83, 0.88)
sc.render.resolution_x, sc.render.resolution_y = 1280, 720
sc.render.image_settings.file_format = "PNG"
sc.render.filepath = "/work/housing/vid/frames/f_"
sc.view_settings.view_transform = "Standard"
bpy.ops.wm.save_as_mainfile(filepath="/work/housing/vid/enclosure_speedrun.blend")
json.dump(dict(starts=starts, total=TOTAL, assemble=ASSEMBLE, orbit=ORBIT, explode=EXPLODE, end=END,
               titles=[s["title"] for s in steps], details=[s["detail"] for s in steps]),
          open("/work/housing/vid/timing.json", "w"))
print("SPEEDRUN_OK", TOTAL)
