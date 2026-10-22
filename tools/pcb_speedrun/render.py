"""PCB design speed-run: schematic capture -> ERC -> placement -> routing -> pour -> DRC -> layer stack -> 3D.
usage: render.py A B  (frames A..B inclusive) -> /home/claude/pcbrun/frames/p_####.png"""
import sys, os, json, math, heapq
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, "/home/claude/pcbrun")
import draw as DR
from draw import View, COL, SS, W, H

OUT = "/home/claude/pcbrun/frames"; os.makedirs(OUT, exist_ok=True)
FD = "/opt/k9/usr/share/fonts/truetype/dejavu/"
F = lambda n, s: ImageFont.truetype(FD + n, int(s))
FPSV = 24

# =========================================================== timeline
SEC = dict(mains=(0, 92), power=(92, 150), driver=(150, 226), esp=(226, 344), erc=(344, 384),
           outline=(396, 440), place=(440, 604), r_mains=(604, 664), r_power=(664, 734), r_sig=(734, 814),
           pour=(814, 856), drc=(856, 904), layers=(904, 1036), final=(1036, 1150))
STEP_NAMES = ["Schematic: mains input", "Schematic: 5 V / 3.3 V", "Schematic: relay driver", "Schematic: ESP32 + UI",
              "ERC", "Board outline + rules", "Place footprints", "Route mains (1.5 mm)", "Route power",
              "Route signals", "GND pour + silkscreen", "DRC", "Layer stack check", "Gerbers + 3D"]
STEP_KEYS = ["mains", "power", "driver", "esp", "erc", "outline", "place", "r_mains", "r_power", "r_sig", "pour", "drc", "layers", "final"]
STEP_DETAIL = ["Terminals, fuse, varistor, HLK-PM01, relay", "AMS1117 + decoupling", "AO3400A low-side switch, flyback diode, LED",
               "ESP32-WROOM-32E, reset/boot, status LED, headers", "0 errors · 0 warnings", "96.5 × 62 mm, 2 layers, 6 mm mains rule",
               "Import netlist, drag every part into place", "1.5 mm tracks, 2 mm clearance", "5 V, 3.3 V, relay drive",
               "ESP32 I/O, LEDs, programming header", "Bottom-layer ground plane, low-voltage side only", "0 violations · 0 unconnected · parity OK",
               "Silkscreen / mask / copper / FR-4 / copper / mask", "Fab files exported, board populated"]
ENDS = [SEC[k][1] for k in STEP_KEYS[:-1]] + [1086]
STARTS = [SEC[k][0] for k in STEP_KEYS]
STOP = 1086
TOTAL = 1150

def ease(t): t = max(0.0, min(1.0, t)); return t * t * (3 - 2 * t)
def lerp(a, b, t): return a + (b - a) * t
def lerp2(a, b, t): return (lerp(a[0], b[0], t), lerp(a[1], b[1], t))

# =========================================================== schematic data
SM = json.load(open("/home/claude/pcbrun/sch_meta.json"))
K = SM["K"]
SCH_IMG = np.asarray(Image.open("/home/claude/pcbrun/sch-1.png").convert("RGB")).astype(np.float32)
SCH_BG = np.array([245, 244, 239], np.float32)
LAB = np.load("/home/claude/pcbrun/sch_lab.npy")
SYM_T = {}
for sec, refs in SM["order"]:
    key = {"Mains input": "mains", "5 V -> 3.3 V": "power", "Relay driver": "driver", "ESP32 + UI": "esp"}[sec]
    s0 = SEC[key][0]
    step = {"mains": 11, "power": 10, "driver": 10, "esp": 9}[key]
    for i, r in enumerate(refs): SYM_T[r] = s0 + 8 + i * step
for i, r in enumerate(SM["flags"]): SYM_T[r] = 70 + 4 * i
TEXT_T = {"MAINS 230": 4, "K1 contact": 80, "POWER": 94, "RELAY DRIVER": 152, "R4 holds": 214, "ESP32 + UI": 228, "J3: connect": 330}
owner_t = []
for o in SM["owner"]:
    if o.startswith("TEXT:"):
        owner_t.append(next(v for k, v in TEXT_T.items() if o[5:].startswith(k[:min(len(k), 15)])))
    else:
        owner_t.append(SYM_T[o])
owner_t = np.array(owner_t, np.float32)
TMAP = np.full(LAB.shape, 1e9, np.float32)
TMAP[LAB >= 0] = owner_t[LAB[LAB >= 0]]
TMAP[LAB == -2] = -100
SYM_EVENTS = sorted((t, r) for r, t in SYM_T.items())

def sch_anchor(r):
    x, y = SM["syms"][r]; return (x, y)

def sch_camera(f):
    """camera centre (mm on sheet) and scale (screen px per mm)."""
    pts = [(t, sch_anchor(r)) for t, r in SYM_EVENTS]
    def cursor_mm(t):
        if t <= pts[0][0]: return pts[0][1]
        for (t0, p0), (t1, p1) in zip(pts, pts[1:]):
            if t0 <= t <= t1: return lerp2(p0, p1, ease((t - t0) / (t1 - t0)))
        return pts[-1][1]
    acc = [0, 0]; n = 0
    for k in range(-14, 15, 2):
        p = cursor_mm(f + k); acc[0] += p[0]; acc[1] += p[1]; n += 1
    c = (acc[0] / n, acc[1] / n)
    s = 6.6
    z = ease((f - SEC["erc"][0]) / 26)
    c = lerp2(c, (210, 150), z); s = lerp(s, 2.12, z)
    return c, s, cursor_mm(f)

SCR_C = (860, 352)
def sch_frame(f):
    c, s, cur = sch_camera(f)
    alpha = np.clip((f - TMAP) / 5.0, 0, 1)[..., None]
    page = SCH_BG + (SCH_IMG - SCH_BG) * alpha
    page_im = Image.fromarray(page.astype(np.uint8))
    # map screen (X,Y) -> page px: px = K*(c + (X - SCR_C)/s)
    a = K / s
    box = page_im.transform((W, H), Image.AFFINE, (a, 0, K * c[0] - a * SCR_C[0], 0, a, K * c[1] - a * SCR_C[1]),
                            resample=Image.BILINEAR, fillcolor=(60, 64, 72))
    d = ImageDraw.Draw(box, "RGBA")
    def scr(mm): return (SCR_C[0] + (mm[0] - c[0]) * s, SCR_C[1] + (mm[1] - c[1]) * s)
    # selection highlight on freshly placed symbols
    for t, r in SYM_EVENTS:
        if t <= f < t + 9 and r in SM["bbox"]:
            x0, y0, x1, y1 = SM["bbox"][r]
            p0, p1 = scr((x0 / K - 1, y0 / K - 1)), scr((x1 / K + 1, y1 / K + 1))
            k = 1 - (f - t) / 9
            d.rounded_rectangle((p0[0], p0[1], p1[0], p1[1]), 4, fill=(120, 180, 255, int(60 * k)), outline=(60, 130, 255, int(230 * k)), width=2)
    cursor = scr(cur) if f < SEC["erc"][0] + 6 else None
    clicks = [t for t, _ in SYM_EVENTS if 0 <= f - t < 7]
    return box, cursor, clicks

# =========================================================== board data
BD = DR.D
FP = {f["ref"]: f for f in BD["footprints"]}
PARTS = [f for f in BD["footprints"] if not f["board_only"]]
HOLES = [f for f in BD["footprints"] if f["board_only"]]
V0 = View(48.25, 31, 8.6)

def fp_bbox(f):
    xs, ys = [], []
    for p in f["pads"]:
        xs += [p["local"][0] - p["size"][0] / 2, p["local"][0] + p["size"][0] / 2]
        ys += [p["local"][1] - p["size"][1] / 2, p["local"][1] + p["size"][1] / 2]
    for pl in f["gfx"].get("F.CrtYd", []):
        for q in pl: xs.append(q[0]); ys.append(q[1])
    return min(xs), min(ys), max(xs), max(ys)

# pile: shelf-pack all parts (unrotated) as "imported" next to each other
order_place = sorted(PARTS, key=lambda f: -(fp_bbox(f)[2] - fp_bbox(f)[0]) * (fp_bbox(f)[3] - fp_bbox(f)[1]))
PILE = {}
x, y, rowh = 2.0, 2.0, 0
for f in order_place:
    x0, y0, x1, y1 = fp_bbox(f); w, h = x1 - x0, y1 - y0
    if x + w > 95: x, y, rowh = 2.0, y + rowh + 1.2, 0
    PILE[f["ref"]] = (x - x0, y - y0); x += w + 1.2; rowh = max(rowh, h)
PLACE_T = {f["ref"]: SEC["place"][0] + 12 + i * 4.5 for i, f in enumerate(order_place)}
MOVE = 14

def fp_pose(ref, f):
    if f < SEC["place"][0]: return None
    t0 = PLACE_T[ref]; k = ease((f - t0) / MOVE)
    a = FP[ref]["angle"]
    return lerp2(PILE[ref], FP[ref]["pos"], k), a * k, (0 < (f - t0) < MOVE)

# nets
NETS = {}
for fp in PARTS:
    for p in fp["pads"]:
        if p["net"] and not p["net"].startswith("unconnected"):
            NETS.setdefault(p["net"], []).append((fp["ref"], p["num"]))
NETS = {k: v for k, v in NETS.items() if len(v) > 1}

def mst(points):
    n = len(points)
    if n < 2: return []
    used = [False] * n; used[0] = True; best = [(math.dist(points[0], p), 0) for p in points]; edges = []
    for _ in range(n - 1):
        j = min((i for i in range(n) if not used[i]), key=lambda i: best[i][0])
        used[j] = True; edges.append((points[best[j][1]], points[j]))
        for i in range(n):
            if not used[i]:
                dd = math.dist(points[j], points[i])
                if dd < best[i][0]: best[i] = (dd, j)
    return edges

# routing schedule
GROUPS = dict(r_mains=["/L_IN", "/L_F", "/N", "/L_SW"],
              r_power=["+5V", "+3V3", "/RELAY_DRV", "GND"],
              r_sig=["/HEAT_EN", "/GATE", "/LED_K1", "/STATUS_LED", "/LED_K2", "/EN", "/IO0", "/TXD0", "/RXD0", "/TEMP_1W"])
def snap(p): return (round(p[0], 2), round(p[1], 2))
SEG_T = []          # (track, t0, t1)
VIA_T = []          # (via, t)
NET_DONE = {}
for g, nets in GROUPS.items():
    g0, g1 = SEC[g]
    plans = []
    for net in nets:
        segs = [t for t in BD["tracks"] if t["net"] == net]
        adj = {}
        for t in segs:
            a, b = snap(t["a"]), snap(t["b"]); L = math.dist(a, b)
            adj.setdefault(a, []).append((b, L)); adj.setdefault(b, []).append((a, L))
        dist = {}; offset = 0.0
        pads = [DR.pad_world(r, n) for r, n in NETS.get(net, [])]
        nodes = list(adj)
        while len(dist) < len(nodes):
            rest = [n for n in nodes if n not in dist]
            src = min(rest, key=lambda n: min(math.dist(n, p) for p in pads) if pads else 0) if not dist else rest[0]
            dd = {src: offset}; pq = [(offset, src)]
            while pq:
                d0, n = heapq.heappop(pq)
                if d0 > dd.get(n, 1e18): continue
                for m, L in adj[n]:
                    if m not in dist and d0 + L < dd.get(m, 1e18): dd[m] = d0 + L; heapq.heappush(pq, (d0 + L, m))
            dist.update(dd); offset = max(dd.values()) + 2
        plans.append((net, segs, dist, max(dist.values()) if dist else 1))
    total = sum(p[3] for p in plans)
    span = (g1 - g0 - 8)
    # nets overlap: net i starts when 55 % of the previous one is done
    eff = sum(p[3] for p in plans[:-1]) * 0.55 + plans[-1][3]
    spd = eff / span
    t = g0 + 2
    for net, segs, dist, L in plans:
        dur = L / spd
        for s in segs:
            da, db = dist[snap(s["a"])], dist[snap(s["b"])]
            if db < da: s = dict(s, a=s["b"], b=s["a"]); da, db = db, da
            SEG_T.append((s, t + da / spd, t + db / spd + 0.6))
        for v in BD["vias"]:
            if v["net"] == net:
                n = min(dist, key=lambda q: math.dist(q, v["pos"])); VIA_T.append((v, t + dist[n] / spd))
        NET_DONE[net] = t + dur + 1
        t += dur * 0.55
NET_DONE["GND"] = SEC["pour"][0] + 30
ZONE_LAY, ZONE_MASK = DR.zone_image(V0)
POUR_C = V0.p(75, 32)

ISO_PATH = [(24.6, 0.5), (24.6, 16.2), (45, 16.2), (45, 40.4), (35, 40.4), (35, 61.5)]

def pcb_frame(f):
    v = V0
    im, d = DR.new_canvas()
    DR.draw_grid(d, v)
    if f >= SEC["outline"][0]:
        DR.draw_edge(d, v, frac=ease((f - SEC["outline"][0] - 2) / 20))
        for i, h in enumerate(HOLES):
            if f >= SEC["outline"][0] + 24 + i * 3:
                DR.draw_footprint(d, v, h, label=False)
    # pour
    if f >= SEC["pour"][0]:
        r = ease((f - SEC["pour"][0]) / 26) * 1000 * SS
        m = Image.new("L", im.size, 0); ImageDraw.Draw(m).ellipse((POUR_C[0] - r, POUR_C[1] - r, POUR_C[0] + r, POUR_C[1] + r), fill=255)
        from PIL import ImageChops
        mm_ = ImageChops.multiply(m, ZONE_MASK)
        col = Image.new("RGBA", im.size, (*COL["zone"], 110))
        im.paste(col, (0, 0), mm_)
        d = ImageDraw.Draw(im, "RGBA")
    # tracks: bottom first, then top
    heads = []
    for layer in ("B.Cu", "F.Cu"):
        for s, t0, t1 in SEG_T:
            if s["layer"] != layer or f < t0: continue
            fr = min(1, (f - t0) / max(t1 - t0, 0.3))
            DR.draw_track(d, v, s, frac=fr)
            if fr < 1: heads.append(lerp2(s["a"], s["b"], fr))
    # footprints
    poses = {}
    if f >= SEC["place"][0]:
        for fp in PARTS:
            pos, ang, moving = fp_pose(fp["ref"], f)
            poses[fp["ref"]] = (pos, ang)
            a_in = int(255 * ease((f - SEC["place"][0]) / 8))
            DR.draw_footprint(d, v, fp, pos=pos, ang=ang, alpha=a_in, crt=moving, glow=0.9 if moving else 0)
    for via, t in VIA_T:
        if f >= t: DR.draw_via(d, v, via)
    if f >= SEC["pour"][0] + 18:
        DR.draw_silk_board(d, v, alpha=int(255 * ease((f - SEC["pour"][0] - 18) / 12)))
    # ratsnest
    if f >= SEC["place"][0]:
        for net, pads in NETS.items():
            if f >= NET_DONE.get(net, 1e9): continue
            pts = [DR.pad_world(r, n, *poses[r]) for r, n in pads]
            k = 1.0 if f < NET_DONE.get(net, 1e9) - 6 else (NET_DONE[net] - f) / 6
            for a, b in mst(pts):
                d.line([v.p(*a), v.p(*b)], fill=(*COL["rats"], int(150 * k)), width=SS)
    # routing heads
    for hpos in heads:
        px, py = v.p(*hpos); r = 4 * SS
        d.ellipse((px - r, py - r, px + r, py + r), fill=(255, 255, 255, 230))
    # DRC sweep + isolation
    f0 = SEC["drc"][0]
    if f0 <= f < f0 + 26:
        x = lerp(-2, 99, (f - f0) / 26); p0, p1 = v.p(x, -2), v.p(x, 64)
        for k, a in ((10, 40), (5, 90), (1.5, 220)):
            d.line([p0, p1], fill=(80, 255, 140, a), width=int(k * SS * 2))
    if f0 + 20 <= f < SEC["drc"][1] + 10:
        a = ease((f - f0 - 20) / 8)
        pts = [v.p(*q) for q in ISO_PATH]
        for k, al in ((14, 50), (7, 110), (2.5, 255)):
            d.line(pts, fill=(255, 120, 40, int(al * a)), width=int(k * SS), joint="curve")
        tx, ty = v.p(36.5, 47)
        d.text((tx, ty), "≥ 6 mm", font=F("DejaVuSans-Bold.ttf", 15 * SS), fill=(255, 170, 90, int(255 * a)), anchor="lm")
    cursor = None
    if SEC["place"][0] <= f < SEC["place"][1]:
        act = [r for r in PLACE_T if PLACE_T[r] <= f < PLACE_T[r] + MOVE]
        if act: cursor = DR_screen(v, poses[act[-1]][0])
    elif f >= SEC["r_mains"][0] and heads:
        cursor = DR_screen(v, heads[-1])
    return DR.finish(im), cursor

def DR_screen(v, p):
    x, y = v.p(*p); return (x / SS, y / SS)

# =========================================================== layer stack
LDIR = "/home/claude/pcbrun/layers"
R_L, OXP, OYP = 20.0, 1.0, 295.0          # layer raster: px per mm and board origin (px)
def load_mask(name):
    a = np.asarray(Image.open(f"{LDIR}/{name}.png").convert("L")).astype(np.float32)
    return 1 - a / 255.0
_edge = load_mask("Edge.Cuts")
BOARD = np.zeros_like(_edge)
ys, xs = np.nonzero(_edge > 0.5)
from PIL import ImageDraw as _ID
_bm = Image.new("L", (_edge.shape[1], _edge.shape[0]), 0)
_ID.Draw(_bm).rounded_rectangle((OXP, OYP, OXP + 96.5 * R_L, OYP + 62 * R_L), radius=3 * R_L, fill=255)
BOARD = np.asarray(_bm).astype(np.float32) / 255
def rgba(color, alpha_arr, a=1.0):
    h, w = alpha_arr.shape
    out = np.zeros((h, w, 4), np.uint8); out[..., :3] = color; out[..., 3] = np.clip(alpha_arr * 255 * a, 0, 255)
    return Image.fromarray(out, "RGBA")
fcu, bcu, silk = load_mask("F.Cu"), load_mask("B.Cu"), load_mask("F.Silkscreen")
fmask_open, bmask_open = load_mask("F.Mask"), load_mask("B.Mask")
GREEN = (18, 96, 52); COPPER = (205, 135, 62); FR4 = (196, 182, 120)
LAYERS = [  # bottom -> top: name, image
    ("Bottom solder mask", rgba(GREEN, BOARD * (1 - bmask_open), 0.80)),
    ("Bottom copper", rgba(COPPER, bcu * BOARD)),
    ("FR-4 core 1.6 mm", rgba(FR4, BOARD)),
    ("Top copper", rgba(COPPER, fcu * BOARD)),
    ("Top solder mask", rgba(GREEN, BOARD * (1 - fmask_open), 0.62)),
    ("Silkscreen", rgba((245, 245, 240), silk * BOARD)),
]

def basis(k):
    """board mm -> screen px basis vectors; k=0 top-down (matches the editor view), k=1 isometric."""
    s0, s1 = 8.6, 5.6
    a = math.radians(26 * k); t = lerp(1.0, 0.40, k); s = lerp(s0, s1, k)
    ex = (s * math.cos(a), s * math.sin(a) * t)
    ey = (-s * math.sin(a), s * math.cos(a) * t)
    return ex, ey

def stack_frame(f):
    f0 = SEC["layers"][0]
    tilt = ease((f - f0 - 12) / 40) if f < f0 + 106 else 1.0
    sep = ease((f - f0 - 18) / 34) * 66 if f < f0 + 106 else (1 - ease((f - f0 - 106) / 22)) * 66
    ex, ey = basis(tilt)
    # keep the board centre where the editor view had it, moving to (820, 395) in iso
    cx, cy = lerp(818, 760, tilt), lerp(352, 372, tilt)
    O = (cx - 48.25 * ex[0] - 31 * ey[0], cy - 48.25 * ex[1] - 31 * ey[1])
    im = Image.new("RGBA", (W * SS, H * SS), (*COL["bg"], 255))
    d = ImageDraw.Draw(im, "RGBA")
    M = np.array([[ex[0], ey[0]], [ex[1], ey[1]]]) * SS
    Mi = np.linalg.inv(M)
    labels = []
    for i, (name, lay) in enumerate(LAYERS):
        z = (i - 2.5) * sep
        ox, oy = O[0] * SS, (O[1] - z) * SS
        # screen -> mm: Mi @ (X-ox, Y-oy); mm -> layer px: R_L*mm + origin
        a, b = Mi[0]; c_, d_ = Mi[1]
        coeffs = (R_L * a, R_L * b, R_L * (-a * ox - b * oy) + OXP, R_L * c_, R_L * d_, R_L * (-c_ * ox - d_ * oy) + OYP)
        tl = lay.transform(im.size, Image.AFFINE, coeffs, resample=Image.BILINEAR)
        if name.startswith("FR-4"):
            for dz in range(int(6 * SS), 0, -2):          # core edge thickness
                sh = lay.transform(im.size, Image.AFFINE, (coeffs[0], coeffs[1], coeffs[2] - coeffs[1] * dz, coeffs[3], coeffs[4], coeffs[5] - coeffs[4] * dz), resample=Image.BILINEAR)
                dark = Image.new("RGBA", im.size, (120, 110, 70, 255)); im.paste(dark, (0, 0), sh)
        im.alpha_composite(tl)
        corner = (O[0] + 96.5 * ex[0] + 62 * ey[0], O[1] + 96.5 * ex[1] + 62 * ey[1] - z)
        right = (O[0] + 96.5 * ex[0] + 31 * ey[0], O[1] + 96.5 * ex[1] + 31 * ey[1] - z)
        labels.append((name, right))
    la = ease((f - f0 - 46) / 10) * (1 - ease((f - f0 - 100) / 8))
    if la > 0:
        fo = F("DejaVuSans-Bold.ttf", 17 * SS)
        for name, (x, y) in labels:
            lx = 1075 * SS
            d.line([(x * SS + 6 * SS, y * SS), (lx - 10 * SS, y * SS)], fill=(255, 255, 255, int(160 * la)), width=SS)
            d.ellipse((x * SS + 2 * SS, y * SS - 4 * SS, x * SS + 10 * SS, y * SS + 4 * SS), fill=(255, 210, 60, int(255 * la)))
            tw = d.textlength(name, font=fo)
            d.rounded_rectangle((lx - 8 * SS, y * SS - 13 * SS, lx + tw + 8 * SS, y * SS + 13 * SS), 6 * SS, fill=(12, 16, 24, int(210 * la)))
            d.text((lx, y * SS), name, font=fo, fill=(255, 255, 255, int(255 * la)), anchor="lm")
    return im.convert("RGB").resize((W, H), Image.LANCZOS)

# =========================================================== HUD
f_row, f_rowb, f_hdr, f_small = F("DejaVuSans.ttf", 14), F("DejaVuSans-Bold.ttf", 14), F("DejaVuSans-Bold.ttf", 16), F("DejaVuSans.ttf", 12)
f_timer, f_timer_ms = F("DejaVuSansMono-Bold.ttf", 52), F("DejaVuSansMono-Bold.ttf", 30)
f_cap, f_capd, f_big = F("DejaVuSans-Bold.ttf", 26), F("DejaVuSans.ttf", 18), F("DejaVuSans-Bold.ttf", 30)
PB = [(e / FPSV) + round(math.sin(i * 2.3) * 0.4 + 0.15, 2) for i, e in enumerate(ENDS)]
def tfmt(sec):
    m, s = divmod(max(sec, 0), 60); return f"{int(m)}:{s:05.2f}"

def hud(im, f, cursor=None, clicks=()):
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    x0, y0, pw, rh = 14, 14, 340, 23
    ph = 56 + rh * len(STEP_NAMES) + 34
    cur = max(i for i in range(len(STARTS)) if f >= STARTS[i])
    d.rounded_rectangle((x0, y0, x0 + pw, y0 + ph), 12, fill=(12, 16, 24, 215))
    d.text((x0 + 14, y0 + 10), "SPOT HEATER PCB", font=f_hdr, fill=(255, 255, 255))
    d.text((x0 + 14, y0 + 32), "KiCad 9  ·  2 layers  ·  Any% (scripted)", font=f_small, fill=(150, 170, 200))
    for i, n in enumerate(STEP_NAMES):
        y = y0 + 56 + i * rh; done = f >= ENDS[i]
        if i == cur and not done: d.rounded_rectangle((x0 + 6, y - 2, x0 + pw - 6, y + rh - 3), 5, fill=(40, 90, 200, 230))
        d.text((x0 + 14, y + 2), n, font=f_rowb if i == cur else f_row, fill=(255, 255, 255) if (done or i == cur) else (150, 160, 175))
        if done:
            sp = ENDS[i] / FPSV; dl = sp - PB[i]
            d.text((x0 + pw - 120, y + 2), f"{dl:+.2f}", font=f_row, fill=(60, 220, 110) if dl < 0 else (240, 80, 70))
            d.text((x0 + pw - 60, y + 2), tfmt(sp), font=f_row, fill=(255, 255, 255))
        else:
            d.text((x0 + pw - 60, y + 2), tfmt(PB[i]), font=f_row, fill=(110, 120, 135))
    yb = y0 + 56 + rh * len(STEP_NAMES) + 6
    d.line([(x0 + 12, yb), (x0 + pw - 12, yb)], fill=(70, 80, 95), width=1)
    d.text((x0 + 14, yb + 7), "Previous segment", font=f_small, fill=(150, 160, 175))
    if cur > 0: d.text((x0 + pw - 60, yb + 7), f"{(ENDS[cur - 1] - STARTS[cur - 1]) / FPSV:.2f}", font=f_small, fill=(255, 255, 255))
    t = min(f, STOP) / FPSV
    ahead = all(ENDS[i] / FPSV - PB[i] < 0.3 for i in range(len(ENDS)) if f >= ENDS[i])
    col = (255, 210, 60) if f >= STOP else ((60, 230, 120) if ahead else (240, 80, 70))
    s = tfmt(t); main, ms = s[:-3], s[-3:]
    ty = y0 + ph + 8
    d.rounded_rectangle((x0, ty - 4, x0 + pw, ty + 66), 12, fill=(12, 16, 24, 215))
    tw = d.textlength(main, font=f_timer)
    d.text((x0 + 8 + pw - 30 - tw - d.textlength(ms, font=f_timer_ms), ty), main, font=f_timer, fill=col)
    d.text((x0 + 8 + pw - 30 - d.textlength(ms, font=f_timer_ms), ty + 18), ms, font=f_timer_ms, fill=col)
    # caption
    if f < STOP:
        a = min(1, (f - STARTS[cur]) / 6)
        title = f"{cur + 1:02d}  {STEP_NAMES[cur]}"; det = STEP_DETAIL[cur]
        tw = max(d.textlength(title, font=f_cap), d.textlength(det, font=f_capd))
        bx = W - 24 - tw - 32
        d.rounded_rectangle((bx, H - 104, W - 24, H - 22), 12, fill=(12, 16, 24, int(215 * a)))
        d.text((bx + 16, H - 96), title, font=f_cap, fill=(255, 255, 255, int(255 * a)))
        d.text((bx + 16, H - 56), det, font=f_capd, fill=(170, 200, 240, int(255 * a)))
    # badges
    def badge(msg, sub, a, color=(20, 120, 60)):
        tw = max(d.textlength(msg, font=f_big), d.textlength(sub, font=f_capd)); bx = (W - tw) / 2 + 170
        d.rounded_rectangle((bx - 20, 22, bx + tw + 20, 112), 14, fill=(*color, int(225 * a)))
        d.text((bx, 32), msg, font=f_big, fill=(255, 255, 255, int(255 * a)))
        d.text((bx, 76), sub, font=f_capd, fill=(220, 255, 230, int(255 * a)))
    e0, e1 = SEC["erc"]
    if e0 + 14 <= f < e1 + 6: badge("ERC: 0 errors · 0 warnings  ✓", f"{len(PARTS)} parts · {len(NETS)} nets · every pin connected or flagged", ease((f - e0 - 14) / 6))
    o0 = SEC["outline"][0]
    if o0 + 10 <= f < SEC["outline"][1] + 6:
        badge("Net classes", "Mains 1.5 mm / 2 mm  ·  Power 0.6 mm  ·  Default 0.3 mm  ·  mains↔LV 6 mm", ease((f - o0 - 10) / 6), (40, 70, 140))
    d0, d1 = SEC["drc"]
    if d0 + 26 <= f < d1 + 8: badge("DRC: 0 violations  ✓", "0 unconnected pads  ·  schematic parity OK  ·  6 mm creepage rule passes", ease((f - d0 - 26) / 6))
    g0 = SEC["final"][0]
    if g0 + 12 <= f < STOP + 4:
        badge("Fab outputs ✓", "Gerbers · Excellon drill · BOM · pick-and-place · STEP", ease((f - g0 - 12) / 6), (40, 70, 140))
    if f >= STOP - 4:
        a = ease((f - STOP + 4) / 10)
        lines = [("RUN COMPLETE", f_big, (255, 210, 60)), (f"Final time {tfmt(STOP / FPSV)}", f_cap, (255, 255, 255)), ("", f_capd, (0, 0, 0)),
                 (f"{len(PARTS)} parts · {len(NETS)} nets · {len(BD['tracks'])} tracks · {len(BD['vias'])} vias", f_capd, (210, 225, 245)),
                 ("96.5 × 62 mm, 2 layers, 1.6 mm FR-4", f_capd, (210, 225, 245)),
                 ("ERC 0 · DRC 0 · 6 mm mains isolation", f_capd, (120, 230, 150))]
        tw = max(d.textlength(s_, font=fo) for s_, fo, _ in lines); bx, by = W - 24 - tw - 40, 24
        hgt = sum(40 if fo is not f_capd else 28 for _, fo, _ in lines) + 30
        d.rounded_rectangle((bx, by, W - 24, by + hgt), 14, fill=(12, 16, 24, int(225 * a)))
        yy = by + 16
        for s_, fo, c in lines:
            d.text((bx + 20, yy), s_, font=fo, fill=(*c, int(255 * a))); yy += 40 if fo is not f_capd else 28
    # mouse cursor
    if cursor:
        x, y = cursor
        for t in clicks:
            pass
        if clicks:
            r = 6 + 4 * len(clicks)
            d.ellipse((x - r, y - r, x + r, y + r), outline=(255, 210, 60, 200), width=2)
        arrow = [(0, 0), (0, 17), (4.5, 13), (7.5, 20), (10, 19), (7, 12), (12.5, 12)]
        d.polygon([(x + 1 + p[0], y + 1 + p[1]) for p in arrow], fill=(0, 0, 0, 90))
        d.polygon([(x + p[0], y + p[1]) for p in arrow], fill=(255, 255, 255, 255), outline=(0, 0, 0, 255))
    return Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")

# =========================================================== frame dispatcher
FINAL_SRC = "/home/claude/anim/post"
def frame(f):
    cursor, clicks = None, ()
    if f < SEC["erc"][1]:
        im, cursor, clicks = sch_frame(f)
    elif f < SEC["outline"][0]:
        a = ease((f - SEC["erc"][1]) / (SEC["outline"][0] - SEC["erc"][1]))
        im = Image.blend(sch_frame(f)[0], pcb_frame(f)[0], a)
    elif f < SEC["layers"][0]:
        im, cursor = pcb_frame(f)
    elif f < SEC["layers"][0] + 12:
        flat = stack_frame(f); ed = pcb_frame(f)[0]
        im = Image.blend(ed, flat, ease((f - SEC["layers"][0]) / 12))
    elif f < SEC["final"][0]:
        im = stack_frame(f)
    else:
        k = f - SEC["final"][0]
        src = Image.open(f"{FINAL_SRC}/p_{min(k, 119):04d}.png").convert("RGB")
        im = Image.blend(stack_frame(SEC["final"][0] - 1), src, ease(k / 14)) if k < 14 else src
    hud(im, f, cursor, clicks).save(f"{OUT}/p_{f:04d}.png")

if __name__ == "__main__":
    a, b = int(sys.argv[1]), int(sys.argv[2])
    for f in range(a, b + 1): frame(f)
