"""Preview rendering helpers (EEVEE, HDRI sky, sun)."""
import bpy, math, os
from mathutils import Vector
from common import ROOT

HDR = os.path.join(ROOT, 'assets_src', 'hdri', 'kloofendal_48d_partly_cloudy_puresky_1k.hdr')


def setup_world(strength=1.0):
    sc = bpy.context.scene
    if sc.world is None:
        sc.world = bpy.data.worlds.new('World')
    w = sc.world
    try:
        w.use_nodes = True
    except Exception:
        pass
    nt = w.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    env = nt.nodes.new('ShaderNodeTexEnvironment')
    env.image = bpy.data.images.load(HDR, check_existing=True)
    bg = nt.nodes.new('ShaderNodeBackground')
    bg.inputs['Strength'].default_value = strength
    out = nt.nodes.new('ShaderNodeOutputWorld')
    nt.links.new(env.outputs['Color'], bg.inputs['Color'])
    nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
    sun = bpy.data.lights.new('Sun', 'SUN')
    sun.energy = 4.0
    sun.angle = math.radians(1.5)
    so = bpy.data.objects.new('Sun', sun)
    so.rotation_euler = (math.radians(40), math.radians(10), math.radians(150))
    sc.collection.objects.link(so)


def render(path, target, dist=60, elev=20, azim=-60, lens=35, res=(1280, 800), samples=32, ground_plane=True):
    sc = bpy.context.scene
    try:
        sc.render.engine = 'BLENDER_EEVEE'
    except TypeError:
        pass
    sc.render.resolution_x, sc.render.resolution_y = res
    try:
        sc.eevee.taa_render_samples = samples
        sc.eevee.use_shadows = True
    except Exception:
        pass
    try:
        sc.view_settings.view_transform = 'AgX'
    except Exception:
        pass
    target = Vector(target)
    if ground_plane and 'PreviewGround' not in bpy.data.objects:
        bpy.ops.mesh.primitive_plane_add(size=2000, location=(target.x, target.y, target.z - 0.02))
        g = bpy.context.active_object
        g.name = 'PreviewGround'
        from common import material
        g.data.materials.append(material('grass'))
        uv = g.data.uv_layers.active
        for l in g.data.loops:
            v = g.data.vertices[l.vertex_index].co
            uv.data[l.index].uv = ((v.x + target.x), (v.y + target.y))
    cam = bpy.data.cameras.new('Cam')
    cam.lens = lens
    cam.clip_end = 5000
    co = bpy.data.objects.new('Cam', cam)
    sc.collection.objects.link(co)
    a, e = math.radians(azim), math.radians(elev)
    co.location = target + Vector((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e))) * dist
    d = target - co.location
    co.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    sc.camera = co
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(co)
    print('rendered', path)
