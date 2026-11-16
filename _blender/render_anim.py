# Blender script: import f4_v18.glb, studio lighting, render one still.
# usage: blender -b -P render_anim.py -- <glb> <anim.json> <outdir> [samples] [width] [height] [cpu] [start] [end] [step]
import bpy, sys, math
from mathutils import Vector
a = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
import json, os
from mathutils import Quaternion
glb = a[0]; anim = json.load(open(a[1])); outdir = a[2]
samples = int(a[3]) if len(a) > 3 else 256
W = int(a[4]) if len(a) > 4 else 1600
H = int(a[5]) if len(a) > 5 else 900
force_cpu = len(a) > 6 and a[6] == 'cpu'
F0 = int(a[7]) if len(a) > 7 else 0
F1 = int(a[8]) if len(a) > 8 else len(anim['frames']) - 1
STEP = int(a[9]) if len(a) > 9 else 1

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

# halo / roll hoop: satin graphite so it separates from the gloss-black body
for m in bpy.data.materials:
    b = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None) if m.use_nodes else None
    if b and abs(b.inputs['Metallic'].default_value - 0.75) < 0.01 and abs(b.inputs['Roughness'].default_value - 0.38) < 0.01:
        b.inputs['Base Color'].default_value = (0.045, 0.047, 0.052, 1)
        b.inputs['Metallic'].default_value = 0.15; b.inputs['Roughness'].default_value = 0.5
        try: b.inputs['Coat Weight'].default_value = 0.0
        except Exception: pass
        print('halo material', m.name)

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

L_top = area('top',   (0.2, 4.2, 0.0),  (0.2, 0, 0),    7.0, 420, sy=2.2)      # long overhead softbox
L_sideL = area('sideL', (0.5, 1.6, 4.5),  (0.2, 0.4, 0),  6.0, 160,  sy=1.0)      # strip, camera side
L_sideR = area('sideR', (0.5, 1.8, -4.5), (0.2, 0.4, 0),  6.0, 90,  sy=1.0)
sK = area('sideKey',(-4.0, 1.4, 2.4), (-0.4, 0.45, 0.5), 3.5, 120, sy=0.5)
L_front = area('front', (6.0, 2.2, 1.0),  (0.5, 0.4, 0),  2.5, 70)
L_rimB = area('rimB',  (-5.0, 1.6, -2.5),(0, 0.5, 0),    2.0, 300, color=(0.25, 0.42, 1.0))
rO = area('rimO',  (-3.2, 2.6, -3.4),(0, 0.5, 0),    0.6, 40,   color=(1.0, 0.45, 0.12))

# floor: dark glossy
bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 0, 0))
fl = bpy.context.object
fm = bpy.data.materials.new('floor'); fm.use_nodes = True
fb = fm.node_tree.nodes['Principled BSDF']
fb.inputs['Base Color'].default_value = (0.012, 0.012, 0.014, 1)
fb.inputs['Roughness'].default_value = 0.38
fb.inputs['Specular IOR Level'].default_value = 0.14
fl.data.materials.append(fm)

# rim/side lights light only the car (no blobs on the floor)
for o in (rO, sK, L_sideL):
    o.light_linking.receiver_collection = carcol

# backfaces invisible to the camera (as in the browser version) for single-sided materials,
# so the camera can sit inside the roll hoop at the end
for m in bpy.data.materials:
    continue
    nt = m.node_tree
    outn = next((n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output), None)
    if not outn or not outn.inputs['Surface'].is_linked: continue
    src = outn.inputs['Surface'].links[0].from_socket
    geo = nt.nodes.new('ShaderNodeNewGeometry'); lp = nt.nodes.new('ShaderNodeLightPath')
    mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'
    nt.links.new(geo.outputs['Backfacing'], mul.inputs[0]); nt.links.new(lp.outputs['Is Camera Ray'], mul.inputs[1])
    tr = nt.nodes.new('ShaderNodeBsdfTransparent'); mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(mul.outputs[0], mix.inputs[0]); nt.links.new(src, mix.inputs[1]); nt.links.new(tr.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], outn.inputs['Surface'])

sweepL = bpy.data.lights.new('sweep', 'POINT'); sweepL.shadow_soft_size = 0.3
sweep = bpy.data.objects.new('sweep', sweepL); sc.collection.objects.link(sweep)
sweep.light_linking.receiver_collection = carcol

cam = bpy.data.cameras.new('cam'); co = bpy.data.objects.new('cam', cam)
sc.collection.objects.link(co); sc.camera = co
co.rotation_mode = 'QUATERNION'
cam.sensor_fit = 'VERTICAL'; cam.sensor_height = 24
cam.clip_start = 0.05
cam.dof.use_dof = True
QC = Quaternion((1, 0, 0), math.radians(90))

parts = {}
for o in sc.objects:
    if o.name.startswith('p') and o.name[1:].isdigit():
        o.rotation_mode = 'QUATERNION'; parts[int(o.name[1:])] = o
print('parts', len(parts))
def hide(o, h):
    o.hide_render = h
    for c in o.children_recursive: c.hide_render = h
base = {L_top: 420, L_sideL: 160, L_sideR: 90, L_front: 70, sK: 120}
rims = {L_rimB: 300, rO: 40}

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
sc.render.image_settings.file_format = 'JPEG'; sc.render.image_settings.quality = 95
sc.render.use_persistent_data = False
os.makedirs(outdir, exist_ok=True)
import time; t0 = time.time(); n = 0
for i in range(F0, F1 + 1, STEP):
    fp = os.path.join(outdir, 'f%04d.jpg' % i)
    if os.path.exists(fp): continue
    f = anim['frames'][i]
    for k, v in enumerate(f['p']):
        o = parts.get(k)
        if o is None: continue
        if not v: hide(o, True); continue
        hide(o, False)
        o.location = (v[0], -v[2], v[1])
        o.rotation_quaternion = (v[3], v[4], -v[6], v[5])
    c = f['cam']
    co.location = (c[0], -c[2], c[1])
    co.rotation_quaternion = QC @ Quaternion((c[3], c[4], c[5], c[6]))
    cam.lens = 12 / math.tan(math.radians(c[7]) / 2)
    e = f['e']
    cam.dof.focus_distance = max(0.5, (Vector((0.6, -0.3, 0.4)) - co.location).length)
    cam.dof.aperture_fstop = 5.6 + (64 - 5.6) * min(1, e * 3)
    for L, p in base.items(): L.data.energy = p * (0.04 + 0.96 * f['L'])
    for L in base: L.data.energy *= (1 - 0.5 * e)
    L_top.data.energy *= (1 - 0.8 * e)
    L_front.data.energy *= (1 - 0.9 * e)
    for L, p in rims.items(): L.data.energy = p * f['R']
    sweep.location = (f['sw'][0], -1.2, 1.5); sweepL.energy = 250 * f['sw'][1]
    sc.render.filepath = fp
    bpy.ops.render.render(write_still=True)
    n += 1; print('FRAME', i, 'done', n, 'avg %.1fs' % ((time.time() - t0) / n), flush=True)
print('DONE', outdir, dev)
