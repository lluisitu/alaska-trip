#!/usr/bin/env python3
"""
Tag every shot, and make every coordinate in the shot list clickable.

    cd tools && python3 build_shots.py

Three things the shot list was missing.

**Tags.** 565 shots across 155 stops, and the only thing you could scan by was
`difficulty` — roadside, short walk, real hike, dawn commitment. That answers "how
hard is it to get there" and nothing else. Standing at camp at 06:40 wondering what
is worth the cold, the question is *when* and *what of*: is this a dawn shot or an
evening one, wildlife or landscape, does it need a clear sky or a dark moon. Those
answers are already inside each shot's own light and craft notes, in prose. This
lifts them out into tags you can read at a glance.

Tags are DERIVED from what the shot already says, not invented — the rules below
read the existing `light`, `craft` and `iphoneKind` fields. Where a derivation is
wrong or too coarse, `shots_db.json` overrides it per shot, and the override wins.
That keeps 565 shots tagged without hand-writing 565 entries, and keeps the hand
work where it actually adds something.

**Clickable coordinates.** Every shot carries `lat`/`lng` — 447 of 565 have them —
and the vantage notes quote more coordinates inline as bare text, e.g.
"between Headquarters (34.4048,-101.0296) and Honey Flat". You cannot tap a
number. Those become real Maps links, and every located shot gets a pin link of
its own.

**No invented locations.** A shot with no coordinate gets no map link. The
coordinates here were sourced when the shot list was researched; this script only
turns them into links, and never guesses one from a place name.

Standard library only; no network. Idempotent: coordinates already wrapped in a
link are left alone, and tags are rebuilt from scratch each run.
"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / 'desktop' / 'index.html'
DB = pathlib.Path(__file__).resolve().parent / 'shots_db.json'

MAPS = 'https://www.google.com/maps/search/?api=1&query={},{}'

# --- Derivation rules -------------------------------------------------------
# Ordered; every rule that matches contributes its tag. Deliberately literal —
# each pattern is a phrase the shot notes actually use.
WHEN_RULES = [
    ('dawn',      r'before sunrise|first light|pre-?dawn|grey light|hour before'),
    ('sunrise',   r'\bsunrise\b|after sunrise|as the sun clears'),
    ('golden',    r'golden hour|last 30 minutes|raking light|low sun'),
    ('sunset',    r'\bsunset\b|as the sun drops'),
    ('blue hour', r'blue hour|after the sun|civil twilight|lit windows'),
    ('night',     r'astronomical dark|milky way|star trail|aurora|moonrise|moonlit|full moon|night mode'),
    ('midday',    r'midday|middle of the day|overhead sun|any time of day'),
]
SUBJECT_FROM_KIND = {
    'wildlife': 'wildlife', 'aurora': 'aurora', 'night': 'astro', 'blue': 'blue hour',
    'water': 'water', 'people': 'people', 'tele': None, 'wide': None, 'general': None,
}
CONDITION_RULES = [
    ('needs clear sky', r'clear sky|cloudless|if the sky is clear|weather-dependent'),
    ('moon-dependent',  r'moon under|dark moon|new moon|full moon|moonrise|% moon'),
    ('truck',           r'in the truck|drive it .*truck|dirt road|4x4|high clearance'),
    ('seasonal',        r'only .* in|migration|lek|ice-?out|runoff|rut\b|calving'),
]


def tags_for(shot):
    text = ' '.join(str(shot.get(k) or '') for k in ('light', 'craft', 'subject', 'vantage'))
    low = text.lower()
    when = [t for t, pat in WHEN_RULES if re.search(pat, low)]
    # A shot is not five times of day at once. Keep the earliest-in-the-day match
    # plus night, which genuinely coexists with a dawn or dusk window.
    if len(when) > 2:
        when = [w for w in when if w != 'midday'][:2]
    subj = SUBJECT_FROM_KIND.get(shot.get('iphoneKind'))
    cond = [t for t, pat in CONDITION_RULES if re.search(pat, low)]
    out = []
    for t in when + ([subj] if subj else []) + cond:
        if t and t not in out:
            out.append(t)
    return out


COORD = re.compile(r'\(?\s*(-?\d{1,3}\.\d{3,6})\s*,\s*(-?\d{1,3}\.\d{3,6})\s*\)?')


def linkify(text):
    """Turn bare 'lat,lng' inside prose into a Maps link. Leaves anything already
    inside an href alone — running twice must not nest links."""
    if not text or 'maps/search' in text:
        return text

    def rep(m):
        lat, lng = m.group(1), m.group(2)
        return (f'<a href="{MAPS.format(lat, lng)}" target="_blank" rel="noopener" '
                f'title="Open {lat},{lng} in Google Maps">{lat},{lng}</a>')
    return COORD.sub(rep, text)


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
    db = json.loads(DB.read_text()) if DB.exists() else {'shots': {}}
    over = db.get('shots', {})
    h = SRC.read_text()
    raw = ex(h, 'const PHOTO =')
    PHOTO = json.loads(raw)

    tagged = pinned = linked = overridden = fixed = resolved = 0
    unlocated = []
    for sid, shots in PHOTO.items():
        by_title = over.get(sid, {})
        for s in shots:
            entry = by_title.get(s['title'], {})
            # ---- Apply review findings to the shot itself -------------------
            # A review pass found 138 problems across 126 shots and wrote each
            # into a flag. Exactly one had ever been applied. So the card showed
            # the wrong time, bearing or distance up top with the correction
            # folded away under "full notes" — and the tag derivation, which
            # reads the light text, was deriving tags from the wrong times.
            #
            # `fix` rewrites the shot's own fields; the flag it resolves is then
            # re-labelled src='fixed', which the renderer already shows as
            # "corrections applied" rather than "problems found".
            for field, repl in (entry.get('fix') or {}).items():
                if isinstance(repl, dict):
                    old, new = repl.get('from'), repl.get('to')
                    # A `to` that still contains its own `from` re-matches on the
                    # next run and the field grows forever — the md5 never
                    # settles. Caught by the three-run idempotency check; this
                    # makes it a hard error instead of a slow leak.
                    if old and new and old in new:
                        sys.exit(f"!! shots_db: fix for {s['title']!r} field {field!r} would "
                                 f"re-apply forever — 'to' contains 'from'")
                    if old and old in (s.get(field) or ''):
                        s[field] = s[field].replace(old, new)
                        fixed += 1
                else:
                    s[field] = repl
                    fixed += 1
            for key in entry.get('resolves') or []:
                for f in (s.get('flags') or []):
                    if key in f.get('text', ''):
                        f['src'] = 'fixed'
                        resolved += 1

            t = entry.get('tags') or tags_for(s)
            if entry.get('tags'):
                overridden += 1
            if entry.get('addTags'):
                t = t + [x for x in entry['addTags'] if x not in t]
            s['tags'] = t
            if t:
                tagged += 1
            # A pin for the shot's own coordinate, separate from the vantage link
            # build_phonecraft already adds.
            if s.get('lat') and s.get('lng'):
                s['mapUrl'] = MAPS.format(s['lat'], s['lng'])
                pinned += 1
            else:
                s.pop('mapUrl', None)
                unlocated.append(f"{sid}: {s['title']}")
            before = s.get('vantage')
            s['vantage'] = linkify(before)
            if before != s.get('vantage'):
                linked += 1
            for extra in entry.get('links') or []:
                s.setdefault('links', [])
                if not any(l.get('url') == extra['url'] for l in s['links']):
                    s['links'].append(extra)

    h = h.replace(raw, json.dumps(PHOTO, ensure_ascii=False), 1)
    SRC.write_text(h)

    total = sum(len(v) for v in PHOTO.values())
    print(f"build_shots: {total} shots across {len(PHOTO)} stops")
    print(f"  tagged {tagged} ({overridden} from shots_db.json, rest derived)")
    print(f"  map pins on {pinned}; {len(unlocated)} shots have no coordinate and get no link")
    print(f"  linkified coordinates in {linked} vantage notes")
    print(f"  applied {fixed} review corrections, resolving {resolved} flag(s)")
    openf = sum(1 for v in PHOTO.values() for x in v
                for f in (x.get("flags") or []) if f.get("src") != "fixed")
    print(f"  STILL OPEN: {openf} review findings not yet applied to their shot")


if __name__ == '__main__':
    main()
