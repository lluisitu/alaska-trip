#!/usr/bin/env python3
"""
Does the right research EXIST at this stop — not "of what exists, how much is linked".

    cd tools && python3 audit_coverage.py           # everything, worst first
    cd tools && python3 audit_coverage.py offroad   # one check

Why this exists
---------------
Great Basin read 100% offroad and had ZERO offroad routes. It read "browse
Nevada hikes" on a national-park stop. Both of its trails started from the top
of a road that is gated on the arrival date. Its dog verdict said prohibited
when NPS permits leashed dogs on a named trail and along every road in the park
— which, with the scenic drive gated, is the best dog day of the stop.

None of that was visible, because `progress.py` and `open_items.py` both answer
"of the entries that exist, how many are filled in". An empty box is 0 of 0,
which is 100%, which is silence. The metric could not see a missing thing.

This asks the other question. Every check below is a shape that produced a real
defect on this project, so none of them is hypothetical:

  empty       a box with nothing in it at a stop where something is plausible
  browse      a park-anchored stop whose trail-box heading falls back to the state
  thin        a multi-night stop carrying one or two trails
  season      a trail or route whose own season text conflicts with the dates
  dogflat     a whole stop answered with one verdict and no per-trail detail,
              where the authority is a national park — the case most likely to
              have named exceptions that a flat verdict hides
  dogmissing  the stop's OWN dog rule names a trail that is not in the trails
              box. This is the sharpest check here and it is how Great Basin
              was caught: the card said dogs prohibited, and the one trail the
              dog can legally walk was simply absent. Where the verdict is
              'prohibited', that named trail is not a nice-to-have — it is the
              only walk the dog gets at the stop.

Nothing here is proof of a defect. It is a worklist ordered by how likely a
look is to change something, which is the thing that did not exist before.
"""
import json, pathlib, re, sys
from collections import defaultdict

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE.parent / 'desktop' / 'index.html'
DB = HERE / 'links_db.json'

# Trail-like proper names, for reading a dog rule's own exceptions back out of it.
TRAILNAME = re.compile(r"\b([A-Z][\w'’.-]+(?:\s+[A-Z][\w'’.-]+){0,3}\s+(?:Trail|Path|Loop|Walk|Pathway))\b")

MONTHS = {m: i for i, m in enumerate(
    ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'])}
# Stops where an empty offroad box is the correct answer, with the reason.
NO_OFFROAD_OK = {
    'yellowstone': 'NPS prohibits off-road driving',
    'banff': 'Parks Canada prohibits off-road driving',
    'jasper': 'Parks Canada prohibits off-road driving',
    'waterton': 'Parks Canada prohibits off-road driving',
    'glacier': 'NPS prohibits off-road driving',
    'austin-depart': 'departure day, not a stay',
}


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


# Phrases that mean "the dog may NOT use this one".
NEGATIVE = re.compile(
    r"(closed to pets|closes to pets|not allowed|no dogs|are not permitted|"
    r"prohibited on|trails? (?:are )?closed|except for service)", re.I)
# ...and the word that flips a prohibition into a permission for whatever follows.
EXCEPT = re.compile(r"\b(except|exception|exceptions|other than|apart from)\b", re.I)
# A name ending in "Trail" that is really a place: "Eagle Trail State Recreation
# Site" is a park, not a walk, and adding it as a trail would be nonsense.
PLACE_SUFFIX = re.compile(r"^\s*(State|National|Provincial|Recreation|Park|Campground|SRA|SP)\b")


def excluded(prose, named):
    """Is the sentence naming this trail saying the dog CANNOT use it?

    Scoped to the sentence, and `except`-aware, because these rules routinely
    state the prohibition and its exceptions in one breath. Both readings failed
    on real data before this: "PROHIBITED on all trails except a named few:
    Peabody Creek Trail…" called three permitted trails closed, and "PROHIBITED
    on ALL trails … NPS names the General Sherman Tree Trail, Big Trees Trail
    and Grant Tree Trail" called a closed one permitted.
    """
    i = prose.find(named)
    if i < 0:
        return False
    start = prose.rfind('.', 0, i) + 1
    end = prose.find('.', i)
    sent = prose[start:end if end > 0 else len(prose)]
    if not NEGATIVE.search(sent):
        return False
    # A negative sentence, but the name sits after an "except" — it is one of
    # the exceptions, so it IS permitted.
    m = EXCEPT.search(sent)
    return not (m and (i - start) > m.end())


def is_place_not_trail(prose, named):
    """"Eagle Trail State Recreation Site" matches the trail-name pattern and is a park."""
    i = prose.find(named)
    return i >= 0 and bool(PLACE_SUFFIX.match(prose[i + len(named):i + len(named) + 24]))


def month_of(datestr):
    try:
        return int(datestr[5:7]) - 1
    except Exception:
        return None


def season_conflict(text, arrive, depart):
    """Port of seasonalTagConflict() in the page, so the audit and the card agree.

    Looks for '<closed months> ... opens/reopens <month>' and asks whether the
    stay falls inside the closed window. Handles the wrap across a new year.
    """
    if not text or not arrive:
        return None
    m = re.search(r'(?:opens?|reopens?)\s*~?\s*([A-Za-z]+)', text, re.I)
    if not m:
        return None
    reopen = MONTHS.get(m.group(1)[:3].lower())
    if reopen is None:
        return None
    closed = [MONTHS[t[:3].lower()] for t in re.findall(r'[A-Za-z]{3,}', text[:m.start()])
              if t[:3].lower() in MONTHS]
    if not closed:
        return None
    start = min(closed)
    def inside(mo):
        return (start <= mo < reopen) if start <= reopen - 1 else (mo >= start or mo < reopen)
    months = [month_of(arrive)] + ([month_of(depart)] if depart else [])
    return any(mo is not None and inside(mo) for mo in months)


def main():
    only = [a for a in sys.argv[1:] if not a.startswith('-')]
    h = SRC.read_text()
    stops = json.loads(ex(h, 'const STOPS =')) + json.loads(ex(h, 'const EXT_DATA =', '{', '}'))['STOPS']
    db = json.loads(DB.read_text())['stops']
    areas = json.loads(re.search(r'Object\.assign\(AREA_BROWSE_ALLTRAILS,\s*(\{.*?\})\);', h, re.S).group(1))

    found = defaultdict(list)
    for s in stops:
        sid, name = s['id'], s['name']
        e = db.get(sid, {})
        nights = s.get('nights') or 0
        park = bool(re.search(r'\bNP\b|National Park|Provincial Park|State Park|NRA|National Monument',
                              name))

        if not (s.get('offroad') or []) and sid not in NO_OFFROAD_OK:
            found['empty'].append((sid, name, 'offroad box is empty'))
        if not (s.get('alltrails') or []) and nights >= 2:
            found['empty'].append((sid, name, f'trails box is empty on a {nights}-night stay'))
        if not (s.get('scenicDrives') or []) and nights >= 3:
            found['empty'].append((sid, name, f'scenic-drives box is empty on a {nights}-night stay'))

        if park and sid not in areas and (s.get('alltrails') or []):
            found['browse'].append((sid, name, 'park stop, but the trail heading falls back to the state'))

        n = len(s.get('alltrails') or [])
        if 0 < n <= 2 and nights >= 3:
            found['thin'].append((sid, name, f'{n} trail(s) for a {nights}-night stay'))

        for box in ('alltrails', 'offroad', 'scenicDrives'):
            for y in (s.get(box) or []):
                for f in ('season', 'note', 'tag'):
                    if season_conflict(y.get(f), s.get('arrive'), s.get('depart')):
                        found['season'].append(
                            (sid, name, f'{box}: {y.get("name","")[:44]} — {f} says shut on these dates'))
                        break

        prose = e.get('dogs') or ''
        if prose and re.search(r'\bonly\b|\bexcept\b|\ballow', prose, re.I):
            # `box` and `n` are used above for the box name and the trail count;
            # shadowing them here worked only because of statement order.
            in_box = {y['name'].lower() for y in (s.get('alltrails') or [])}
            for named in set(TRAILNAME.findall(prose)):
                if any(named.lower() in b or b in named.lower() for b in in_box):
                    continue
                if is_place_not_trail(prose, named):
                    continue          # a park whose name ends in "Trail"
                if excluded(prose, named):
                    # The rule names it as a trail the dog may NOT use. Adding it
                    # as a dog walk would be exactly backwards, and 7 of the first
                    # 16 flags were this: Acadia's Ladder Trail, Fort Bragg's Fern
                    # Canyon, Sequoia's Grant Tree, Indiana Dunes' Pinhook Bog.
                    found['dogexcluded'].append(
                        (sid, name, f'dog rule names {named!r} as CLOSED to pets — do not add it'))
                    continue
                tail = (' — and the verdict is prohibited, so it is the ONLY walk'
                        if e.get('dogs_verdict') == 'prohibited' else '')
                found['dogmissing'].append(
                    (sid, name, f'dog rule names {named!r} as permitted, not in the trails box{tail}'))

        if e.get('dogs_verdict') in ('allowed', 'prohibited') and not (e.get('trail_dogs') or {}) \
                and park and len(s.get('alltrails') or []) >= 2:
            found['dogflat'].append(
                (sid, name, f"one flat '{e['dogs_verdict']}' verdict for {len(s['alltrails'])} trails"))

    order = ['dogmissing', 'dogexcluded', 'empty', 'browse', 'thin', 'season', 'dogflat']
    total = 0
    for k in order:
        if only and k not in only:
            continue
        rows = found[k]
        if not rows:
            continue
        total += len(rows)
        print(f'=== {k}: {len(rows)}')
        for sid, name, why in sorted(rows):
            print(f'   {sid:24s} {name[:32]:34s} {why}')
        print()
    print(f'{total} things worth a look')
    if not only:
        print('\nNone of these is proof of a defect — it is a worklist ordered by how likely')
        print('a look is to change something. Great Basin scored on four of the five.')


if __name__ == '__main__':
    main()
