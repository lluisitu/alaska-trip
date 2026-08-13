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

EXPLICIT_CONFLICT = re.compile(
    r'\b(CLOSED FOR THIS STOP|CONFLICTS? WITH THE STOP DATES|SHUT FOR THIS STOP|'
    r'SPLITS THE STAY|PARTIAL CONFLICT)\b')

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
    'caprock-canyons': 'TPWD publishes no unpaved driving route; the Trailway is hike/bike/horse only',
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
# Every one of these was learned from a real sentence in this db. "are not
# permitted" missed "NOT permitted off the Dunes Overlook Trail … or on Sand
# Ramp Trail", and that single missing word inverted the answer for a trail the
# authority bans.
NEGATIVE = re.compile(
    r"(closed to pets|closes to pets|not allowed|no dogs|not permitted|"
    r"prohibited on|barred|banned|trails? (?:are )?closed|except for service)", re.I)
# ...and the word that flips a prohibition into a permission for whatever follows.
EXCEPT = re.compile(r"\b(except|exception|exceptions|other than|apart from)\b", re.I)
# A name ending in "Trail" that is really a place: "Eagle Trail State Recreation
# Site" is a park, not a walk, and adding it as a trail would be nonsense.
# ...and "Colorado Trail Explorer" is a state trail DATABASE, not a walk.
PLACE_SUFFIX = re.compile(r"^\s*(State|National|Provincial|Recreation|Park|Campground|SRA|SP|Explorer|Register|Database)\b")


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
    # Kept in step with EXPLICIT_CONFLICT in desktop/index.html. A researcher who
    # already did the date arithmetic writes the answer in words; that is better
    # evidence than a pattern match, not worse.
    if EXPLICIT_CONFLICT.search(text):
        return True
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

        # `offroad_finding` records a stop researched and found to have nothing.
        if not (s.get('offroad') or []) and sid not in NO_OFFROAD_OK \
                and not e.get('offroad_finding'):
            found['empty'].append((sid, name, 'offroad box is empty'))
        if not (s.get('alltrails') or []) and nights >= 2:
            found['empty'].append((sid, name, f'trails box is empty on a {nights}-night stay'))
        if not (s.get('scenicDrives') or []) and nights >= 3:
            found['empty'].append((sid, name, f'scenic-drives box is empty on a {nights}-night stay'))

        if park and sid not in areas and (s.get('alltrails') or []) \
                and not e.get('area_browse_finding'):
            found['browse'].append((sid, name, 'park stop, but the trail heading falls back to the state'))

        # Thin has to scale with the stay. A flat "2 or fewer" passed Moab —
        # SEVEN nights in Arches and Canyonlands carrying three trails — and
        # Bryce with three for four nights. Roughly one walk per night up to a
        # sensible ceiling is the test that would have caught them.
        n = len(s.get('alltrails') or [])
        want = min(6, max(3, nights))
        if 0 < n < want and nights >= 2 and not e.get('trails_finding'):
            found['thin'].append(
                (sid, name, f'{n} trail(s) for a {nights}-night stay — expected about {want}'))

        for box in ('alltrails', 'offroad', 'scenicDrives'):
            for y in (s.get(box) or []):
                for f in ('season', 'note', 'tag'):
                    if season_conflict(y.get(f), s.get('arrive'), s.get('depart')):
                        found['season'].append(
                            (sid, name, f'{box}: {y.get("name","")[:44]} — {f} says shut on these dates'))
                        break

        prose = e.get('dogs') or ''
        # \bexcept\b does NOT match "exception", and "with one exception, the
        # Rim Rock Trail" is exactly how these rules are written — that typo
        # hid Black Canyon's only dog-legal trail. No trailing boundary.
        if prose and re.search(r'\bonly\b|\bexcept|\ballow|\bpermit', prose, re.I):
            # `box` and `n` are used above for the box name and the trail count;
            # shadowing them here worked only because of statement order.
            # Check EVERY box, not just trails: Mesa Top Loop is correctly filed
            # as a scenic drive, and flagging it as a missing trail was noise.
            in_box = {y['name'].lower()
                      for b in ('alltrails', 'scenicDrives', 'offroad')
                      for y in (s.get(b) or [])}
            # ...and allow the authority's current name to differ from the one
            # quoted in the rule: NPS's pets page says "Roadside Hiking Trail"
            # and its trail page says "Roadside Trail". Match on the distinctive
            # words rather than the whole string.
            # An authority can call the same trail two things on two of its own
            # pages — NPS's pets page says "Roadside Hiking Trail" and its trail
            # page says "Roadside Trail". `trail_aliases` in links_db records
            # that explicitly rather than leaving a permanent false positive or
            # loosening the matcher until it starts hiding real gaps.
            aliases = {k.lower(): v.lower() for k, v in (e.get('trail_aliases') or {}).items()}

            def covered(nm):
                low = aliases.get(nm.lower(), nm.lower())
                if any(low in b or b in low for b in in_box):
                    return True
                words = [w for w in re.findall(r"[a-z']+", low)
                         if w not in ('trail', 'path', 'loop', 'walk', 'pathway', 'the')]
                return bool(words) and any(
                    all(w in b for w in words) for b in in_box)
            for named in set(TRAILNAME.findall(prose)):
                if covered(named) or named in (e.get('dog_trails_noted') or {}):
                    continue          # on the card, or a recorded deliberate omission
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

        # A dog rule with no source url cannot be re-checked when the authority
        # changes it, and one sourced FROM AllTrails is forbidden outright by
        # §5 — its dog flag has contradicted the managing authority twice on
        # this trip. Sawtooth's rule was "Allowed on leash (per AllTrails
        # listing)" until it was re-sourced to the USFS wilderness regulations.
        if prose:
            if re.search(r'alltrails|per reviews', prose, re.I):
                found['dogsource'].append(
                    (sid, name, 'dog rule is sourced from AllTrails — §5 forbids it'))
            elif not e.get('dogs_source'):
                found['dogsource'].append(
                    (sid, name, 'dog rule has no source url to re-check it against'))

        if e.get('dogs_verdict') in ('allowed', 'prohibited') and not (e.get('trail_dogs') or {}) \
                and park and len(s.get('alltrails') or []) >= 2:
            found['dogflat'].append(
                (sid, name, f"one flat '{e['dogs_verdict']}' verdict for {len(s['alltrails'])} trails"))

    # A review COUNT repeated across two different trails is a copied figure,
    # not a coincidence — Bryce's Fairyland Loop and Moab's Mesa Arch both read
    # 12,704, and two Bisbee trails on the SAME card both read 397. Bare star
    # ratings ("4.6") repeat legitimately and are ignored.
    seen_rating = defaultdict(list)
    for s in stops:
        for y in (s.get('alltrails') or []):
            r = (y.get('rating') or '').strip()
            if r and re.search(r'\d[\d,]{2,}', r):
                seen_rating[r].append((s['id'], y.get('name', '')))
    for r, rows in seen_rating.items():
        if len(rows) > 1:
            for sid_, nm in rows:
                found['dupstat'].append(
                    (sid_, next(x['name'] for x in stops if x['id'] == sid_),
                     f'{nm[:34]!r} rating {r!r} also appears on '
                     f'{", ".join(f"{a}/{b[:24]}" for a, b in rows if (a, b) != (sid_, nm))}'))

    order = ['dogmissing', 'dupstat', 'dogsource', 'dogexcluded', 'empty', 'browse', 'thin', 'dogflat', 'season']
    # `season` is not a worklist: every hit is a conflict the card already
    # renders with a warning marker. Counting it as outstanding work made the
    # total jump from 8 to 35 the moment the flag started working, which is
    # exactly backwards.
    # `dogflat` is a weak signal now that `dogmissing` exists. It asks "is this
    # park answered with one verdict and no per-trail detail", which was worth
    # asking before anything read the exceptions back out of the prose. All 13
    # it flagged were hand-checked and every one is correctly answered — the
    # authority genuinely states a park-wide rule (Yellowstone, Grand Teton,
    # Glacier, Sequoia) or a park-wide permission (Parks Canada's 3 m leash).
    # Kept as information, not work.
    INFORMATIONAL = {'season', 'dogexcluded', 'dogflat'}
    total = 0
    for k in order:
        if only and k not in only:
            continue
        rows = found[k]
        if not rows:
            continue
        if k not in INFORMATIONAL:
            total += len(rows)
        print(f'=== {k}: {len(rows)}')
        for sid, name, why in sorted(rows):
            print(f'   {sid:24s} {name[:32]:34s} {why}')
        print()
    info = sum(len(found[k]) for k in INFORMATIONAL)
    print(f'{total} things worth a look, plus {info} informational '
          f'(seasonal conflicts the card flags, and trails correctly ruled out for dogs)')
    if not only:
        print('\nNone of these is proof of a defect — it is a worklist ordered by how likely')
        print('a look is to change something. Great Basin scored on four of the five.')


if __name__ == '__main__':
    main()
