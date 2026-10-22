"""Dump everything the PCB speed-run needs from the KiCad 9 board (run inside the KiCad sandbox)."""
import pcbnew, json, math
B = pcbnew.LoadBoard("/work/spot_heater/spot_heater.kicad_pcb")
mm = pcbnew.ToMM
OX, OY = 100, 100
def P(v): return [round(mm(v.x) - OX, 4), round(mm(v.y) - OY, 4)]
LAYERS = {pcbnew.F_SilkS: "F.Silk", pcbnew.F_Fab: "F.Fab", pcbnew.F_CrtYd: "F.CrtYd"}

def shape_polyline(s):
    """Return a list of polylines (world coords) approximating a PCB_SHAPE."""
    t = s.GetShape()
    if t == pcbnew.SHAPE_T_SEGMENT:
        return [[P(s.GetStart()), P(s.GetEnd())]]
    if t == pcbnew.SHAPE_T_RECTANGLE:
        a, b = s.GetStart(), s.GetEnd()
        pts = [(a.x, a.y), (b.x, a.y), (b.x, b.y), (a.x, b.y), (a.x, a.y)]
        return [[P(pcbnew.VECTOR2I(int(x), int(y))) for x, y in pts]]
    if t == pcbnew.SHAPE_T_CIRCLE:
        c, r = s.GetCenter(), s.GetRadius()
        return [[P(pcbnew.VECTOR2I(int(c.x + r * math.cos(a / 24 * 2 * math.pi)), int(c.y + r * math.sin(a / 24 * 2 * math.pi)))) for a in range(25)]]
    if t == pcbnew.SHAPE_T_ARC:
        c, r = s.GetCenter(), s.GetRadius()
        st = s.GetStart()
        a0 = math.atan2(st.y - c.y, st.x - c.x)
        sweep = math.radians(s.GetArcAngle().AsDegrees())
        n = max(4, int(abs(sweep) / 0.2))
        return [[P(pcbnew.VECTOR2I(int(c.x + r * math.cos(a0 + sweep * k / n)), int(c.y + r * math.sin(a0 + sweep * k / n)))) for k in range(n + 1)]]
    if t == pcbnew.SHAPE_T_POLY:
        ps = s.GetPolyShape(); out = []
        for i in range(ps.OutlineCount()):
            ch = ps.Outline(i); pts = [P(ch.CPoint(k)) for k in range(ch.PointCount())]
            out.append(pts + [pts[0]])
        return out
    return []

out = dict(footprints=[], tracks=[], vias=[], zones=[], silk_lines=[], silk_texts=[], edge=[])
for f in B.GetFootprints():
    pos = f.GetPosition(); ang = f.GetOrientationDegrees()
    th = math.radians(ang)
    def local(w):
        dx, dy = w[0] - (mm(pos.x) - OX), w[1] - (mm(pos.y) - OY)
        # inverse of KiCad's rotation (y down, positive angle = CCW on screen)
        c, s_ = math.cos(th), math.sin(th)
        return [round(dx * c - dy * s_, 4), round(dx * s_ + dy * c, 4)]
    fp = dict(ref=f.GetReference(), value=f.GetValue(), pos=P(pos), angle=ang, pads=[], gfx={}, board_only=f.IsBoardOnly())
    for p in f.Pads():
        shape = {pcbnew.PAD_SHAPE_RECTANGLE: "rect", pcbnew.PAD_SHAPE_ROUNDRECT: "roundrect", pcbnew.PAD_SHAPE_CIRCLE: "circle",
                 pcbnew.PAD_SHAPE_OVAL: "oval"}.get(p.GetShape(pcbnew.F_Cu), "rect")
        fp["pads"].append(dict(num=p.GetNumber(), net=p.GetNetname(), shape=shape,
                               local=local(P(p.GetPosition())), size=[round(mm(p.GetSize(pcbnew.F_Cu).x), 3), round(mm(p.GetSize(pcbnew.F_Cu).y), 3)],
                               angle=p.GetOrientationDegrees() - ang, drill=round(mm(p.GetDrillSize().x), 3),
                               smd=p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD, npth=p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH))
    for g in f.GraphicalItems():
        L = LAYERS.get(g.GetLayer())
        if L and isinstance(g, pcbnew.PCB_SHAPE):
            for pl in shape_polyline(g):
                fp["gfx"].setdefault(L, []).append([local(q) for q in pl])
    out["footprints"].append(fp)

for t in B.GetTracks():
    if t.GetClass() == "PCB_VIA":
        out["vias"].append(dict(pos=P(t.GetPosition()), d=round(mm(t.GetWidth(pcbnew.F_Cu)), 3), drill=round(mm(t.GetDrillValue()), 3), net=t.GetNetname()))
    else:
        out["tracks"].append(dict(a=P(t.GetStart()), b=P(t.GetEnd()), w=round(mm(t.GetWidth()), 3), layer=t.GetLayerName(), net=t.GetNetname()))

filler = pcbnew.ZONE_FILLER(B); filler.Fill(B.Zones())
for z in B.Zones():
    if z.GetIsRuleArea(): continue
    for lid in (pcbnew.F_Cu, pcbnew.B_Cu):
        if not z.IsOnLayer(lid): continue
        ps = z.GetFilledPolysList(lid)
        polys = []
        for i in range(ps.OutlineCount()):
            o = ps.Outline(i)
            holes = [[P(ps.Hole(i, j).CPoint(k)) for k in range(ps.Hole(i, j).PointCount())] for j in range(ps.HoleCount(i))]
            polys.append(dict(outline=[P(o.CPoint(k)) for k in range(o.PointCount())], holes=holes))
        out["zones"].append(dict(layer=B.GetLayerName(lid), net=z.GetNetname(), polys=polys))

for d in B.GetDrawings():
    if isinstance(d, pcbnew.PCB_SHAPE):
        if d.GetLayer() == pcbnew.Edge_Cuts: out["edge"] += shape_polyline(d)
        elif d.GetLayer() == pcbnew.F_SilkS: out["silk_lines"] += [dict(pts=pl, w=round(mm(d.GetWidth()), 3)) for pl in shape_polyline(d)]
    elif isinstance(d, pcbnew.PCB_TEXT) and d.GetLayer() == pcbnew.F_SilkS:
        out["silk_texts"].append(dict(text=d.GetText(), pos=P(d.GetPosition()), size=round(mm(d.GetTextSize().y), 3), angle=d.GetTextAngleDegrees()))

ns = B.GetDesignSettings().m_NetSettings
json.dump(out, open("/work/pcbrun/board.json", "w"))
print("footprints", len(out["footprints"]), "tracks", len(out["tracks"]), "vias", len(out["vias"]),
      "zones", [(z["layer"], len(z["polys"])) for z in out["zones"]], "edge", len(out["edge"]), "silk", len(out["silk_lines"]), len(out["silk_texts"]))
