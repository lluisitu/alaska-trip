#!/usr/bin/env python3
"""
Where the research actually stands, per leg and per section.

    cd tools && python3 progress.py

Why two numbers
---------------
A single percentage was hiding two different things and making both of them
unreadable. "Leg 1 trails 97%" meant FINISHED — the one gap is a trail with no
listing anywhere. "Leg 1 shots 5/13" meant barely started. Same column, same
kind of number, opposite meanings.

So every cell shows:

    have   what is actually filled in, out of everything there is
    prog   what is done out of what CAN be done

`prog` reaches 100% when there is nothing left to research — including the items
that will never be fillable. Those are counted as BLOCKED, not as failures:

  * a trail the managing authority confirms exists and no database has indexed
    (Mesa Trail at Caprock — TPWD lists it, AllTrails never has)
  * a highlight with no entity in it at all ("Dawn and dusk wildlife watching
    from established roads and overlooks" — there is nothing to link to)
  * a dog rule the authority states for some trails and is silent on for others
    (Great Sand Dunes names Mosca Pass and the dunefield, says nothing about
    Montville — so that one stays blank rather than inheriting a guess)
  * a shot finding needing a coordinate nobody has published

The distinction matters because `have` will never reach 100% and pretending
otherwise means either inventing data or treating finished work as unfinished.
Blocked items are the honest floor.

Standard library only; no network. Reads the built page and the two dbs.
"""
import json, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / 'desktop' / 'index.html'
HERE = pathlib.Path(__file__).resolve().parent

# A headline with no proper noun has no entity to link to. This is the same
# test the resolver uses, run offline so no API call is needed to count it.
PROPER = re.compile(r'\b[A-Z][a-z\'’-]{2,}')
STOPWORD = {'Day', 'Drive', 'Visit', 'Walk', 'Hike', 'Wildlife', 'Dawn', 'Explore',
            'Stroll', 'Soak', 'Build', 'Final', 'Ride', 'See', 'Tour', 'Add', 'Spend'}


def has_entity(name):
    return any(w not in STOPWORD for w in PROPER.findall(name or ''))


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


def cell(have, blocked, total):
    """have/total, and have out of what is reachable."""
    reachable = total - blocked
    a = f"{100 * have // total:d}%" if total else "-"
    b = f"{100 * (have + blocked) // total:d}%" if total else "-"
    return a, b, blocked


def main():
    h = SRC.read_text()
    STOPS = json.loads(ex(h, 'const STOPS ='))
    EXT = json.loads(ex(h, 'const EXT_DATA =', '{', '}'))['STOPS']
    PHOTO = json.loads(ex(h, 'const PHOTO =', '{', '}'))
    db = json.loads((HERE / 'links_db.json').read_text())['stops']
    sdb = json.loads((HERE / 'shots_db.json').read_text())['shots']

    groups = [(lg, [x for x in STOPS if x['leg'] == lg]) for lg in
              ('leg1', 'leg2', 'leg3', 'leg4', 'leg5', 'leg6')] + [('EAST', EXT)]

    print(f"{'':9s}" + ''.join(f"{c:>17s}" for c in
                               ('trails', 'dogs', 'highlights', 'scenic', 'offroad', 'shot fixes')))
    print(f"{'':9s}" + ''.join(f"{'have  prog':>17s}" for _ in range(6)))
    print('-' * 111)
    tot = {k: [0, 0, 0] for k in ('tr', 'dg', 'hl', 'sc', 'of', 'sh')}

    def acc(k, have, blocked, total):
        tot[k][0] += have; tot[k][1] += blocked; tot[k][2] += total

    for name, L in groups:
        row, ids = [], {x['id'] for x in L}
        # trails: blocked when the db records that no listing exists
        t_h = t_b = t_t = 0
        for s in L:
            entry = db.get(s['id'], {})
            noted = {t['name'] for t in (entry.get('trails') or [])
                     if (t.get('alltrails') or {}).get('match') == 'none'
                     or (t.get('alltrails') or {}).get('tier') == 'unlisted'}
            for y in (s.get('alltrails') or []):
                t_t += 1
                if y.get('url'): t_h += 1
                elif y['name'] in noted: t_b += 1
        row.append(cell(t_h, t_b, t_t)); acc('tr', t_h, t_b, t_t)

        # dogs: blocked where the authority is verdict-partial and silent on this trail
        d_h = d_b = d_t = 0
        for s in L:
            e = db.get(s['id'], {})
            partial = e.get('dogs_verdict') == 'partial'
            named = e.get('trail_dogs') or {}
            for y in (s.get('alltrails') or []):
                d_t += 1
                if 'dogs' in y: d_h += 1
                elif partial and named.get(y['name'], 'x') is None: d_b += 1
                elif partial: d_b += 1
        row.append(cell(d_h, d_b, d_t)); acc('dg', d_h, d_b, d_t)

        # highlights: blocked when the headline contains no entity at all
        h_h = h_b = h_t = 0
        for s in L:
            for a in (s.get('activities') or []):
                h_t += 1
                if a.get('links'): h_h += 1
                elif not has_entity(a.get('name')): h_b += 1
        row.append(cell(h_h, h_b, h_t)); acc('hl', h_h, h_b, h_t)

        for key, field in (('sc', 'scenicDrives'), ('of', 'offroad')):
            a_h = a_t = 0
            for s in L:
                for y in (s.get(field) or []):
                    a_t += 1
                    if y.get('url'): a_h += 1
            row.append(cell(a_h, 0, a_t)); acc(key, a_h, 0, a_t)

        # shot findings: blocked where marked so in shots_db
        f_h = f_b = f_t = 0
        for sid in ids:
            for sh in PHOTO.get(sid, []):
                spec = (sdb.get(sid) or {}).get(sh['title'], {})
                for f in (sh.get('flags') or []):
                    f_t += 1
                    if f.get('src') == 'fixed': f_h += 1
                    elif spec.get('blocked'): f_b += 1
        row.append(cell(f_h, f_b, f_t)); acc('sh', f_h, f_b, f_t)

        print(f"{name:9s}" + ''.join(f"{a:>8s}{b:>9s}" for a, b, _ in row))

    print('-' * 111)
    print(f"{'TRIP':9s}" + ''.join(
        f"{cell(*[tot[k][0], tot[k][1], tot[k][2]])[0]:>8s}{cell(*[tot[k][0], tot[k][1], tot[k][2]])[1]:>9s}"
        for k in ('tr', 'dg', 'hl', 'sc', 'of', 'sh')))
    blocked = sum(tot[k][1] for k in tot)
    print(f"\n{blocked} items counted as blocked — researched, and confirmed unfillable.")
    print("have = what is filled in.  prog = filled in, plus what never can be.")


if __name__ == '__main__':
    main()
