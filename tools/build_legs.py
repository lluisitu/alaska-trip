#!/usr/bin/env python3
"""
Work out how long each driving day actually is, and flag the long ones.

    cd tools && python3 build_legs.py

The cards have always shown a straight-line "~N mi to next stop", which
understates every leg that follows a road round a mountain instead of through
it. Where a routed polyline exists — 145 of the 155 legs — the real road
distance can be measured off it, and that is what a driving day is made of.

A 40 ft coach towing a pickup is not a car. Sustained speed on secondary roads
is nearer 50 mph than 65, fuel stops take longer, and an eight-hour day in a
2005 chassis is a hard day. So each leg gets a road distance, an honest driving
estimate at 52 mph moving average, and a flag when it crosses the thresholds
that matter: over 250 miles is long, over 300 is a day worth splitting.

Where there is no routed geometry the straight-line distance is used and the
record says so, because a straight line between two mountain towns can be half
the real thing.

Standard library only; no network.
"""
import json, math, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / 'desktop' / 'index.html'

MOVING_MPH = 52.0     # what a 60 ft combination actually averages door to door
LONG_MI = 250
SPLIT_MI = 300


def ex(hh, decl, o='{', c='}'):
    i = hh.index(decl); s = hh.index(o, i); d = 0; ins = False; esc = False
    for j in range(s, len(hh)):
        ch = hh[j]
        if ins:
            if esc: esc = False
            elif ch == '\\': esc = True
            elif ch == '"': ins = False
        else:
            if ch == '"': ins = True
            elif ch == o: d += 1
            elif ch == c:
                d -= 1
                if d == 0: return hh[s:j + 1]
    raise ValueError('unterminated: ' + decl)


def decode(enc):
    pts, i, lat, lng = [], 0, 0, 0
    while i < len(enc):
        for k in range(2):
            shift = result = 0
            while True:
                c = ord(enc[i]) - 63; i += 1
                result |= (c & 0x1f) << shift; shift += 5
                if c < 0x20: break
            d = ~(result >> 1) if result & 1 else result >> 1
            if k == 0: lat += d
            else: lng += d
        pts.append((lat / 1e5, lng / 1e5))
    return pts


def haversine(a, b, c, d):
    R = 3958.8
    p1, p2 = math.radians(a), math.radians(c)
    dp, dl = math.radians(c - a), math.radians(d - b)
    x = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(x))


def path_miles(pts):
    return sum(haversine(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
               for i in range(len(pts) - 1))


def build(stops, geom, label):
    out, routed, straight = {}, 0, 0
    for i in range(len(stops) - 1):
        a, b = stops[i], stops[i + 1]
        key = a['id'] + '>' + b['id']
        enc = geom.get(key)
        if enc:
            mi = path_miles(decode(enc)); src = 'road'; routed += 1
        else:
            mi = haversine(a['lat'], a['lng'], b['lat'], b['lng']); src = 'straight'; straight += 1
        mi = round(mi)
        hours = mi / MOVING_MPH
        out[key] = {
            'from': a['id'], 'to': b['id'], 'mi': mi, 'src': src,
            'hours': round(hours, 1),
            'long': mi >= LONG_MI,
            'split': mi >= SPLIT_MI,
        }
    print(f"  {label}: {len(out)} legs — {routed} measured off the road, {straight} straight-line only")
    return out


def main():
    h = SRC.read_text()
    stops = json.loads(ex(h, 'const STOPS =', '[', ']'))
    ext = json.loads(ex(h, 'const EXT_DATA ='))['STOPS']
    geom = json.loads(ex(h, 'const ROUTE_GEOM ='))
    egeom = json.loads(ex(h, 'const EXT_ROUTE_GEOM ='))

    legs = build(stops, geom, 'main loop')
    legs.update(build(ext, egeom, 'east trip'))

    longs = sorted((v for v in legs.values() if v['long']), key=lambda v: -v['mi'])
    print(f"  {len(longs)} legs over {LONG_MI} mi, {sum(1 for v in longs if v['split'])} over {SPLIT_MI}:")
    for v in longs[:8]:
        note = '' if v['src'] == 'road' else '  (straight-line — no routed geometry)'
        print(f"     {v['from']:>22} → {v['to']:<22} {v['mi']:>4} mi  ~{v['hours']}h{note}")

    payload = json.dumps({'legs': legs, 'mph': MOVING_MPH,
                          'longMi': LONG_MI, 'splitMi': SPLIT_MI},
                         ensure_ascii=False, sort_keys=True)
    decl = re.compile(r'const LEGINFO = \{.*?\};\n', re.S)
    block = f'const LEGINFO = {payload};\n'
    if decl.search(h):
        h = decl.sub(lambda _m: block, h, count=1)
    else:
        anchor = 'const PHOTO ='
        assert anchor in h, 'PHOTO declaration missing'
        h = h.replace(anchor, block + '\n' + anchor, 1)
    SRC.write_text(h)
    print("wrote", SRC)


if __name__ == '__main__':
    main()
