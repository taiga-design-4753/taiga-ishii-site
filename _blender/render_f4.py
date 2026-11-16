# Blender script: import f4_v18.glb, studio lighting, render one still.
# usage: blender -b -P render_f4.py -- <glb> <out.png> [samples] [width] [height] [cpu]
import bpy, sys, math
from mathutils import Vector
a = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
glb = a[0]; out = a[1]
samples = int(a[2]) if len(a) > 2 else 256
W = int(a[3]) if len(a) > 3 else 1920
H = int(a[4]) if len(a) > 4 else 1080
force_cpu = len(a) > 5 and a[5] == 'cpu'

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb)
sc = bpy.context.scene
carcol = bpy.data.collections.new('car_only')
for o in list(sc.objects):
    carcol.objects.link(o)

def T(x, y, z):  # three.js (x fwd, y up, z side) -> Blender (x, -z, y)
    return Vector((x, -z, y))

# materials: unlit -> principled, tune paint / carbon / rubber
for m in bpy.data.materials:
    if not m.use_nodes: continue
    nt = m.node_tree
    bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    outn = next((n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'), None)
    if bsdf is None and outn is not None:
        tex = next((n for n in nt.nodes if n.type == 'TEX_IMAGE'), None)
        col = None
        for n in nt.nodes:
            if n.type in ('EMISSION', 'BACKGROUND') and not n.inputs[0].is_linked:
                col = tuple(n.inputs[0].default_value)
        for l in list(nt.links):
            if l.to_node == outn: nt.links.remove(l)
        bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
        if tex: nt.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
        elif col: bsdf.inputs['Base Color'].default_value = col
        bsdf.inputs['Roughness'].default_value = 0.35
        nt.links.new(bsdf.outputs[0], outn.inputs['Surface'])

# world: dark with a faint gradient
w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
bg = w.node_tree.nodes['Background']
bg.inputs[0].default_value = (0.012, 0.013, 0.016, 1); bg.inputs[1].default_value = 1.0

def area(name, pos, target, size, power, color=(1, 1, 1), sy=None):
    L = bpy.data.lights.new(name, 'AREA'); L.energy = power; L.color = color
    L.shape = 'RECTANGLE'; L.size = size; L.size_y = sy or size
    o = bpy.data.objects.new(name, L); sc.collection.objects.link(o)
    o.location = T(*pos)
    d = T(*target) - o.location
    o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return o

area('top',   (0.2, 4.2, 0.0),  (0.2, 0, 0),    7.0, 420, sy=2.2)      # long overhead softbox
area('sideL', (0.5, 1.6, 4.5),  (0.2, 0.4, 0),  6.0, 160,  sy=1.0)      # strip, camera side
area('sideR', (0.5, 1.8, -4.5), (0.2, 0.4, 0),  6.0, 90,  sy=1.0)
sK = area('sideKey',(-4.0, 1.4, 2.4), (-0.4, 0.45, 0.5), 3.5, 120, sy=0.5)
area('front', (6.0, 2.2, 1.0),  (0.5, 0.4, 0),  2.5, 70)
area('rimB',  (-5.0, 1.6, -2.5),(0, 0.5, 0),    2.0, 300, color=(0.25, 0.42, 1.0))
rO = area('rimO',  (-3.2, 2.6, -3.4),(0, 0.5, 0),    0.6, 40,   color=(1.0, 0.45, 0.12))

# floor: dark glossy
bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 0, 0))
fl = bpy.context.object
fm = bpy.data.materials.new('floor'); fm.use_nodes = True
fb = fm.node_tree.nodes['Principled BSDF']
fb.inputs['Base Color'].default_value = (0.012, 0.012, 0.014, 1)
fb.inputs['Roughness'].default_value = 0.16
fl.data.materials.append(fm)

# rim/side lights light only the car (no blobs on the floor)
for o in (rO, sK):
    o.light_linking.receiver_collection = carcol

# camera at the hero pose
cam = bpy.data.cameras.new('cam'); co = bpy.data.objects.new('cam', cam)
sc.collection.objects.link(co); sc.camera = co
co.location = T(4.08, 0.75, 2.654)
co.rotation_euler = (T(0.55, 0.33, 0) - co.location).to_track_quat('-Z', 'Y').to_euler()
cam.sensor_fit = 'VERTICAL'; cam.sensor_height = 24
cam.lens = 12 / math.tan(math.radians(31) / 2)
cam.dof.use_dof = True; cam.dof.focus_distance = (T(0.6, 0.4, 0.3) - co.location).length
cam.dof.aperture_fstop = 5.6

sc.render.engine = 'CYCLES'
sc.cycles.samples = samples
sc.cycles.use_denoising = True
sc.render.resolution_x = W; sc.render.resolution_y = H
sc.view_settings.view_transform = 'AgX'
try: sc.view_settings.look = 'AgX - Medium High Contrast'
except Exception: pass
dev = 'CPU'
if not force_cpu:
    try:
        pr = bpy.context.preferences.addons['cycles'].preferences
        for t in ('OPTIX', 'CUDA'):
            try:
                pr.compute_device_type = t; pr.get_devices()
                ds = [d for d in pr.devices if d.type == t]
                if ds:
                    for d in pr.devices: d.use = d.type == t
                    dev = 'GPU'; print('GPU:', t, [d.name for d in ds]); break
            except Exception as e: print(t, 'n/a', e)
    except Exception as e: print('no cycles prefs', e)
sc.cycles.device = dev
sc.render.filepath = out; sc.render.image_settings.file_format = 'PNG'
bpy.ops.render.render(write_still=True)
print('DONE', out, dev)
