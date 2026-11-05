"""Build the 1997 Yonsei campus dataset from OpenStreetMap + elevation data.

Inputs : data/raw/osm_campus.json (Overpass), data/terrain.json, data/terrain_far.json
Outputs: data/campus.json                (used by Blender build + web)
         web/public/data/campus.json     (same, for the browser)
         web/public/data/terrain_near.bin / terrain_far.bin (Float32, row-major south->north)
         web/public/assets/textures/ground_splat.png
         data/debug_map.png              (top-down sanity check)

Local frame: x = east (m), y = north (m), origin lat 37.5640 / lon 126.9380.
Run with the project venv:  .venv/bin/python tools/build_campus.py
"""
import json, math, os, random
import numpy as np
from scipy import ndimage
from shapely.geometry import Polygon, LineString, Point, MultiPolygon
from shapely.ops import unary_union
from PIL import Image, ImageDraw

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
LAT0, LON0 = 37.5640, 126.9380
rng = random.Random(1997)


def xy(p):
    return ((p['lon'] - LON0) * 111320 * math.cos(math.radians(LAT0)), (p['lat'] - LAT0) * 110574)


osm = json.load(open(os.path.join(ROOT, 'data/raw/osm_campus.json')))['elements']
ways = {e['id']: e for e in osm if e.get('geometry')}

# ---------------------------------------------------------------------------
# 1997 building table.  OSM way id -> (style, levels, label override)
#   style 'lm:<builder>' = hand-modelled landmark (see blender/landmarks.py)
#   other styles = procedural facade generator (blender/generic.py)
# Buildings built after 1997 (학술정보원, 공학원, 새천년관, 경영관, 백양누리, 암병원 ...)
# are intentionally omitted.
# ---------------------------------------------------------------------------
# Names are the ones a 1997 student used (several halls were renamed in 1999, 2001 and 2013); halls built after
# May 1997 are left out, the ones going up then are marked 공사중.  Checked against the university's building history
# (yonsei.ac.kr/sc/349/subview.do), namu.wiki and OSM; three outlines once listed here are on the Ewha campus.
B = {
    163525865: ('lm:library', 5, '중앙도서관'),
    1444448640: ('lm:union', 4, '학생회관'),
    1444448646: ('white', 3, '학생회관 별관'),
    324328422: ('lm:centennial', 4, '백주년기념관'),
    246156115: ('lm:underwood', 3, '언더우드관'),
    246156116: ('lm:appenzeller', 3, '아펜젤러관'),
    246156118: ('lm:stimson', 2, '스팀슨관'),
    371403811: ('lm:auditorium', 4, '대강당'),
    429249499: ('lm:chapel', 2, '루스채플'),
    205583531: ('lm:engineering', 5, '제1공학관'),
    246156113: ('stone', 3, '핀슨관'),
    429249496: ('lm:hanok', 1, '광혜원'),
    # engineering / science quarter
    1451926793: ('modern', 5, '제1공학관'), 1451926787: ('modern', 5, '제1공학관'),
    1451926794: ('modern', 4, '제1공학관'), 256932940: ('modern', 6, '제2공학관'),
    224955691: ('modern', 5, '제3공학관 (공사중)'), 324328471: ('white', 2, '별동연구동'),
    222843398: ('white', 6, '과학관'), 468614722: ('brick', 3, '광복관'),
    256933753: ('white', 5, '경영학교실단'),
    421415366: ('gym', 2, '체육관'), 421415365: ('white', 4, '체육교육관'),
    # humanities / north campus
    246156112: ('modern', 6, '인문관'), 246156114: ('modern', 5, '인문관'),
    246156119: ('white', 4, '제2인문관 (공사중)'), 245623759: ('lm:yeonhui', 4, '연희관'),
    246156121: ('stone', 2, '연합신학대학원'), 246156123: ('modern', 6, '종합관'),
    246156117: ('stone', 3, '성암관'), 246156111: ('stone', 3, '교육관'),
    245623193: ('stone_pale', 4, '생활과학관'), 413217834: ('house', 1, '논지당'),
    242897922: ('lm:daewoo', 6, '대우관'), 242897923: ('lm:daewoo_annex', 5, '대우관 별관'),
    429077789: ('white', 4, '음악대학'), 429077790: ('white', 4, '음악대학'),
    429079066: ('stone', 2, '언더우드가 사택'), 472512289: ('brick', 2, '알렌관'),
    472512292: ('white', 2, '어린이생활지도연구원'), 472965030: ('house', 2, '대학사택'),
    472987415: ('house', 2, '대학사택'), 472987419: ('house', 2, '대학사택'),
    472534641: ('house', 2, '영빈관'), 472534642: ('house', 2, '총장공관'),
    472516998: ('tile', 5, '국제학사'), 371403603: ('brick', 5, '한국어학당'),
    429077785: ('white', 1, '영선실'), 472516999: ('white', 1, '차량실'),
    722550503: ('white', 2, '행정동'),
    # medical quarter (old Severance)
    472648570: ('modern', 10, '세브란스병원'), 429249489: ('modern', 6, '의료원 종합관'),
    429249493: ('white', 5, '치과대학'), 429249490: ('modern', 6, '치과대학병원'),
    429249494: ('white', 5, '간호대학'),
    473006250: ('white', 4, '광혜관'), 473006251: ('white', 5, '제중관'),
    324328456: ('white', 4, '의학도서관'), 473014379: ('modern', 5, '임상의학연구센터'),
    1178739301: ('white', 5, '의과대학'), 1178739302: ('white', 5, '의과대학'),
    473014385: ('white', 4, '동문회관'), 429079067: ('white', 4, '재활병원'),
    324328481: ('modern', 7, '심장혈관병원'), 324328472: ('white', 5, '안·이비인후과병원'),
    # in 1997 too, missing before
    246156110: ('stone', 2, '한경관'), 429249497: ('house', 1, '수경원 정자각'), 1178743320: ('white', 3, '미우학사'),
}
FLOOR_H = {'modern': 3.8, 'white': 3.6, 'stone': 4.2, 'house': 3.4, 'gym': 6.5, 'city': 3.0, 'brick': 3.6, 'tile': 3.4, 'stone_pale': 4.0}

# ---------------------------------------------------------------------------
# Terrain
# ---------------------------------------------------------------------------
tn = json.load(open(os.path.join(ROOT, 'data/terrain.json')))
tf = json.load(open(os.path.join(ROOT, 'data/terrain_far.json')))
H10 = np.array(tn['rows_south_to_north'], dtype=np.float64)       # 10 m grid, +-1400
H10 = ndimage.gaussian_filter(H10, 1.6)                             # remove DSM building bumps
NEAR_HALF, NEAR_STEP = 800, 5.0
n_near = int(2 * NEAR_HALF / NEAR_STEP) + 1
gx = np.linspace(-NEAR_HALF, NEAR_HALF, n_near)
ii = (gx + tn['half']) / tn['step']
JJ, II = np.meshgrid(ii, ii, indexing='ij')                          # rows = y, cols = x
Hn = ndimage.map_coordinates(H10, [JJ, II], order=3)
Hn = ndimage.gaussian_filter(Hn, 1.5)
Hn_orig = Hn.copy()


def sample(H, half, step, x, y):
    fx = (x + half) / step
    fy = (y + half) / step
    return float(ndimage.map_coordinates(H, [[fy], [fx]], order=1, mode='nearest')[0])


def grid_pts():
    X, Y = np.meshgrid(gx, gx)
    return X, Y

# --- 1997 백양로: OSM pedestrian way (old road alignment) + extension to the 삼거리
bys = None
for w in ways.values():
    if w.get('tags', {}).get('name') == '백양로' and w['tags'].get('highway') == 'pedestrian':
        bys = [xy(p) for p in w['geometry']]
bys = list(reversed(bys))                       # gate (south) -> north
bys = [(-108.0, -428.0)] + bys[1:] + [(33.0, 145.0), (38.0, 168.0)]
bline = LineString(bys)
# Road cross-section, half widths from the centre line.  As in the 1997 aerial photo (reference/1997_백양로_항공사진.jpg):
# a two-lane carriageway (white dashed centre line, yellow edge lines) with no median, a raised verge of
# clipped round boxwood on each side, a wide paver sidewalk, and an outer planting strip carrying the
# ginkgo row and a low clipped hedge.
ROAD = dict(median=0.0, lane=4.2, curb=0.25, verge=1.8, walk=6.5, strip=2.2)
E_CURB = ROAD['median'] + ROAD['lane'] + ROAD['curb']       # carriageway edge (curb top)
E_VERGE = E_CURB + ROAD['verge']                             # inner edge of the sidewalk
E_WALK = E_VERGE + ROAD['walk']                              # outer edge of the sidewalk
ROAD_HALF = E_WALK + ROAD['strip']


def s_at(x, y):
    return float(bline.project(Point(x, y)))

# Height profile along 백양로: sample, smooth, enforce gentle monotonic climb
L = bline.length
ss = np.arange(0, L + 0.1, 2.0)
prof = np.array([sample(Hn, NEAR_HALF, NEAR_STEP, *bline.interpolate(s).coords[0]) for s in ss])
prof = ndimage.gaussian_filter1d(prof, 12)
prof = np.maximum.accumulate(prof)              # 백양로 climbs steadily toward 본관
prof = ndimage.gaussian_filter1d(prof, 8)


def prof_h(s):
    return float(np.interp(s, ss, prof))


# zebra crossings (arc length): 백주년기념관, 학생회관-중앙도서관, 대강당, 삼거리.  Near the gate the 1997 photo
# shows a yellow/white hatched speed bump (paint only) instead.  The carriageway itself stays clear of objects.
CROSS = [round(s_at(-55, -200), 1), round(s_at(-20, -62), 1), round(s_at(5, 40), 1), round(L - 30, 1)]
BUMP_S = 64.0

X, Y = grid_pts()
pts = np.stack([X.ravel(), Y.ravel()], 1)
from shapely import points as shp_points, distance as shp_distance, line_locate_point
P = shp_points(pts)
dist = shp_distance(P, bline).reshape(X.shape)
spos = line_locate_point(bline, P).reshape(X.shape)
hline = np.interp(spos, ss, prof)
w = np.clip((dist - (ROAD_HALF + 4)) / 30.0, 0, 1)
w = w * w * (3 - 2 * w)
Hn = hline * (1 - w) + Hn * w

# --- 대운동장 / pitches: flatten to their mean height
for wv in ways.values():
    t = wv.get('tags', {})
    if t.get('leisure') in ('pitch', 'track', 'stadium') and len(wv['geometry']) > 3:
        poly = Polygon([xy(p) for p in wv['geometry']])
        if not poly.is_valid or poly.area < 400:
            continue
        inside = np.array([poly.contains(Point(x, y)) for x, y in pts]).reshape(X.shape)
        if inside.any():
            m = ndimage.binary_dilation(inside, iterations=2)
            soft = ndimage.gaussian_filter(m.astype(float), 1.2)
            Hn = Hn * (1 - soft) + float(Hn[inside].mean()) * soft

# --- 대강당 앞 농구장 (1997): an outdoor court between 백양로 and the 대강당 driveway, where 금호아트홀 (under
# 백양누리) was later built (namu.wiki 연세대학교/신촌캠퍼스).  No photo found: a standard 28 x 15 m court, long side
# along 백양로.  Flatten the ground under it.
COURT = dict(pos=[21.9, 2.5], rot=1.313, L=28.0, W=15.0)
# --- 활천 (活泉) fountain in front of 제1공학관 (alumni memory; namu.wiki lists 활천대 among the landmarks moved for
# 금호아트홀).  No photo found: a round granite basin with a central jet on the lawn before the hall's 백양로 front.
FOUNTAIN = dict(pos=[-99.0, -255.0], r=4.2)


def court_poly(pad=0.0):
    c_, s_ = math.cos(COURT['rot']), math.sin(COURT['rot'])
    hl, hw = COURT['L'] / 2 + pad, COURT['W'] / 2 + pad
    return Polygon([(COURT['pos'][0] + u * c_ - v * s_, COURT['pos'][1] + u * s_ + v * c_)
                    for u, v in ((-hl, -hw), (hl, -hw), (hl, hw), (-hl, hw))])


_inside = np.array([court_poly(1.5).contains(Point(x, y)) for x, y in pts]).reshape(X.shape)
if _inside.any():
    _soft = ndimage.gaussian_filter(ndimage.binary_dilation(_inside, iterations=1).astype(float), 1.0)
    Hn = Hn * (1 - _soft) + float(Hn[_inside].mean()) * _soft

# --- old 노천극장 (1997): bowl carved into the hillside east of the stage
AMPH = dict(cx=160.0, cy=163.0, arena_rx=18.0, arena_ry=14.0, rows=15, row_d=1.6, row_h=0.45,
            rot=math.radians(45))      # local -x (stage / open side) faces SW, downhill; seats climb toward 안산
amph_poly = None
for wv in ways.values():
    if wv['id'] == 180788744:
        amph_poly = Polygon([xy(p) for p in wv['geometry']]).buffer(0)
AMPH['arena_h'] = round(sample(Hn, NEAR_HALF, NEAR_STEP, AMPH['cx'], AMPH['cy']) - 0.6, 2)


def amph_height(x, y):
    """Terraced bowl height (continuous); used both for terrain carving and Blender."""
    dx, dy = x - AMPH['cx'], y - AMPH['cy']
    c, s = math.cos(-AMPH['rot']), math.sin(-AMPH['rot'])
    u, v = dx * c - dy * s, dx * s + dy * c
    r = math.hypot(u / AMPH['arena_rx'], v / AMPH['arena_ry'])
    if r <= 1:
        return AMPH['arena_h']
    d = (r - 1) * min(AMPH['arena_rx'], AMPH['arena_ry'])
    return AMPH['arena_h'] + d / AMPH['row_d'] * AMPH['row_h']

R_OUT = AMPH['rows'] * AMPH['row_d'] + max(AMPH['arena_rx'], AMPH['arena_ry'])
# the bowl replaces the hillside (cut and fill), blending back over 30 m
for j in range(n_near):
    for i in range(n_near):
        x, y = gx[i], gx[j]
        dx, dy = x - AMPH['cx'], y - AMPH['cy']
        c_, s_ = math.cos(-AMPH['rot']), math.sin(-AMPH['rot'])
        u, v = dx * c_ - dy * s_, dx * s_ + dy * c_
        ang = math.atan2(v / AMPH['arena_ry'], u / AMPH['arena_rx'])
        r_el = math.hypot(u / (AMPH['arena_rx'] + AMPH['rows'] * AMPH['row_d']), v / (AMPH['arena_ry'] + AMPH['rows'] * AMPH['row_d']))
        if r_el > 2.2:
            continue
        open_side = abs(ang) > math.radians(128)          # stage side (west): flat apron
        hb = AMPH['arena_h'] + 0.1 if open_side else min(amph_height(x, y), AMPH['arena_h'] + AMPH['rows'] * AMPH['row_h']) - 0.25
        t = float(np.clip((r_el - 1.0) / (0.35 if open_side else 0.9), 0, 1))
        t = t * t * (3 - 2 * t)
        Hn[j, i] = hb * (1 - t) + Hn[j, i] * t

# ---------------------------------------------------------------------------
# Buildings
# ---------------------------------------------------------------------------


def ground_h(x, y):
    return sample(Hn, NEAR_HALF, NEAR_STEP, x, y)


def footprint(wv):
    pts_ = [xy(p) for p in wv['geometry']]
    if pts_[0] == pts_[-1]:
        pts_ = pts_[:-1]
    poly = Polygon(pts_).buffer(0)
    if isinstance(poly, MultiPolygon):
        poly = max(poly.geoms, key=lambda g: g.area)
    poly = poly.simplify(0.35)
    if not poly.exterior.is_ccw:
        poly = Polygon(list(poly.exterior.coords)[::-1])
    return poly


buildings = []
campus_polys = []
for wid, (style, lv, label) in B.items():
    wv = ways.get(wid)
    if not wv:
        print('missing', wid, label)
        continue
    poly = footprint(wv)
    campus_polys.append(poly)
    hs = [ground_h(x, y) for x, y in poly.exterior.coords]
    fh = FLOOR_H.get(style, 4.0)
    buildings.append(dict(id=wid, name=label, style=style, levels=lv,
                          height=round(lv * fh + (1.2 if not style.startswith('lm') else 0), 2),
                          base=round(min(hs), 2), top_ground=round(max(hs), 2),
                          footprint=[[round(x, 2), round(y, 2)] for x, y in list(poly.exterior.coords)[:-1]]))

# 용재관 (demolished; 경영관 has stood on its site since 2015, so it is not in OSM).  Placed from the 경영관 indoor
# corridors in OSM (x 72..120, y 88..136) and reference/용재관.jpg, taken from behind the Underwood statue looking
# south-east: a white modernist hall whose slender stair tower faces the end of 백양로, a three-storey wing with a
# dark hipped roof and the entrance canopy beside it, and a five-storey block behind.
YONGJAE = dict(o=(74.0, 124.0), ang=math.radians(20), parts=[
    (990001, 'lm:yongjae', 7, (-3.2, 3.2, -4, 3.5)),        # tower: u0, u1, v0, v1 (v = towards 백양로 / the statue)
    (990002, 'lm:none', 3, (3.2, 34, -11, 1)),          # wing
    (990003, 'lm:none', 5, (-2, 36, -27, -11)),       # block
])


def yongjae_poly(u0, u1, v0, v1):
    (ox, oy), a = YONGJAE['o'], YONGJAE['ang']
    c, s_ = math.cos(a), math.sin(a)
    return Polygon([(ox + u * c - v * s_, oy + u * s_ + v * c) for u, v in ((u0, v0), (u1, v0), (u1, v1), (u0, v1))])


for pid, style, lv, uv in YONGJAE['parts']:
    poly = yongjae_poly(*uv)
    campus_polys.append(poly)
    hs = [ground_h(x, y) for x, y in poly.exterior.coords]
    buildings.append(dict(id=pid, name='용재관', style=style, levels=lv, height=round(lv * 3.6, 2),
                          base=round(min(hs), 2), top_ground=round(max(hs), 2),
                          footprint=[[round(x, 2), round(y, 2)] for x, y in list(poly.exterior.coords)[:-1]],
                          frame=dict(o=YONGJAE['o'], ang=round(YONGJAE['ang'], 5), uv=uv)))

campus_zone = unary_union([p.buffer(60) for p in campus_polys]).buffer(-20)

# unnamed buildings: neighbourhood houses outside the campus (1990s low-rise 주택가)
n_city = 0
for wv in ways.values():
    t = wv.get('tags', {})
    if 'building' not in t or 'name' in t or wv['type'] != 'way':
        continue
    poly = footprint(wv)
    if poly.area < 25 or campus_zone.contains(poly.centroid):
        continue
    c = poly.centroid
    if bline.distance(c) < 40:
        continue
    hs = [ground_h(x, y) for x, y in poly.exterior.coords]
    lv = rng.choice([2, 2, 2, 3, 3, 4]) if poly.area < 400 else rng.choice([3, 4, 5])
    buildings.append(dict(id=wv['id'], name='', style='city', levels=lv, height=round(lv * 3.0 + 0.8, 2),
                          base=round(min(hs), 2), top_ground=round(max(hs), 2),
                          footprint=[[round(x, 2), round(y, 2)] for x, y in list(poly.exterior.coords)[:-1]]))
    n_city += 1
print('buildings', len(buildings), 'city', n_city)
bpolys = [Polygon(b['footprint']) for b in buildings]
ball = unary_union(bpolys)

# ---------------------------------------------------------------------------
# Ground splat map  (R asphalt, G pavers, B dirt/forest floor ; rest = grass)
# ---------------------------------------------------------------------------
SPLAT = dict(x0=-560.0, y0=-560.0, x1=640.0, y1=680.0, res=0.5)
SW = int((SPLAT['x1'] - SPLAT['x0']) / SPLAT['res'])
SH = int((SPLAT['y1'] - SPLAT['y0']) / SPLAT['res'])


def to_px(x, y):
    return ((x - SPLAT['x0']) / SPLAT['res'], (SPLAT['y1'] - y) / SPLAT['res'])

layers = {k: Image.new('L', (SW, SH), 0) for k in ('asphalt', 'pavers', 'dirt')}
dr = {k: ImageDraw.Draw(v) for k, v in layers.items()}


def draw_line(layer, coords, width):
    pp = [to_px(x, y) for x, y in coords]
    wpx = max(1, int(width / SPLAT['res']))
    dr[layer].line(pp, fill=255, width=wpx, joint='curve')
    r = wpx / 2
    for x, y in pp:
        dr[layer].ellipse([x - r, y - r, x + r, y + r], fill=255)


def draw_poly(layer, poly, val=255):
    if poly.is_empty:
        return
    geoms = poly.geoms if hasattr(poly, 'geoms') else [poly]
    for g in geoms:
        if g.geom_type != 'Polygon':
            continue
        dr[layer].polygon([to_px(x, y) for x, y in g.exterior.coords], fill=val)
        for hole in g.interiors:
            dr[layer].polygon([to_px(x, y) for x, y in hole.coords], fill=0)

# forest floor under woods (natural=wood / landuse=forest)
woods = []
for wv in ways.values():
    t = wv.get('tags', {})
    if t.get('natural') == 'wood' or t.get('landuse') == 'forest':
        if len(wv['geometry']) > 3:
            pg = Polygon([xy(p) for p in wv['geometry']]).buffer(0)
            if pg.area > 200:
                woods.append(pg)
woods_u = unary_union(woods) if woods else Polygon()
draw_poly('dirt', woods_u.buffer(-6), 170)

# city ground: everything around houses is concrete/asphalt-ish alleys
city = unary_union([bp.buffer(5) for bp, b in zip(bpolys, buildings) if b['style'] == 'city'])
draw_poly('asphalt', city, 210)

# OSM roads / paths (indoor corridors skipped; modern 백양로 garden paths skipped)
WID = {'primary': 24, 'primary_link': 9, 'secondary': 14, 'tertiary': 10, 'residential': 6.5,
       'living_street': 6, 'service': 6, 'unclassified': 6, 'road': 6, 'busway': 8,
       'footway': 2.6, 'path': 2.0, 'steps': 3.0, 'pedestrian': 4}
bcorr = bline.buffer(ROAD_HALF + 12)
# 정문 안쪽 왼편 화단섬 (1997 photo): hedge-bordered flower bed with azaleas, a pine, a stone marker and a sign,
# wrapped by a small road that curves from the gate toward the 공학관 motorbike parking.
ISL = Polygon([(-122.5, -393.0), (-140.0, -396.0), (-146.5, -386.0), (-145.5, -352.0), (-139.0, -330.0),
               (-124.0, -321.0), (-104.5, -327.0)]).difference(bline.buffer(ROAD_HALF + 0.6))
if isinstance(ISL, MultiPolygon):
    ISL = max(ISL.geoms, key=lambda g: g.area)
ISL_ROAD = [(-112, -403.5), (-130, -403.0), (-145.5, -400.5), (-152.5, -389), (-153.5, -364), (-150, -340),
            (-143, -322), (-133, -313)]
# east of 백양로 between the gate and 백주년기념관: in 1997 a lawn with scattered trees and a shaded car park
# (the curving promenade paths in OSM belong to the 2015 백양로 garden)
EAST_LAWN = Polygon([(-86, -404), (-18, -404), (-18, -266), (-50, -258)]).difference(bline.buffer(ROAD_HALF + 1))
paths_out = []
for wv in ways.values():
    t = wv.get('tags', {})
    hw = t.get('highway')
    if hw not in WID or t.get('area') == 'yes' or t.get('indoor') or t.get('level', '0') not in ('0', '0;1'):
        continue
    if t.get('tunnel') or t.get('layer', '0').startswith('-'):
        continue
    if t.get('name') == '백양로':
        continue
    g = [xy(p) for p in wv['geometry']]
    ls = LineString(g)
    if ls.intersects(ISL.buffer(-0.5)) and hw not in ('footway', 'path', 'steps', 'pedestrian'):
        continue
    if hw in ('footway', 'path', 'steps', 'pedestrian'):
        if EAST_LAWN.contains(ls.centroid):
            continue
        ls = ls.difference(bcorr).difference(ISL.buffer(1.0))
        if ls.is_empty:
            continue
        lsl = ls.geoms if hasattr(ls, 'geoms') else [ls]
        for l in lsl:
            if l.length < 3:
                continue
            draw_line('pavers', l.coords, WID[hw])
            paths_out.append(dict(kind=hw, w=WID[hw], pts=[[round(x, 1), round(y, 1)] for x, y in l.coords]))
    else:
        draw_line('asphalt', g, WID[hw])
        paths_out.append(dict(kind=hw, w=WID[hw], pts=[[round(x, 1), round(y, 1)] for x, y in g]))

# 1997 roads branching at the 삼거리 + 정문 forecourt
extra_roads = [
    [(38, 168), (20, 175), (-2, 178), (-43, 186), (-74, 194)],                 # west fork
    [(38, 168), (62, 160), (85, 150), (110, 140)],                            # east fork toward 노천극장
    [(-108, -428), (-150, -432), (-250, -428)], [(-108, -428), (0, -440), (120, -440)],
    ISL_ROAD,
]
for r in extra_roads:
    draw_line('asphalt', r, 7 if r is ISL_ROAD else 8)
    paths_out.append(dict(kind='service', w=7 if r is ISL_ROAD else 8, pts=[list(p) for p in r]))


def along_raw(s, off):
    p = bline.interpolate(s)
    p2 = bline.interpolate(min(L, s + 1))
    p0 = bline.interpolate(max(0, s - 1))
    tx, ty = p2.x - p0.x, p2.y - p0.y
    n_ = math.hypot(tx, ty)
    return p.x - ty / n_ * off, p.y + tx / n_ * off, math.atan2(ty, tx)


# shaded car park on the lawn south-west of 백주년기념관 (red car under the trees in the 1997 photo)
LOT_E = [along_raw(s, -(ROAD_HALF + 8.5)) for s in np.arange(150, 196, 3.2)]
draw_line('asphalt', [(x, y) for x, y, _ in LOT_E], 7.0)
draw_line('asphalt', [along_raw(150, -(ROAD_HALF + 1))[:2], LOT_E[0][:2]], 5.0)
# 백양로 itself is real geometry (Blender) – paint asphalt below so seams never show grass
draw_line('asphalt', bys, 2 * E_CURB)
draw_line('pavers', bys, 2 * ROAD_HALF)


# building aprons (paved strips around campus buildings), library forecourt, 정문 plaza
aprons = unary_union([bp.buffer(3.5) for bp, b in zip(bpolys, buildings) if b['style'] != 'city'])
draw_poly('pavers', aprons)
plazas = [
    Polygon([(-85, -72), (-66, 4), (-12, -8), (-30, -88)]),                     # 중앙도서관 앞 광장
    Polygon([(18, -60), (4, -112), (-14, -105), (2, -52)]),                     # 학생회관 앞
    Point(-108, -418).buffer(22),                                              # 정문
    Polygon([(40, 150), (100, 140), (110, 185), (55, 195)]).buffer(2),          # 노천극장 진입
]
for pz in plazas:
    draw_poly('pavers', pz)

# ---------------------------------------------------------------------------
# Front gardens laid out from the photos (reference/학교연혁_언더우드관.jpg, 언더우드관_2024_*, 학교연혁_연희관.jpg,
# 연희관_2024_*, 학교연혁_대우관.jpg, 대우관_*): each in a frame (u across, v towards the building)
# ---------------------------------------------------------------------------
def frame(ox, oy, ux, uy):
    n_ = math.hypot(ux, uy)
    ux, uy = ux / n_, uy / n_
    return lambda u, v: (ox + u * ux - v * uy, oy + u * uy + v * ux)


def frame_from(bid):
    # the recessed front edge (footprint[3] -> [4]) of an H-plan hall; v points into the building
    fp_ = next(b for b in buildings if b['id'] == bid)['footprint']
    (ax, ay), (bx, by) = fp_[3], fp_[4]
    return frame(ax, ay, bx - ax, by - ay)


def fpoly(W, pts):
    return Polygon([W(u, v) for u, v in pts])


# 언더우드관 앞 정원: a formal parterre.  The axis runs from the Underwood statue to the hall's door; four lawn beds
# edged with clipped boxwood carry clipped pines and topiary; a cross walk halfway.
WU = frame(62.0, 213.0, 0.970, -0.243)
garden = Polygon([(30, 190), (80, 177), (95, 236), (44, 250)])
draw_poly('pavers', garden.buffer(1.5))
draw_poly('pavers', garden.buffer(-3), 0)
draw_line('pavers', [WU(0, -30), WU(0, 31)], 5.5)
draw_line('dirt', [WU(-25, 2), WU(25, 2)], 3.0)
# 연희관 앞: an axis walk from the door to a round stone planter, boxwood beds either side, big shade trees
WY = frame_from(245623759)
yeonhui_garden = fpoly(WY, [(-2, -2), (42, -2), (44, -34), (-4, -34)])
draw_line('pavers', [WY(20, 0), WY(20, -34)], 4.0)
draw_poly('pavers', Point(*WY(20, -13)).buffer(4.6))
draw_line('dirt', [WY(-2, -24), WY(42, -24)], 2.6)
# 대우관 상뜰: the round garden south of the hall, on the OSM footway ring (9 m across) with its radial walks:
# a round bed in the middle, benches on the ring, pines on the lawns between the walks
WD = frame_from(242897922)
SANG = (106.8, 427.1)
daewoo_garden = Point(*SANG).buffer(17)
draw_poly('pavers', Point(*SANG).buffer(6.4))
draw_poly('pavers', Point(*SANG).buffer(3.9), 0)
draw_line('pavers', [WD(23.5, 0), SANG], 4.0)
draw_poly('pavers', court_poly(1.0))
draw_poly('pavers', Point(*FOUNTAIN['pos']).buffer(FOUNTAIN['r'] + 2.2))
GARDEN_ZONES = [garden, yeonhui_garden, daewoo_garden, court_poly(2.0), Point(*FOUNTAIN['pos']).buffer(FOUNTAIN['r'] + 4)]

# amphitheater arena (dirt), sports field (dirt), tree-root patches done in web shader
draw_poly('dirt', Point(AMPH['cx'], AMPH['cy']).buffer(1).simplify(0))
c, s = math.cos(AMPH['rot']), math.sin(AMPH['rot'])
ell = [(AMPH['cx'] + (AMPH['arena_rx'] + 1) * math.cos(a) * c - (AMPH['arena_ry'] + 1) * math.sin(a) * s,
        AMPH['cy'] + (AMPH['arena_rx'] + 1) * math.cos(a) * s + (AMPH['arena_ry'] + 1) * math.sin(a) * c)
       for a in np.linspace(0, 2 * math.pi, 48)]
draw_poly('dirt', Polygon(ell))
for wv in ways.values():
    t = wv.get('tags', {})
    if t.get('leisure') in ('pitch', 'track') and len(wv['geometry']) > 3:
        pg = Polygon([xy(p) for p in wv['geometry']]).buffer(0)
        if pg.area > 1500:
            draw_poly('dirt', pg, 230)

# the old amphitheater: no paths across the bowl
bowl = Polygon([(AMPH['cx'] + (AMPH['arena_rx'] + AMPH['rows'] * AMPH['row_d'] + 1) * math.cos(a) * math.cos(AMPH['rot']) - (AMPH['arena_ry'] + AMPH['rows'] * AMPH['row_d'] + 1) * math.sin(a) * math.sin(AMPH['rot']),
                  AMPH['cy'] + (AMPH['arena_rx'] + AMPH['rows'] * AMPH['row_d'] + 1) * math.cos(a) * math.sin(AMPH['rot']) + (AMPH['arena_ry'] + AMPH['rows'] * AMPH['row_d'] + 1) * math.sin(a) * math.cos(AMPH['rot'])) for a in np.linspace(0, 2 * math.pi, 64)])
draw_poly('asphalt', bowl, 0)
draw_poly('pavers', bowl, 0)
draw_poly('dirt', bowl, 0)
draw_poly('dirt', Polygon(ell))
spl = np.stack([np.array(layers['asphalt']), np.array(layers['pavers']), np.array(layers['dirt'])], -1).astype(np.float32)
# priority: asphalt > pavers > dirt
spl[..., 1] = np.minimum(spl[..., 1], 255 - spl[..., 0])
spl[..., 2] = np.minimum(spl[..., 2], 255 - spl[..., 0] - spl[..., 1])
for ch in range(3):
    spl[..., ch] = ndimage.gaussian_filter(spl[..., ch], 0.7)
os.makedirs(os.path.join(ROOT, 'web/public/assets/textures'), exist_ok=True)
Image.fromarray(np.clip(spl, 0, 255).astype(np.uint8), 'RGB').save(
    os.path.join(ROOT, 'web/public/assets/textures/ground_splat.png'), optimize=True)

# ---------------------------------------------------------------------------
# Vegetation
# ---------------------------------------------------------------------------
trees = []        # [species, x, y, scale, rot]
shrubs = []       # [kind, x, y, scale, rot]
asph = np.array(layers['asphalt']) > 40
pav = np.array(layers['pavers']) > 40


def blocked(x, y, pad=4.0):
    px, py = to_px(x, y)
    if not (0 <= px < SW and 0 <= py < SH):
        return False
    r = int(pad / SPLAT['res'])
    x0, x1, y0, y1 = int(px) - r, int(px) + r, int(py) - r, int(py) + r
    x0, y0 = max(0, x0), max(0, y0)
    return bool(asph[y0:y1, x0:x1].any() or pav[y0:y1, x0:x1].any())

ball_buf = ball.buffer(5)
# Openings in the verge / outer strip where side roads and the 정문 화단섬 road meet 백양로
GAPS = []          # (s, side, half_width)
for pth in paths_out:
    if pth['kind'] in ('footway', 'path', 'steps', 'pedestrian'):
        continue
    ls_ = LineString(pth['pts'])
    hit = ls_.intersection(bline.buffer(ROAD_HALF + 0.5))
    if hit.is_empty or bline.distance(ls_) > ROAD_HALF:
        continue
    for side in (-1, 1):
        edge = bline.offset_curve(side * (E_CURB + 0.5))
        cut = ls_.intersection(edge)
        for g in (cut.geoms if hasattr(cut, 'geoms') else [cut]):
            if g.is_empty or g.geom_type != 'Point':
                continue
            s_ = float(bline.project(g))
            if 6 < s_ < L - 6:
                GAPS.append((round(s_, 1), side, round(pth['w'] / 2 + 1.5, 1)))
GAPS.append((round(s_at(*ISL_ROAD[0]), 1), 1, 5.0))


def in_gap(s, side, pad=0.0):
    if any(abs(s - c) < 3.0 + pad for c in CROSS):
        return True
    return any(sd == side and abs(s - g) < hw + pad for g, sd, hw in GAPS)


# 백양로 ginkgo rows (은행나무 가로수) in the outer planting strip with a clipped hedge, and the boxwood verges
for side in (-1, 1):
    s = 22.0
    while s < L - 30:
        x, y, _ = along_raw(s, side * (E_WALK + ROAD['strip'] * 0.5))
        if not in_gap(s, side, 1.0) and not ball.buffer(2).contains(Point(x, y)):
            trees.append(['ginkgo', round(x, 2), round(y, 2), round(rng.uniform(0.85, 1.0), 2), round(rng.uniform(0, 6.28), 2)])
        s += 8.5
    s = 18.0
    while s < L - 24:
        if not in_gap(s, side, 0.6):
            x, y, a = along_raw(s, side * (E_WALK + ROAD['strip'] * 0.5))
            if not ball.buffer(1).contains(Point(x, y)):
                shrubs.append(['hedge_low', round(x, 2), round(y, 2), round(rng.uniform(0.95, 1.05), 2), round(a, 3)])
        s += 1.5
    s = 14.0
    while s < L - 20:
        if not in_gap(s, side, 0.8):
            x, y, _ = along_raw(s, side * (E_CURB + ROAD['verge'] * 0.5))
            shrubs.append(['topiary_round', round(x, 2), round(y, 2), round(rng.uniform(0.95, 1.1), 2), 0])
        s += 2.6

# 정문 화단섬: hedge border, red azaleas massed along the south and east edges, pine + maple + zelkova
ring = ISL.buffer(-0.8).exterior
for d_ in np.arange(0, ring.length, 1.5):
    p = ring.interpolate(d_)
    q = ring.interpolate(min(ring.length, d_ + 0.5))
    shrubs.append(['hedge_low', round(p.x, 2), round(p.y, 2), 1.0, round(math.atan2(q.y - p.y, q.x - p.x), 3)])
# azaleas massed in two rows just inside the hedge along the south and the 백양로 (east) edges
for off in (0.0, 1.15):
    rr = ISL.buffer(-1.9 - off).exterior
    d_ = 0.0
    while d_ < rr.length:
        p = rr.interpolate(d_)
        if p.y < -380 or bline.distance(p) < ROAD_HALF + 4.5:
            shrubs.append(['azalea_red', round(p.x + rng.uniform(-.15, .15), 2), round(p.y + rng.uniform(-.15, .15), 2),
                           round(rng.uniform(0.85, 1.05), 2), round(rng.uniform(0, 6.28), 2)])
        d_ += 1.25
for sp, x, y, sc in (('pine', -132, -364, 1.35), ('maple', -138, -381, 1.0), ('pine', -128, -340, 1.1),
                     ('zelkova', -137, -345, 1.0), ('maple', -122, -332, 0.9)):
    trees.append([sp, x, y, sc, round(rng.uniform(0, 6.28), 2)])

# east lawn between the gate and 백주년기념관: a denser 1997 planting (zelkova, pine, cherry, maple)
lot_line = LineString([(x, y) for x, y, _ in LOT_E]).buffer(4.5)
east_pts = []
for k in range(6000):
    x, y = rng.uniform(-90, -18), rng.uniform(-404, -258)
    pt = Point(x, y)
    if not EAST_LAWN.buffer(-2).contains(pt) or ball_buf.contains(pt) or lot_line.contains(pt) or blocked(x, y, 2.5):
        continue
    if any((x - u) ** 2 + (y - v) ** 2 < 8.0 ** 2 for u, v in east_pts):
        continue
    east_pts.append((x, y))
    trees.append([rng.choice(['zelkova', 'zelkova', 'pine', 'pine', 'cherry', 'maple']), round(x, 2), round(y, 2),
                  round(rng.uniform(0.85, 1.2), 2), round(rng.uniform(0, 6.28), 2)])

# campus scatter (Poisson-ish)
species_campus = ['zelkova'] * 5 + ['pine'] * 3 + ['cherry'] * 1 + ['ginkgo'] * 1 + ['maple'] * 1
placed = [(t[1], t[2]) for t in trees]
from scipy.spatial import cKDTree


def far_enough(x, y, r):
    for px_, py_ in placed[-400:]:
        if (px_ - x) ** 2 + (py_ - y) ** 2 < r * r:
            return False
    return True

zone_campus = campus_zone.buffer(30)
bbox = (-420, -430, 560, 600)
cand = 0
grid_cells = {}
CELL = 9.0
for k in range(60000):
    x = rng.uniform(bbox[0], bbox[2])
    y = rng.uniform(bbox[1], bbox[3])
    pt = Point(x, y)
    in_wood = woods_u.contains(pt)
    in_campus = zone_campus.contains(pt)
    if not (in_wood or in_campus):
        continue
    r = 6.5 if in_wood else 11.0
    key = (int(x // CELL), int(y // CELL))
    ok = True
    for dx in (-2, -1, 0, 1, 2):
        for dy in (-2, -1, 0, 1, 2):
            for (qx, qy) in grid_cells.get((key[0] + dx, key[1] + dy), []):
                if (qx - x) ** 2 + (qy - y) ** 2 < r * r:
                    ok = False
    if not ok or ball_buf.contains(pt) or blocked(x, y, 3.5 if in_wood else 4.5) or bcorr.contains(pt):
        continue
    if amph_poly is not None and Point(AMPH['cx'], AMPH['cy']).distance(pt) < R_OUT + 1:
        continue
    if any(z.contains(pt) for z in GARDEN_ZONES) or ISL.buffer(3).contains(pt) or EAST_LAWN.contains(pt) or lot_line.contains(pt):
        continue
    sp = rng.choice(['pine', 'pine', 'oak', 'oak', 'zelkova']) if in_wood else rng.choice(species_campus)
    trees.append([sp, round(x, 2), round(y, 2), round(rng.uniform(0.8, 1.25), 2), round(rng.uniform(0, 6.28), 2)])
    grid_cells.setdefault(key, []).append((x, y))
# ring of pines around the old amphitheater (as in the April 1997 photo)
for a in np.linspace(0, 2 * math.pi, 26, endpoint=False):
    if abs(((a - math.pi - AMPH["rot"]) + math.pi) % (2 * math.pi) - math.pi) < 0.8:
        continue        # keep the stage side open
    rr = R_OUT + rng.uniform(3, 8)
    x, y = AMPH['cx'] + rr * math.cos(a), AMPH['cy'] + rr * math.sin(a)
    if not ball_buf.contains(Point(x, y)):
        trees.append(['pine', round(x, 2), round(y, 2), round(rng.uniform(1.0, 1.3), 2), round(rng.uniform(0, 6.28), 2)])
def hedge_rect(W, u0, u1, v0, v1, gap=None, step=1.5):
    """low clipped boxwood round a bed; gap=(edge index, centre, half width) leaves an opening"""
    corners = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
    for e in range(4):
        (ua, va), (ub, vb) = corners[e], corners[(e + 1) % 4]
        L_ = math.hypot(ub - ua, vb - va)
        (xa, ya), (xb, yb) = W(ua, va), W(ub, vb)
        a_ = math.atan2(yb - ya, xb - xa)
        for k in range(int(L_ / step) + 1):
            f_ = min(1.0, (k + 0.5) * step / L_)
            if gap and gap[0] == e and abs(f_ * L_ - gap[1]) < gap[2]:
                continue
            shrubs.append(['hedge_low', round(xa + (xb - xa) * f_, 2), round(ya + (yb - ya) * f_, 2), 1.0, round(a_, 3)])


def plant(kind, W, u, v, sc, rot=0.0):
    x, y = W(u, v)
    (trees if kind in ('pine', 'zelkova', 'ginkgo', 'cherry', 'maple', 'oak') else shrubs).append(
        [kind, round(x, 2), round(y, 2), round(sc, 2), round(rot, 3)])


def axis_angle(W):
    (x0, y0), (x1, y1) = W(0, 0), W(0, 1)
    return math.atan2(y1 - y0, x1 - x0)


# 언더우드관 앞 정원
for su in (-1, 1):
    for (v0, v1) in ((-23.0, -0.5), (4.5, 25.0)):
        u0, u1 = sorted((su * 4.5, su * 22.5))
        hedge_rect(WU, u0, u1, v0, v1)
        uc, vc = (u0 + u1) / 2, (v0 + v1) / 2
        plant('pine', WU, uc, vc, 0.55, rng.uniform(0, 6.28))                      # the clipped pine in each bed
        for du in (-5.5, 5.5):
            for dv in (-6.5, 6.5):
                plant('topiary_round', WU, uc + du, vc + dv, 1.25)
        for (cu, cv) in ((u0 + 1.4, v0 + 1.4), (u1 - 1.4, v0 + 1.4), (u0 + 1.4, v1 - 1.4), (u1 - 1.4, v1 - 1.4)):
            plant('topiary_cone', WU, cu, cv, 1.1)
# tall trees standing round the parterre's edge
for (u, v) in ((-27, -20), (-28, 8), (-27, 26), (27, -22), (28, 6), (27, 27)):
    plant('zelkova', WU, u, v, 1.15, rng.uniform(0, 6.28))
# 연희관 앞 정원
hedge_rect(WY, 3.0, 15.5, -28.0, -5.0)
hedge_rect(WY, 24.5, 37.0, -28.0, -5.0)
for uc in (9.25, 30.75):
    for vv in (-9.0, -16.5, -24.0):
        plant('topiary_round', WY, uc, vv, 1.3)
for k in range(8):                                                        # round planter on the axis
    a_ = 2 * math.pi * k / 8
    plant('topiary_round', WY, 20 + 2.6 * math.cos(a_), -13 + 2.6 * math.sin(a_), 0.85)
plant('bush', WY, 20, -13, 1.2)
for (u, v) in ((-1.5, -31), (41.5, -31), (-9, -16), (49, -16), (12, -33), (28, -33)):
    plant('zelkova', WY, u, v, 1.2, rng.uniform(0, 6.28))
# 대우관 상뜰
ang_d = axis_angle(WD)
trees.append(['pine', SANG[0], SANG[1], 0.7, 0.4])
for k in range(9):
    a_ = 2 * math.pi * k / 9
    x_, y_ = SANG[0] + 2.9 * math.cos(a_), SANG[1] + 2.9 * math.sin(a_)
    shrubs.append(['topiary_round', round(x_, 2), round(y_, 2), 0.8, 0])
for k in range(8):
    a_ = 2 * math.pi * k / 8 + math.pi / 8
    x_, y_ = SANG[0] + 11.5 * math.cos(a_), SANG[1] + 11.5 * math.sin(a_)
    trees.append(['pine', round(x_, 2), round(y_, 2), round(rng.uniform(0.75, 0.95), 2), round(rng.uniform(0, 6.28), 2)])
# shrubs around building aprons
for b, bp in zip(buildings, bpolys):
    if b['style'] == 'city':
        continue
    ring = bp.buffer(5.5).exterior
    nshr = int(ring.length / 7)
    for k in range(nshr):
        p = ring.interpolate(rng.uniform(0, ring.length))
        if not blocked(p.x, p.y, 1.2) and not ball.contains(p) and not any(z.contains(p) for z in GARDEN_ZONES) and rng.random() < 0.55:
            shrubs.append(['bush', round(p.x, 2), round(p.y, 2), round(rng.uniform(0.7, 1.3), 2), round(rng.uniform(0, 6.28), 2)])
print('trees', len(trees), 'shrubs', len(shrubs))

# ---------------------------------------------------------------------------
# Props & landmarks
# ---------------------------------------------------------------------------


def along(s, off):
    p = bline.interpolate(s)
    p2 = bline.interpolate(min(L, s + 1))
    tx, ty = p2.x - p.x, p2.y - p.y
    n_ = math.hypot(tx, ty)
    return p.x - ty / n_ * off, p.y + tx / n_ * off, math.atan2(ty, tx)

props = []
# 백양로 street lamps: two-armed lamps with box heads at the inner edge of both sidewalks (1997 aerial photo)
for s in np.arange(40, L - 20, 34):
    for side in (-1, 1):
        s_ = s + (17 if side > 0 else 0)
        if in_gap(s_, side, 1.0):
            s_ += 4.0
        x, y, a = along_raw(s_, side * (E_VERGE + 0.45))
        props.append(['lamp_arm', round(x, 2), round(y, 2), round(a + (math.pi if side < 0 else 0), 3)])
# white vertical flags hung along the outer edge of the west sidewalk near the gate
for s in np.arange(30, 165, 7.0):
    if not in_gap(s, 1, 0.5):
        x, y, a = along_raw(s, E_WALK - 0.35)
        props.append(['flag_white', round(x, 2), round(y, 2), round(a, 3)])
# banners (현수막) across the road, poles in the boxwood verges.  The first three are read off the 1997 photo.
BANNERS = [
    (46, dict(text='창립 7주년 기념 세미나 및 학부모 초빙 행사', sub='연세대학교 사회환경건축공학부 도시공학전공', marks=['경', '축']), 'white'),
    (92, dict(text='기술고등고시 설명회', sub='분야: 기계, 전기, 화공, 환경, 토목, 건축, 전산, 통신기술'), 'white_yellow'),
    (138, dict(text='설계공동연구소 10주년 기념식 및 초청강연회'), 'white'),
    # 연고전 응원 현수막: 신촌 상점들이 걸어 준 푸른 현수막이 줄지어 걸리는 건 가을(연고제)뿐이다.
    # 글귀는 reference/1997_제2백양로_파란물결_연고전현수막_연세춘추.jpg 에서 읽은 것.
    (160, dict(text='연고전이 그대를 기다린다  —  주색가무를 갖춘자여!', sub='다복주전 · 연세대학교 응원단', only='autumn'), 'blue'),
    (175, dict(text='그 이름 찬란히 빛나라, 연세여!', sub='YESSS · 연세대학교 응원단', only='autumn'), 'blue'),
    (190, dict(text='독수리여! 본질을 꿰뚫는 이성으로', sub='복성각 · 연세대학교 응원단', only='autumn'), 'blue'),
    (205, dict(text='ENJOY! THIS IS BEAUTIFUL!', sub='SLAMMERS 337-8169 · 연세대학교 응원단', only='autumn'), 'blue'),
    (220, dict(text='연고전, 연세의 승리를 위한 푸른 함성', sub='연세대학교 응원단', only='autumn'), 'blue'),
    (235, dict(text='연고전이 열리는 날, 신촌이 푸르다', sub='신촌 상점가 · 연세대학교 응원단', only='autumn'), 'blue'),
    (250, dict(text='거친파도 해치고 나가자. 연세!', sub='먹쇠식당 · 연세대학교 응원단', only='autumn'), 'blue'),
    (310, dict(text='’97 대동제  ·  5월, 백양로에서 만나요',
               seasons=dict(autumn=dict(text='’97 가을 학술제  ·  학과별 발표회와 초청강연', color='white'))), 'yellow'),
    (390, dict(text='신입생 여러분 환영합니다  —  총학생회',
               seasons=dict(autumn=dict(text='2학기 중간고사  ·  중앙도서관 열람실 24시간 개방  —  총학생회'))), 'white'),
    # 연고전 is in September: in spring the 4·19 marathon (reference/1997_마라톤대회.jpg), in May the 대동제 shows,
    # in late October the victory (reference/1997_연고전_승리.jpg: 3승 1무 1패)
    (460, dict(text='’97 4·19 마라톤대회  —  4월 19일 백양로 출발',
               seasons=dict(summer=dict(text='’97 대동제 축하공연  ·  노천극장', color='yellow'),
                            autumn=dict(text='’97 정기 연고전 3승 1무 1패 압승!  고마워요 연세인'))), 'blue'),
]
banners = []
for s, spec, col in BANNERS:
    x1, y1, a = along_raw(s, -(E_CURB + ROAD['verge'] * 0.5))
    x2, y2, _ = along_raw(s, (E_CURB + ROAD['verge'] * 0.5))
    banners.append(dict(color=col, a=[round(x1, 2), round(y1, 2)], b=[round(x2, 2), round(y2, 2)],
                        h=round(prof_h(s), 2), **spec))

def P(name, x, y, rot=0.0):
    props.append([name, round(x, 2), round(y, 2), round(rot, 3)])

# payphones & benches near student hubs
for (x, y, r) in [(-2, -70, 1.3), (0, -76, 1.3), (-44, -60, -0.25), (-46, -54, -0.25), (-92, -408, 0.0), (-88, -409, 0.0), (36, -112, 2.9)]:
    P('payphone', x, y, r)
for (x, y, r) in [(-50, -25, -1.82), (-47, -14, -1.82), (-58, -60, -1.82),
                  (-20, 35, 1.3), (6, 60, -1.82), (110, 160, 1.3), (-36, -140, -1.82), (-46, -180, -1.82)]:
    P('bench', x, y, r)
# garden benches, long side along the walk, seat towards it (BENCH_FACE: which way the bench model looks)
BENCH_FACE = math.pi


def bench_along(W, u, v, face_u):
    (x, y) = W(u, v)
    a_ = axis_angle(W) - math.pi / 2 + (0 if face_u < 0 else math.pi) + BENCH_FACE
    P('bench', x, y, a_)


for v in (-17.0, -6.0, 10.0, 20.0):                 # 언더우드관: along the axis, both sides
    bench_along(WU, -3.6, v, 1)
    bench_along(WU, 3.6, v, -1)
for v in (-20.0, -26.5):                            # 연희관: along the axis walk
    bench_along(WY, 17.6, v, 1)
    bench_along(WY, 22.4, v, -1)
for k in range(6):                                  # 대우관 상뜰: round the court, facing the middle
    a_ = 2 * math.pi * k / 6 + math.pi / 6
    x_, y_ = SANG[0] + 5.6 * math.cos(a_), SANG[1] + 5.6 * math.sin(a_)
    P('bench', x_, y_, a_ + math.pi / 2 + BENCH_FACE)
for (x, y) in [(-48, -40), (-4, -64), (45, 200), (-94, -404), (-44, -175)]:
    P('trashcan', x, y, 0)
# double-globe lamps around the library forecourt (1997 library photo) and at the tip of the 화단섬
for (x, y) in [(-64, -58), (-58, -22), (-74, -40), (-121, -394)]:
    P('lamp_double', x, y, -0.25)
# 화단섬: natural stone marker, campus guide sign, white round planters along the little road
P('stone_marker', -126, -371, 0.4)
P('sign_board', -141, -390, -0.9)
for k in range(7):
    x, y = -116 - k * 4.6, -408.2 + k * 0.2
    P('planter', x, y, 0)

# parked & moving cars (1990s 승용차), engineering-side motorbikes
cars = []
# west of 백양로 between 제1공학관 and 중앙도서관 (cars along the side road in the 1997 photo)
LOT_W = [along_raw(s, ROAD_HALF + 9.0) for s in np.arange(255, 300, 3.0)]
lots = [((60, 100), (100, 92), 9), ((-130, 110), (-80, 130), 8), ((20, -150), (40, -180), 6)]
for (a, b_, n) in lots:
    for k in range(n):
        t_ = k / max(1, n - 1)
        x = a[0] + (b_[0] - a[0]) * t_
        y = a[1] + (b_[1] - a[1]) * t_
        ang = math.atan2(b_[1] - a[1], b_[0] - a[0]) + math.pi / 2
        if rng.random() < 0.85 and not ball.buffer(1.5).contains(Point(x, y)):
            cars.append([rng.choice(['sedan', 'sedan', 'hatch', 'taxi']), round(x, 2), round(y, 2), round(ang + rng.uniform(-.05, .05), 3), rng.randrange(8)])
for line in (LOT_W, LOT_E):
    for (x, y, a) in line:
        if rng.random() < 0.8 and not ball.buffer(1.5).contains(Point(x, y)):
            cars.append([rng.choice(['sedan', 'sedan', 'hatch', 'taxi']), round(x, 2), round(y, 2),
                         round(a + math.pi / 2 + rng.uniform(-.05, .05), 3), rng.randrange(8)])
# motorbikes in front of the south end of 제1공학관
for k in range(16):
    t_ = k / 15
    x, y = -150 + 15 * t_ + rng.uniform(-.3, .3), -294 - 17 * t_
    P('motorbike', x, y, -0.85 + rng.uniform(-.2, .2))

# keep the carriageway clear: nothing static may stand on 백양로's driving lanes
def on_carriageway(x, y):
    return bline.distance(Point(x, y)) < E_CURB + 0.3 and bline.project(Point(x, y)) < L - 1
n0 = (len(props), len(cars), len(trees), len(shrubs))
props = [p for p in props if not on_carriageway(p[1], p[2])]
cars = [c for c in cars if not on_carriageway(c[1], c[2])]
trees = [t for t in trees if not on_carriageway(t[1], t[2])]
shrubs = [t for t in shrubs if not on_carriageway(t[1], t[2])]
print('removed from carriageway (props, cars, trees, shrubs):',
      n0[0] - len(props), n0[1] - len(cars), n0[2] - len(trees), n0[3] - len(shrubs))

LANDMARKS = [
    dict(id='gate', name='정문', pos=[-106, -410], r=22, photo=None,
         title='연세대학교 정문', year='1997',
         text='신촌 로터리에서 걸어 올라오면 만나는 정문. 1997년의 정문 앞에는 학교 버스와 오토바이, 그리고 오늘도 늦은 학생들이 뒤섞였다. 여기서 백양로가 북쪽 본관까지 곧게 뻗어 있다.'),
    dict(id='baekyangro', name='백양로', pos=[-82, -300], r=26, photo=['photos/baekyangro_1997_pano.jpg', 'photos/yongo_banner_news_1997.jpg'],
         title='그때의 백양로', year='1997',
         text='1997년의 백양로는 차와 사람이 함께 오가던 아스팔트 길이었다. 2차선 차도 양옆의 둥근 회양목, 넓은 보도와 은행나무 가로수, 그리고 길을 가로지른 현수막들. 연고제가 있는 가을이면 신촌 상점들이 건 푸른 응원 현수막이 줄지어 걸려 「제2백양로의 파란물결」이라 불렸다. 2015년 백양로 재창조 사업으로 차도는 지하로 들어가고 지금은 보행자 전용 숲길이 되었다.'),
    dict(id='engineering', name='제1공학관', pos=[-104, -262], r=20, photo=None,
         title='공과대학 (제1공학관)', year='1997',
         text='정문을 들어서면 왼편으로 길게 늘어선 공학관. 1997년 사진 속 공학관 앞에는 오토바이들이 줄지어 서 있다.'),
    dict(id='centennial', name='백주년기념관', pos=[-30, -215], r=26, photo=['photos/centennial_1997.jpg'],
         title='백주년기념관', year='1997',
         text='원통형 매스가 인상적인 백주년기념관. 공연과 강연, 졸업 행사가 열리던 곳으로, 1997년 백양로 오른편 풍경의 중심이었다.'),
    dict(id='eagle', name='독수리상', pos=[-52, -82], r=16, photo=['photos/eagle_2024.jpg'],
         title='독수리상', year='1997',
         text='연세의 상징 독수리. 높은 기둥 위에서 날개를 편 독수리는 지금도 같은 자리에서 백양로를 내려다본다.'),
    dict(id='library', name='중앙도서관', pos=[-58, -40], r=22, photo=['photos/library_1997.jpg', 'photos/library_reading_1997.jpg', 'photos/baekyangro_library_1995.jpg'],
         title='1997년 중앙도서관', year='1997',
         text='1984년 준공된 중앙도서관. 아치형 기둥이 늘어선 정면은 그 시절 연세인 모두의 배경이었다. 시험 기간이면 열람실 자리를 맡으려 새벽부터 줄을 섰다.'),
    dict(id='union', name='학생회관', pos=[0, -62], r=22, photo=['photos/union_1997.jpg', 'photos/marathon_news_1997.jpg'],
         title='1997년 학생회관', year='1997',
         credit='사진: 연세춘추 제1316호(1997.5.5) 「4·19 정신잇기」 김민정 기자 · 연세대학교 기록관',
         text='격자무늬 콘크리트 외벽의 학생회관. 동아리방과 식당, 총학생회가 있던 캠퍼스의 사랑방이었다. 벽면에는 늘 대자보와 현수막이 걸려 있었다. 1997년 4월 18일에는 이 앞에서 4·19 정신 계승 마라톤이 열렸다. 200여 명의 학생이 10km를 달리며 선전전을 벌였다.'),
    dict(id='chapel', name='루스채플', pos=[50, -70], r=18, photo=None,
         title='루스채플', year='1997',
         text='1974년 미국 헨리 루스 재단의 기부금과 학교 보조금으로 지어진 채플. 채플 수업 시간이면 학생들이 이 앞에 모여들었다.'),
    dict(id='auditorium', name='대강당', pos=[38, 30], r=22, photo=None,
         title='대강당', year='1997',
         text='1980년 완공된 대강당(선교70주년기념관). 입학식과 졸업식, 각종 집회와 공연이 열린 큰 무대였다.'),
    dict(id='amphitheater', name='노천극장', pos=[150, 150], r=30, photo=['photos/amphitheater_1997.jpg', 'photos/amphitheater_1999.jpg'],
         title='구 노천극장의 마지막 모습', year='1997.04',
         text='잔디 계단이 언덕을 따라 둥글게 둘러선 옛 노천극장. 1997년 4월 사진은 철거 전 마지막 모습이다. 아카라카와 응원제의 함성이 울리던 이 자리에는 1999년 5월 지금의 새 노천극장이 들어섰다.'),
    dict(id='underwood', name='언더우드관', pos=[58, 215], r=30, photo=['photos/underwood_2023.jpg', 'photos/underwood_2024.jpg', 'photos/underwood_garden_2024.jpg'],
         title='언더우드관 · 스팀슨관 · 아펜젤러관', year='1920s',
         text='백양로 끝, 담쟁이로 덮인 석조 건물들. 언더우드관 앞 정원을 사이에 두고 스팀슨관과 아펜젤러관이 마주 선다. 연세의 역사가 시작된 곳.'),
    dict(id='events', name='게시판 · 그때 우리는', pos=[9, -36], r=9, photo=['photos/marathon_1997.jpg', 'photos/daedongje_1997.jpg', 'photos/yongo_1997.jpg', 'photos/cheer_1997.jpg', 'photos/yongo_banner_1997.jpg'],
         title='신촌 캠퍼스 1997 · 그때 우리는', year='1997',
         text='4월 마라톤대회, 5월 빗속의 대동제, 9월 정기 연고전 출정식과 응원제. 백양로는 늘 푸른 물결로 가득했다.'),
    dict(id='yongjae', name='용재관', pos=[71.8, 136.0], r=18, photo=['photos/yongjae_1990s.jpg'],
         title='용재관', year='1957 – 2013',
         credit='사진: 동문 제공 (reference/용재관.jpg)',
         text='연세대 초대 총장 용재(庸齋) 백낙준의 호를 딴 흰 건물. 1957년 도서관으로 지어졌고, 언더우드 동상 너머로 보이던 세로로 긴 계단탑이 상징이었다. 2013년 헐리고 그 자리에 경영관(2015)이 섰다. 경영관 한쪽의 「용재관 타워」가 옛 모습을 잇는다.'),
    dict(id='daewoo', name='대우관', pos=[113.5, 453.8], r=26,
         photo=['photos/daewoo_2017.jpg', 'photos/daewoo_2024.jpg', 'photos/daewoo_annex_2017.jpg'],
         title='대우관과 상뜰', year='1996',
         credit='사진: 연세대 상경대학 홈페이지 (blog.naver.com/maxx5335/221067910905 재인용) · 다음 카페 「훌리건 천국」 이호성 (2024)',
         text='1996년 6월 문을 연 상경대학 · 경영대학의 새 집. 대우그룹 김우중 회장과 상경대 동문들의 기부로 지어져 대우관(김우중 기념관)이라 불렸다. 흰 석조의 고딕풍 건물로, 앞뜰의 소나무 정원 「상뜰」은 공강 시간마다 붐볐다. 정문에서 900m, 캠퍼스에서 가장 높고 깊숙한 곳.'),
    dict(id='yeonhui', name='연희관', pos=[88.0, 343.0], r=20, photo=['photos/yeonhui_2024a.jpg', 'photos/yeonhui_2024b.jpg'],
         title='연희관 가는 길', year='1956',
         credit='사진: 다음 카페 「훌리건 천국」 이호성 (2024)',
         text='1956년 과학관으로 지어져 1984년부터 연희관으로 불린 석조 건물. 담쟁이 덮인 벽과 회양목 정원 사이로, 대우관까지 이어지는 오르막길이 시작된다.'),
]
STATUES = dict(
    eagle=dict(pos=[-52, -82], rot=math.radians(-14 + 90)),
    underwood_statue=dict(pos=[55.5, 187.5], rot=math.radians(-14)),
    court=dict(pos=COURT['pos'], rot=COURT['rot'], L=COURT['L'], W=COURT['W']),
    fountain=dict(pos=FOUNTAIN['pos'], r=FOUNTAIN['r'], rot=0.0),     # courtyard entrance, facing down the campus axis
    gate=dict(pos=[-108, -424], rot=math.radians(-14)),
)
for v in STATUES.values():
    v['h'] = round(ground_h(*v['pos']), 2)

SPAWN = dict(pos=[-118, -397], yaw=math.radians(-14))

# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------
os.makedirs(os.path.join(ROOT, 'web/public/data'), exist_ok=True)
Hn.astype(np.float32).tofile(os.path.join(ROOT, 'web/public/data/terrain_near.bin'))
Hf = np.array(tf['rows_south_to_north'], dtype=np.float32)
Hf = ndimage.gaussian_filter(Hf, 0.7).astype(np.float32)
Hf.tofile(os.path.join(ROOT, 'web/public/data/terrain_far.bin'))
# ---------------------------------------------------------------------------
# Building name markers (bird's-eye pins, walk-mode labels, big map).  One per name, over its largest footprint.
# MARKER_NAME: the name a 1997 student would use (or None: no marker, e.g. not built yet in 1997).
# ---------------------------------------------------------------------------
MARKER_NAME = {n: None for n in ('별동연구동', '영빈관', '영선실', '차량실', '행정동', '학생회관 별관', '광혜관')}
EXTRA_MARKERS = [('청송대', 238.0, 284.0), ('농구장', 21.9, 2.5), ('활천 분수', -99.0, -255.0)]          # the wooded park east of 연희관 (OSM leisure=park)
LANDMARK_NAMES = {l['name'] for l in LANDMARKS}
groups = {}
for b in buildings:
    if not b['name'] or b['style'] == 'city':
        continue
    nm = MARKER_NAME.get(b['name'], b['name'])
    if not nm or nm in LANDMARK_NAMES:
        continue
    poly = Polygon(b['footprint'])
    g = groups.get(nm)
    if g is None or poly.area > g[0]:
        groups[nm] = (poly.area, poly, b)
markers = []
for nm, (area, poly, b) in groups.items():
    c = poly.representative_point() if not poly.contains(poly.centroid) else poly.centroid
    markers.append(dict(name=nm, pos=[round(c.x, 1), round(c.y, 1)], top=round(b['base'] + b['height'] + 1.0, 1)))
for nm, x, y in EXTRA_MARKERS:
    markers.append(dict(name=nm, pos=[x, y], top=round(ground_h(x, y) + 12, 1)))
print('markers', len(markers))

out = dict(
    origin=[LAT0, LON0],
    terrain=dict(near=dict(half=NEAR_HALF, step=NEAR_STEP, n=n_near, file='data/terrain_near.bin'),
                 far=dict(half=tf['half'], step=tf['step'], n=tf['n'], file='data/terrain_far.bin')),
    splat=SPLAT,
    baekyangro=dict(pts=[[round(x, 2), round(y, 2)] for x, y in bys], profile_s=[round(v, 1) for v in ss[::2]],
                    profile_h=[round(float(v), 3) for v in prof[::2]], crossings=CROSS, bump=BUMP_S,
                    gaps=[list(g) for g in GAPS], **ROAD),
    amphitheater={k: (round(v, 3) if isinstance(v, float) else v) for k, v in AMPH.items()},
    buildings=buildings, trees=trees, shrubs=shrubs, props=props, cars=cars, banners=banners,
    paths=paths_out, landmarks=LANDMARKS, statues=STATUES, spawn=SPAWN, markers=markers,
)
for p in (os.path.join(ROOT, 'data/campus.json'), os.path.join(ROOT, 'web/public/data/campus.json')):
    json.dump(out, open(p, 'w'), ensure_ascii=False, separators=(',', ':'))
np.save(os.path.join(ROOT, 'data/terrain_near.npy'), Hn.astype(np.float32))
print('baekyangro length %.0f m, rise %.1f -> %.1f m' % (L, prof[0], prof[-1]))

# ---------------------------------------------------------------------------
# Debug map
# ---------------------------------------------------------------------------
dbg = Image.fromarray(np.clip(spl, 0, 255).astype(np.uint8), 'RGB').resize((SW // 2, SH // 2))
d = ImageDraw.Draw(dbg)
COL = {'modern': (150, 150, 200), 'white': (230, 230, 230), 'stone': (160, 120, 90), 'house': (200, 150, 120),
       'gym': (120, 200, 200), 'city': (90, 90, 90)}
def tp(x, y):
    a, b_ = to_px(x, y)
    return a / 2, b_ / 2
for b in buildings:
    col = (255, 80, 80) if b['style'].startswith('lm') else COL.get(b['style'], (255, 0, 255))
    d.polygon([tp(x, y) for x, y in b['footprint']], fill=col, outline=(0, 0, 0))
for t in trees:
    x, y = tp(t[1], t[2])
    c_ = {'ginkgo': (255, 230, 0), 'pine': (0, 90, 30), 'zelkova': (40, 160, 40), 'cherry': (255, 150, 200), 'maple': (200, 60, 20), 'oak': (60, 120, 30)}[t[0]]
    d.ellipse([x - 2, y - 2, x + 2, y + 2], fill=c_)
for l in LANDMARKS:
    x, y = tp(*l['pos'])
    d.ellipse([x - 5, y - 5, x + 5, y + 5], outline=(255, 0, 255), width=2)
for bn in banners:
    d.line([tp(*bn['a']), tp(*bn['b'])], fill=(0, 0, 255), width=2)
dbg.save(os.path.join(ROOT, 'data/debug_map.png'))
