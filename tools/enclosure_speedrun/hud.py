"""Speed-run HUD (splits, timer, step captions, checks, end card) over the rendered frames.
usage: hud.py A B  -> reads frames/f_####.png, writes hud/h_####.png"""
import sys, os, json, math
from PIL import Image, ImageDraw, ImageFont

D = "/home/claude/housing/vid"
SRC = os.environ.get("HUD_SRC", f"{D}/frames")
os.makedirs(f"{D}/hud", exist_ok=True)
T = json.load(open(f"{D}/timing.json"))
FIT = json.load(open("/home/claude/housing/fit_report.json"))
FD = "/opt/k9/usr/share/fonts/truetype/dejavu/"
F = lambda n, s: ImageFont.truetype(FD + n, s)
f_row, f_rowb, f_hdr, f_small = F("DejaVuSans.ttf", 14), F("DejaVuSans-Bold.ttf", 14), F("DejaVuSans-Bold.ttf", 16), F("DejaVuSans.ttf", 12)
f_timer, f_timer_ms = F("DejaVuSansMono-Bold.ttf", 52), F("DejaVuSansMono-Bold.ttf", 30)
f_cap, f_capd, f_big = F("DejaVuSans-Bold.ttf", 26), F("DejaVuSans.ttf", 18), F("DejaVuSans-Bold.ttf", 30)
W, H, FPS = 1280, 720, 24

starts = T["starts"]
names = T["titles"] + ["Assemble + check"]
ends = starts[1:] + [T["assemble"], T["orbit"]]           # frame each split completes
STOP = T["end"]                                            # timer stops when the run is complete
PB = [ (e / FPS) + round(math.sin(i * 1.7) * 0.35 + 0.18, 2) for i, e in enumerate(ends)]   # a "personal best" to race

def tfmt(sec, ms=True):
    m, s = divmod(max(sec, 0), 60)
    return f"{int(m)}:{s:05.2f}" if ms else f"{int(m)}:{int(s):02d}"

def rbox(d, xy, fill, r=8): d.rounded_rectangle(xy, r, fill=fill)

def frame(f):
    im = Image.open(f"{SRC}/f_{f:04d}.png").convert("RGBA")
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    t = min(f, STOP) / FPS
    cur = max([i for i in range(len(ends)) if f >= (starts + [T["assemble"]])[i]], default=0)

    # ---------------- splits panel
    x0, y0, pw, rh = 14, 14, 340, 23
    ph = 56 + rh * len(names) + 34
    rbox(d, (x0, y0, x0 + pw, y0 + ph), (12, 16, 24, 215), 12)
    d.text((x0 + 14, y0 + 10), "SPOT HEATER ENCLOSURE", font=f_hdr, fill=(255, 255, 255))
    d.text((x0 + 14, y0 + 32), "FreeCAD 1.0  ·  Part WB  ·  Any% (scripted)", font=f_small, fill=(150, 170, 200))
    for i, n in enumerate(names):
        y = y0 + 56 + i * rh
        done = f >= ends[i]
        if i == cur and not done:
            rbox(d, (x0 + 6, y - 2, x0 + pw - 6, y + rh - 3), (40, 90, 200, 230), 5)
        label = n if len(n) <= 27 else n[:26] + "…"
        d.text((x0 + 14, y + 2), label, font=f_rowb if i == cur else f_row,
               fill=(255, 255, 255) if (done or i == cur) else (150, 160, 175))
        if done:
            split = ends[i] / FPS; delta = split - PB[i]
            col = (60, 220, 110) if delta < 0 else (240, 80, 70)
            d.text((x0 + pw - 120, y + 2), f"{delta:+.2f}", font=f_row, fill=col)
            d.text((x0 + pw - 60, y + 2), tfmt(split), font=f_row, fill=(255, 255, 255))
        else:
            d.text((x0 + pw - 60, y + 2), tfmt(PB[i]), font=f_row, fill=(110, 120, 135))
    yb = y0 + 56 + rh * len(names) + 6
    d.line([(x0 + 12, yb), (x0 + pw - 12, yb)], fill=(70, 80, 95), width=1)
    d.text((x0 + 14, yb + 7), "Previous segment", font=f_small, fill=(150, 160, 175))
    if cur > 0:
        seg = (ends[cur - 1] - (starts + [T["assemble"]])[cur - 1]) / FPS
        d.text((x0 + pw - 60, yb + 7), f"{seg:.2f}", font=f_small, fill=(255, 255, 255))

    # ---------------- timer (bottom-left, under the splits)
    ahead = all((ends[i] / FPS) - PB[i] < 0.3 for i in range(len(ends)) if f >= ends[i])
    col = (255, 210, 60) if f >= STOP else ((60, 230, 120) if ahead else (240, 80, 70))
    s = tfmt(t); main, ms = s[:-3], s[-3:]
    tx, ty = x0 + 8, y0 + ph + 8
    rbox(d, (x0, ty - 4, x0 + pw, ty + 66), (12, 16, 24, 215), 12)
    tw = d.textlength(main, font=f_timer)
    d.text((tx + pw - 30 - tw - d.textlength(ms, font=f_timer_ms), ty), main, font=f_timer, fill=col)
    d.text((tx + pw - 30 - d.textlength(ms, font=f_timer_ms), ty + 18), ms, font=f_timer_ms, fill=col)

    # ---------------- step caption (bottom right)
    if f < T["assemble"]:
        i = max(k for k in range(len(starts)) if f >= starts[k])
        a = min(1, (f - starts[i]) / 6)
        title, detail = T["titles"][i], T["details"][i]
        title = f"{i + 1:02d}  {title}"
        tw = max(d.textlength(title, font=f_cap), d.textlength(detail, font=f_capd))
        bx = W - 24 - tw - 32
        rbox(d, (bx, H - 104, W - 24, H - 22), (12, 16, 24, int(215 * a)), 12)
        d.text((bx + 16, H - 96), title, font=f_cap, fill=(255, 255, 255, int(255 * a)))
        d.text((bx + 16, H - 56), detail, font=f_capd, fill=(170, 200, 240, int(255 * a)))

    # ---------------- interference check badge (PCB step)
    p0 = starts[15]
    if p0 + 26 <= f < starts[16] + 10:
        a = min(1, (f - p0 - 26) / 6)
        msg = f"Interference with PCB: {FIT['base'] + FIT['lid']:.3f} mm³  ✓"
        sub = f"lid ribs clear parts by {FIT['lid_clearance_mm']} mm  ·  solder pins clear floor by {FIT['pin_clearance_mm']} mm"
        tw = max(d.textlength(msg, font=f_big), d.textlength(sub, font=f_capd))
        bx = (W - tw) / 2 + 170
        rbox(d, (bx - 20, 22, bx + tw + 20, 112), (20, 120, 60, int(225 * a)), 14)
        d.text((bx, 32), msg, font=f_big, fill=(255, 255, 255, int(255 * a)))
        d.text((bx, 76), sub, font=f_capd, fill=(220, 255, 230, int(255 * a)))

    # ---------------- end card
    if f >= T["end"] - 6:
        a = min(1, (f - T["end"] + 6) / 10)
        lines = [("RUN COMPLETE", f_big, (255, 210, 60)),
                 (f"Final time {tfmt(STOP / FPS)}", f_cap, (255, 255, 255)),
                 ("", f_capd, (0, 0, 0)),
                 ("PC/ABS, UL94 V-0  ·  2.5 mm walls  ·  1° draft", f_capd, (210, 225, 245)),
                 ("Tongue-and-groove TPE gasket (IP54 target)", f_capd, (210, 225, 245)),
                 (f"{FIT['outer_mm'][0]:.0f} × {FIT['outer_mm'][1]:.0f} × {FIT['outer_mm'][2]:.0f} mm incl. wall ears", f_capd, (210, 225, 245)),
                 (f"Base {FIT['mass_g_PC_ABS']['base']:.0f} g + lid {FIT['mass_g_PC_ABS']['lid']:.0f} g", f_capd, (210, 225, 245)),
                 ("0.000 mm³ interference with the populated PCB", f_capd, (120, 230, 150))]
        tw = max(d.textlength(s_, font=fo) for s_, fo, _ in lines)
        bx, by = W - 24 - tw - 40, 24
        hgt = sum(40 if fo is not f_capd else 28 for _, fo, _ in lines) + 30
        rbox(d, (bx, by, W - 24, by + hgt), (12, 16, 24, int(225 * a)), 14)
        yy = by + 16
        for s_, fo, c in lines:
            d.text((bx + 20, yy), s_, font=fo, fill=(*c, int(255 * a)))
            yy += 40 if fo is not f_capd else 28
    Image.alpha_composite(im, ov).convert("RGB").save(f"{D}/hud/h_{f:04d}.png")

if __name__ == "__main__":
    a, b = int(sys.argv[1]), int(sys.argv[2])
    for f in range(a, b + 1):
        if os.path.exists(f"{SRC}/f_{f:04d}.png"): frame(f)
