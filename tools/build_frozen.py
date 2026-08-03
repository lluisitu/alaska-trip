#!/usr/bin/env python3
"""
Regenerate the frozen-date table and the start-date what-if data.

    cd tools && python3 build_frozen.py

Most of this trip is elastic. A handful of stops are not: they exist to hit
something that happens on a date nobody controls - a larch turn, a tide series,
a border that closes on Sep 15, Christmas Day. This records those, with the real
earliest and latest arrival each one tolerates, so the dashboard can answer the
question that actually matters when you are thinking about leaving earlier or
later: WHICH of these breaks first, and by how many days.

The allowed shift for a frozen stop is (earliest - current) to (latest - current)
in days. Intersect those across every frozen stop and you get the trip's true
departure freedom, which is usually much smaller than it feels.

Standard library only; no network.
"""
import json, pathlib, sys, datetime as dt

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / 'desktop' / 'index.html'
D = dt.date.fromisoformat

# stop id, hardness, earliest arrival, latest arrival, what it is pinned to
#   hard  = a real-world gate. Miss it and the thing is gone or closed.
#   soft  = a peak you want to be near. Missing it costs quality, not access.
MAIN = [
 ('denali', 'soft', '2027-07-20', '2027-08-12',
  'Past mosquito peak and late enough to give the Polychrome road repair a chance'),
 ('dawson-city', 'hard', '2027-08-26', '2027-09-02',
  'Dempster tundra peaks Aug 25 - Sep 5, AND the Top of the World border closes Sep 15 for good'),
 ('winthrop', 'hard', '2027-09-28', '2027-10-05',
  'Alpine larch prime is Sep 29 - Oct 8; Oct 10-15 is already the fade'),
 ('long-beach', 'hard', '2027-10-27', '2027-10-30',
  'Razor-clam digs only happen on negative evening tides - this is the Oct 27 - Nov 1 series'),
 ('sequoia-kings-canyon', 'hard', '2027-12-21', '2027-12-25',
  'Christmas Day has to fall inside the stay'),
 ('imperial-dam', 'soft', '2028-01-06', '2028-01-18',
  'First-come BLM ground, and the Yuma shop days after it are weekday-only - MLK Monday is Jan 17'),
 ('moab', 'hard', '2028-03-20', '2028-04-01',
  'Must be out before Easter Jeep Safari opens about Apr 8 and closes seven trails'),
 ('banff', 'soft', '2027-05-24', '2027-06-05',
  'Parks Canada reservations; the campground has to be open and booked months ahead'),
]
EAST = [
 ('badlands-sd', 'soft', '2028-06-01', '2028-06-20',
  'Ahead of the high-summer heat on the northern plains'),
 ('munising-mi', 'soft', '2028-07-15', '2028-08-05',
  'Lake Superior is only warm in this window'),
 ('stowe-vt', 'hard', '2028-09-26', '2028-10-02',
  'Northern Vermont peaks late Sep to the first week of Oct, and Oct 7-9 is the holiday weekend'),
 ('bar-harbor-me', 'hard', '2028-10-13', '2028-10-19',
  'Maine Forest Service puts Zone 2 - Bar Harbor and Penobscot Bay - at Oct 14-20'),
 ('asheville-nc-v3', 'hard', '2028-12-21', '2028-12-25',
  'Christmas Day has to fall inside the stay'),
]


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


def build(stops, table, which):
    by = {s['id']: s for s in stops}
    out = []
    prev_idx = 0
    lo_all, hi_all = -3650, 3650
    for sid, _h, _l, _hi, _w in table:
        if sid not in by:
            sys.exit(f"!! {which}: frozen stop '{sid}' is not in the itinerary. "
                     f"A stop was renamed or removed - fix build_frozen.py before publishing.")
    # The table is written in whatever order made sense to a human; the pools below
    # only mean anything in itinerary order. Banff is written last but travelled
    # first, and sorting is what stops that silently corrupting every pool.
    order = {s['id']: i for i, s in enumerate(stops)}
    for sid, hardness, lo, hi, why in sorted(table, key=lambda r: order[r[0]]):
        s = by[sid]
        cur = D(s['arrive'])
        lo_d, hi_d = (D(lo) - cur).days, (D(hi) - cur).days
        if lo_d > 0 or hi_d < 0:
            print(f"   !! {sid} is ALREADY outside its own window "
                  f"({s['arrive']}, wants {lo}..{hi})")
        idx = stops.index(s)
        # The pool this stop can absorb a shift from: every stop between the
        # previous frozen stop and this one. Trimming a night in here moves this
        # stop earlier and leaves everything AFTER it untouched — which is why a
        # later departure is nothing like as constrained as a rigid shift implies.
        pool = stops[prev_idx:idx]
        trim = sum(max(0, x['nights'] - 1) for x in pool)
        out.append({
            'id': sid, 'name': s['name'], 'hardness': hardness, 'why': why,
            'arrive': s['arrive'], 'depart': s['depart'], 'nights': s['nights'],
            'earliest': lo, 'latest': hi,
            # how far the whole trip may slide before THIS stop leaves its window
            'shiftMin': lo_d, 'shiftMax': hi_d,
            'index': idx,
            'poolCount': len(pool),
            'poolNights': sum(x['nights'] for x in pool),
            'poolTrim': trim,
            # the fattest stops in that pool — where the nights would actually come from
            'poolTop': [{'id': x['id'], 'name': x['name'], 'nights': x['nights']}
                        for x in sorted(pool, key=lambda x: -x['nights'])[:6]],
        })
        prev_idx = idx + 1
        if hardness == 'hard':
            lo_all, hi_all = max(lo_all, lo_d), min(hi_all, hi_d)
    return out, lo_all, hi_all


def main():
    h = SRC.read_text()
    S = json.loads(ex(h, 'const STOPS =', '[', ']'))
    E = json.loads(ex(h, 'const EXT_DATA ='))['STOPS']

    payload = {}
    for key, stops, table, label in (('main', S, MAIN, 'main loop'),
                                     ('east', E, EAST, 'east ext')):
        rows, lo, hi = build(stops, table, label)
        firsthard = next((r for r in rows if r['hardness'] == 'hard'), None)
        # Everything from departure up to the first hard date is fair game: trim a
        # night anywhere in there and every frozen date downstream stays put.
        cum_trim = cum_nights = cum_count = 0
        cum_top = []
        if firsthard:
            head = stops[:firsthard['index']]
            cum_trim = sum(max(0, x['nights'] - 1) for x in head)
            cum_nights = sum(x['nights'] for x in head)
            cum_count = len(head)
            cum_top = [{'id': x['id'], 'name': x['name'], 'nights': x['nights']}
                       for x in sorted(head, key=lambda x: -x['nights'])[:8]]
        payload[key] = {'stops': rows, 'shiftMin': lo, 'shiftMax': hi,
                        'start': stops[0]['arrive'], 'end': stops[-1]['depart'],
                        'totalNights': sum(x['nights'] for x in stops),
                        # absorbing a later start before the FIRST hard date leaves the
                        # entire rest of the trip untouched, so this is the real headline
                        'firstHardId': firsthard['id'] if firsthard else None,
                        'firstHardName': firsthard['name'] if firsthard else None,
                        'absorbTrim': cum_trim,
                        'absorbNights': cum_nights,
                        'absorbCount': cum_count,
                        'absorbTop': cum_top}
        print(f"  {label}: {len(rows)} frozen stops "
              f"({sum(1 for r in rows if r['hardness']=='hard')} hard) — "
              f"rigid shift {lo:+d}..{hi:+d} days; "
              f"but {payload[key]['absorbTrim']} nights are trimmable before the first hard date "
              f"({payload[key]['firstHardName']}), so a later start is absorbable up to that")
        for r in rows:
            print(f"     {'HARD' if r['hardness']=='hard' else 'soft':<5} {r['name'][:34]:<36}"
                  f"{r['arrive']}  can slide {r['shiftMin']:+d}..{r['shiftMax']:+d}")

    decl = 'const FROZEN ='
    if decl in h:
        old = ex(h, decl)
        h = h.replace(old, json.dumps(payload, ensure_ascii=False), 1)
    else:
        anchor = '// ==================== STRATEGY BAND ===================='
        assert anchor in h, 'strategy band anchor missing'
        h = h.replace(anchor, f'const FROZEN = {json.dumps(payload, ensure_ascii=False)};\n\n' + anchor, 1)
    SRC.write_text(h)
    print("wrote", SRC)


if __name__ == '__main__':
    main()
