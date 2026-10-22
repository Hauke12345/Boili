"""Boili product hero shot: closed enclosure, studio light, glowing light pipes (Blender 5, Cycles)."""
import bpy, math, sys
from mathutils import Vector

W_, H_ = int(sys.argv[-4]), int(sys.argv[-3])
SAMPLES = int(sys.argv[-2])
NFR = int(sys.argv[-1])
D = "/work/boili_prod/steps/16"
mm = 0.001
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene

def mat(name, col, rough=0.5, metal=0.0, coat=0.0, emit=None, estr=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*col, 1); b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal; b.inputs["Coat Weight"].default_value = coat
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1); b.inputs["Emission Strength"].default_value = estr
    return m

def load(name, material, smooth=True):
    bpy.ops.wm.stl_import(filepath=f"{D}/{name}.stl", global_scale=mm)
    o = bpy.context.selected_objects[0]; o.name = name
    o.data.materials.clear(); o.data.materials.append(material)
    if smooth:
        bpy.ops.object.shade_auto_smooth(angle=math.radians(35))
    return o

M_base = mat("base", (0.028, 0.030, 0.034), 0.42, coat=0.15)
M_lid = mat("lid", (0.30, 0.31, 0.33), 0.5, coat=0.1)
M_black = mat("gland", (0.012, 0.012, 0.013), 0.55)
M_screw = mat("screw", (0.75, 0.75, 0.77), 0.28, metal=1.0)
M_cable = mat("cable", (0.015, 0.015, 0.016), 0.38)
base = load("base", M_base); lid = load("lid", M_lid)
load("glands", M_black); load("screws", M_screw)

# light pipes: split into the two pipes and make them glow
lp = load("lightpipes", M_lid, smooth=False)
bpy.context.view_layer.objects.active = lp
bpy.ops.object.mode_set(mode="EDIT"); bpy.ops.mesh.separate(type="LOOSE"); bpy.ops.object.mode_set(mode="OBJECT")
pipes = [o for o in bpy.data.objects if o.name.startswith("lightpipes")]
for o in pipes:
    xs = [(o.matrix_world @ v.co).x for v in o.data.vertices]; cx = sum(xs) / len(xs) / mm
    heat = cx < 56
    col = (1.0, 0.32, 0.06) if heat else (0.15, 1.0, 0.35)
    o.data.materials.clear(); o.data.materials.append(mat("pipe_" + ("heat" if heat else "status"), (0.9, 0.9, 0.9), 0.2, emit=col, estr=40 if heat else 22))
    top = max((o.matrix_world @ v.co).z for v in o.data.vertices)
    cy = sum((o.matrix_world @ v.co).y for v in o.data.vertices) / len(o.data.vertices)
    l = bpy.data.objects.new("glow", bpy.data.lights.new("glow", "POINT")); sc.collection.objects.link(l)
    l.location = (cx * mm, cy, top + 0.004); l.data.energy = 0.006 if heat else 0.003; l.data.color = col; l.data.shadow_soft_size = 0.002

# cables out of the glands, curving down and away
def cable(y):
    x0, z0 = -45 * mm, 12.5 * mm
    pts = [Vector((x0 + 6 * mm, y, z0)), Vector((x0 - 18 * mm, y, z0)), Vector((x0 - 45 * mm, y + 0.006, z0 - 6 * mm)),
           Vector((x0 - 70 * mm, y + 0.03, -0.0005 + 3.6 * mm)), Vector((x0 - 160 * mm, y + 0.11, 3.6 * mm)), Vector((x0 - 400 * mm, y + 0.26, 3.6 * mm))]
    cu = bpy.data.curves.new("cable", "CURVE"); cu.dimensions = "3D"; cu.bevel_depth = 3.6 * mm; cu.bevel_resolution = 6
    sp = cu.splines.new("BEZIER"); sp.bezier_points.add(len(pts) - 1)
    for bp, p in zip(sp.bezier_points, pts):
        bp.co = p; bp.handle_left_type = bp.handle_right_type = "AUTO"
    o = bpy.data.objects.new("cable", cu); sc.collection.objects.link(o); cu.materials.append(M_cable)
    bpy.context.view_layer.objects.active = o
# turntable: everything that belongs to the product spins around its own centre
C = Vector((44 * mm, 31 * mm, 0))
pivot = bpy.data.objects.new("turntable", None); sc.collection.objects.link(pivot); pivot.location = C
bpy.context.view_layer.update()
for o in list(sc.objects):
    if o.name.startswith(("base", "lid", "glands", "screws", "lightpipes", "glow")):
        mw = o.matrix_world.copy(); o.parent = pivot; o.matrix_world = mw
sc.frame_start, sc.frame_end = 1, NFR
for f in (1, NFR + 1):
    pivot.rotation_euler = (0, 0, -2 * math.pi * (f - 1) / NFR); pivot.keyframe_insert("rotation_euler", frame=f)
for fc in pivot.animation_data.action.fcurves if hasattr(pivot.animation_data.action, "fcurves") else []:
    for k in fc.keyframe_points: k.interpolation = "LINEAR"
try:
    for fc in pivot.animation_data.action.layers[0].strips[0].channelbags[0].fcurves:
        for k in fc.keyframe_points: k.interpolation = "LINEAR"
except Exception as ex:
    print("interp note", ex)

# floor: large, dark, slightly glossy; seamless sweep behind
M_floor = mat("floor", (0.020, 0.021, 0.025), 0.42)
bpy.ops.mesh.primitive_plane_add(size=6, location=(0, 0, -2.5 * mm)); bpy.context.object.data.materials.append(M_floor)
bpy.ops.mesh.primitive_cylinder_add(radius=1.2, depth=6, location=(0, 1.6, 1.2 - 2.5 * mm), rotation=(0, math.radians(90), 0), vertices=96)
sweep = bpy.context.object; sweep.data.materials.append(M_floor); bpy.ops.object.shade_smooth()

# lights
def area(name, loc, energy, size, color, target=(0.045, 0.03, 0.01), shape="RECTANGLE", sy=None):
    l = bpy.data.objects.new(name, bpy.data.lights.new(name, "AREA")); sc.collection.objects.link(l)
    l.data.energy = energy; l.data.size = size; l.data.color = color; l.data.shape = shape
    if sy: l.data.size_y = sy
    l.location = loc; l.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
area("key", (-0.32, -0.12, 0.24), 4.5, 0.3, (1.0, 0.97, 0.93), sy=0.3)
area("rim", (0.35, 0.45, 0.22), 3.5, 0.25, (1.0, 0.55, 0.25), sy=0.08)
area("fill", (0.55, -0.30, 0.12), 1.2, 0.6, (0.75, 0.85, 1.0))
area("front", (0.10, -0.50, 0.20), 1.6, 0.5, (1.0, 0.98, 0.95))
area("top", (0.05, 0.05, 0.60), 0.6, 0.35, (1.0, 1.0, 1.0))
world = bpy.data.worlds.new("w"); sc.world = world; world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.004, 0.005, 0.007, 1)

# camera: product on the right, empty dark space on the left for the headline
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
cam.data.lens = 52
cam.data.dof.use_dof = True; cam.data.dof.aperture_fstop = 5.6
tgt = bpy.data.objects.new("tgt", None); sc.collection.objects.link(tgt); tgt.location = (0.044, 0.031, 0.012)
cam.location = (0.044, 0.031 - 0.36, 0.20)
tc = cam.constraints.new("TRACK_TO"); tc.target = tgt; tc.track_axis = "TRACK_NEGATIVE_Z"; tc.up_axis = "UP_Y"
cam.data.dof.focus_object = tgt; cam.data.dof.aperture_fstop = 8

r = sc.render; r.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = SAMPLES
sc.cycles.use_denoising = False; sc.cycles.max_bounces = 6
r.resolution_x, r.resolution_y = W_, H_
sc.view_settings.view_transform = "Standard"
vl = sc.view_layers[0]; vl.use_pass_normal = True; vl.use_pass_diffuse_color = True; vl.use_pass_glossy_color = True; vl.use_pass_emit = True
r.use_compositing = True
ng = bpy.data.node_groups.new("comp", "CompositorNodeTree"); sc.compositing_node_group = ng
rl = ng.nodes.new("CompositorNodeRLayers")
add = ng.nodes.new("ShaderNodeMix"); add.data_type = "RGBA"; add.blend_type = "ADD"; add.inputs[0].default_value = 1.0
ng.links.new(rl.outputs["Diffuse Color"], add.inputs[6]); ng.links.new(rl.outputs["Glossy Color"], add.inputs[7])
for sub, src in [("img", rl.outputs["Image"]), ("alb", add.outputs[2]), ("nrm", rl.outputs["Normal"]), ("emi", rl.outputs["Emission"])]:
    fo = ng.nodes.new("CompositorNodeOutputFile"); fo.directory = "/work/boili_prod/turn/"; fo.file_name = sub
    fo.format.media_type = "IMAGE"; fo.format.file_format = "OPEN_EXR"; fo.format.color_depth = "32"
    fo.file_output_items.new("RGBA", sub); ng.links.new(src, fo.inputs[0])
r.filepath = "/work/boili_prod/turn/preview_"
r.image_settings.file_format = "PNG"
bpy.ops.wm.save_as_mainfile(filepath="/work/boili_prod/boili_turntable.blend")
print("TURN_SAVED")
