"""Tone-map the CC0 Poly Haven 8k pure-sky HDRI into an LDR sky texture for the web
(upper hemisphere only) and locate the sun direction. Then bake the environment light without the sun
(env_1k_nosun.hdr) and measure what the sun's disc threw (sky.json sun_E), for the game's DirectionalLight."""
import bpy, os, sys, json
import numpy as np
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
src = os.path.join(ROOT, 'assets_src/hdri/kloofendal_48d_partly_cloudy_puresky_8k.hdr')
img = bpy.data.images.load(src)
w, h = img.size
px = np.empty(w * h * 4, dtype=np.float32)
img.pixels.foreach_get(px)
px = px.reshape(h, w, 4)[..., :3]        # row 0 = bottom
lum = px @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
j, i = np.unravel_index(np.argmax(lum), lum.shape)
u, v = (i + 0.5) / w, (j + 0.5) / h
az = (u - 0.5) * 2 * np.pi                 # equirect longitude
el = (v - 0.5) * np.pi
print('SUN u=%.4f v=%.4f el=%.1fdeg' % (u, v, np.degrees(el)))
# exposure + ACES-like filmic curve, upper hemisphere (+3 deg below horizon)
up = px[int(h * 0.48):, :, :]
x = up * 0.55
a, b, c, d, e = 2.51, 0.03, 2.43, 0.59, 0.14
x = np.clip((x * (a * x + b)) / (x * (c * x + d) + e), 0, 1) ** (1 / 2.2)
out = bpy.data.images.new('sky', w, x.shape[0], alpha=False)
rgba = np.concatenate([x, np.ones(x.shape[:2] + (1,), np.float32)], -1)
out.pixels.foreach_set(rgba.astype(np.float32).ravel())
out.filepath_raw = os.path.join(ROOT, 'web/public/assets/hdri/sky_8k.jpg')
out.file_format = 'JPEG'
bpy.context.scene.render.image_settings.quality = 88
out.save()
del px, lum, up, x, rgba

# ---------------------------------------------------------------------------------------- environment light, no sun
# The game lights the scene with the 1k copy of the same HDRI (three's PMREM) and the sun with a DirectionalLight. Left
# in the environment, the sun's disc is ~2/3 of the light an upward face gets from it, and the shadow maps only stop
# the DirectionalLight: the shade under a tree or a building was still lit by the environment's sun. So the disc goes
# (its pixels filled with the sky round it: a smooth membrane from the ring outside, the circumsolar glow and the lit
# cloud near the sun stay) and what it threw, measured here, is given to the DirectionalLight instead (main.js).
# The backdrop (sky_8k.jpg above) keeps its sun.
SUN_R = 1.6                                 # degrees round the sun: its disc and the blur of the 1k downsample
env = bpy.data.images.load(os.path.join(ROOT, 'assets_src/hdri/kloofendal_48d_partly_cloudy_puresky_1k.hdr'))
ew, eh = env.size
E = np.empty(ew * eh * 4, dtype=np.float32)
env.pixels.foreach_get(E)
E = E.reshape(eh, ew, 4)[..., :3].astype(np.float64)        # row 0 = bottom
elv = ((np.arange(eh) + 0.5) / eh - 0.5) * np.pi           # elevation of each row
azv = ((np.arange(ew) + 0.5) / ew - 0.5) * 2 * np.pi
dirs = np.stack([np.cos(elv)[:, None] * np.cos(azv)[None], np.repeat(np.sin(elv)[:, None], ew, 1),
                 np.cos(elv)[:, None] * np.sin(azv)[None]], -1)
sun = np.array([np.cos(el) * np.cos(az), np.sin(el), np.cos(el) * np.sin(az)])
ang = np.degrees(np.arccos(np.clip(dirs @ sun, -1, 1)))
hole = ang < SUN_R
# fill: start from the mean of the ring just outside, relax to the average of the four neighbours (in a window round
# the hole: it is far from the image's edges)
ring = (ang >= SUN_R) & (ang < SUN_R + 1.0)
F = E.copy()
F[hole] = E[ring].mean(0)
rs, cs = np.nonzero(hole)
win = (slice(rs.min() - 4, rs.max() + 5), slice(cs.min() - 4, cs.max() + 5))
Fw, Hw = F[win], hole[win]
for _ in range(3000):
    nb = (np.roll(Fw, 1, 0) + np.roll(Fw, -1, 0) + np.roll(Fw, 1, 1) + np.roll(Fw, -1, 1)) / 4
    Fw[Hw] = nb[Hw]
F[win] = Fw
dO = (2 * np.pi / ew) * (np.pi / eh) * np.cos(elv)          # solid angle of a pixel in each row
removed = ((E - F) * hole[..., None] * dO[:, None, None]).sum((0, 1))   # irradiance facing the sun, linear RGB
upw = np.clip(dirs[..., 1], 0, None)[..., None] * dO[:, None, None]
share = ((E - F) * upw).sum((0, 1)) / (E * upw).sum((0, 1))
print('SUN DISC irradiance (facing it) rgb', removed, 'share of the upward irradiance', share)


def write_hdr(path, rgb):
    """Radiance RGBE, run-length encoded scanlines (rgb: rows from the top, linear). Written here: Blender's own HDR
    writer stores a new float image's pixels gamma-encoded."""
    hh, ww, _ = rgb.shape
    m = rgb.max(-1)
    ex = np.where(m > 1e-32, np.floor(np.log2(np.maximum(m, 1e-32))) + 1, -128)
    mant = np.where(m[..., None] > 1e-32, rgb / np.ldexp(1.0, ex.astype(int))[..., None] * 256, 0)
    q = np.concatenate([np.clip(mant, 0, 255).astype(np.uint8), np.clip(ex + 128, 0, 255).astype(np.uint8)[..., None]], -1)
    q[m <= 1e-32] = 0
    buf = bytearray(b'#?RADIANCE\nFORMAT=32-bit_rle_rgbe\n\n-Y %d +X %d\n' % (hh, ww))
    for row in q:
        buf += bytes([2, 2, ww >> 8, ww & 255])
        for ch in range(4):
            s, k = row[:, ch].tobytes(), 0
            while k < ww:
                r = 1                                   # a run of equal bytes from k
                while k + r < ww and r < 127 and s[k + r] == s[k]:
                    r += 1
                if r >= 3:
                    buf += bytes([128 + r, s[k]])
                    k += r
                    continue
                n = 1                                   # literal bytes up to the next run of 3
                while k + n < ww and n < 128 and not (k + n + 2 < ww and s[k + n] == s[k + n + 1] == s[k + n + 2]):
                    n += 1
                buf += bytes([n]) + s[k:k + n]
                k += n
    open(path, 'wb').write(buf)


write_hdr(os.path.join(ROOT, 'web/public/assets/hdri/env_1k_nosun.hdr'), F[::-1])

json.dump({'sun_u': float(u), 'sun_v': float(v), 'sky_v0': 0.48, 'sun_E': [round(float(c), 4) for c in removed]},
          open(os.path.join(ROOT, 'web/public/data/sky.json'), 'w'))
