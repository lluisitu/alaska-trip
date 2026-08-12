#!/usr/bin/env python3
"""
Exactly what is still open, per box, with the stop it belongs to.

    cd tools && python3 open_items.py                    # everything
    cd tools && python3 open_items.py dogs               # one box
    cd tools && python3 open_items.py highlights leg3 leg6

Why this is not just progress.py
---------------------------------
progress.py answers "how far along is this", which is the question for a
status table. This answers "what do I do next", which is the question for a
research pass — and the two differ, because most of what is *unfilled* is
deliberately unfillable and must not be handed to anyone as work.

So this prints only genuinely open items. It excludes, in each case for a
reason already established on this project:

  * `pending` entries — prose and trailheads sitting in a trails box ("Choose
    signed, well-used routes and carry bear spray."). There is no listing to
    find for a sentence and no authority publishes a dog rule for one.
  * trails whose db entry records `match: none` / `tier: unlisted` — searched,
    confirmed real by the authority, and indexed nowhere.
  * dogs on a `partial` stop — the authority named some trails and is silent on
    the rest, and that silence is the researched answer.
  * highlights with no entity in the headline, and highlights whose db entry
    already records a deliberate decision not to link.

Standard library only; no network.
"""
import json, pathlib, sys
from collections import Counter

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE.parent / 'desktop' / 'index.html'
DB = HERE / 'links_db.json'

BOXES = ('trails', 'dogs', 'highlights', 'scenicDrives', 'offroad')


def ex(hh, decl, o='[', c=']'):
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


PROPER = __import__('re').compile(r'\b[A-Z][a-z\'’-]{2,}')
STOPWORD = {'Day', 'Drive', 'Visit', 'Walk', 'Hike', 'Wildlife', 'Dawn', 'Explore',
            'Stroll', 'Soak', 'Build', 'Final', 'Ride', 'See', 'Tour', 'Add', 'Spend'}


def has_entity(name):
    return any(w not in STOPWORD for w in PROPER.findall(name or ''))


def collect():
    h = SRC.read_text()
    stops = json.loads(ex(h, 'const STOPS =')) + json.loads(ex(h, 'const EXT_DATA =', '{', '}'))['STOPS']
    db = json.loads(DB.read_text())['stops']
    out = {b: [] for b in BOXES}
    for s in stops:
        leg = s.get('leg', 'EAST')
        sid = s['id']
        e = db.get(sid, {})
        partial = e.get('dogs_verdict') == 'partial'
        noted = {t['name'] for t in (e.get('trails') or [])
                 if (t.get('alltrails') or {}).get('match') == 'none'
                 or (t.get('alltrails') or {}).get('tier') == 'unlisted'}
        decided = e.get('activities') or {}
        for y in (s.get('alltrails') or []):
            if y.get('pending'):
                continue
            if not y.get('url') and y['name'] not in noted:
                out['trails'].append((leg, sid, s['name'], y['name']))
            if 'dogs' not in y and not partial:
                out['dogs'].append((leg, sid, s['name'], y['name']))
        for a in (s.get('activities') or []):
            if not a.get('links') and has_entity(a['name']) and a['name'] not in decided:
                out['highlights'].append((leg, sid, s['name'], a['name']))
        for box in ('scenicDrives', 'offroad'):
            for y in (s.get(box) or []):
                if not y.get('url'):
                    out[box].append((leg, sid, s['name'], y['name']))
    return out


def main():
    args = [a for a in sys.argv[1:]]
    want = [a for a in args if a in BOXES] or list(BOXES)
    legs = [a for a in args if a not in BOXES]
    data = collect()
    total = 0
    for box in want:
        rows = [r for r in data[box] if not legs or r[0] in legs]
        if not rows:
            continue
        total += len(rows)
        print(f'=== {box}: {len(rows)} open  {dict(sorted(Counter(r[0] for r in rows).items()))}')
        last = None
        for leg, sid, sname, item in sorted(rows):
            if (leg, sid) != last:
                print(f'  -- {leg} / {sid}  ({sname})')
                last = (leg, sid)
            print(f'     {item}')
        print()
    print(f'{total} open items')


if __name__ == '__main__':
    main()
