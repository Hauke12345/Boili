#!/bin/bash
# Build the enclosure speedrun GIF + photoreal turntable extension.
# usage: make_gif.sh WIDTH LOSSY
set -e
W=${1:-560}; LOSSY=${2:-140}
D=/home/claude/boili_prod/gif; rm -rf $D; mkdir -p $D/seq
# 1) speedrun, 2.2x speed, 9 fps
ffmpeg -y -loglevel error -i /home/claude/enclosure_speedrun.mp4 -vf "setpts=PTS/2.2,fps=9,scale=$W:-2:flags=lanczos" $D/seq/a_%04d.png
python3 - "$W" <<'EOF'
import sys, glob, os
from PIL import Image, ImageDraw, ImageFont
W = int(sys.argv[1]); H = round(W * 9 / 16 / 2) * 2
D = "/home/claude/boili_prod/gif/seq"
FD = "/opt/k9/usr/share/fonts/truetype/dejavu/"
fb = ImageFont.truetype(FD + "DejaVuSans-Bold.ttf", max(10, W // 40)); fs = ImageFont.truetype(FD + "DejaVuSans.ttf", max(9, W // 52))
a = sorted(glob.glob(D + "/a_*.png"))
turn = sorted(glob.glob("/home/claude/boili_prod/turn_png/t_*.png"))
last = Image.open(a[-1]).convert("RGB")
def label(im, k):
    d = ImageDraw.Draw(im, "RGBA")
    t1, t2 = "BOILI · final product", "Studio render · Blender Cycles"
    w = max(d.textlength(t1, font=fb), d.textlength(t2, font=fs)) + 2 * (W // 40)
    x, y = W // 40, H - W // 40 - (W // 40 + W // 52 + W // 40)
    al = min(1, k / 4)
    d.rounded_rectangle((x, y, x + w, H - W // 40), radius=W // 70, fill=(12, 16, 24, int(200 * al)))
    d.text((x + W // 40, y + W // 80), t1, font=fb, fill=(255, 210, 60, int(255 * al)))
    d.text((x + W // 40, y + W // 80 + W // 36), t2, font=fs, fill=(200, 215, 235, int(255 * al)))
    return im
frames = [Image.open(p).convert("RGB").resize((W, H), Image.LANCZOS) for p in turn]
n = len(a)
for k in range(5):                                   # crossfade
    Image.blend(last, frames[0], (k + 1) / 6).save(f"{D}/b_{k:04d}.png")
for k, im in enumerate(frames):
    label(im, k).save(f"{D}/c_{k:04d}.png")
# renumber into one sequence
seq = sorted(glob.glob(D + "/a_*.png")) + sorted(glob.glob(D + "/b_*.png")) + sorted(glob.glob(D + "/c_*.png"))
for i, p in enumerate(seq): os.rename(p, f"{D}/f_{i:04d}.png")
print("frames", len(seq))
EOF
ffmpeg -y -loglevel error -framerate 9 -i $D/seq/f_%04d.png -vf "palettegen=max_colors=200:stats_mode=diff" $D/pal.png
ffmpeg -y -loglevel error -framerate 9 -i $D/seq/f_%04d.png -i $D/pal.png -lavfi "[0:v][1:v]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle" $D/raw.gif
gifsicle -O3 --lossy=$LOSSY --loopcount=forever $D/raw.gif -o /home/claude/boili_enclosure_speedrun_studio.gif
ls -l /home/claude/boili_enclosure_speedrun_studio.gif
