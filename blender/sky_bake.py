"""Tone-map the CC0 Poly Haven 8k pure-sky HDRI into an LDR sky texture for the web
(upper hemisphere only) and locate the sun direction."""
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
json.dump({'sun_u': float(u), 'sun_v': float(v), 'sky_v0': 0.48}, open(os.path.join(ROOT, 'web/public/data/sky.json'), 'w'))
