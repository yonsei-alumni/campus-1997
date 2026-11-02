"""Download CC0 assets from Poly Haven (https://polyhaven.com, CC0 license).
usage: fetch_polyhaven.py textures RES name...   -> assets_src/textures/<name>/{diff,nor,rough,arm}.jpg
       fetch_polyhaven.py models   RES name...   -> assets_src/models/<name>/ (gltf + textures)
       fetch_polyhaven.py hdris    RES name...   -> assets_src/hdri/<name>.hdr"""
import json, os, sys, urllib.request

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets_src')
UA = {'User-Agent': 'yonsei1997-campus-game/1.0'}

def get(url, dst):
    if os.path.exists(dst) and os.path.getsize(dst) > 0:
        return
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r, open(dst + '.part', 'wb') as f:
        f.write(r.read())
    os.replace(dst + '.part', dst)

def files(name):
    req = urllib.request.Request(f'https://api.polyhaven.com/files/{name}', headers=UA)
    return json.load(urllib.request.urlopen(req, timeout=60))

def texture(name, res):
    fl = files(name)
    want = {'Diffuse': 'diff', 'nor_gl': 'nor', 'Rough': 'rough', 'arm': 'arm', 'Displacement': 'disp'}
    for key, short in want.items():
        if key in fl and res in fl[key]:
            ent = fl[key][res].get('jpg') or fl[key][res].get('png')
            ext = 'jpg' if 'jpg' in fl[key][res] else 'png'
            get(ent['url'], os.path.join(ROOT, 'textures', name, f'{short}.{ext}'))

def model(name, res):
    fl = files(name)
    g = fl['gltf'][res]['gltf']
    d = os.path.join(ROOT, 'models', name)
    get(g['url'], os.path.join(d, os.path.basename(g['url'])))
    for rel, ent in g.get('include', {}).items():
        get(ent['url'], os.path.join(d, rel))

def hdri(name, res):
    fl = files(name)
    get(fl['hdri'][res]['hdr']['url'], os.path.join(ROOT, 'hdri', f'{name}_{res}.hdr'))

if __name__ == '__main__':
    kind, res, *names = sys.argv[1:]
    fn = {'textures': texture, 'models': model, 'hdris': hdri}[kind]
    for n in names:
        try:
            fn(n, res); print('ok', n)
        except Exception as e:
            print('FAIL', n, e)
