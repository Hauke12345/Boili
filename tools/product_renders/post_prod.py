import sys
sys.path.insert(0,'/home/claude/anim/scripts')
import post, numpy as np, OpenEXR, Imath, pyoidn
from PIL import Image
def rd(p):
    x=OpenEXR.InputFile(p); dw=x.header()["dataWindow"]; w,h=dw.max.x-dw.min.x+1,dw.max.y-dw.min.y+1
    pt=Imath.PixelType(Imath.PixelType.FLOAT); return np.stack([np.frombuffer(x.channel(c,pt),np.float32).reshape(h,w) for c in "RGB"],-1)
R="/home/claude/boili_prod/render/"
img,alb,nrm,emi=rd(R+"imgimg.exr"),np.clip(rd(R+"albalb.exr"),0,1),np.clip(rd(R+"nrmnrm.exr"),-1,1),rd(R+"emiemi.exr")
den=pyoidn.denoise(np.maximum(img,0),alb,nrm,hdr=True,quality="high")
br=np.maximum(emi,0)*0.12
bloom=0.6*post.blur(br,3)+0.4*post.blur(br,10)+0.3*post.blur(br,30)
post.EXPOSURE=float(sys.argv[2]) if len(sys.argv)>2 else 1.0
out=post.tonemap(den+bloom)
Image.fromarray((out*255+.5).astype(np.uint8)).save(sys.argv[1])
