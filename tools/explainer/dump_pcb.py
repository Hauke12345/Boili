import pcbnew, json
b=pcbnew.LoadBoard("/work/spot_heater/spot_heater.kicad_pcb")
mm=pcbnew.ToMM; OX,OY=100,100
def bx(v): return [round(mm(v.x)-OX,3), round(mm(v.y)-OY,3)]
out={"nets":{}, "pads":{}, "parts":{}}
for t in b.GetTracks():
    n=t.GetNetname(); d=out["nets"].setdefault(n,{"segs":[],"vias":[]})
    if t.GetClass()=="PCB_VIA": d["vias"].append(bx(t.GetPosition()))
    else: d["segs"].append(bx(t.GetStart())+bx(t.GetEnd())+[round(mm(t.GetWidth()),3), t.GetLayerName()])
for f in b.GetFootprints():
    out["parts"][f.GetReference()]=bx(f.GetPosition())+[f.GetOrientationDegrees()]
    for p in f.Pads():
        out["pads"][f"{f.GetReference()}.{p.GetNumber()}"]=bx(p.GetPosition())+[p.GetNetname()]
json.dump(out,open("/work/anim/pcb.json","w"))
print({k:len(v["segs"]) for k,v in out["nets"].items()})
