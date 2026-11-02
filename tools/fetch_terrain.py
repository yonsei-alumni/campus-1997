"""Download AWS Terrarium elevation tiles around Yonsei Sinchon campus and
write a local heightmap grid (meters) in campus-local coordinates.
Local frame: origin lat0/lon0, x = east (m), y = north (m)."""
import math, json, io, os, sys, urllib.request
from PIL import Image

LAT0, LON0 = 37.5640, 126.9380
MODE = sys.argv[1] if len(sys.argv) > 1 else 'near'
Z, HALF, STEP, NAME = {'near': (15, 1400, 10, 'terrain.json'),
                       'far': (12, 8000, 100, 'terrain_far.json')}[MODE]
OUT = os.path.join(os.path.dirname(__file__), '..', 'data')

def tile_xy(lat, lon, z):
    n = 2 ** z
    x = (lon + 180) / 360 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return x, y

def local_to_ll(x, y):
    lat = LAT0 + y / 110574.0
    lon = LON0 + x / (111320.0 * math.cos(math.radians(LAT0)))
    return lat, lon

cache = {}
def tile(tx, ty):
    if (tx, ty) not in cache:
        p = os.path.join(OUT, 'raw', f'terrarium_{Z}_{tx}_{ty}.png')
        if not os.path.exists(p):
            url = f'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{Z}/{tx}/{ty}.png'
            urllib.request.urlretrieve(url, p)
        cache[(tx, ty)] = Image.open(p).convert('RGB')
    return cache[(tx, ty)]

def elev(lat, lon):
    fx, fy = tile_xy(lat, lon, Z)
    px, py = fx * 256, fy * 256
    # bilinear in global pixel space
    x0, y0 = int(math.floor(px - .5)), int(math.floor(py - .5))
    ax, ay = px - .5 - x0, py - .5 - y0
    def h(gx, gy):
        im = tile(gx // 256, gy // 256)
        r, g, b = im.getpixel((gx % 256, gy % 256))
        return r * 256 + g + b / 256 - 32768
    return (h(x0, y0) * (1-ax) * (1-ay) + h(x0+1, y0) * ax * (1-ay) +
            h(x0, y0+1) * (1-ax) * ay + h(x0+1, y0+1) * ax * ay)

n = 2 * HALF // STEP + 1
rows = []
for j in range(n):
    y = -HALF + j * STEP
    rows.append([round(elev(*local_to_ll(-HALF + i * STEP, y)), 2) for i in range(n)])
json.dump({'origin': [LAT0, LON0], 'half': HALF, 'step': STEP, 'n': n,
           'rows_south_to_north': rows}, open(os.path.join(OUT, NAME), 'w'))
flat = [v for r in rows for v in r]
print('grid', n, 'min', min(flat), 'max', max(flat))
