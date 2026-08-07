#!/usr/bin/env python3
"""
Put the mountain passes, grades and hard size limits onto each stop card.

    cd tools && python3 build_passes.py

Why this exists. Until now the file held no elevation field at all — not one
stop, not one leg. Everything known about grades lived as prose inside
individual scenic-drive write-ups, which is fine when you happen to read that
box and useless when you are deciding whether the coach can physically get from
A to B.

For a 2005 40 ft Class A towing a pickup — roughly 60 ft, heavy, older chassis
— the things that actually cause trouble are sustained grades, tunnel and
bridge clearances, and posted length limits. The route has all three, and
several of them are absolute: the coach cannot pass the Zion–Mount Carmel
tunnel at any time, cannot use Going-to-the-Sun Road, cannot reach Giant Forest
in Sequoia, and is illegal through Smugglers Notch. A routing app will happily
suggest all four.

The data is curated in passes_db.json, one record per leg, and every figure
carries the URL it came from. Where a figure could not be verified it is null
with a note saying so — a wrong length limit is worse than a stated unknown,
because a wrong one gets acted on.

Standard library only; no network.
"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / 'desktop' / 'index.html'
DB = pathlib.Path(__file__).resolve().parent / 'passes_db.json'

SEVERITY_RANK = {'easy': 0, 'moderate': 1, 'hard': 2, 'severe': 3}


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


def main():
    h = SRC.read_text()
    db = json.loads(DB.read_text())

    stops = json.loads(ex(h, 'const STOPS ='.replace('const STOPS =', 'const STOPS ='), '[', ']'))
    ext = json.loads(ex(h, 'const EXT_DATA ='))['STOPS']
    ids = {s['id'] for s in stops} | {s['id'] for s in ext}

    out, bad = {}, []
    for leg in db['legs']:
        for k in ('from', 'to'):
            if leg[k] not in ids:
                bad.append(f"{leg[k]} ({k} of a leg record)")
        key = leg['from'] + '>' + leg['to']
        passes = leg.get('passes') or []
        # The card shows the worst thing on the leg first — a hard length limit
        # matters more than a pretty summit.
        passes = sorted(passes, key=lambda p: -SEVERITY_RANK.get(p.get('severity'), 0))
        worst = passes[0].get('severity') if passes else None
        # A pass record with no verified numbers is still worth showing when it
        # names a restriction; one with neither is not worth the space.
        keep = [p for p in passes
                if p.get('elev_ft') or p.get('max_grade_pct') or p.get('rv_restriction')
                or p.get('direction_note')]
        if not keep and not leg.get('verdict'):
            continue
        out[key] = {
            'from': leg['from'], 'to': leg['to'],
            'route': leg.get('route') or '',
            'verdict': leg.get('verdict') or '',
            'worst': worst,
            'passes': keep,
        }

    if bad:
        sys.exit("!! pass records reference stop ids that do not exist: " + ', '.join(sorted(set(bad))[:10]))

    counts = {}
    for v in out.values():
        counts[v['worst'] or 'unrated'] = counts.get(v['worst'] or 'unrated', 0) + 1
    hard = sum(1 for v in out.values() if SEVERITY_RANK.get(v['worst'], 0) >= 2)
    restrictions = sum(1 for v in out.values() for p in v['passes'] if p.get('rv_restriction'))

    payload = json.dumps({'legs': out}, ensure_ascii=False, sort_keys=True)
    decl = re.compile(r'const PASSES = \{.*?\};\n', re.S)
    block = f'const PASSES = {payload};\n'
    if decl.search(h):
        h = decl.sub(lambda _m: block, h, count=1)
    else:
        anchor = 'const PHOTO ='
        assert anchor in h, 'PHOTO declaration missing'
        h = h.replace(anchor, block + '\n' + anchor, 1)
    SRC.write_text(h)

    print(f"  {len(out)} legs carry pass or restriction data "
          f"({sum(len(v['passes']) for v in out.values())} records)")
    print(f"  {hard} legs rated hard or severe · {restrictions} carry a posted size/weight restriction")
    for k in ('severe', 'hard', 'moderate', 'easy', 'unrated'):
        if counts.get(k):
            print(f"     {k:<9}{counts[k]:>4}")
    print("wrote", SRC)


if __name__ == '__main__':
    main()
