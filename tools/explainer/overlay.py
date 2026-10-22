"""Draw captions, 3D-anchored labels and the spot-price chart onto post-processed frames.
usage: overlay.py --range A B   (reads post/p_####.png, writes final/o_####.png)"""
import sys, os, json
from PIL import Image, ImageDraw, ImageFont, ImageFilter
sys.path.insert(0, "/home/claude/anim/scripts")
import timeline as T

SRC = os.environ.get("OV_SRC", "/home/claude/anim/post"); DST = os.environ.get("OV_DST", "/home/claude/anim/final")
os.makedirs(DST, exist_ok=True)
FD = "/opt/k9/usr/share/fonts/truetype/dejavu/"
F = lambda size, bold=False: ImageFont.truetype(FD + ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"), size)
F_CAP, F_LAB, F_TITLE, F_SUB = F(30, True), F(21, True), F(54, True), F(26)
F_CH, F_CHS, F_CLK = F(17, True), F(14), F(34, True)
LABELS = json.load(open("/home/claude/anim/labels.json"))
W, H = 1280, 720

def fade(f, a, b, ramp=12):
    if f < a or f > b: return 0.0
    return max(0.0, min(1.0, (f - a) / ramp, (b - f) / ramp))

def interp(keys, f):
    if f <= keys[0][0]: return keys[0][1]
    for (f0, v0), (f1, v1) in zip(keys, keys[1:]):
        if f0 <= f <= f1:
            t = (f - f0) / (f1 - f0); t = t * t * (3 - 2 * t)
            return v0 + (v1 - v0) * t
    return keys[-1][1]

def rbox(d, xy, fill, r=10): d.rounded_rectangle(xy, r, fill=fill)

def multiline_size(d, txt, font, spacing=4):
    b = d.multiline_textbbox((0, 0), txt, font=font, spacing=spacing)
    return b[2] - b[0], b[3] - b[1]

def caption(d, txt, a):
    tw, th = multiline_size(d, txt, F_CAP)
    x, y = (W - tw) / 2, H - 78
    rbox(d, (x - 22, y - 14, x + tw + 22, y + th + 18), (8, 12, 20, int(190 * a)), 12)
    d.text((x, y), txt, font=F_CAP, fill=(255, 255, 255, int(255 * a)))

def title(d, big, sub, a):
    size = 54
    while multiline_size(d, big, F(size, True))[0] > W - 160: size -= 2
    font = F(size, True)
    tw, th = multiline_size(d, big, font)
    sw, sh = multiline_size(d, sub, F_SUB)
    y = H * 0.36
    rbox(d, ((W - max(tw, sw)) / 2 - 36, y - 26, (W + max(tw, sw)) / 2 + 36, y + th + sh + 52), (8, 12, 20, int(170 * a)), 18)
    d.text(((W - tw) / 2, y), big, font=font, fill=(255, 255, 255, int(255 * a)))
    d.text(((W - sw) / 2, y + th + 22), sub, font=F_SUB, fill=(120, 220, 255, int(255 * a)))

CHART_RECT = (W - 430 - 24 - 150, 24, W - 24, 24 + 262)
def overlaps(r1, r2):
    return not (r1[2] < r2[0] or r1[0] > r2[2] or r1[3] < r2[1] or r1[1] > r2[3])

STICKY = {}
def label(d, txt, x, y, a, avoid=(), key=None):
    """Place a label near its anchor, trying positions until it overlaps nothing in `avoid`. Returns its box.
    The chosen side/offset is remembered per label so labels don't jump between frames."""
    tw, th = multiline_size(d, txt, F_LAB)
    pref_right = x < W * 0.62
    best = None
    if key in STICKY:
        side, dy = STICKY[key]
        lx = min(max(x + 70 if side else x - 70 - tw, 16), W - tw - 16)
        ly = min(max(y + dy - th / 2, 16), H - 130 - th)
        box = (lx - 10, ly - 7, lx + tw + 10, ly + th + 11)
        if not any(overlaps(box, r) for r in avoid): best = (box, lx, ly, side, dy)
    for side in (() if best else ((True, False) if pref_right else (False, True))):
        for dy in (-70, 70, -120, 120, -170, 170):
            lx = x + 70 if side else x - 70 - tw
            lx = min(max(lx, 16), W - tw - 16)
            ly = min(max(y + dy - th / 2, 16), H - 130 - th)
            box = (lx - 10, ly - 7, lx + tw + 10, ly + th + 11)
            if best is None: best = (box, lx, ly, side, dy)
            if not any(overlaps(box, r) for r in avoid):
                best = (box, lx, ly, side, dy); break
        else:
            continue
        break
    box, lx, ly, side, dy = best
    if key: STICKY[key] = (side, dy)
    ex = lx - 10 if side else lx + tw + 10
    ey = ly + th / 2 + 2
    col = (255, 255, 255, int(255 * a))
    d.line([(x, y), (ex, ey)], fill=(255, 255, 255, int(220 * a)), width=2)
    d.ellipse((x - 5, y - 5, x + 5, y + 5), fill=(255, 210, 60, int(255 * a)), outline=(20, 20, 20, int(200 * a)))
    rbox(d, box, (8, 12, 20, int(200 * a)), 8)
    d.multiline_text((lx, ly), txt, font=F_LAB, fill=col, spacing=4)
    return box

def chart(d, f, a, clock):
    x0, y0, cw, ch = W - 430 - 24, 24, 430, 262
    rbox(d, (x0, y0, x0 + cw, y0 + ch), (8, 12, 20, int(205 * a)), 14)
    d.text((x0 + 16, y0 + 12), "Tomorrow's spot price  (c/kWh)", font=F_CH, fill=(255, 255, 255, int(255 * a)))
    bx, by, bw, bh = x0 + 18, y0 + 58, cw - 36, 140
    pmax = max(T.PRICES)
    grow_start = T.CHART[0] + 10
    for h, p in enumerate(T.PRICES):
        g = max(0.0, min(1.0, (f - grow_start - h * 2.0) / 14)) if f < T.CHART[1] + 50 else 1.0
        hh = bh * p / pmax * g
        xl = bx + h * bw / 24 + 2; xr = bx + (h + 1) * bw / 24 - 2
        cheap = h in T.CHEAP_HOURS and f >= grow_start + 80
        col = (60, 230, 110) if cheap else (95, 125, 170)
        d.rectangle((xl, by + bh - hh, xr, by + bh), fill=(*col, int(255 * a)))
    for h in (0, 6, 12, 18):
        d.text((bx + h * bw / 24, by + bh + 6), f"{h:02d}", font=F_CHS, fill=(190, 200, 215, int(255 * a)))
    if f >= grow_start + 80:
        d.text((bx, by + bh + 26), "green = 4 cheapest hours", font=F_CHS, fill=(60, 230, 110, int(255 * a)))
    # clock cursor
    hc = clock % 24
    cx = bx + hc * bw / 24
    d.line([(cx, by - 6), (cx, by + bh)], fill=(255, 210, 60, int(255 * a)), width=3)
    heating = T.RELAY_ON <= f < T.HEAT_OFF
    hh_, mm_ = int(hc), int((hc - int(hc)) * 60)
    kx = x0 - 150
    rbox(d, (kx, y0, x0 - 12, y0 + 100), (8, 12, 20, int(205 * a)), 14)
    d.text((kx + 14, y0 + 8), f"{hh_:02d}:{mm_:02d}", font=F_CLK, fill=(255, 255, 255, int(255 * a)))
    st, sc = ("HEATING", (255, 90, 60)) if heating else ("OFF", (150, 160, 175))
    rbox(d, (kx + 14, y0 + 56, kx + 14 + (96 if heating else 46), y0 + 86), (*sc, int(230 * a)), 8)
    d.text((kx + 22, y0 + 61), st, font=F_CH, fill=(255, 255, 255, int(255 * a)))

def render(f):
    base = Image.open(f"{SRC}/p_{f:04d}.png").convert("RGBA")
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    chart_on = fade(f, *T.CHART, 14) > 0 or fade(f, *T.CHART_OUTRO, 14) > 0
    placed = [CHART_RECT] if chart_on else []
    for k in sorted(LABELS.get(str(f), {}), key=lambda k: T.LABELS[k][2]):     # stable order: by first frame
        x, y, front = LABELS[str(f)][k]
        txt, _, a0, b0 = T.LABELS[k]
        a = fade(f, a0, b0, 10)
        if a > 0 and front and 0 < x < W and 0 < y < H: placed.append(label(d, txt, x, y, a, placed, k))
    for k, (c0, c1) in enumerate([T.CHART, T.CHART_OUTRO]):
        a = fade(f, c0, c1, 14)
        if a > 0: chart(d, f, a, interp(T.CLOCK if k == 0 else T.OUTRO_CLOCK, f))
    for i, (txt, a0, b0) in enumerate(T.CAPTIONS):
        a = fade(f, a0, b0, 14)
        if a <= 0: continue
        if i == 0: title(d, txt, "ESP32  ·  WiFi  ·  Nord Pool spot price", a)
        elif i == len(T.CAPTIONS) - 1: title(d, txt, "Spot-price water heater controller", a)
        else: caption(d, txt, a)
    Image.alpha_composite(base, ov).convert("RGB").save(f"{DST}/o_{f:04d}.png")

if __name__ == "__main__":
    SP = DST + "/sticky.json"
    if os.path.exists(SP):
        STICKY.update({k: tuple(v) for k, v in json.load(open(SP)).items()})
    a = sys.argv[1:]
    frames = range(int(a[1]), int(a[2]) + 1) if a[0] == "--range" else [int(x) for x in a]
    for f in frames:
        if os.path.exists(f"{SRC}/p_{f:04d}.png"): render(f)
    json.dump(STICKY, open(SP, "w"))
