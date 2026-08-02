#!/usr/bin/env python3
"""
Regenerate the strategy band under the timeline bars.

    cd tools && python3 build_strategy.py

The band shows the seasonal windows the route is actually bent around, drawn on
the same date scale as the month bar. Because each target carries the list of
stops that fall inside it, the data goes stale the moment the itinerary changes
- so this is a build step, not a one-off edit. Run it after any change to nights,
order or stop ids, alongside build_parks.py.

Standard library only; no network.

Each target carries an ANCHOR: the stop the window actually exists for. Without
it the band jumped to whichever stop happened to fall first inside the date
range, which is usually the wrong place - clicking "Larch, North Cascades"
landed on Stewart/Hyder, a bear-viewing stop 700 miles north of the nearest
larch. The anchor is the point of the window; the other stops inside it merely
share the dates.
"""
import json, pathlib, datetime as dt, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC  = ROOT / 'desktop' / 'index.html'


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
                if d == 0: return hh[s:j+1]
    raise ValueError('unterminated: ' + decl)


D = dt.date.fromisoformat

# key, icon, label, window start, window end, ANCHOR stop id, why this is a target
MAIN = [
 ('parks-canada','◉','Parks Canada window','2027-05-25','2027-06-09','banff',
  'Waterton, Banff and Jasper — the reservations that sell out in minutes'),
 ('alaska','☀','Alaska season','2027-06-01','2027-09-15','denali',
  'The one hard seasonal ceiling on the whole trip'),
 ('gold','🍂','Boreal & tundra gold','2027-08-20','2027-09-20','dawson-city',
  'Klondike aspen and birch, and the Dempster tundra turning'),
 ('larch','🌲','Larch, North Cascades','2027-09-25','2027-10-16','winthrop',
  'Alpine larch above Washington Pass — a two-week event, and the reason Winthrop moved earlier'),
 ('storm','🌊','Pacific storm season','2027-10-25','2027-12-05','long-beach',
  'Not a colour stop — storm watching, razor clams, rainforest'),
 ('xmas27','🎄','Christmas','2027-12-20','2027-12-27','sequoia-kings-canyon',
  'Where the holiday actually lands'),
 ('desert','🌵','Desert winter','2027-12-26','2028-03-15','quartzsite',
  'The winter tail, and the only real buffer in the plan'),
 ('spring','🌸','Colorado Plateau spring','2028-03-15','2028-04-30','moab',
  'Utah and the San Juans before the summer heat and after the snow'),
]
EAST = [
 ('plains','🌾','Plains & Badlands','2028-05-20','2028-07-05','badlands-sd',
  'Before the high-summer heat on the northern plains'),
 ('lakes','🏖','Great Lakes summer','2028-07-05','2028-09-01','munising-mi',
  'Superior and Michigan are only warm for this window'),
 ('fall','🍁','Fall colour chase','2028-09-20','2028-10-27','stowe-vt',
  'The one truly fixed anchor of the extension'),
 ('xmas28','🎄','Christmas','2028-12-20','2028-12-27','asheville-nc-v3',
  'Where the holiday actually lands'),
 ('appal','❄','Appalachian winter','2029-01-01','2029-02-10','bryson-city-nc',
  'Cold, quiet and cheap — Blue Ridge access is not assumable'),
 ('ozarks','🌱','Ozarks & Hill Country spring','2029-02-10','2029-03-08','hill-country-tx',
  'Running the bloom north to south on the way home'),
]


def build(stops, targets, which):
    by = {s['id']: s for s in stops}
    t0, t1 = D(stops[0]['arrive']), D(stops[-1]['depart'])
    span = (t1 - t0).days
    out = []
    for key, icon, label, a, b, anchor, why in targets:
        if anchor not in by:
            sys.exit(f"!! {which}/{key}: anchor '{anchor}' is not a stop id. A stop was "
                     f"renamed or removed — fix the anchor before publishing.")
        A, B = D(a), D(b)
        inside = [s for s in stops if not (D(s['depart']) <= A or D(s['arrive']) >= B)]
        an = by[anchor]
        # The anchor is supposed to sit inside its own window. When it doesn't, the
        # plan has drifted off the very thing the window exists for — say so loudly
        # rather than drawing a band that quietly lies.
        drift = D(an['depart']) <= A or D(an['arrive']) >= B
        left = max(0, (A - t0).days) / span * 100
        out.append({
            'key': key, 'icon': icon, 'label': label, 'why': why, 'start': a, 'end': b,
            'left': round(left, 3),
            'width': round(min(span, (B - t0).days) / span * 100 - left, 3),
            'anchor': anchor, 'anchorName': an['name'], 'anchorArrive': an['arrive'],
            'anchorDepart': an['depart'], 'anchorNights': an['nights'], 'anchorDrift': drift,
            'stops': [{'id': s['id'], 'name': s['name'], 'arrive': s['arrive']} for s in inside],
            'n': len(inside),
        })
    return out


def main():
    h = SRC.read_text()
    S = json.loads(ex(h, 'const STOPS =', '[', ']'))
    E = json.loads(ex(h, 'const EXT_DATA ='))['STOPS']
    for decl, stops, targets, label in (
            ('const STRATEGY_TARGETS =', S, MAIN, 'main loop'),
            ('const EXT_STRATEGY_TARGETS =', E, EAST, 'east ext ')):
        data = build(stops, targets, label.strip())
        empty = [t['label'] for t in data if t['n'] == 0]
        drift = [t['label'] for t in data if t['anchorDrift']]
        print(f"  {label}: {len(data)} targets, "
              f"{sum(t['n'] for t in data)} stop-hits" + (f"  !! empty: {empty}" if empty else ''))
        for t in data:
            mark = '  <-- ANCHOR OUTSIDE WINDOW' if t['anchorDrift'] else ''
            print(f"     {t['label']:<30} {t['start']} .. {t['end']}  {t['n']:>2} stops   "
                  f"anchor: {t['anchorName'][:32]}{mark}")
        if drift:
            print(f"     !! anchors sitting outside their own window: {drift}")
        old = ex(h, decl, '[', ']')
        h = h.replace(old, json.dumps(data, ensure_ascii=False), 1)
    SRC.write_text(h)
    print("wrote", SRC)


if __name__ == '__main__':
    main()
