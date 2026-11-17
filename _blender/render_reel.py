# Instagram reel (vertical) of the #47 F4 CG model: studio reveal -> launch -> high speed through light gates.
# usage: blender -b -P render_reel.py -- <glb> <anim.json> <outdir> [samples] [W] [H] [cpu|gpu] [start] [end] [step]
import bpy, sys, math, os, json, time
from mathutils import Vector, Quaternion
a = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
glb = a[0]; anim = json.load(open(a[1])); outdir = a[2]
samples = int(a[3]) if len(a) > 3 else 256
W = int(a[4]) if len(a) > 4 else 1080
H = int(a[5]) if len(a) > 5 else 1920
force_cpu = len(a) > 6 and a[6] == 'cpu'
F0 = int(a[7]) if len(a) > 7 else 0
F1 = int(a[8]) if len(a) > 8 else 419
STEP = int(a[9]) if len(a) > 9 else 1

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb)
sc = bpy.context.scene
carcol = bpy.data.collections.new('car_only')
for o in list(sc.objects): carcol.objects.link(o)

# ---------- materials (same conversion as the hero render) ----------
KEEP_EMIT = {'Material_62'}  # rain light stays emissive
for m in bpy.data.materials:
    if not m.use_nodes: continue
    nt = m.node_tree
    bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    outn = next((n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'), None)
    if m.name in KEEP_EMIT and outn is not None:
        for l in list(nt.links):
            if l.to_node == outn: nt.links.remove(l)
        em = nt.nodes.new('ShaderNodeEmission'); em.name = 'RAIN'
        em.inputs[0].default_value = (1.0, 0.02, 0.01, 1); em.inputs[1].default_value = 0.0
        nt.links.new(em.outputs[0], outn.inputs['Surface']); continue
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
        if tex and m.blend_method != 'OPAQUE': nt.links.new(tex.outputs['Alpha'], bsdf.inputs['Alpha'])
        nt.links.new(bsdf.outputs[0], outn.inputs['Surface'])
for m in bpy.data.materials:
    b = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None) if m.use_nodes else None
    if b and abs(b.inputs['Metallic'].default_value - 0.75) < 0.01 and abs(b.inputs['Roughness'].default_value - 0.38) < 0.01:
        b.inputs['Base Color'].default_value = (0.045, 0.047, 0.052, 1)
        b.inputs['Metallic'].default_value = 0.15; b.inputs['Roughness'].default_value = 0.5
        try: b.inputs['Coat Weight'].default_value = 0.0
        except Exception: pass

# ---------- assemble the finished car (last frame of the hero animation) ----------
fin = anim['frames'][-1]['p']
parts = {}
for o in sc.objects:
    if o.name.startswith('p') and o.name[1:].isdigit():
        k = int(o.name[1:]); v = fin[k] if k < len(fin) else None
        o.rotation_mode = 'QUATERNION'; parts[k] = o
        if not v:
            o.hide_render = True
            for c in o.children_recursive: c.hide_render = True
            continue
        o.location = (v[0], -v[2], v[1])
        o.rotation_quaternion = (v[3], v[4], -v[6], v[5])
WHEELS = [parts[k] for k in (48, 49, 50, 51) if k in parts]
R_WHEEL = 0.28

# ---------- world: near black ----------
w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
w.node_tree.nodes['Background'].inputs[0].default_value = (0.004, 0.0045, 0.006, 1)

# ---------- timing ----------
FPS = 30; NF = 420
sc.render.fps = FPS; sc.frame_start = 0; sc.frame_end = NF - 1
SHOTS = [0, 75, 135, 255, 345, 420]   # cut frames
V_TOP = 1.9  # m/frame (~205 km/h)
def speed(f):
    if f < 88: return 0.0
    t = min(1.0, (f - 88) / 62.0)
    return V_TOP * (t * t * (3 - 2 * t))
dist = [0.0]
for f in range(1, NF + 2): dist.append(dist[-1] + speed(f))

def key_linear(obj):
    if obj.animation_data and obj.animation_data.action:
        try:
            for fc in obj.animation_data.action.fcurves:
                for k in fc.keyframe_points: k.interpolation = 'LINEAR'
        except Exception:
            pass

# ---------- road (moves backwards under the car) ----------
road = bpy.data.objects.new('road', None); sc.collection.objects.link(road)
bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 0))
fl = bpy.context.object; fl.scale = (2400, 60, 1); fl.location = (900, 0, 0)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True); fl.parent = road
fm = bpy.data.materials.new('asphalt'); fm.use_nodes = True; nt = fm.node_tree; N = nt.nodes; Lk = nt.links.new
fb = N['Principled BSDF']
tc = N.new('ShaderNodeTexCoord')
nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 35.0; nz.inputs['Detail'].default_value = 6
Lk(tc.outputs['Object'], nz.inputs['Vector'])
rp = N.new('ShaderNodeValToRGB'); rp.color_ramp.elements[0].color = (0.006, 0.006, 0.007, 1); rp.color_ramp.elements[1].color = (0.03, 0.03, 0.033, 1)
Lk(nz.outputs['Fac'], rp.inputs[0])
# wet patches -> varying roughness
nz2 = N.new('ShaderNodeTexNoise'); nz2.inputs['Scale'].default_value = 0.18
Lk(tc.outputs['Object'], nz2.inputs['Vector'])
mr = N.new('ShaderNodeMapRange'); mr.inputs[1].default_value = 0.35; mr.inputs[2].default_value = 0.65; mr.inputs[3].default_value = 0.12; mr.inputs[4].default_value = 0.55
Lk(nz2.outputs['Fac'], mr.inputs[0]); Lk(mr.outputs[0], fb.inputs['Roughness'])
# lane lines: dashed white at |y|=2.3 (object space in metres)
sep = N.new('ShaderNodeSeparateXYZ'); Lk(tc.outputs['Object'], sep.inputs[0])
def mth(op, a_, b_=None):
    n = N.new('ShaderNodeMath'); n.operation = op
    if isinstance(a_, float): n.inputs[0].default_value = a_
    else: Lk(a_, n.inputs[0])
    if b_ is not None:
        if isinstance(b_, float): n.inputs[1].default_value = b_
        else: Lk(b_, n.inputs[1])
    return n.outputs[0]
yw = mth('ABSOLUTE', sep.outputs['Y'])
line = mth('LESS_THAN', mth('ABSOLUTE', mth('SUBTRACT', yw, 2.3)), 0.07)
xw = sep.outputs['X']
dash = mth('LESS_THAN', mth('MODULO', mth('ADD', xw, 10000.0), 8.0), 4.0)
mark = mth('MULTIPLY', line, dash)
mix = N.new('ShaderNodeMix'); mix.data_type = 'RGBA'
Lk(mark, mix.inputs['Factor']); Lk(rp.outputs[0], mix.inputs[6]); mix.inputs[7].default_value = (0.55, 0.55, 0.55, 1)
Lk(mix.outputs[2], fb.inputs['Base Color'])
fb.inputs['Specular IOR Level'].default_value = 0.5
fl.data.materials.append(fm)

# light gates: overhead bars + low side strips, orange / blue / white, every 9 m, parented to road
def emit_mat(name, col, strength):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != 'OUTPUT_MATERIAL': nt.nodes.remove(n)
    e = nt.nodes.new('ShaderNodeEmission'); e.inputs[0].default_value = col + (1,); e.inputs[1].default_value = strength
    nt.links.new(e.outputs[0], next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL').inputs['Surface'])
    return m, e
GATE_EMIT = []
def gate_row(name, col, strength, x0, spacing, count, boxes):
    m, e = emit_mat(name, col, strength); GATE_EMIT.append((e, strength))
    for i, (loc, size) in enumerate(boxes):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x0 + loc[0], loc[1], loc[2]))
        o = bpy.context.object; o.scale = size; o.parent = road; o.data.materials.append(m)
        o.visible_shadow = False
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        am = o.modifiers.new('arr', 'ARRAY'); am.count = count
        am.use_relative_offset = False; am.use_constant_offset = True; am.constant_offset_displace = (spacing, 0, 0)
gate_boxes = [((0, 0, 3.4), (0.35, 7.0, 0.06)),
              ((0, 3.6, 1.2), (0.25, 0.05, 2.4)), ((0, -3.6, 1.2), (0.25, 0.05, 2.4))]
side_boxes = [((0, 3.4, 0.08), (2.4, 0.04, 0.04)), ((0, -3.4, 0.08), (2.4, 0.04, 0.04))]
gate_row('g_orange', (1.0, 0.28, 0.02), 30.0, 14.0, 27.0, 38, gate_boxes)
gate_row('g_blue',   (0.05, 0.25, 1.0), 30.0, 23.0, 27.0, 38, gate_boxes)
gate_row('g_white',  (1.0, 0.95, 0.9),  3.0, 32.0, 27.0, 38, gate_boxes)
gate_row('g_side',   (1.0, 0.35, 0.05), 20.0, 6.0, 4.5, 230, side_boxes)

for f in range(0, NF + 1):
    road.location = (-dist[f], 0, 0); road.keyframe_insert('location', index=0, frame=f)
    for wo in WHEELS:
        wo.rotation_mode = 'XYZ'
        wo.rotation_euler = (0, dist[f] / R_WHEEL, 0); wo.keyframe_insert('rotation_euler', index=1, frame=f)
key_linear(road)
for wo in WHEELS: key_linear(wo)
# gates dark during the studio reveal, then flick on
for e, s in GATE_EMIT:
    for f, val in ((0, 0.0), (80, 0.0), (86, s * 1.6), (92, s)):
        e.inputs[1].default_value = val; e.inputs[1].keyframe_insert('default_value', frame=f)

# ---------- studio lights (fixed to the car) ----------
def T(x, y, z): return Vector((x, -z, y))  # three.js -> Blender
def area(name, pos, target, size, power, color=(1, 1, 1), sy=None):
    L = bpy.data.lights.new(name, 'AREA'); L.energy = power; L.color = color
    L.shape = 'RECTANGLE'; L.size = size; L.size_y = sy or size
    o = bpy.data.objects.new(name, L); sc.collection.objects.link(o)
    o.location = T(*pos); d = T(*target) - o.location
    o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return o
L_top = area('top', (0.2, 4.2, 0.0), (0.2, 0, 0), 7.0, 260, sy=2.2)
L_sideL = area('sideL', (0.5, 1.6, 4.5), (0.2, 0.4, 0), 6.0, 90, sy=1.0)
L_rimB = area('rimB', (-5.0, 1.6, -2.5), (0, 0.5, 0), 2.0, 260, color=(0.25, 0.42, 1.0))
rO = area('rimO', (-3.2, 2.6, -3.4), (0, 0.5, 0), 0.6, 40, color=(1.0, 0.45, 0.12))
for o in (L_sideL, rO): o.light_linking.receiver_collection = carcol
# studio key lights: start dark, swell during the reveal, ease down once the gates take over
for o, p in ((L_top, 260), (L_sideL, 90), (L_rimB, 260), (rO, 40)):
    for f, k in ((0, 0.05), (40, 0.6), (74, 1.0), (95, 1.0), (140, 0.45)):
        o.data.energy = p * k; o.data.keyframe_insert('energy', frame=f)
# sweeping strip light for the opening reveal (front -> back)
sw = area('sweep', (2.8, 1.6, 1.8), (0, 0.3, 0), 0.25, 0, sy=2.5)
sw.light_linking.receiver_collection = carcol
for f, x, p in ((0, 3.2, 0), (6, 3.0, 260), (70, -2.6, 260), (78, -3.0, 0)):
    sw.location.x = x; sw.keyframe_insert('location', index=0, frame=f)
    sw.data.energy = p; sw.data.keyframe_insert('energy', frame=f)
# rain light blinks once moving
rn = bpy.data.materials['Material_62'].node_tree.nodes['RAIN']
for f in range(0, NF, 8):
    rn.inputs[1].default_value = 0.0 if f < 88 or (f // 8) % 2 else 25.0
    rn.inputs[1].keyframe_insert('default_value', frame=f)
try:
    for fc in bpy.data.materials['Material_62'].node_tree.animation_data.action.fcurves:
        for k in fc.keyframe_points: k.interpolation = 'CONSTANT'
except Exception: pass

# ---------- camera: shots with hard cuts ----------
cam = bpy.data.cameras.new('cam'); co = bpy.data.objects.new('cam', cam); sc.collection.objects.link(co); sc.camera = co
tgt = bpy.data.objects.new('tgt', None); sc.collection.objects.link(tgt)
tr = co.constraints.new('TRACK_TO'); tr.target = tgt; tr.track_axis = 'TRACK_NEGATIVE_Z'; tr.up_axis = 'UP_Y'
cam.sensor_fit = 'HORIZONTAL'; cam.sensor_width = 36; cam.clip_start = 0.03
cam.dof.use_dof = True; cam.dof.focus_object = tgt
# (frame, cam pos, target, lens(mm, horizontal 36mm), f-stop)
KEYS = [
  # 1 studio reveal: low slide along the left side, nose -> cockpit
  [(0, (3.4, -1.45, 0.34), (2.0, 0.0, 0.2), 32, 2.4), (74, (1.0, -1.5, 0.52), (-0.2, 0.0, 0.5), 32, 2.4)],
  # 2 front wheel close-up, wheels start turning, gates flick on
  [(75, (1.75, -1.75, 0.30), (1.41, -0.74, 0.28), 34, 2.8), (134, (1.55, -1.62, 0.34), (1.41, -0.74, 0.30), 34, 2.8)],
  # 3 front 3/4 low tracking at speed
  [(135, (3.9, -1.9, 0.36), (0.3, 0.0, 0.42), 26, 5.6), (254, (3.1, -1.25, 0.28), (0.1, 0.0, 0.42), 26, 5.6)],
  # 4 high orbit, side -> rear
  [(255, (1.2, -3.4, 2.6), (0.0, 0.0, 0.35), 20, 6.0), (300, (-1.6, -2.9, 2.3), (0.0, 0.0, 0.40), 20, 6.0),
   (344, (-3.6, -0.8, 1.8), (0.0, 0.0, 0.45), 20, 6.0)],
  # 5 behind the rear wing, car pulls away from camera
  [(345, (-3.0, 0.5, 0.42), (-1.9, 0.0, 0.72), 26, 3.2), (380, (-4.2, 0.4, 0.5), (-1.6, 0.0, 0.65), 26, 4.0),
   (419, (-7.0, 0.25, 0.7), (-0.8, 0.0, 0.55), 26, 6.0)],
]
for shot in KEYS:
    for i, (f, p, t, lens, fs) in enumerate(shot):
        co.location = p; co.keyframe_insert('location', frame=f)
        tgt.location = t; tgt.keyframe_insert('location', frame=f)
        cam.lens = lens; cam.keyframe_insert('lens', frame=f)
        cam.dof.aperture_fstop = fs; cam.dof.keyframe_insert('aperture_fstop', frame=f)
LAST = {s[-1][0] for s in KEYS}
def fix_cuts(idb):
    ad = idb.animation_data
    if not ad or not ad.action: return
    try: fcs = ad.action.fcurves
    except Exception:
        fcs = [fc for l in ad.action.layers for st in l.strips for cb in st.channelbags for fc in cb.fcurves]
    for fc in fcs:
        for k in fc.keyframe_points:
            k.interpolation = 'CONSTANT' if int(k.co[0]) in LAST else 'BEZIER'
            k.handle_left_type = k.handle_right_type = 'AUTO_CLAMPED'
        fc.update()
    return fcs
fix_cuts(tgt); fix_cuts(cam)
cfc = fix_cuts(co)
# hand-held shake in the high-speed shots
for fc in cfc:
    if fc.data_path == 'location':
        nm = fc.modifiers.new('NOISE'); nm.scale = 6.0; nm.strength = 0.03 if fc.array_index == 2 else 0.018
        nm.phase = fc.array_index * 7.0
        nm.use_restricted_range = True; nm.frame_start = 135; nm.frame_end = 254; nm.blend_in = 15; nm.blend_out = 5

# ---------- render settings ----------
sc.render.engine = 'CYCLES'
sc.cycles.samples = samples; sc.cycles.use_denoising = True
sc.cycles.max_bounces = 8
sc.render.resolution_x = W; sc.render.resolution_y = H; sc.render.resolution_percentage = 100
sc.render.use_motion_blur = True; sc.render.motion_blur_shutter = 0.5
try: sc.cycles.motion_blur_position = 'START'
except Exception: pass
try: sc.render.motion_blur_position = 'START'
except Exception: pass
for wo in WHEELS:
    try: wo.cycles.motion_steps = 6
    except Exception: pass
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
sc.render.use_persistent_data = True
os.makedirs(outdir, exist_ok=True)
t0 = time.time(); n = 0
for i in range(F0, F1 + 1, STEP):
    fp = os.path.join(outdir, 'f%04d.jpg' % i)
    if os.path.exists(fp): continue
    sc.frame_set(i); sc.render.filepath = fp
    bpy.ops.render.render(write_still=True)
    n += 1; print('FRAME', i, 'done', n, 'avg %.1fs' % ((time.time() - t0) / n), flush=True)
print('DONE', outdir, dev)
