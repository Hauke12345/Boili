"""Build the explainer scene in Blender 5 (Cycles) from the populated board GLB and the PCB track data."""
import bpy, json, math, sys, heapq
from mathutils import Vector
sys.path.insert(0, "/work/anim/scripts")
import timeline as T

TOP = 0.016                                   # world z of the board top surface
def W(x, y, z=TOP): return Vector(((x - 48.25) * 0.01, (31 - y) * 0.01, z))

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.frame_start, sc.frame_end = 0, T.END - 1
sc.render.fps = T.FPS

# ---------------------------------------------------------------- helpers
def mat(name, color=(0.8, 0.8, 0.8), rough=0.5, metal=0.0, emit=None, estr=0.0, alpha=1.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough; b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1); b.inputs["Emission Strength"].default_value = estr
    b.inputs["Alpha"].default_value = alpha
    return m

def glow_mat(name, color, transparent=False):
    """Emission material; returns (material, strength socket, mix-factor socket or None)."""
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission"); em.inputs[0].default_value = (*color, 1); em.inputs[1].default_value = 0
    if transparent:
        tr = nt.nodes.new("ShaderNodeBsdfTransparent"); mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(tr.outputs[0], mix.inputs[1]); nt.links.new(em.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs[0]); mix.inputs[0].default_value = 0
        return m, em.inputs[1], mix.inputs[0], em.inputs[0]
    nt.links.new(em.outputs[0], out.inputs[0])
    return m, em.inputs[1], None, em.inputs[0]

def key(sock_or_obj, attr, frames_vals, interp="BEZIER"):
    for f, v in frames_vals:
        if attr == "default_value": sock_or_obj.default_value = v; sock_or_obj.keyframe_insert("default_value", frame=f)
        else: setattr(sock_or_obj, attr, v); sock_or_obj.keyframe_insert(attr, frame=f)
    ad = sock_or_obj.id_data.animation_data if hasattr(sock_or_obj, "id_data") else None
    return ad

def box(name, center, size, material, parent=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    o = bpy.context.object; o.name = name; o.scale = size
    bpy.ops.object.transform_apply(scale=True)
    o.data.materials.append(material)
    if parent: o.parent = parent
    return o

def bevel(o, w=0.004, seg=2):
    m = o.modifiers.new("bevel", "BEVEL"); m.width = w; m.segments = seg; m.limit_method = "ANGLE"
    return o

def cyl(name, center, r, h, material, verts=32, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=h, location=center, vertices=verts, rotation=rot)
    o = bpy.context.object; o.name = name; o.data.materials.append(material)
    bpy.ops.object.shade_smooth()
    return o

def tube(name, pts, radius, material, res=12):
    cu = bpy.data.curves.new(name, "CURVE"); cu.dimensions = "3D"
    cu.bevel_depth = radius; cu.bevel_resolution = 3; cu.use_fill_caps = True
    sp = cu.splines.new("BEZIER"); sp.bezier_points.add(len(pts) - 1)
    for bp, p in zip(sp.bezier_points, pts):
        bp.co = p; bp.handle_left_type = bp.handle_right_type = "AUTO"
    sp.resolution_u = res
    o = bpy.data.objects.new(name, cu); sc.collection.objects.link(o); cu.materials.append(material)
    return o

def text(name, body, loc, size, material, rot=(0, 0, 0), align="CENTER", extrude=0.0005):
    cu = bpy.data.curves.new(name, "FONT"); cu.body = body; cu.size = size; cu.extrude = extrude
    cu.align_x = align; cu.align_y = "CENTER"
    o = bpy.data.objects.new(name, cu); o.location = loc; o.rotation_euler = rot
    sc.collection.objects.link(o); cu.materials.append(material)
    return o

# ---------------------------------------------------------------- board
bpy.ops.import_scene.gltf(filepath="/work/anim/board.glb")
root = bpy.data.objects["Node_0"]; root.scale = (10, 10, 10)
for m in bpy.data.materials:
    if not m.use_nodes: continue
    b = m.node_tree.nodes.get("Principled BSDF")
    if not b: continue
    c = tuple(round(x, 2) for x in b.inputs["Base Color"].default_value[:3])
    if c == (0.08, 0.2, 0.14):                       # solder mask
        b.inputs["Base Color"].default_value = (0.010, 0.085, 0.035, 1); b.inputs["Alpha"].default_value = 0.88
        b.inputs["Roughness"].default_value = 0.32
    elif c == (0.3, 0.3, 0.3):                       # FR-4 body
        b.inputs["Base Color"].default_value = (0.11, 0.13, 0.06, 1); b.inputs["Roughness"].default_value = 0.6
    elif c == (0.7, 0.61, 0.0):                      # copper / ENIG
        b.inputs["Base Color"].default_value = (0.85, 0.62, 0.25, 1); b.inputs["Metallic"].default_value = 1
        b.inputs["Roughness"].default_value = 0.3
    elif c == (1.0, 1.0, 1.0):                       # silkscreen
        b.inputs["Roughness"].default_value = 0.7; b.inputs["Alpha"].default_value = 1.0

# ---------------------------------------------------------------- relay K1 (no library 3D model)
relay_m = mat("relay_body", (0.015, 0.02, 0.05), 0.35)
white = mat("white_print", (0.9, 0.9, 0.9), 0.6)
relay = bevel(box("K1_body", W(31.1, 49.8, TOP + 0.0765), (0.205, 0.101, 0.153), relay_m), 0.004)
text("K1_txt", "OMRON\nG5Q-1A  5VDC", W(31.1, 49.8, TOP + 0.1535), 0.022, white)

# ---------------------------------------------------------------- floor and stand-offs
floor_m = mat("floor", (0.010, 0.011, 0.014), 0.5)
bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, -0.045)); bpy.context.object.data.materials.append(floor_m)
brass = mat("brass", (0.75, 0.6, 0.3), 0.35, 1.0)
for x, y in [(4, 4), (4, 58), (92.5, 58), (52, 5)]:
    c = W(x, y, -0.0225); cyl("standoff", c, 0.028, 0.045, brass, verts=6)

# ---------------------------------------------------------------- LED glows
def led(name, x, y, color):
    m, s, _, _ = glow_mat(name, color)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.0065, location=W(x, y, TOP + 0.009), segments=16, ring_count=8)
    o = bpy.context.object; o.name = name; o.data.materials.append(m)
    return s
green_led = led("glow_D3", 62, 51, (0.2, 1.0, 0.35))
red_led = led("glow_D2", 51, 48, (1.0, 0.12, 0.05))
key(green_led, "default_value", [(0, 0)], "CONSTANT")
f = T.STATUS_BLINK_FROM
while f < T.END:
    key(green_led, "default_value", [(f, 40.0), (f + 10, 40.0), (f + 11, 0.0), (f + 23, 0.0)])
    f += 24
key(red_led, "default_value", [(0, 0), (T.RELAY_ON - 1, 0), (T.RELAY_ON, 50.0), (T.HEAT_OFF, 50.0), (T.HEAT_OFF + 1, 0)])

# ---------------------------------------------------------------- current-flow tubes along real copper
pcb = json.load(open("/work/anim/pcb.json"))
def snap(p): return (round(p[0], 1), round(p[1], 1))
for net, src, start, color in T.FLOWS:
    segs = pcb["nets"][net]["segs"]
    adj = {}
    for i, s in enumerate(segs):
        a, b = snap(s[0:2]), snap(s[2:4]); L = math.dist(a, b)
        adj.setdefault(a, []).append((b, L, i)); adj.setdefault(b, []).append((a, L, i))
    sp = pcb["pads"][src][:2]
    start_node = min(adj, key=lambda n: math.dist(n, sp))
    dist = {start_node: 0.0}; pq = [(0.0, start_node)]
    while pq:
        d, n = heapq.heappop(pq)
        if d > dist.get(n, 1e9): continue
        for m_, L, _ in adj[n]:
            if d + L < dist.get(m_, 1e9): dist[m_] = d + L; heapq.heappush(pq, (d + L, m_))
    maxd = max(dist.values()) if dist else 0
    m, strength, _, _ = glow_mat("flow_" + net, color)
    sustain = T.HEAT_OFF if start >= 800 else T.END + 10
    key(strength, "default_value", [(start - 1, 0.0), (start, 9.0), (start + 70, 9.0), (start + 110, 2.2)])
    if sustain < T.END:
        key(strength, "default_value", [(sustain, 2.2), (sustain + 18, 0.0)])
    for i, s in enumerate(segs):
        a, b = snap(s[0:2]), snap(s[2:4])
        da, db = dist.get(a, maxd), dist.get(b, maxd)
        if db < da: a, b, da, db = b, a, db, da
        cu = bpy.data.curves.new(f"seg_{net}_{i}", "CURVE"); cu.dimensions = "3D"
        cu.bevel_depth = max(s[4] * 0.0042, 0.0016); cu.bevel_resolution = 2; cu.use_fill_caps = True
        z = TOP + 0.0045
        spl = cu.splines.new("POLY"); spl.points.add(1)
        spl.points[0].co = (*W(*a, z), 1); spl.points[1].co = (*W(*b, z), 1)
        cu.materials.append(m)
        o = bpy.data.objects.new(cu.name, cu); sc.collection.objects.link(o)
        t0 = start + da / T.FLOW_SPEED_MM_PER_FRAME
        t1 = start + db / T.FLOW_SPEED_MM_PER_FRAME + 1
        cu.bevel_factor_end = 0; cu.keyframe_insert("bevel_factor_end", frame=t0)
        cu.bevel_factor_end = 1; cu.keyframe_insert("bevel_factor_end", frame=t1)
        o.hide_render = True; o.keyframe_insert("hide_render", frame=0)
        o.hide_render = False; o.keyframe_insert("hide_render", frame=int(t0) + 1)
        if sustain < T.END:
            o.hide_render = True; o.keyframe_insert("hide_render", frame=sustain + 19)

# ---------------------------------------------------------------- WiFi rings from the antenna
ant = W(84, 2.5, TOP + 0.035)
for k in range(4):
    m, s, mix, _ = glow_mat(f"wifi{k}", (0.35, 0.7, 1.0), transparent=True)
    bpy.ops.mesh.primitive_torus_add(major_radius=1, minor_radius=0.035, major_segments=48, minor_segments=8,
                                     location=ant, rotation=(math.radians(60), 0, 0))
    o = bpy.context.object; o.name = f"wifi{k}"; o.data.materials.append(m)
    s.default_value = 14.0
    a0, a1 = T.WIFI
    o.hide_render = True; o.keyframe_insert("hide_render", frame=0)
    o.hide_render = False; o.keyframe_insert("hide_render", frame=a0 + k * 12 - 1)
    o.hide_render = True; o.keyframe_insert("hide_render", frame=a1 + 45)
    o.scale = (0.001,) * 3; o.keyframe_insert("scale", frame=0)
    mix.default_value = 0; mix.keyframe_insert("default_value", frame=0)
    t = a0 + k * 12
    while t + 48 <= a1 + 40:
        o.scale = (0.02,) * 3; o.keyframe_insert("scale", frame=t)
        mix.default_value = 0; mix.keyframe_insert("default_value", frame=t - 1)
        mix.default_value = 1; mix.keyframe_insert("default_value", frame=t)
        o.scale = (0.38,) * 3; o.keyframe_insert("scale", frame=t + 48)
        mix.default_value = 1; mix.keyframe_insert("default_value", frame=t + 30)
        mix.default_value = 0; mix.keyframe_insert("default_value", frame=t + 48)
        t += 48
    for fc in o.animation_data.action.fcurves if o.animation_data.action and hasattr(o.animation_data.action, "fcurves") else []:
        for kp in fc.keyframe_points: kp.interpolation = "LINEAR"

# ---------------------------------------------------------------- off-board: cables, contactor, tank
wire_L = mat("wire_brown", (0.22, 0.09, 0.03), 0.4)
wire_N = mat("wire_blue", (0.02, 0.12, 0.55), 0.4)
cable = mat("cable_black", (0.02, 0.02, 0.022), 0.45)
ez = TOP + 0.042
# mains in: J1 pin1 L (6.5,16), pin2 N (6.5,10.92)
tube("mains_L", [W(1.5, 16, ez), W(-12, 16, ez), W(-30, 22, -0.035), (-0.9, 1.2, -0.035), (-0.9, 3.5, -0.035)], 0.009, wire_L)
tube("mains_N", [W(1.5, 10.92, ez), W(-12, 10.92, ez), W(-30, 17, -0.035), (-0.84, 1.2, -0.035), (-0.84, 3.5, -0.035)], 0.009, wire_N)

con_c = Vector((-1.05, -0.30, 0.0))
grey = mat("contactor_grey", (0.62, 0.63, 0.65), 0.45)
dark = mat("contactor_dark", (0.05, 0.05, 0.06), 0.5)
metal = mat("screw", (0.7, 0.7, 0.72), 0.25, 1.0)
cont = bevel(box("contactor", con_c + Vector((0, 0, 0.13)), (0.20, 0.26, 0.35), grey), 0.01)
box("contactor_front", con_c + Vector((0, -0.131, 0.15)), (0.15, 0.004, 0.17), dark)
for dx, lbl in [(-0.05, "A1"), (0.05, "A2")]:
    cyl("termA", con_c + Vector((dx, -0.07, 0.31)), 0.014, 0.012, metal)
    text("t_" + lbl, lbl, con_c + Vector((dx, -0.133, 0.26)), 0.03, white, rot=(math.radians(90), 0, 0))
text("t_con", "CONTACTOR\n3P 25A", con_c + Vector((0, -0.134, 0.11)), 0.024, white, rot=(math.radians(90), 0, 0))
flag_m, flag_s, _, flag_col = glow_mat("flag", (0.1, 1.0, 0.3))
flag = box("contactor_flag", con_c + Vector((0, -0.134, 0.2)), (0.05, 0.006, 0.03), flag_m)
key(flag_s, "default_value", [(0, 0.3), (T.CONTACTOR_ON - 1, 0.3), (T.CONTACTOR_ON, 8.0), (T.HEAT_OFF + 8, 8.0), (T.HEAT_OFF + 9, 0.3)])
key(flag, "location", [(0, flag.location.copy()), (T.CONTACTOR_ON - 1, flag.location.copy())])
flag.location.z -= 0.035; flag.keyframe_insert("location", frame=T.CONTACTOR_ON + 2)
flag.keyframe_insert("location", frame=T.HEAT_OFF + 8)
flag.location.z += 0.035; flag.keyframe_insert("location", frame=T.HEAT_OFF + 11)
# board J2 -> contactor coil A1/A2
tube("coil_L", [W(1.5, 48, ez), W(-10, 48, ez), con_c + Vector((-0.05 + 0.25, -0.07, 0.42)), con_c + Vector((-0.05, -0.07, 0.42)), con_c + Vector((-0.05, -0.07, 0.315))], 0.007, wire_L)
tube("coil_N", [W(1.5, 42.92, ez), W(-10, 42.92, ez), con_c + Vector((0.05 + 0.22, -0.07, 0.44)), con_c + Vector((0.05, -0.07, 0.44)), con_c + Vector((0.05, -0.07, 0.315))], 0.007, wire_N)
# supply to contactor main contacts (from the back) and contactor -> tank
tube("supply", [con_c + Vector((0, 0.05, 0.31)), con_c + Vector((0, 0.25, 0.4)), con_c + Vector((0.0, 0.9, -0.03)), con_c + Vector((0.0, 3.5, -0.03))], 0.016, cable)
tank_c = Vector((-1.75, 0.10, -0.045))
tube("to_thermostat", [con_c + Vector((0, -0.05, -0.03)), con_c + Vector((-0.15, -0.05, -0.035)), Vector((-1.58, -0.15, 0.05)), Vector((-1.60, -0.15, 0.31))], 0.016, cable)

enamel = mat("tank_white", (0.82, 0.83, 0.84), 0.28)
tank = cyl("tank", tank_c + Vector((0, 0, 0.5)), 0.27, 1.0, enamel, verts=64)
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.27, location=tank_c + Vector((0, 0, 1.0)), segments=64, ring_count=32)
dome = bpy.context.object; dome.scale.z = 0.35; dome.data.materials.append(enamel); bpy.ops.object.shade_smooth()
copper = mat("pipe_copper", (0.8, 0.45, 0.25), 0.3, 1.0)
for dx in (-0.1, 0.1):
    cyl("pipe", tank_c + Vector((dx, 0, 1.15)), 0.022, 0.18, copper)
for a in range(3):
    ang = math.radians(a * 120 + 30)
    cyl("foot", tank_c + Vector((0.21 * math.cos(ang), 0.21 * math.sin(ang), 0.0)), 0.03, 0.03, metal)
# thermostat / limiter box on the tank front
th = bevel(box("thermostat", Vector((-1.60, -0.15, 0.40)), (0.13, 0.06, 0.18), grey), 0.008)
red_dial = mat("dial", (0.7, 0.05, 0.03), 0.4)
cyl("dial", Vector((-1.60, -0.183, 0.43)), 0.028, 0.012, red_dial, rot=(math.radians(90), 0, 0))
# thermometer gauge on the tank front
gauge_bg = mat("gauge_bg", (0.04, 0.04, 0.05), 0.5)
box("gauge_bg", Vector((-1.75, -0.176, 0.55)), (0.07, 0.014, 0.55), gauge_bg)
gm, gs, _, gcol = glow_mat("gauge_fill", (0.15, 0.4, 1.0))
gs.default_value = 4.0
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
fill = bpy.context.object; fill.name = "gauge_fill"; fill.data.materials.append(gm)
fill.scale = (0.045, 0.006, 1.0); bpy.ops.object.transform_apply(scale=True)
# geometry origin at the bottom of the gauge so scaling z grows it upwards
fill.data.transform(__import__("mathutils").Matrix.Translation((0, 0, 0.5)))
fill.location = (-1.75, -0.185, 0.29)
h0, h1 = 0.12, 0.50
fill.scale = (1, 1, h0); fill.keyframe_insert("scale", frame=0); fill.keyframe_insert("scale", frame=T.TANK_HEAT[0])
fill.scale = (1, 1, h1); fill.keyframe_insert("scale", frame=T.TANK_HEAT[1])
key(gcol, "default_value", [(0, (0.15, 0.4, 1.0, 1)), (T.TANK_HEAT[0], (0.15, 0.4, 1.0, 1)), (T.TANK_HEAT[1], (1.0, 0.25, 0.05, 1))])
text("gauge_txt", "°C", Vector((-1.75, -0.186, 0.87)), 0.05, white, rot=(math.radians(90), 0, 0))
# heating element glow ring at the bottom of the tank
hm, hs, _, _ = glow_mat("element", (1.0, 0.35, 0.05))
bpy.ops.mesh.primitive_torus_add(major_radius=0.272, minor_radius=0.012, location=tank_c + Vector((0, 0, 0.12)))
bpy.context.object.data.materials.append(hm)
key(hs, "default_value", [(0, 0), (T.TANK_HEAT[0] - 1, 0), (T.TANK_HEAT[0] + 12, 12.0), (T.TANK_HEAT[1], 12.0), (T.TANK_HEAT[1] + 12, 0)])

# ---------------------------------------------------------------- isolation barrier (safety shot)
iso_m, iso_s, iso_mix, _ = glow_mat("isolation", (1.0, 0.1, 0.05), transparent=True)
iso_s.default_value = 3.0
path = [(24.6, 0.5), (24.6, 16.2), (45, 16.2), (45, 40.4), (35, 40.4), (35, 61.5)]
verts, faces = [], []
for i, (x, y) in enumerate(path):
    verts += [W(x, y, TOP), W(x, y, TOP + 0.19)]
    if i: faces.append((2 * i - 2, 2 * i - 1, 2 * i + 1, 2 * i))
me = bpy.data.meshes.new("iso"); me.from_pydata(verts, [], faces); me.materials.append(iso_m)
iso = bpy.data.objects.new("isolation", me); sc.collection.objects.link(iso)
a, b = T.ISOLATION
key(iso_mix, "default_value", [(0, 0), (a, 0), (a + 15, 0.45), (b - 10, 0.45), (b + 5, 0)])

# ---------------------------------------------------------------- camera
target = bpy.data.objects.new("cam_target", None); sc.collection.objects.link(target)
cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera")); sc.collection.objects.link(cam)
cam.data.lens = 35; cam.data.clip_start = 0.01; sc.camera = cam
tc = cam.constraints.new("TRACK_TO"); tc.target = target; tc.track_axis = "TRACK_NEGATIVE_Z"; tc.up_axis = "UP_Y"
for f, loc, tgt in T.SHOTS:
    cam.location = loc; cam.keyframe_insert("location", frame=f)
    target.location = tgt; target.keyframe_insert("location", frame=f)

# ---------------------------------------------------------------- lights and world
def area(name, loc, energy, size, color=(1, 1, 1)):
    l = bpy.data.objects.new(name, bpy.data.lights.new(name, "AREA")); l.data.energy = energy
    l.data.size = size; l.data.color = color; l.location = loc; sc.collection.objects.link(l)
    l.rotation_euler = (Vector((-0.4, 0, 0.2)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
area("key", (1.2, -1.6, 2.2), 260, 1.6, (1.0, 0.96, 0.9))
area("fill", (-2.6, -1.2, 1.6), 110, 2.0, (0.75, 0.85, 1.0))
area("rim", (-0.3, 2.8, 1.8), 200, 2.0, (0.9, 0.95, 1.0))
world = bpy.data.worlds.new("world"); sc.world = world; world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.012, 0.016, 0.028, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 1.0

# ---------------------------------------------------------------- render settings
r = sc.render; r.engine = "CYCLES"
sc.cycles.device = "CPU"; sc.cycles.samples = 5; sc.cycles.use_adaptive_sampling = True; sc.cycles.adaptive_threshold = 0.05
sc.cycles.use_denoising = False
sc.cycles.max_bounces = 4; sc.cycles.diffuse_bounces = 2; sc.cycles.glossy_bounces = 2
sc.cycles.transmission_bounces = 2; sc.cycles.transparent_max_bounces = 6
sc.cycles.caustics_reflective = False; sc.cycles.caustics_refractive = False
sc.cycles.blur_glossy = 1.0
r.use_persistent_data = True; r.use_sequencer = False
r.resolution_x, r.resolution_y, r.resolution_percentage = 960, 540, 100
vl = sc.view_layers[0]; vl.use_pass_normal = True; vl.use_pass_diffuse_color = True; vl.use_pass_glossy_color = True; vl.use_pass_emit = True
r.image_settings.media_type = "IMAGE"; r.image_settings.file_format = "JPEG"; r.image_settings.quality = 70
r.filepath = "/work/anim/frames_main/m_"
r.use_compositing = True
ng = bpy.data.node_groups.new("comp", "CompositorNodeTree"); sc.compositing_node_group = ng
rl = ng.nodes.new("CompositorNodeRLayers")
add = ng.nodes.new("ShaderNodeMix"); add.data_type = "RGBA"; add.blend_type = "ADD"; add.inputs[0].default_value = 1.0
ng.links.new(rl.outputs["Diffuse Color"], add.inputs[6]); ng.links.new(rl.outputs["Glossy Color"], add.inputs[7])
for sub, src in [("img", rl.outputs["Image"]), ("alb", add.outputs[2]), ("nrm", rl.outputs["Normal"]), ("emi", rl.outputs["Emission"])]:
    fo = ng.nodes.new("CompositorNodeOutputFile")
    fo.directory = f"/work/anim/frames/{sub}/"; fo.file_name = "f"
    fo.format.media_type = "IMAGE"; fo.format.file_format = "OPEN_EXR"
    fo.format.color_depth = "16"; fo.format.exr_codec = "PIZ"
    fo.file_output_items.new("RGBA", sub)
    ng.links.new(src, fo.inputs[0])
sc.view_settings.view_transform = "Standard"
bpy.ops.wm.save_as_mainfile(filepath="/work/anim/spot_heater_explainer.blend")
print("SCENE_OK", len(bpy.data.objects))
