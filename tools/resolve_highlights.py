#!/usr/bin/env python3
"""
Find the real entity behind each highlight, and write it into links_db.json.

    cd tools && python3 resolve_highlights.py          # dry run, prints what it would add
    cd tools && python3 resolve_highlights.py --write  # writes links_db.json

Why
---
The highlights list renders three links per entry built by pushing the entry's
own headline into a search URL. "Bike or walk the Caprock Canyons Trailway"
searched Wikipedia for that whole sentence and returned "List of cycleways" —
the real article was not even in the results. There are ~1,100 highlights, so
hand-resolving every one is not the way to finish.

How it stays honest
-------------------
Each headline is reduced to candidate entity names by stripping the imperative
verb and the trailing advice — "Visit Turkey, TX (Bob Wills hometown) and the
Bob Wills Museum" yields "Turkey, TX", "Turkey, Texas", "Bob Wills Museum",
"Bob Wills". Every candidate is then checked against Wikipedia's real article
index in batches of 40.

**Only an EXACT page hit counts**, following redirects. A fuzzy search hit is
discarded: "Milton Reimers Ranch Park" fuzzy-matches "The Alamo (2004 film)",
and that class of near-miss is what produced the wrong links to begin with. A
highlight with no exact match gets NO link and keeps the generic search
fallback, which is the honest state rather than a failure.

This writes to links_db.json — the auditable source — so build_links.py stays
offline and idempotent. Nothing here touches desktop/index.html.
"""
import json, pathlib, re, sys, time, urllib.parse, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / 'desktop' / 'index.html'
DB = pathlib.Path(__file__).resolve().parent / 'links_db.json'
API = 'https://en.wikipedia.org/w/api.php'
UA = {'User-Agent': 'alaska-trip-dashboard/1.0 (highlight entity resolution)'}

# Imperative openers the headlines use. Order matters — longest first.
LEAD = [
    'day trip to ', 'half-day trip to ', 'drive/hike toward ', 'day hike toward ',
    'bike or walk the ', 'soak in ', 'stroll historic downtown ', 'stroll ',
    'walk into ', 'visit the ', 'visit ', 'explore ', 'tour ', 'drive the ', 'drive ',
    'hike the ', 'hike ', 'see the ', 'see ', 'boating/kayaking on ',
    'wildlife watching — ', 'wildlife viewing for ', 'scenic drive/short hikes around ',
]
# Trailing advice to cut before the entity ends.
TAIL = re.compile(
    r'\s*(—|--|\(|,\s*(if|when|only|checking|after|before)\b|'
    r'\s+(if|only if|when|after|before|for|as a|as the|is|are|and make|and its|and the)\b).*$',
    re.I)
PROPER = re.compile(r'\b([A-Z][\w\'’.-]*(?:\s+(?:of|the|and|de|du|la|le)\s+[A-Z\w\'’.-]+|\s+[A-Z][\w\'’.-]*)*)')
STATE = {'TX': 'Texas', 'NM': 'New Mexico', 'CO': 'Colorado', 'WY': 'Wyoming', 'UT': 'Utah',
         'ID': 'Idaho', 'MT': 'Montana', 'AK': 'Alaska', 'WA': 'Washington', 'OR': 'Oregon',
         'CA': 'California', 'NV': 'Nevada', 'AZ': 'Arizona', 'BC': 'British Columbia',
         'YT': 'Yukon', 'AB': 'Alberta', 'ME': 'Maine', 'VT': 'Vermont', 'NC': 'North Carolina',
         'NH': 'New Hampshire', 'NY': 'New York', 'VA': 'Virginia', 'WV': 'West Virginia',
         'PA': 'Pennsylvania', 'AR': 'Arkansas', 'MI': 'Michigan', 'ON': 'Ontario'}


VERBS = {'ride','build','final','walking','history','spend','add','visit','drive','hike','see',
         'tour','explore','walk','stroll','soak','day','half','boating','wildlife','scenic'}


def candidates(name):
    """Entity names worth checking, best first. Single words are never candidates —
    they match common-noun articles ("Ride", "Build", "Final") that have nothing to
    do with the place."""
    s = name.strip().rstrip('.')
    low = s.lower()
    for lead in LEAD:
        if low.startswith(lead):
            s = s[len(lead):]
            break
    out, seen = [], set()

    def add(c):
        c = c.strip(' .,;:').replace('’', "'")
        if (len(c) > 3 and c[0].isupper() and c not in seen
                and len(c.split()) >= 2 and c.split()[0].lower() not in VERBS):
            seen.add(c); out.append(c)
            m = re.match(r'^(.*),\s*([A-Z]{2})$', c)   # "Turkey, TX" -> "Turkey, Texas"
            if m and m.group(2) in STATE:
                add(f'{m.group(1)}, {STATE[m.group(2)]}')

    add(TAIL.sub('', s))
    add(s)
    for m in PROPER.finditer(s):
        add(m.group(1))
    return out[:4]


def call(params, tries=6):
    url = API + '?' + urllib.parse.urlencode({**params, 'format': 'json'})
    for n in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 and n < tries - 1:
                time.sleep(8 * (n + 1)); continue
            raise
    raise RuntimeError('gave up on ' + url)


def resolve_all(titles):
    """title -> (real article title, (lat, lng) or None), or None for no article.

    Exact hits only, AND the article's own coordinates come back with it. A name
    match is not enough: "Twin Falls / Glacier Gulch trail" is at Smithers, BC
    and matches the Idaho city 1,500 km away; "Spend a morning in Magog" matched
    "Spend", which redirects to Consumption (economics). The caller checks the
    distance against the stop, which is the only thing that can tell those apart.
    """
    got = {}
    titles = sorted(set(titles))
    for i in range(0, len(titles), 40):
        chunk = titles[i:i + 40]
        q = call({'action': 'query', 'titles': '|'.join(chunk), 'redirects': 1,
                  'prop': 'coordinates', 'colimit': 'max'})['query']
        norm = {n['from']: n['to'] for n in q.get('normalized', [])}
        redir = {r['from']: r['to'] for r in q.get('redirects', [])}
        coords = {}
        for p in q['pages'].values():
            if p.get('coordinates'):
                c = p['coordinates'][0]
                coords[p['title']] = (c['lat'], c['lon'])
        # MediaWiki returns EVERY missing title as its own negative pageid —
        # -1, -2, -3 and so on. An earlier version excluded only '-1', so every
        # miss after the first counted as a real article and the resolver
        # "resolved" 1,031 of 1,042 headlines, including "Build in quiet days;
        # this remote destination justifies six nights". The `missing` key is
        # the actual signal.
        real = {p['title'] for p in q['pages'].values() if 'missing' not in p}
        for t in chunk:
            step = redir.get(norm.get(t, t), norm.get(t, t))
            got[t] = (step, coords.get(step)) if step in real else None
        time.sleep(3.0)
    return got


def km(a, b):
    from math import radians, sin, cos, asin, sqrt
    lat1, lon1, lat2, lon2 = map(radians, [a[0], a[1], b[0], b[1]])
    return 2 * 6371 * asin(sqrt(sin((lat2 - lat1) / 2) ** 2
                                + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2))


# How far an article may sit from the stop and still be the thing the highlight
# means. Day trips on this trip genuinely run 100 km+ (City of Rocks is 115 km
# from Twin Falls), so the window has to be generous — but 250 km still rejects
# the Idaho Twin Falls when the stop is in British Columbia.
MAX_KM = 250


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


def main():
    write = '--write' in sys.argv
    h = SRC.read_text()
    stops = json.loads(ex(h, 'const STOPS =')) + json.loads(ex(h, 'const EXT_DATA =', '{', '}'))['STOPS']
    db = json.loads(DB.read_text())

    # Skip highlights already resolved by hand — those carry richer links.
    todo, at = [], {}
    for s in stops:
        at[s['id']] = (s.get('lat'), s.get('lng'))
        have = (db['stops'].get(s['id'], {}).get('activities') or {})
        for a in (s.get('activities') or []):
            if a['name'] in have or a.get('links'):
                continue
            todo.append((s['id'], a['name']))

    cand = {n: candidates(n) for _, n in todo}
    res = resolve_all([c for cs in cand.values() for c in cs])

    added = miss = farflung = nocoord = 0
    for sid, name in todo:
        stop_ll = at.get(sid)
        pick = None
        for c in cand[name]:
            r = res.get(c)
            if not r:
                continue
            title, ll = r
            if not ll:
                nocoord += 1          # a person, a museum, an abstract topic
                continue
            if not (stop_ll and stop_ll[0]) or km(stop_ll, ll) > MAX_KM:
                farflung += 1         # right name, wrong continent
                continue
            pick = (c, title, round(km(stop_ll, ll)))
            break
        if not pick:
            miss += 1
            continue
        hit, title, dist = pick
        url = 'https://en.wikipedia.org/wiki/' + urllib.parse.quote(title.replace(' ', '_'))
        acts = db['stops'].setdefault(sid, {}).setdefault('activities', {})
        acts[name] = {'entity': title, 'links': [{'label': 'Wikipedia', 'url': url}],
                      'auto': True, 'auto_km': dist}
        added += 1

    print(f"{len(todo)} unlinked highlights across {len(set(s for s, _ in todo))} stops")
    print(f"  resolved to a real article: {added}")
    print(f"  rejected — article has no coordinates: {nocoord}")
    print(f"  rejected — article too far from the stop: {farflung}")
    print(f"  no usable match, left with the search fallback: {miss}")
    if write:
        db['_auto'] = ("Entries marked auto:true were resolved by resolve_highlights.py — the headline reduced to "
                       "candidate entity names and checked against Wikipedia's real article index. Exact hits only; "
                       "a fuzzy match is treated as no match. Hand-written entries are richer and are never overwritten.")
        DB.write_text(json.dumps(db, ensure_ascii=False, indent=2) + '\n')
        print("  written to links_db.json")
    else:
        print("  (dry run — pass --write to save)")


if __name__ == '__main__':
    main()
