"""Precompute the schematic reveal: which pixel belongs to which symbol (nearest anchor)."""
import json, re, numpy as np
from PIL import Image
from scipy.spatial import cKDTree
from kiutils.schematic import Schematic

DPI = 200
K = DPI / 25.4
im = np.asarray(Image.open("/home/claude/pcbrun/sch-1.png").convert("RGB")).astype(np.int16)
Hh, Ww, _ = im.shape
BG = np.array([245, 244, 239])
ink = np.abs(im - BG).sum(-1) > 30

sch = Schematic.from_file("/home/claude/spot_heater/spot_heater.kicad_sch")
syms = {}
for s in sch.schematicSymbols:
    ref = [p.value for p in s.properties if p.key == "Reference"][0]
    if ref.startswith("#PWR"): continue
    syms[ref] = (s.position.X, s.position.Y)

ORDER = [
    ("Mains input", ["J1", "F1", "RV1", "PS1", "K1", "J2"]),
    ("5 V -> 3.3 V", ["C1", "U1", "C2", "C3", "C4"]),
    ("Relay driver", ["R3", "R4", "Q1", "D1", "R5", "D2"]),
    ("ESP32 + UI", ["U2", "R1", "C5", "SW1", "R2", "SW2", "R6", "D3", "J3", "R7", "J4"]),
]
# PWR_FLAG symbols belong to the mains section
flags = [r for r in syms if r.startswith("#FLG")]
anchors, owner = [], []
for sec, refs in ORDER:
    for r in refs:
        anchors.append(syms[r]); owner.append(r)
for r in flags:
    anchors.append(syms[r]); owner.append(r)
# notes: anchors every 8 mm along each line; section headers / notes revealed with their section
notes = []
for t in sch.texts:
    lines = t.text.replace("\\n", "\n").split("\n")
    size = t.effects.font.height
    for li, line in enumerate(lines):
        y = t.position.Y + li * size * 1.6
        n = max(1, int(len(line) * size * 0.75 / 8))
        for k in range(n + 1):
            anchors.append((t.position.X + k * 8, y)); owner.append("TEXT:" + t.text[:20])
    notes.append(t.text[:20])

A = np.array(anchors) * K
ys, xs = np.nonzero(ink)
tree = cKDTree(A)
dist, idx = tree.query(np.stack([xs, ys], 1))
lab = np.full((Hh, Ww), -1, np.int16)
lab[ys, xs] = idx
# border, frame and title block are shown from the start
mx = xs / K; my = ys / K
frame = (mx < 14) | (mx > 406) | (my < 14) | (my > 283) | ((mx > 300) & (my > 252))
lab[ys[frame], xs[frame]] = -2
np.save("/home/claude/pcbrun/sch_lab.npy", lab)
# per-anchor pixel bounding boxes (for selection boxes)
bbox = {}
for i, o in enumerate(owner):
    if o.startswith("TEXT"): continue
    sel = lab == i
    yy, xx = np.nonzero(sel)
    if len(xx): bbox[o] = [int(xx.min()), int(yy.min()), int(xx.max()), int(yy.max())]
json.dump(dict(owner=owner, order=ORDER, flags=flags, bbox=bbox, size=[Ww, Hh], K=K,
               syms={k: v for k, v in syms.items()}), open("/home/claude/pcbrun/sch_meta.json", "w"))
print("anchors", len(anchors), "ink px", len(xs), "notes", notes)
