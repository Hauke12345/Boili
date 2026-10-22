"""Spot-price heater controller enclosure -- parametric FreeCAD (1.0) model for injection moulding.

Coordinates (mm): X/Y = PCB plane (board spans X 0..96.5, Y 0..62), Z = up.
Inside floor surface is Z = 0, the PCB rests on 6 mm stand-offs.
Every modelling step is snapshotted (meshes + sketches) for the speed-run video.
"""
import sys, os, json, math
sys.path.append("/usr/lib/freecad/lib")
import FreeCAD, Part, Mesh, MeshPart, Import
from FreeCAD import Vector as V

OUT = "/work/boili_prod"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# ------------------------------------------------------------------ parameters
P = dict(
    wall=2.5,             # nominal wall (PC/ABS, UL94 V-0)
    floor=2.5,
    lid_top=2.5,
    draft_deg=1.0,        # draft on all walls parallel to the opening direction
    ix0=-20.0, ix1=108.0, # interior X: 20 mm wiring bay left of the PCB, screw towers right of it
    iy0=-3.0, iy1=65.0,   # interior Y
    ir=4.0,               # interior corner radius
    rim_z=24.0,           # base rim / parting line height above the inside floor
    lid_in_z=28.0,        # underside of the lid top plate
    standoff_h=6.0,       # PCB bottom height above the floor
    boss_d=8.0, boss_hole=2.8,          # PT/self-tapping screw towers (ST3.5)
    lid_hole=3.7, cbore_d=7.0, cbore_depth=3.5,
    standoff_d=7.0, standoff_hole=2.3,  # PCB screws (PT K25)
    gland_hole=16.2, gland_z=12.5,      # M16 x 1.5 cable glands
    tongue=(0.6, 1.8, 2.0),             # tongue band (inner, outer offset, height)
    groove=(0.3, 2.1, 3.0),             # lid groove band (inner, outer offset, depth)
    lid_skirt_in=-1.0,                  # lid skirt inner face (offset from interior outline)
    rib_t=1.5, rib_h=3.0,               # 60 % of the wall
    fillet=1.5,
)
T = math.tan(math.radians(P["draft_deg"]))
TOP = P["lid_in_z"] + P["lid_top"]          # lid top surface z
BOT = -P["floor"]                            # base underside z

PCB_HOLES = [(4, 58), (4, 4), (92.5, 4), (52, 57)]          # housing coords of the 4 PCB holes
BOSSES = [(P["ix0"] + 5, P["iy0"] + 5), (P["ix0"] + 5, P["iy1"] - 5),
          (P["ix1"] - 5, P["iy0"] + 5), (P["ix1"] - 5, P["iy1"] - 5)]
GLANDS_Y = [44.0, 20.0]                      # in line with J1 (mains) and J2 (contactor)
LED_HEAT, LED_STATUS = (51.0, 14.0), (62.0, 11.0)
BUTTON = (81.15, 18.75)                      # SW2 (boost) centre
BUTTON_TOP = P["standoff_h"] + 5.89

# ------------------------------------------------------------------ helpers
def outline(d, z):
    """Face of the interior outline offset by d (outward +), at height z."""
    x0, x1, y0, y1, r = P["ix0"] - d, P["ix1"] + d, P["iy0"] - d, P["iy1"] + d, max(P["ir"] + d, 0.4)
    pts = [V(x0 + r, y0 + r, z), V(x1 - r, y0 + r, z), V(x1 - r, y1 - r, z), V(x0 + r, y1 - r, z)]
    f = Part.Face(Part.makePolygon(pts + [pts[0]]))
    return f.makeOffset2D(r, 0)

def loft(d0, z0, d1, z1):
    return Part.makeLoft([outline(d0, z0).OuterWire, outline(d1, z1).OuterWire], True, True)

def band(d_in, d_out, z0, z1):
    return outline(d_out, z0).extrude(V(0, 0, z1 - z0)).cut(outline(d_in, z0).extrude(V(0, 0, z1 - z0)))

def cyl(r, z0, z1, x, y):
    return Part.makeCylinder(r, z1 - z0, V(x, y, z0))

def box(x0, x1, y0, y1, z0, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))

def slot(x, y, r, half_len, z0, z1):            # stadium slot along Y
    s = box(x - r, x + r, y - half_len, y + half_len, z0, z1)
    return s.fuse(cyl(r, z0, z1, x, y - half_len)).fuse(cyl(r, z0, z1, x, y + half_len))

def text(s, size, x, y, z, height, center=True):
    wires = Part.makeWireString(s, FONT, size, 0)
    faces = []
    for ch in wires:
        ws = [w for w in ch]
        if not ws: continue
        ws.sort(key=lambda w: -Part.Face(w).Area)
        f = Part.Face(ws[0])
        for h in ws[1:]:
            f = f.cut(Part.Face(h))
        faces.append(f)
    comp = Part.Compound(faces)
    bb = comp.BoundBox
    dx = x - (bb.XMin + bb.XMax) / 2 if center else x - bb.XMin
    dy = y - (bb.YMin + bb.YMax) / 2
    comp.translate(V(dx, dy, z))
    return Part.Compound([f.extrude(V(0, 0, height)) for f in comp.Faces])

def fillet_edges_at(shape, z, r):
    edges = [e for e in shape.Edges if all(abs(v.Point.z - z) < 1e-3 for v in e.Vertexes)]
    try:
        return shape.makeFillet(r, edges)
    except Exception as ex:
        print("fillet skipped:", ex); return shape

# ------------------------------------------------------------------ snapshots for the speed-run
STEPS = []
PREV = {}
os.makedirs(f"{OUT}/steps", exist_ok=True)
def poly(edge_list, n=48):
    out = []
    for e in edge_list:
        pts = e.discretize(n if e.Curve.TypeId != "Part::GeomLine" else 2)
        out.append([[round(p.x, 3), round(p.y, 3), round(p.z, 3)] for p in pts])
    return out

def snap(title, detail, parts, sketch=None, focus=None):
    i = len(STEPS)
    d = f"{OUT}/steps/{i:02d}"; os.makedirs(d, exist_ok=True)
    names = {}
    diff = {}
    def wmesh(shp, fn):
        m = MeshPart.meshFromShape(Shape=shp, LinearDeflection=0.06, AngularDeflection=0.3, Relative=False)
        m.write(f"{d}/{fn}")
    for name, shp in parts.items():
        wmesh(shp, f"{name}.stl"); names[name] = f"{name}.stl"
        if name in ("base", "lid"):
            prev = PREV.get(name)
            try:
                add = shp if prev is None else shp.cut(prev)
                rem = None if prev is None else prev.cut(shp)
                if add is not None and add.Volume > 0.5:
                    wmesh(add, f"{name}_add.stl"); diff[name + "_add"] = round(add.Volume, 1)
                if rem is not None and rem.Volume > 0.5:
                    wmesh(rem, f"{name}_rem.stl"); diff[name + "_rem"] = round(rem.Volume, 1)
            except Exception as ex:
                print("diff failed", name, ex)
            PREV[name] = shp
    STEPS.append(dict(title=title, detail=detail, parts=names, diff=diff,
                      sketch=poly(sketch.Edges) if sketch is not None else None, focus=focus))
    print(f"step {i:02d}: {title}")

# ================================================================== BASE
sk_outline = outline(P["wall"], 0)
pcb_rect = Part.makePolygon([V(0, 0, 0), V(96.5, 0, 0), V(96.5, 62, 0), V(0, 62, 0), V(0, 0, 0)])
snap("Sketch the footprint", "PCB 96.5 x 62 + 20 mm wiring bay + screw towers",
     {}, sketch=Part.Compound([sk_outline.OuterWire, outline(0, 0).OuterWire, pcb_rect]), focus="top")

outer = loft(P["wall"] - (P["rim_z"] - BOT) * T, BOT, P["wall"], P["rim_z"])     # 1 deg draft
outer = fillet_edges_at(outer, BOT, P["fillet"])
snap("Pad with 1° draft", "26.5 mm tall block, draft for mould release", {"base": outer})

cavity = loft(-P["rim_z"] * T, 0, 3 * T, P["rim_z"] + 3)
base = outer.cut(cavity)
snap("Shell 2.5 mm", "Uniform 2.5 mm walls and floor (PC/ABS)", {"base": base})

tongue = band(P["tongue"][0], P["tongue"][1], P["rim_z"], P["rim_z"] + P["tongue"][2])
base = base.fuse(tongue)
snap("Sealing tongue", "1.2 mm tongue on the rim for the gasket", {"base": base}, focus="rim")

towers = None
for (x, y) in BOSSES:
    t_ = cyl(P["boss_d"] / 2, 0, P["rim_z"], x, y)
    # tie the tower to both walls with ribs (avoids a free-standing core)
    sx = -1 if x < 50 else 1; sy = -1 if y < 30 else 1
    rx = box(min(x, x + sx * 6), max(x, x + sx * 6), y - P["rib_t"] / 2, y + P["rib_t"] / 2, 0, P["rim_z"] - 1)
    ry = box(x - P["rib_t"] / 2, x + P["rib_t"] / 2, min(y, y + sy * 6), max(y, y + sy * 6), 0, P["rim_z"] - 1)
    t_ = t_.fuse(rx).fuse(ry)
    towers = t_ if towers is None else towers.fuse(t_)
base = base.fuse(towers.common(cavity))
for (x, y) in BOSSES:
    base = base.cut(cyl(P["boss_hole"] / 2, P["rim_z"] - 16, P["rim_z"] + 1, x, y))
snap("Screw towers", "4 × Ø8 towers for ST3.5 screws, tied to the walls with ribs", {"base": base})

for (x, y) in PCB_HOLES:
    s = cyl(P["standoff_d"] / 2, -0.5, P["standoff_h"], x, y)
    base = base.fuse(s).cut(cyl(P["standoff_hole"] / 2, 1.0, P["standoff_h"] + 0.1, x, y))
snap("PCB stand-offs", "6 mm stand-offs clear the 3.3 mm solder pins", {"base": base})

for gy in GLANDS_Y:
    base = base.cut(Part.makeCylinder(P["gland_hole"] / 2, 12, V(P["ix0"] - P["wall"] - 6, gy, P["gland_z"]), V(1, 0, 0)))
snap("Cable gland holes", "2 × M16 glands: mains in, contactor out", {"base": base}, focus="left")

ears = None
for x in (-4.0, 92.0):
    for side in (-1, 1):
        yo = (P["iy0"] - P["wall"]) if side < 0 else (P["iy1"] + P["wall"])
        e = box(x - 7, x + 7, min(yo, yo + side * 11), max(yo, yo + side * 11), BOT, BOT + 3.5)
        for gx in (x - 5.5, x + 4.0):                         # two triangular gussets per ear
            g = Part.Face(Part.makePolygon([V(gx, yo, BOT), V(gx, yo, BOT + 9), V(gx, yo + side * 9, BOT + 3.5),
                                            V(gx, yo + side * 9, BOT), V(gx, yo, BOT)]))
            e = e.fuse(g.extrude(V(1.5, 0, 0)))
        e = e.cut(slot(x, yo + side * 6.5, 2.3, 1.8, BOT - 1, BOT + 10))
        ears = e if ears is None else ears.fuse(e)
base = base.fuse(ears)
snap("Wall-mount ears", "4 slotted ears for Ø4 screws, gusseted", {"base": base})
base = base.removeSplitter()

# ================================================================== LID
lid_outer = loft(P["wall"], P["rim_z"], P["wall"] - (TOP - P["rim_z"]) * T, TOP)
lid_outer = fillet_edges_at(lid_outer, TOP, P["fillet"])
lid_view = lid_outer.copy(); lid_view.translate(V(0, 0, 0))
snap("Lid blank", "Flush lid, same 1° draft, R1.5 top edge", {"base": base, "lid": lid_outer}, focus="lid")

pocket = loft(P["lid_skirt_in"], P["rim_z"] - 0.01, P["lid_skirt_in"] - (P["lid_in_z"] - P["rim_z"]) * T, P["lid_in_z"])
lid = lid_outer.cut(pocket)
lid = lid.cut(band(P["groove"][0], P["groove"][1], P["rim_z"] - 0.01, P["rim_z"] + P["groove"][2]))
snap("Lid pocket + gasket groove", "Groove receives the tongue and a Ø1.6 TPE cord", {"base": base, "lid": lid}, focus="lid")

for (x, y) in BOSSES:
    lid = lid.fuse(cyl(P["boss_d"] / 2, P["rim_z"] + 0.3, P["lid_in_z"] + 0.1, x, y))
    lid = lid.cut(cyl(P["lid_hole"] / 2, P["rim_z"], TOP + 1, x, y))
    lid = lid.cut(cyl(P["cbore_d"] / 2, TOP - P["cbore_depth"], TOP + 1, x, y))
snap("Lid screw bosses", "Counterbored Ø3.7 holes, heads sit 3.5 mm deep", {"base": base, "lid": lid}, focus="lid")

ribs = box(P["ix0"] + 2, P["ix1"] - 2, 31 - P["rib_t"] / 2, 31 + P["rib_t"] / 2, P["lid_in_z"] - P["rib_h"], P["lid_in_z"] + 0.1)
ribs = ribs.fuse(box(44 - P["rib_t"] / 2, 44 + P["rib_t"] / 2, P["iy0"] + 2, P["iy1"] - 2, P["lid_in_z"] - P["rib_h"], P["lid_in_z"] + 0.1))
lid = lid.fuse(ribs.common(pocket))
snap("Stiffening ribs", "1.5 mm ribs (60 % of wall) stop the lid oil-canning", {"base": base, "lid": lid}, focus="lid_under")

for (x, y) in (LED_HEAT, LED_STATUS):
    lid = lid.fuse(cyl(3.0, 12.0, P["lid_in_z"] + 0.1, x, y))
    lid = lid.cut(cyl(1.6, 11.0, TOP + 1, x, y))
snap("Light-pipe holders", "Tubes guide Ø3 clear-PC light pipes onto the 2 LEDs", {"base": base, "lid": lid}, focus="lid_under")

bx, by = BUTTON
tx0, tx1, ty0, ty1 = bx - 5, bx + 5, by - 6, by + 8          # tongue; hinge at the +Y end
u = box(tx0 - 1, tx0, ty0 - 1, ty1, P["lid_in_z"] - 1, TOP + 1)
u = u.fuse(box(tx1, tx1 + 1, ty0 - 1, ty1, P["lid_in_z"] - 1, TOP + 1))
u = u.fuse(box(tx0 - 1, tx1 + 1, ty0 - 1, ty0, P["lid_in_z"] - 1, TOP + 1))
lid = lid.cut(u)
lid = lid.cut(box(tx0, tx1, ty0, ty1 - 2, TOP - 0.9, TOP + 1))             # finger dish -> 1.6 mm flex tongue
lid = lid.fuse(cyl(2.5, BUTTON_TOP + 1.0, P["lid_in_z"] + 0.1, bx, by))       # plunger, 1 mm above SW2
snap("Flex button", "Living cantilever + plunger presses the BOOST switch", {"base": base, "lid": lid}, focus="button")

emb = text("BOILI", 9.0, 40, 55, TOP - 0.01, 0.45)
tri = Part.Face(Part.makePolygon([V(-14, 44, 0), V(0, 44, 0), V(-7, 56.1, 0), V(-14, 44, 0)]))
tri_in = Part.Face(Part.makePolygon([V(-11.9, 45.2, 0), V(-2.1, 45.2, 0), V(-7, 53.7, 0), V(-11.9, 45.2, 0)]))
bolt = Part.Face(Part.makePolygon([V(-6.2, 52.6, 0), V(-8.6, 48.6, 0), V(-6.9, 48.6, 0), V(-8.0, 45.8, 0),
                                   V(-5.4, 49.6, 0), V(-7.1, 49.6, 0), V(-6.2, 52.6, 0)]))
warn = tri.cut(tri_in).fuse(bolt); warn.translate(V(0, 0, TOP - 0.01))
emb = emb.fuse(warn.extrude(V(0, 0, 0.4)))
emb = emb.fuse(text("230 V~", 3.2, -7, 40.5, TOP - 0.01, 0.4))
emb = emb.fuse(text("HEAT", 2.6, LED_HEAT[0], LED_HEAT[1] + 4.2, TOP - 0.01, 0.4))
emb = emb.fuse(text("STATUS", 2.6, LED_STATUS[0], LED_STATUS[1] - 4.2, TOP - 0.01, 0.4))
emb = emb.fuse(text("BOOST", 2.6, bx, ty0 - 3.6, TOP - 0.01, 0.4))
lid = lid.fuse(emb).removeSplitter()
snap("Embossed graphics", "0.4 mm raised text and the 230 V hazard symbol", {"base": base, "lid": lid}, focus="lid")

# ================================================================== purchased / secondary parts
lp = None
for (x, y) in (LED_HEAT, LED_STATUS):
    r = cyl(1.5, P["standoff_h"] + 3.4, TOP + 0.2, x, y).fuse(Part.makeSphere(1.5, V(x, y, TOP + 0.2)))
    lp = r if lp is None else lp.fuse(r)
path = outline((P["groove"][0] + P["groove"][1]) / 2, P["rim_z"] + P["tongue"][2] + 0.8).OuterWire
e0 = path.Edges[0]
circ = Part.Wire(Part.makeCircle(0.8, e0.valueAt(e0.FirstParameter), e0.tangentAt(e0.FirstParameter)))
try:
    gasket = path.makePipeShell([circ], True, False)
except Exception as ex:
    print("gasket sweep failed", ex); gasket = band(P["groove"][0] + 0.1, P["groove"][1] - 0.1, P["rim_z"] + 2, P["rim_z"] + 2.9)
glands = None
for gy in GLANDS_Y:
    x0 = P["ix0"] - P["wall"]
    g = Part.makeCylinder(8.0, P["wall"] + 4, V(x0 - 0.5, gy, P["gland_z"]), V(1, 0, 0))     # thread + inner nut
    nut = Part.makePolygon([V(x0 + P["wall"] + 0.45, gy + 11 * math.cos(math.radians(a)), P["gland_z"] + 11 * math.sin(math.radians(a))) for a in range(0, 361, 60)])
    g = g.fuse(Part.Face(nut).extrude(V(5, 0, 0)))
    body = Part.makePolygon([V(x0, gy + 11 * math.cos(math.radians(a)), P["gland_z"] + 11 * math.sin(math.radians(a))) for a in range(30, 391, 60)])
    g = g.fuse(Part.Face(body).extrude(V(-8, 0, 0)))
    g = g.fuse(Part.makeCone(9.0, 6.0, 12, V(x0 - 8, gy, P["gland_z"]), V(-1, 0, 0)))
    g = g.cut(Part.makeCylinder(4.0, 40, V(x0 - 25, gy, P["gland_z"]), V(1, 0, 0)))
    glands = g if glands is None else glands.fuse(g)
screws = None
for (x, y) in BOSSES:
    s = cyl(1.75, P["rim_z"] - 12, TOP - P["cbore_depth"], x, y).fuse(cyl(3.2, TOP - P["cbore_depth"], TOP - P["cbore_depth"] + 2.4, x, y))
    s = s.cut(box(x - 0.4, x + 0.4, y - 2.2, y + 2.2, TOP - P["cbore_depth"] + 1.4, TOP))
    screws = s if screws is None else screws.fuse(s)

# ================================================================== PCB fit check
doc = FreeCAD.newDocument("Housing")
Import.insert(f"{OUT}/pcb.step", doc.Name)
pcb_shapes = [o.Shape.copy() for o in doc.Objects if hasattr(o, "Shape") and o.TypeId == "Part::Feature" and o.Shape.Volume > 0.01]
pcb = Part.Compound(pcb_shapes); pcb.translate(V(-100, 162, P["standoff_h"]))
relay = box(31.1 - 10.25, 31.1 + 10.25, (62 - 49.8) - 5.05, (62 - 49.8) + 5.05, P["standoff_h"] + 1.6, P["standoff_h"] + 1.6 + 15.3)
for n in [o.Name for o in doc.Objects]:
    if doc.getObject(n): doc.removeObject(n)
snap("Drop in the populated PCB", "Interference check against every 3D part", {"base": base, "lid": lid}, focus="pcb")

report = {}
for name, shp in (("base", base), ("lid", lid)):
    clash = 0.0
    for s in pcb_shapes + [relay]:
        ss = s.copy()
        if s is not relay: ss.translate(V(-100, 162, P["standoff_h"]))
        try: clash += shp.common(ss).Volume
        except Exception: pass
    report[name] = round(clash, 4)
bb_pcb = pcb.BoundBox
report["pcb_top_z"] = round(max(bb_pcb.ZMax, relay.BoundBox.ZMax), 2)
report["lid_clearance_mm"] = round(P["lid_in_z"] - P["rib_h"] - report["pcb_top_z"], 2)
report["pin_clearance_mm"] = round(bb_pcb.ZMin, 2)
report["volume_cm3"] = {"base": round(base.Volume / 1000, 1), "lid": round(lid.Volume / 1000, 1)}
report["mass_g_PC_ABS"] = {k: round(v * 1.15, 1) for k, v in report["volume_cm3"].items()}
report["outer_mm"] = [round(x, 1) for x in (base.BoundBox.XLength, base.BoundBox.YLength, TOP - BOT)]
report["valid"] = {"base": base.isValid(), "lid": lid.isValid()}
gl_clash = 0.0
for s in pcb_shapes:
    ss = s.copy(); ss.translate(V(-100, 162, P["standoff_h"])); gl_clash += glands.common(ss).Volume
report["glands_vs_pcb"] = round(gl_clash, 4)
report["glands_vs_base"] = round(glands.common(base.cut(Part.Compound([Part.makeCylinder(P["gland_hole"] / 2 + 0.01, 12, V(P["ix0"] - P["wall"] - 6, gy, P["gland_z"]), V(1, 0, 0)) for gy in GLANDS_Y]))).Volume, 4)
report["glands_vs_lid"] = round(glands.common(lid).Volume, 4)
print("FIT", json.dumps(report))
json.dump(report, open(f"{OUT}/fit_report.json", "w"), indent=1)

snap("Light pipes, gasket, glands, screws", "Purchased + secondary parts complete the assembly",
     {"base": base, "lid": lid, "lightpipes": lp, "gasket": gasket, "glands": glands, "screws": screws}, focus="final")

# ================================================================== exports
os.makedirs(f"{OUT}/export", exist_ok=True)
objs = {}
for name, shp, col in (("Base", base, (0.20, 0.22, 0.25)), ("Lid", lid, (0.85, 0.86, 0.88)),
                       ("LightPipes", lp, (0.9, 0.9, 1.0)), ("Gasket", gasket, (0.05, 0.05, 0.05)),
                       ("CableGlands", glands, (0.15, 0.15, 0.15)), ("Screws", screws, (0.7, 0.7, 0.72))):
    o = doc.addObject("Part::Feature", name); o.Shape = shp; objs[name] = o
    shp.exportStep(f"{OUT}/export/spot_heater_{name.lower()}.step")
Import.insert(f"{OUT}/pcb.step", doc.Name)
for o in doc.Objects:
    if o.TypeId == "Part::Feature" and o.Name not in objs and o.Shape.Volume > 0:
        o.Placement.move(V(-100, 162, P["standoff_h"]))
sp = doc.addObject("Spreadsheet::Sheet", "Parameters")
for i, (k, v) in enumerate(P.items(), 1):
    sp.set(f"A{i}", k); sp.set(f"B{i}", str(v))
doc.recompute()
Import.export([objs["Base"], objs["Lid"], objs["LightPipes"], objs["Gasket"], objs["CableGlands"], objs["Screws"]],
              f"{OUT}/export/spot_heater_enclosure_assembly.step")
doc.saveAs(f"{OUT}/export/spot_heater_enclosure.FCStd")
json.dump(dict(steps=STEPS, params=P, top=TOP, bot=BOT), open(f"{OUT}/steps/steps.json", "w"), indent=1)
print("DONE", len(STEPS), "steps")
