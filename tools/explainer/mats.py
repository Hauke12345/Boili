import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath="/work/anim/board.glb")
use={}
for o in bpy.data.objects:
    if o.type=='MESH':
        for s in o.material_slots:
            use.setdefault(s.material.name,set()).add(o.name)
for m in bpy.data.materials:
    b=m.node_tree.nodes.get("Principled BSDF") if m.use_nodes else None
    c=tuple(round(x,2) for x in b.inputs["Base Color"].default_value) if b else None
    a=round(b.inputs["Alpha"].default_value,2) if b else None
    print("MAT",m.name,c,a,sorted(use.get(m.name,[]))[:6])
for o in bpy.data.objects:
    if o.type=='MESH' and o.name.startswith("=>"): print("OBJ",o.name,len(o.data.polygons), [s.material.name for s in o.material_slots])
for o in bpy.data.objects:
    if o.name.startswith("=>") : print("NODE",o.name,o.type,[c.name for c in o.children][:5])
