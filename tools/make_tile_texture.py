"""Paint two white facade textures (diff / nor / rough), seamless, from the 1996 graduation-album photos (2022 재상봉
기념문집 「25년 전 우리는」, reference/재상봉_기념집_고증.md, reference/음악관_현관_1996.jpg,
reference/백주년기념관_박물관입구_1996_*.jpg):

  white_square_tiles   음악관's walls and planters: small glazed white square tiles, 8 x 8 per repeat, grey grout
                       (reference/학교연혁_음악관.jpg still shows them)
  white_stone_panels   백주년기념관's cylinders and walls: large white panels on a square grid, 4 x 4 per repeat,
                       thin pale joints, each panel a little different

Outputs: assets_src/textures/<name>/{diff,nor,rough}.jpg (tools/prepare_web_textures.py copies them into
web/public/assets/textures/pbr/; blender/materials.json scales them with `tile`).
Run: .venv/bin/python tools/make_tile_texture.py
"""
import os
import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
N = 1024


def paint(name, K, G, grout, shade_sd, glaze, seed):
    out = os.path.join(ROOT, 'assets_src/textures', name)
    os.makedirs(out, exist_ok=True)
    rng = np.random.default_rng(seed)
    T = N // K
    y, x = np.mgrid[0:N, 0:N]
    u, v = x % T, y % T
    d_edge = np.minimum.reduce([u, v, T - 1 - u, T - 1 - v]).astype(np.float64)
    joint = d_edge < G / 2
    # each tile / panel a slightly different white, a faint cloud over all, a softly bevelled edge
    shade = rng.normal(0.0, shade_sd, (K, K))[y // T, x // T]
    cloud = ndimage.gaussian_filter(rng.normal(0, 1, (N, N)), 18, mode='wrap')
    cloud = cloud / (np.abs(cloud).max() + 1e-6) * 0.025
    speck = ndimage.gaussian_filter(rng.normal(0, 1, (N, N)), 0.8, mode='wrap') * 0.012
    bevel = np.clip((d_edge - G / 2) / 4.0, 0, 1)
    face = (0.93 + shade + cloud + speck) * (0.95 + 0.05 * bevel)
    jcol = grout + ndimage.gaussian_filter(rng.normal(0, 1, (N, N)), 1.5, mode='wrap') * 0.03
    lum = np.where(joint, jcol, face)
    rgb = np.stack([lum * 0.995, lum * 0.995, lum * 0.985], -1)
    Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8)).save(os.path.join(out, 'diff.jpg'), quality=92)
    # height: the joints a little down, the faces gently domed at their bevels
    h = ndimage.gaussian_filter(np.where(joint, 0.0, 0.6 + 0.4 * bevel) + cloud * 0.3, 0.8, mode='wrap')
    gx, gy = ndimage.sobel(h, axis=1, mode='wrap'), ndimage.sobel(h, axis=0, mode='wrap')
    nx, ny, nz = -gx * 2.2, gy * 2.2, np.ones_like(h)
    L = np.sqrt(nx * nx + ny * ny + nz * nz)
    Image.fromarray(((np.stack([nx / L, ny / L, nz / L], -1) * 0.5 + 0.5) * 255).astype(np.uint8)).save(
        os.path.join(out, 'nor.jpg'), quality=92)
    rough = np.where(joint, 0.92, glaze + np.abs(cloud) * 2.0)
    Image.fromarray((np.clip(rough, 0, 1) * 255).astype(np.uint8), 'L').save(os.path.join(out, 'rough.jpg'), quality=90)
    print(name, 'ok')


paint('white_square_tiles', K=8, G=5, grout=0.66, shade_sd=0.009, glaze=0.32, seed=1996)
paint('white_stone_panels', K=4, G=3, grout=0.8, shade_sd=0.014, glaze=0.55, seed=1988)
