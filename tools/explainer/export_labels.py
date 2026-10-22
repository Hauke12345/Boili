import bpy, json, sys
sys.path.insert(0, "/work/anim/scripts")
import timeline as T
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector
sc = bpy.context.scene; cam = sc.camera
out = {}
for f in range(T.END):
    sc.frame_set(f)
    d = {}
    for k, (txt, p, a, b) in T.LABELS.items():
        if a - 15 <= f <= b + 15:
            v = world_to_camera_view(sc, cam, Vector(p))
            d[k] = [round(v.x * 1280, 1), round((1 - v.y) * 720, 1), v.z > 0]
    out[f] = d
json.dump(out, open("/work/anim/labels.json", "w"))
print("LABELS_OK")
