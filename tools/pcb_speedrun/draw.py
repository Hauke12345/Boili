"""KiCad-editor-style 2D drawing of the board from board.json (supersampled PIL)."""
import json, math
from PIL import Image, ImageDraw, ImageFont

D = json.load(open("/home/claude/pcbrun/board.json"))
FPS = {f["ref"]: f for f in D["footprints"]}
FD = "/opt/k9/usr/share/fonts/truetype/dejavu/"
SS = 2                                    # supersampling factor
W, H = 1280, 720

# KiCad 9 default-theme-like colours
COL = dict(bg=(12, 15, 22), fcu=(200, 52, 52), bcu=(77, 127, 196), pad_tht=(212, 162, 48), hole=(20, 22, 28),
           edge=(208, 210, 205), silk=(242, 237, 161), fab=(130, 136, 150), crt=(200, 60, 200),
           rats=(245, 245, 245), via=(236, 236, 236), zone=(77, 127, 196), grid=(34, 40, 52))

class View:
    """mm -> screen (supersampled) transform."""
    def __init__(self, cx, cy, scale):
        self.cx, self.cy, self.s = cx, cy, scale        # board point (cx,cy) maps to screen centre of the board area
        self.ox, self.oy = 818, 352                      # screen anchor (right of the splits panel)
    def p(self, x, y):
        return ((self.ox + (x - self.cx) * self.s) * SS, (self.oy + (y - self.cy) * self.s) * SS)
    def d(self, v): return v * self.s * SS

def font(sz, bold=True):
    return ImageFont.truetype(FD + ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"), max(4, int(sz)))

def rot(v, ang):
    th = math.radians(ang); c, s = math.cos(th), math.sin(th)
    return (v[0] * c + v[1] * s, -v[0] * s + v[1] * c)     # KiCad y-down, CCW-positive

def world(fp_pos, fp_ang, loc):
    r = rot(loc, fp_ang); return (fp_pos[0] + r[0], fp_pos[1] + r[1])

def pad_poly(cx, cy, sx, sy, ang, shape, n=10):
    if shape in ("circle", "oval") or shape == "roundrect":
        rr = min(sx, sy) / 2 if shape != "roundrect" else min(sx, sy) * 0.25
        pts = []
        hx, hy = sx / 2 - rr, sy / 2 - rr
        for qx, qy, a0 in ((hx, hy, 0), (-hx, hy, 90), (-hx, -hy, 180), (hx, -hy, 270)):
            for k in range(n + 1):
                a = math.radians(a0 + 90 * k / n)
                pts.append((qx + rr * math.cos(a), qy + rr * math.sin(a)))
    else:
        pts = [(-sx / 2, -sy / 2), (sx / 2, -sy / 2), (sx / 2, sy / 2), (-sx / 2, sy / 2)]
    return [(cx + r[0], cy + r[1]) for r in (rot(p, ang) for p in pts)]

def new_canvas():
    im = Image.new("RGB", (W * SS, H * SS), COL["bg"])
    return im, ImageDraw.Draw(im, "RGBA")

def draw_grid(d, v, alpha=255):
    step = 2.54
    x0, x1, y0, y1 = -40, 140, -30, 95
    c = (*COL["grid"], alpha)
    x = x0
    while x <= x1:
        y = y0
        while y <= y1:
            px, py = v.p(x, y)
            d.point((px, py), fill=c)
            y += step
        x += step

def draw_edge(d, v, alpha=255, frac=1.0):
    pls = D["edge"]
    total = sum(math.dist(a, b) for pl in pls for a, b in zip(pl, pl[1:]))
    left = total * frac
    for pl in pls:
        for a, b in zip(pl, pl[1:]):
            L = math.dist(a, b)
            if left <= 0: return
            t = min(1, left / L) if L else 1
            e = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
            d.line([v.p(*a), v.p(*e)], fill=(*COL["edge"], alpha), width=max(1, int(v.d(0.25))))
            left -= L

def draw_footprint(d, v, f, pos=None, ang=None, alpha=255, fab=True, crt=False, silk=True, label=True, glow=0.0):
    pos = pos if pos is not None else f["pos"]; ang = f["angle"] if ang is None else ang
    if fab:
        for pl in f["gfx"].get("F.Fab", []):
            d.line([v.p(*world(pos, ang, q)) for q in pl], fill=(*COL["fab"], int(alpha * 0.9)), width=max(1, int(v.d(0.12))))
    if crt or glow > 0:
        c = COL["crt"] if glow <= 0 else (255, 210, 60)
        for pl in f["gfx"].get("F.CrtYd", []):
            d.line([v.p(*world(pos, ang, q)) for q in pl], fill=(*c, int(alpha * (0.8 if glow <= 0 else glow))), width=max(1, int(v.d(0.12 if glow <= 0 else 0.3))))
    if silk:
        for pl in f["gfx"].get("F.Silk", []):
            d.line([v.p(*world(pos, ang, q)) for q in pl], fill=(*COL["silk"], alpha), width=max(1, int(v.d(0.15))))
    for p in f["pads"]:
        c = world(pos, ang, p["local"])
        poly = [v.p(*q) for q in pad_poly(c[0], c[1], p["size"][0], p["size"][1], ang + p["angle"], p["shape"])]
        if p["npth"]:
            continue
        col = COL["fcu"] if p["smd"] else COL["pad_tht"]
        d.polygon(poly, fill=(*col, alpha))
        if p["drill"] > 0:
            r = v.d(p["drill"] / 2); px, py = v.p(*c)
            d.ellipse((px - r, py - r, px + r, py + r), fill=(*COL["hole"], alpha))
    if label and not f["board_only"]:
        px, py = v.p(*pos)
        sz = v.d(1.5 if f["ref"] not in ("U2", "PS1", "K1") else 2.6)
        fo = font(sz)
        d.text((px, py), f["ref"], font=fo, fill=(*COL["fab"], int(alpha * 0.95)), anchor="mm")

def pad_world(ref, num, pos=None, ang=None):
    f = FPS[ref]; pos = pos if pos is not None else f["pos"]; ang = f["angle"] if ang is None else ang
    for p in f["pads"]:
        if p["num"] == num: return world(pos, ang, p["local"])

def draw_track(d, v, t, frac=1.0, alpha=255, color=None):
    a, b = t["a"], t["b"]
    e = (a[0] + (b[0] - a[0]) * frac, a[1] + (b[1] - a[1]) * frac)
    col = color or (COL["fcu"] if t["layer"] == "F.Cu" else COL["bcu"])
    w = v.d(t["w"])
    pa, pe = v.p(*a), v.p(*e)
    d.line([pa, pe], fill=(*col, alpha), width=max(1, int(w)))
    for q in (pa, pe):
        d.ellipse((q[0] - w / 2, q[1] - w / 2, q[0] + w / 2, q[1] + w / 2), fill=(*col, alpha))

def draw_via(d, v, via, alpha=255):
    px, py = v.p(*via["pos"]); r = v.d(via["d"] / 2); rh = v.d(via["drill"] / 2)
    d.ellipse((px - r, py - r, px + r, py + r), fill=(*COL["via"], alpha))
    d.ellipse((px - rh, py - rh, px + rh, py + rh), fill=(*COL["hole"], alpha))

def zone_image(v, color=COL["zone"], alpha=110):
    """Filled zone (with holes) as an RGBA layer at supersampled size."""
    lay = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
    m = Image.new("L", (W * SS, H * SS), 0); md = ImageDraw.Draw(m)
    for z in D["zones"]:
        for poly in z["polys"]:
            md.polygon([v.p(*q) for q in poly["outline"]], fill=255)
            for h in poly["holes"]:
                md.polygon([v.p(*q) for q in h], fill=0)
    col = Image.new("RGBA", (W * SS, H * SS), (*color, alpha))
    lay.paste(col, (0, 0), m)
    return lay, m

def draw_silk_board(d, v, alpha=255):
    for s in D["silk_lines"]:
        d.line([v.p(*q) for q in s["pts"]], fill=(*COL["silk"], alpha), width=max(1, int(v.d(s["w"]))))
    for t in D["silk_texts"]:
        fo = font(v.d(t["size"] * 1.15))
        px, py = v.p(*t["pos"])
        if abs(t["angle"]) < 1:
            d.text((px, py), t["text"], font=fo, fill=(*COL["silk"], alpha), anchor="lm")

def finish(im):
    return im.resize((W, H), Image.LANCZOS)

if __name__ == "__main__":
    v = View(48.25, 31, 8.6)
    im, d = new_canvas()
    draw_grid(d, v)
    lay, m = zone_image(v); im.paste(lay, (0, 0), lay)
    d = ImageDraw.Draw(im, "RGBA")
    for t in D["tracks"]: draw_track(d, v, t)
    for f in D["footprints"]: draw_footprint(d, v, f)
    for via in D["vias"]: draw_via(d, v, via)
    draw_edge(d, v); draw_silk_board(d, v)
    finish(im).save("/tmp/claude-0/drawtest.png")
