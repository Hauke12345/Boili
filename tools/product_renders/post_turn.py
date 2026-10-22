import sys, os
sys.path.insert(0,'/home/claude/anim/scripts')
import post, numpy as np, OpenEXR, Imath, pyoidn
from PIL import Image
def rd(p):
    x=OpenEXR.InputFile(p); dw=x.header()["dataWindow"]; w,h=dw.max.x-dw.min.x+1,dw.max.y-dw.min.y+1
    pt=Imath.PixelType(Imath.PixelType.FLOAT); return np.stack([np.frombuffer(x.channel(c,pt),np.float32).reshape(h,w) for c in "RGB"],-1)
R="/home/claude/boili_prod/turn/"; O="/home/claude/boili_prod/turn_png/"; os.makedirs(O,exist_ok=True)
for f in [int(a) for a in sys.argv[1:]]:
    k=f"{f:04d}"
    img,alb,nrm,emi=rd(R+f"imgimg{k}.exr"),np.clip(rd(R+f"albalb{k}.exr"),0,1),np.clip(rd(R+f"nrmnrm{k}.exr"),-1,1),rd(R+f"emiemi{k}.exr")
    den=pyoidn.denoise(np.maximum(img,0),alb,nrm,hdr=True,quality="high")
    br=np.maximum(emi,0)*0.12
    bloom=0.6*post.blur(br,2)+0.4*post.blur(br,6)+0.3*post.blur(br,18)
    out=post.tonemap(den+bloom)
    Image.fromarray((out*255+.5).astype(np.uint8)).save(O+f"t_{k}.png")
