#!/usr/bin/env python3
"""
Fetch the real driving route between every pair of consecutive stops and bake
the geometry into desktop/index.html.

Run this on a machine with open internet — the Cowork cloud sandbox cannot
reach any routing service, which is why this is a separate script rather than
something the dashboard does at page load.

    cd tools && python3 build_routes.py

It writes ROUTE_GEOM and EXT_ROUTE_GEOM into desktop/index.html as encoded
polylines. The map then draws real roads; any leg that fails to route keeps the
old dashed straight line, which is the honest way to show it.

Results are cached in tools/route_cache.json and keyed by stop id + rounded
coordinates, so a re-run after adding or moving one stop only fetches what
actually changed. Standard library only — no pip install.
"""

import json, pathlib, subprocess, sys, time

ROOT   = pathlib.Path(__file__).resolve().parent.parent
SRC    = ROOT / 'desktop' / 'index.html'
CACHE  = ROOT / 'tools' / 'route_cache.json'

OSRM   = 'https://router.project-osrm.org/route/v1/driving/{},{};{},{}?overview=simplified&geometries=polyline'
PAUSE  = 1.0    # be polite to the public demo server
TIMEOUT = 30


def ex(h, decl, o='{', c='}'):
    """Brace-matching, string-aware extractor — safer than any regex here."""
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


def key_for(a, b):
    return f"{a['id']}>{b['id']}"


def sig_for(a, b):
    """Cache signature — changes if either endpoint moves."""
    return f"{round(a['lat'],4)},{round(a['lng'],4)}|{round(b['lat'],4)},{round(b['lng'],4)}"


def fetch(a, b):
    url = OSRM.format(a['lng'], a['lat'], b['lng'], b['lat'])
    # curl, not urllib: the Python 3.9 shipped with Xcode Command Line Tools is
    # linked against LibreSSL 2.8.3 and dies on this host with
    # SSLV3_ALERT_HANDSHAKE_FAILURE. curl uses the system TLS stack and works.
    out = subprocess.run(['curl', '-sS', '--max-time', str(TIMEOUT),
                          '-A', 'alaska-trip-dashboard/1.0', url],
                         capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError((out.stderr.strip() or 'curl exit %d' % out.returncode)[:120])
    data = json.loads(out.stdout)
    if data.get('code') != 'Ok' or not data.get('routes'):
        raise RuntimeError(data.get('code', 'no route'))
    return data['routes'][0]['geometry']


def build(stops, cache, label):
    geom, fetched, cached, failed = {}, 0, 0, []
    pairs = [(stops[i], stops[i+1]) for i in range(len(stops) - 1)]
    for n, (a, b) in enumerate(pairs, 1):
        k, sig = key_for(a, b), sig_for(a, b)
        hit = cache.get(k)
        if hit and hit.get('sig') == sig and hit.get('geom'):
            geom[k] = hit['geom']; cached += 1
            continue
        sys.stdout.write(f"\r  {label}: {n}/{len(pairs)}  {a['id']} -> {b['id']:<28}")
        sys.stdout.flush()
        try:
            g = fetch(a, b)
            geom[k] = g
            cache[k] = {'sig': sig, 'geom': g}
            fetched += 1
        except Exception as e:
            failed.append((k, str(e)))
        time.sleep(PAUSE)
    print(f"\r  {label}: {len(pairs)} legs — {cached} cached, {fetched} fetched, {len(failed)} failed" + " " * 30)
    for k, why in failed:
        print(f"     ! {k}: {why}  (will draw as a dashed straight line)")
    return geom


def main():
    if not SRC.exists():
        sys.exit(f"Can't find {SRC} — run this from inside the repo.")

    h = SRC.read_text()
    STOPS = json.loads(ex(h, 'const STOPS =', '[', ']'))
    EXT   = json.loads(ex(h, 'const EXT_DATA ='))['STOPS']
    print(f"{len(STOPS)} main-loop stops, {len(EXT)} East Extension stops")

    cache = {}
    if CACHE.exists():
        try: cache = json.loads(CACHE.read_text())
        except Exception: print("  (cache unreadable — starting fresh)")

    print("\nRouting. This calls a public server once per leg with a 1s pause,")
    print("so a first full run takes roughly 5 minutes. Re-runs are near-instant.\n")

    main_geom = build(STOPS, cache, 'main loop')
    ext_geom  = build(EXT,   cache, 'east ext ')

    CACHE.write_text(json.dumps(cache, indent=0))

    for decl, data in (('const ROUTE_GEOM =', main_geom), ('const EXT_ROUTE_GEOM =', ext_geom)):
        old = ex(h, decl)
        if h.count(old) != 1:
            # the empty "{}" placeholder appears twice before the first run
            i = h.index(decl); s = h.index('{', i)
            h = h[:s] + json.dumps(data, ensure_ascii=False) + h[s + len(old):]
        else:
            h = h.replace(old, json.dumps(data, ensure_ascii=False), 1)

    SRC.write_text(h)
    kb = (len(json.dumps(main_geom)) + len(json.dumps(ext_geom))) / 1024
    print(f"\nBaked {len(main_geom) + len(ext_geom)} routed legs into desktop/index.html (+{kb:.0f} KB)")

    # The phone build carries the same geometry inside its compact JSON blob, so
    # patch it here too rather than forcing a full build_mobile.py regeneration.
    MOB = ROOT / 'mobile' / 'index.html'
    if MOB.exists():
        m = MOB.read_text()
        ok = True
        for field, data in (('"routeGeom":', main_geom), ('"extRouteGeom":', ext_geom)):
            if field not in m:
                print(f"  ! {field} not found in mobile/index.html — run build_mobile.py instead")
                ok = False; continue
            i = m.index(field)
            old = ex(m[i:], field)
            m = m[:i] + field + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + m[i + len(field) + len(old):]
        if ok:
            MOB.write_text(m)
            print("Also patched mobile/index.html — the offline map follows the roads too.")
    else:
        print("  (no mobile/index.html here — skipped)")

    print("\nBoth files are updated. Commit and push when ready.")


if __name__ == '__main__':
    main()
