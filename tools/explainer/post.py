"""Denoise (OIDN with albedo+normal), add bloom, tone-map and upscale rendered EXR frames.
usage: post.py FRAME [FRAME ...]   or   post.py --range A B"""
import sys, os
import numpy as np, OpenEXR, Imath, pyoidn
from PIL import Image, ImageFilter

SRC = "/home/claude/anim/frames"
DST = "/home/claude/anim/post"
OUT_W, OUT_H = 1280, 720
EXPOSURE = 1.0
os.makedirs(DST, exist_ok=True)

def read(kind, f):
    p = f"{SRC}/{kind}/f{kind}{f:04d}.exr"
    x = OpenEXR.InputFile(p); dw = x.header()["dataWindow"]
    w, h = dw.max.x - dw.min.x + 1, dw.max.y - dw.min.y + 1
    pt = Imath.PixelType(Imath.PixelType.FLOAT)
    return np.stack([np.frombuffer(x.channel(c, pt), np.float32).reshape(h, w) for c in "RGB"], -1)

from scipy.ndimage import gaussian_filter
from scipy.ndimage import zoom
def blur(a, radius):
    if radius <= 6: return gaussian_filter(a, sigma=(radius, radius, 0), mode="nearest")
    k = 4                                   # blur large radii at quarter resolution
    small = a[::k, ::k]
    b = gaussian_filter(small, sigma=(radius / k, radius / k, 0), mode="nearest")
    return zoom(b, (a.shape[0] / b.shape[0], a.shape[1] / b.shape[1], 1), order=1)[:a.shape[0], :a.shape[1]]

def tonemap(x):
    # ACES filmic fit (Narkowicz), then sRGB transfer
    x = x * EXPOSURE
    y = (x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14)
    y = np.clip(y, 0, 1)
    return np.where(y <= 0.0031308, 12.92 * y, 1.055 * np.power(y, 1 / 2.4) - 0.055)

def process(f):
    img, alb, nrm = read("img", f), np.clip(read("alb", f), 0, 1), np.clip(read("nrm", f), -1, 1)
    img = np.maximum(img, 0)
    den = pyoidn.denoise(img, alb, nrm, hdr=True, quality="balanced")
    emi = read("emi", f)
    bright = np.maximum(emi, 0) * 0.6
    bloom = 0.55 * blur(bright, 4) + 0.35 * blur(bright, 14) + 0.25 * blur(bright, 40)
    out = tonemap(den + bloom)
    im = Image.fromarray((out * 255 + 0.5).astype(np.uint8), "RGB").resize((OUT_W, OUT_H), Image.LANCZOS)
    im.save(f"{DST}/p_{f:04d}.png")

if __name__ == "__main__":
    a = sys.argv[1:]
    frames = range(int(a[1]), int(a[2]) + 1) if a[0] == "--range" else [int(x) for x in a]
    for f in frames:
        if os.path.exists(f"{SRC}/img/fimg{f:04d}.exr"): process(f)
