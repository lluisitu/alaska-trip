#!/usr/bin/env python3
"""
Rebuild the state/provincial park map layers from the park database.

    cd tools && python3 build_parks.py

`parks_db.json` is the canonical record: every state, provincial and territorial
park within ~50 miles of either route, with its official page, coordinates, camping
type and — where anyone publishes one — a maximum RV length plus where that number
came from. It is researched once and kept; nothing here calls the network.

This script recomputes, for every park, which stop it is nearest to, how far, and
whether it is somewhere you are staying / visiting / neither, then writes the
result into desktop/index.html. So when the itinerary changes — a stop added,
moved or dropped — you re-run this and every park re-assigns itself. The rig-fit
research is never repeated.

    parks_db.json  +  STOPS in desktop/index.html   ->   STATE_PARKS layers

Standard library only.
"""

import json, pathlib, math, re, collections

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC  = ROOT / 'desktop' / 'index.html'
DB   = ROOT / 'tools' / 'parks_db.json'

MAX_MILES = 70          # drop anything further than this from every stop
FITS_FT   = 40          # the coach


def ex(h, decl, o='{', c='}'):
    """Brace-matching, string-aware extractor."""
    i = h.index(decl); s = h.index(o, i); d = 0; ins = False; esc = False
    for j in range(s, len(h)):
        ch = h[j]
        if ins:
            if esc: esc = False
            elif ch == '\\': esc = True
            elif ch == '"': ins = False
        else:
            if ch == '"': ins = True
            elif ch == o: d += 1
            elif ch == c:
                d -= 1
                if d == 0: return h[s:j+1]
    raise ValueError('unterminated: ' + decl)


def miles(alat, alng, blat, blng):
    R = 3958.8
    p1, p2 = math.radians(alat), math.radians(blat)
    dp = p2 - p1; dl = math.radians(blng - alng)
    x = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(x))


def blob(s):
    return json.dumps({k: v for k, v in s.items() if k not in ('lat', 'lng')}, ensure_ascii=False).lower()


def short_name(name):
    n = name.lower()
    return re.sub(r'\s+(state|provincial|territorial)\s+'
                  r'(park|recreation area|recreation site|natural area|historic park|historic site|park museum|wilderness area|forest).*$',
                  '', n).strip()


def rig_state(p):
    """Two independent facts stay independent: this is only about the coach."""
    n = p.get('maxRvFt')
    if isinstance(n, (int, float)) and n > 0:
        return 'fits' if n >= FITS_FT else 'short'
    if p.get('camping') == 'none': return 'dayuse'
    if p.get('camping') == 'tent': return 'short'
    return 'unknown'


def classify(park, stops, blobs, camps):
    best = min(stops, key=lambda s: miles(park['lat'], park['lng'], s['lat'], s['lng']))
    dist = miles(park['lat'], park['lng'], best['lat'], best['lng'])
    nm, sh = park['name'].lower(), short_name(park['name'])
    plan = 'none'
    if len(sh) > 4 and (sh in camps[best['id']] or nm in camps[best['id']]):
        plan = 'stay'
    elif len(sh) > 4 and (sh in blobs[best['id']] or nm in blobs[best['id']]):
        plan = 'visit'
    return best, round(dist), plan


def main():
    h = SRC.read_text()
    STOPS = json.loads(ex(h, 'const STOPS =', '[', ']'))
    EXT_RAW = ex(h, 'const EXT_DATA =')
    EXT = json.loads(EXT_RAW)
    parks = json.loads(DB.read_text())
    print(f"{len(parks)} parks in the database, {len(STOPS)} main stops, {len(EXT['STOPS'])} east stops")

    mb = {s['id']: blob(s) for s in STOPS}
    mc = {s['id']: (s.get('camp') or '').lower() for s in STOPS}
    eb = {s['id']: blob(s) for s in EXT['STOPS']}
    ec = {s['id']: (s.get('camp') or '').lower() for s in EXT['STOPS']}

    main_out, ext_out, dropped = [], [], 0
    for p in parks:
        ms, md, mplan = classify(p, STOPS, mb, mc)
        es, ed, eplan = classify(p, EXT['STOPS'], eb, ec)
        stop, dist, plan, bucket = (ms, md, mplan, main_out) if md <= ed else (es, ed, eplan, ext_out)
        if dist > MAX_MILES:
            dropped += 1
            continue
        row = {k: p[k] for k in ('name', 'state', 'lat', 'lng', 'url') if k in p}
        row.update({
            'kind': p.get('kind') or 'park',
            'camping': p.get('camping'),
            'maxRvFt': p.get('maxRvFt'),
            'maxRvSource': p.get('maxRvSource'),
            'stopId': stop['id'], 'miles': dist,
            'plan': plan, 'rig': rig_state(p),
            'why': p.get('why') or '',
        })
        if p.get('rigNote'): row['rigNote'] = p['rigNote']
        bucket.append(row)

    for arr in (main_out, ext_out):
        arr.sort(key=lambda x: (x['state'], x['miles']))

    def tally(a, label):
        print(f"  {label}: {len(a):4}  plan={dict(collections.Counter(x['plan'] for x in a))}"
              f"  rig={dict(collections.Counter(x['rig'] for x in a))}")
    tally(main_out, 'main loop'); tally(ext_out, 'east ext ')
    if dropped: print(f"  ({dropped} parks further than {MAX_MILES} mi from any stop — not shown)")

    src = collections.Counter(p.get('maxRvSource') for p in parks if p.get('maxRvFt'))
    print(f"  length known for {sum(src.values())}/{len(parks)}: {dict(src)}")

    old_sp = ex(h, 'const STATE_PARKS =', '[', ']')
    h = h.replace(old_sp, json.dumps(main_out, ensure_ascii=False), 1)
    EXT2 = json.loads(EXT_RAW); EXT2['STATE_PARKS'] = ext_out
    h = h.replace(EXT_RAW, json.dumps(EXT2, ensure_ascii=False, indent=1), 1)
    SRC.write_text(h)
    print(f"wrote {SRC}")
    print("Now run:  python3 build_mobile.py   then commit.")


if __name__ == '__main__':
    main()
