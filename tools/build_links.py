#!/usr/bin/env python3
"""
Inject researched trail links and attributes from links_db.json into STOPS/EXT_DATA.

    cd tools && python3 build_links.py

Why this exists
---------------
Half the named trails on the dashboard had no direct link. 264 of 498 trail
items across the two trips rendered as a search magnifier, because when the
cards were first built the real listing URLs could not be found and a guessed
URL is worse than an honest search. They can be found now, so this replaces the
search fallbacks with real listings — and, more importantly, with the numbers
you actually decide on: distance, time, difficulty and how many people rated it.

It also fixes three things that were not link problems at all:

  * Trailheads filed as trails. Wind River's entire box was Elkhart Park, Scab
    Creek and Big Sandy — car parks. Nothing there told you what you would walk.
  * Prose filed as trails. "Alluvial Fan and Horseshoe Park." is two place
    names; "Red Canyon rim paths for the best effort-to-view ratio." duplicates
    the trail listed directly above it.
  * Drives filed as trails. Sheep Creek Loop Scenic Byway sat in Flaming Gorge's
    hiking box; AllTrails calls it "Easy" because it is a 12.9-mile drive.

What it does NOT do
-------------------
It does not invent anything. A trail with no listing keeps its name and its
official length and carries no trail link at all — see Mesa Trail at Caprock,
which Texas Parks & Wildlife confirms exists and AllTrails has never indexed.
Absence is recorded as absence, because an absence gets phoned about and a
wrong link gets trusted.

Evidence tiers, carried per link in the db:
  official  fetched from the managing authority and confirmed 200 here
  indexed   returned by search with a matching title and a review count;
            alltrails.com answers 403 to every request from this sandbox, so
            the page itself could not be loaded and a 403 proves nothing
  unlisted  confirmed real by the authority, no listing exists

Shape written into each trail item
----------------------------------
{name, url, difficulty, distance, time, rating, note} — deliberately the shape
trailPillsHtml() in desktop/index.html already renders, so the four numbers
appear with no page change. `note` carries the uses/cruise/season text until
those get their own badges.

STOPS is re-serialised compact and EXT_DATA with indent=1, matching every other
script that writes them; build_parks.py sets that convention and two scripts
disagreeing reformat the file back and forth forever.

Idempotent: each run rebuilds the covered stops' lists from the db, so running
it twice changes nothing the second time. Standard library only; no network.
"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / 'desktop' / 'index.html'
DB = pathlib.Path(__file__).resolve().parent / 'links_db.json'


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


def note_for(t):
    """What is left after the pills have taken everything they can show.

    Uses, difficulty, distance, time, rating and the cruise verdict are all pills
    now. Repeating them here made every row a paragraph — on Caprock, where every
    trail is multiuse, "hike/bike/horse · bike-legal but not cruising" appeared
    seven times in one box. The note keeps only what a pill cannot carry.
    """
    bits = []
    if t.get('elevation_gain'):
        bits.append(t['elevation_gain'] + ' gain')
    at = t.get('alltrails') or {}
    if at.get('match') == 'contains':
        # The distance pill is the longer route's; say so once, briefly. The full
        # explanation rides in stats_note as a tooltip, not as body text.
        bits.append('AllTrails route includes this trail'
                    + (f"; official {t['official_length']}" if t.get('official_length') else ''))
    elif at.get('match') == 'none' or at.get('tier') == 'unlisted':
        bits.append('no AllTrails listing — official source')
    if t.get('season'):
        bits.append(t['season'])
    return ' · '.join(bits) or None


def item_sort_key(x):
    """Same rule as sort_key, applied to a built item so the whole box is ordered —
    including entries this pass did not touch. Built items keep the review string
    in `rating`, which review_count()/star() both read.

    Entries still awaiting research sort below everything real, whatever their
    difficulty — they are placeholders, not options."""
    return (1 if x.get('pending') else 0,) + tuple(sort_key(x))


def build_item(t):
    at = t.get('alltrails') or {}
    item = {'name': t['name']}
    # No AllTrails listing does not mean no link. Mesa Trail is real per TPWD and
    # unindexed by AllTrails, but Komoot has it — and supplied the packed-sand
    # surface note that decided whether it is rideable.
    url = at.get('url') or next((o['url'] for o in (t.get('other_links') or []) if o.get('url')), None)
    if url:
        item['url'] = url
        if not at.get('url'):
            item['label'] = (t.get('other_links') or [{}])[0].get('label') or 'source'
    for k in ('difficulty', 'time'):
        if t.get(k):
            item[k] = t[k]
    # Distance is always a pill, never buried in the note. Where the listing has
    # no distance the authority's own length takes the pill — Mesa Trail is not
    # on AllTrails and TPWD's 3.1 mi is the real number, so it belongs up top
    # with every other trail's mileage rather than in a sentence underneath.
    dist = t.get('distance') or t.get('official_length')
    if dist:
        item['distance'] = dist
    if t.get('reviews'):
        # "4.8 (1,307)" is the normal shape. A bare count arrives when the star
        # could not be sourced — DuckDuckGo's AllTrails titles carry the review
        # count and never the star — and that count is worth showing on its own.
        # Test for the word too, or "285 reviews" becomes "285 reviews reviews".
        r = t['reviews'].strip()
        item['rating'] = r if ('(' in r or 'review' in r.lower()) else r + ' reviews'
    if t.get('uses'):
        item['uses'] = t['uses']
    if t.get('dogs') is not None:
        item['dogs'] = t['dogs']
    # A `false` verdict with a reason is worth as much as a positive one — the
    # Trailway reads as a flat rail bed everywhere else and is sand, rock and
    # goatheads. Carry it as a pill with the reason on hover, not as a paragraph.
    if t.get('cruise') in (True, 'candidate') or (t.get('cruise') is False and t.get('cruise_reason')):
        item['cruise'] = t['cruise']
        if t.get('cruise_reason'):
            item['cruiseWhy'] = t['cruise_reason']
    note = note_for(t)
    if note:
        item['note'] = note
    return item


def norm(s):
    return ' '.join(str(s or '').lower().split()).rstrip('.')


# The keys each box's builder owns. Anything outside these sets is hand-written
# prose that lives only in desktop/index.html and must survive a rebuild.
OFFROAD_KEYS = ('name', 'url', 'distance', 'difficulty', 'note', 'season', 'rig')
DRIVE_KEYS = ('name', 'url', 'note', 'season', 'distance', 'rig')
TRAIL_KEYS = ('name', 'url', 'label', 'difficulty', 'time', 'distance', 'rating',
              'uses', 'dogs', 'cruise', 'cruiseWhy', 'note')


def merge_keep(old, new, owned):
    """Replace the keys this script owns; carry everything else across.

    The three boxes used to assign `box[hit] = item`, which silently deleted
    any field the builder does not know about. That cost the east extension's
    offroad `tag` prose — trip-specific judgement like "the most realistic
    early-May 4x4 day of the stop" — which lives ONLY in desktop/index.html.
    No db holds it, so a wholesale replace destroyed it with nothing to
    rebuild from.

    Owned keys are cleared even when the new item omits them, because that is
    how a stale value gets removed: a trail that gains a real url must lose
    its old label 'search AllTrails'. Unowned keys are never touched.
    """
    kept = {k: v for k, v in old.items() if k not in owned}
    kept.update(new)
    return kept


# Ordering, in the order the rules apply:
#
#   1. Easy and moderate are ONE band, not two. Inside it, review count decides.
#      A 4.6 from 3,000 people is a stronger signal than a 4.9 from 11 — the star
#      is the verdict, the count is the confidence.
#   2. Hard and challenging drop below that band, but a hard trail with
#      outstanding reviews still earns its place rather than being cut. Haynes
#      Ridge at 4.8 from 1,307 is worth seeing on the card even on a stop where
#      nothing that steep will be walked.
#   3. Unknown difficulty rides in the easy/moderate band. Roughly half the
#      listings publish no grade, and burying a 1,300-review trail for a missing
#      field would be the field deciding, not the trail.
HARD = {'hard', 'challenging', 'strenuous', 'difficult', 'moderately challenging'}


def review_count(t):
    """'4.5 (611)' -> 611; '721' -> 721; absent -> 0."""
    raw = str(t.get('reviews') or t.get('rating') or '')
    inner = raw.split('(')[-1].split(')')[0] if '(' in raw else raw
    digits = ''.join(c for c in inner if c.isdigit())
    return int(digits) if digits else 0


def star(t):
    """Leading 4.8 out of '4.8 (1,307)'. 0 when only a bare count is known."""
    raw = str(t.get('reviews') or t.get('rating') or '').strip()
    head = raw.split('(')[0].strip()
    try:
        v = float(head)
        return v if v <= 5 else 0.0
    except ValueError:
        return 0.0


def outstanding(t):
    """Well loved by enough people to survive being hard."""
    n, s = review_count(t), star(t)
    return n >= 1000 or (s >= 4.7 and n >= 300)


# Rating and count are one signal, not two sorts. A shrunk average pulls a
# thinly-reviewed score toward the prior, so 4.9 from 11 people does not beat
# 4.6 from 3,000 — while a genuinely great trail with thousands of reviews keeps
# almost all of its score. PRIOR_N is how many reviews it takes to be believed.
PRIOR_N = 200
PRIOR_STAR = 4.5


def score(t):
    n, s = review_count(t), star(t)
    # A count with no published star is common on these listings. Fall back to the
    # prior so it sits neutrally rather than scoring zero, and let the raw count
    # break the tie below.
    observed = s if s else PRIOR_STAR
    return (n * observed + PRIOR_N * PRIOR_STAR) / (n + PRIOR_N)


def unrated(t):
    return review_count(t) == 0 and star(t) == 0


def band(t):
    if norm(t.get('difficulty')) in HARD:
        return 1 if outstanding(t) else 2
    return 0


def sort_key(t):
    # band, then known-before-unknown, then the combined score, then raw count.
    return (band(t), 1 if unrated(t) else 0, -score(t), -review_count(t),
            norm(t.get('name')))


def apply_stop(stop, entry, log):
    sid = stop['id']
    trails = entry.get('trails') or []
    # MERGE, never replace. The db only carries the items that were researched
    # this pass; the rest of the box is already correct and must survive. An
    # earlier version of this assigned the list wholesale and silently dropped
    # Santa Fe's five good trails and six of Estes Park's eight.
    real = sorted([t for t in trails if t.get('name') and not t.get('problem')], key=sort_key)
    if real:
        existing = stop.get('alltrails') or []
        # A db trail replaces the item it came from — matched on the `was` field
        # (the old, often wrong, name) and on the new name.
        replaced = 0
        for t in real:
            keys = {norm(t['name'])}
            # `was_name` is the exact previous name. `was` is prose and was
            # being split on an em-dash to recover it — which fails whenever the
            # old name itself contains one ("Double Arch — Windows Section"),
            # silently adding a duplicate instead of replacing.
            if t.get('was_name'):
                keys.add(norm(t['was_name']))
            if t.get('was'):
                keys.add(norm(t['was'].split(' — ')[0]))
            item = build_item(t)
            hit = next((i for i, x in enumerate(existing) if norm(x.get('name')) in keys), None)
            if hit is None:
                existing.append(item)
            else:
                existing[hit] = merge_keep(existing[hit], item, TRAIL_KEYS)
                replaced += 1
        stop['alltrails'] = existing
        log.append(f"  {sid}: {replaced} replaced, {len(real) - replaced} added, "
                   f"{len(existing)} in the box")
    # Scenic drives, same merge-by-name rule.
    for r in entry.get('scenicDrives_patch') or []:
        box = stop.setdefault('scenicDrives', [])
        keys = {norm(r['name'])}
        if r.get('was_name'):
            keys.add(norm(r['was_name']))
        item = {k: v for k, v in r.items()
                if k in DRIVE_KEYS and v}
        item['rig'] = 'truck'
        hit = next((i for i, x in enumerate(box) if norm(x.get('name')) in keys), None)
        if hit is None:
            box.append(item)
        else:
            box[hit] = merge_keep(box[hit], item, DRIVE_KEYS)

    # Offroad routes, same merge rule as trails: replace by name or was_name,
    # never append blindly.
    for r in entry.get('offroad') or []:
        box = stop.setdefault('offroad', [])
        keys = {norm(r['name'])}
        if r.get('was_name'):
            keys.add(norm(r['was_name']))
        item = {k: v for k, v in r.items()
                if k in OFFROAD_KEYS and v}
        item['rig'] = 'truck'
        hit = next((i for i, x in enumerate(box) if norm(x.get('name')) in keys), None)
        if hit is None:
            box.append(item)
        else:
            box[hit] = merge_keep(box[hit], item, OFFROAD_KEYS)
    for x in entry.get('not_a_route') or []:
        box = stop.get('offroad') or []
        before = len(box)
        stop['offroad'] = [y for y in box if norm(y.get('name')) != norm(x['entry'])]
        if len(stop['offroad']) != before:
            log.append(f"  {sid}: dropped {x['entry'][:40]!r} from offroad — {x['problem'][:50]}")

    # Prose and trailheads that are not trails at all come out by name.
    # Research arrives as patch files written by hand and by agents, and a
    # patch using {name, what_it_really_is} instead of {entry, problem} crashed
    # this script with a bare KeyError. The build loop was swallowing stderr at
    # the time, so it looked like the merge simply had no effect — the data was
    # in the db and never reached the page. Name the file and the field.
    for x in (entry.get('not_a_trail') or []) + (entry.get('not_a_route') or []):
        if 'entry' not in x:
            sys.exit(f"!! links_db.json: {sid} has a not_a_trail/not_a_route item with no "
                     f"'entry' key: {json.dumps(x, ensure_ascii=False)[:120]}\n"
                     f"   The shape is {{entry, problem}}, not {{name, what_it_really_is}}.")
    drop = {norm(x['entry']) for x in (entry.get('not_a_trail') or [])}
    un = entry.get('unresolved')
    if un:
        drop.add(norm(un['entry']))
    if drop:
        before = len(stop.get('alltrails') or [])
        stop['alltrails'] = [x for x in (stop.get('alltrails') or [])
                             if norm(x.get('name')) not in drop]
        gone = before - len(stop['alltrails'])
        if gone:
            log.append(f"  {sid}: dropped {gone} entry/entries that were not trails")
    for r in entry.get('reclassify') or []:
        if r.get('from') == 'alltrails' and r.get('to') == 'scenicDrives':
            before = len(stop.get('alltrails') or [])
            stop['alltrails'] = [x for x in (stop.get('alltrails') or [])
                                 if x.get('name') != r['name']]
            if len(stop.get('alltrails') or []) != before:
                # The destination box may already describe the same road under a
                # different name — Flaming Gorge already had "Sheep Creek Canyon
                # Geological Loop" when Sheep Creek Loop Scenic Byway arrived from
                # the trail box, and appending blindly listed one road twice.
                dest = stop.setdefault('scenicDrives', [])
                same = r.get('same_as')
                hit = next((x for x in dest if same and norm(same) in norm(x.get('name'))), None)
                if hit is not None:
                    hit.setdefault('alt_url', r.get('url'))
                    log.append(f"  {sid}: {r['name']!r} folded into {hit['name'][:40]!r} "
                               f"(same road, already listed)")
                else:
                    dest.append({'name': r['name'], 'url': r.get('url')})
                    log.append(f"  {sid}: moved {r['name']!r} to scenic drives")
    # Same merge rule as the trails — appending unconditionally made the file
    # grow by one Trailway per run and the md5 never settled.
    for b in entry.get('biking') or []:
        box = stop.setdefault('alltrails', [])
        item = build_item(b)
        hit = next((i for i, x in enumerate(box) if norm(x.get('name')) == norm(b['name'])), None)
        if hit is None:
            box.append(item)
            log.append(f"  {sid}: + {b['name']} (biking)")
        else:
            box[hit] = item
    # A stop `note` that only explains a scheduling decision already made. The
    # reasoning was worth writing down when the date was being chosen; on the
    # card it is a paragraph of history above the things you actually act on.
    # Removed here rather than in build_staynotes, which filters notes it
    # recognises as pacing changelog and did not catch this one.
    if entry.get('drop_note') and stop.get('note'):
        stop['note'] = None
        log.append(f"  {sid}: removed the stop note — {entry.get('drop_note_why', 'no reason given')[:70]}")

    fix = entry.get('blurb_fix')
    if fix and fix['replace'] in (stop.get('blurb') or ''):
        stop['blurb'] = stop['blurb'].replace(fix['replace'], fix['with'])
        log.append(f"  {sid}: blurb corrected — {fix['problem'][:60]}...")
    for a in (stop.get('activities') or []):
        if fix and fix['replace'] in (a.get('detail') or ''):
            a['detail'] = a['detail'].replace(fix['replace'], fix['with'])

    # ---- Highlights ---------------------------------------------------------
    # The activity list was the worst-served box on the card: 1,105 entries, each
    # rendering three links built by shoving its own headline into a search URL.
    # "Bike or walk the Caprock Canyons Trailway" searched Wikipedia for that
    # whole sentence and returned "List of cycleways". And where a highlight IS a
    # trail — Perrine Bridge, City of Rocks — it showed none of the distance,
    # difficulty or rating the trails box shows for the same thing.
    #
    # An entry here gives a highlight its real entity: verified links, and the
    # trail stats when it is a trail. Activities with no entry keep the generic
    # search links, which stays honest until they are researched.
    acts = entry.get('activities') or {}
    if acts:
        kept, dropped = [], 0
        for a in (stop.get('activities') or []):
            spec = acts.get(a.get('name'))
            if spec and spec.get('drop'):
                dropped += 1
                continue
            if spec:
                for k in ('entity', 'links', 'difficulty', 'distance', 'time',
                          'uses', 'cruise', 'dogs'):
                    if spec.get(k) is not None:
                        a[k] = spec[k]
                if spec.get('reviews'):
                    a['rating'] = spec['reviews']
                if spec.get('cruise_reason'):
                    a['cruiseWhy'] = spec['cruise_reason']
            kept.append(a)
        stop['activities'] = kept
        linked = sum(1 for a in kept if a.get('links'))
        log.append(f"  {sid}: {linked} highlights given real links"
                   + (f", {dropped} duplicate(s) removed" if dropped else ""))

    # ---- Dog verdict, per trail -------------------------------------------
    # LAST in this function on purpose. An earlier version ran it before the
    # biking entries were merged in, so the Caprock Trailway — the one bike
    # option at that stop — came out with no verdict while the six trails beside
    # it were all green. Anything that annotates the box has to run after
    # everything that adds to the box.
    #
    # The trip carries a dog for 405 nights and four US national parks on this
    # route close every trail to it. This puts the answer on each row.
    #
    # Absence is NOT a green light. A stop with no researched rule gets no icon
    # at all, because "we did not check" and "dogs are welcome" must never look
    # the same on a card read at a trailhead.
    verdict = entry.get('dogs_verdict')
    per_trail = entry.get('trail_dogs') or {}
    if verdict or per_trail:
        for it in (stop.get('alltrails') or []):
            name = it.get('name')
            if name in per_trail:                 # the authority named this trail
                val = per_trail[name]
                if val is None:
                    it.pop('dogs', None)          # named neither way — stay silent
                else:
                    it['dogs'] = val
            elif verdict == 'allowed':
                it['dogs'] = True
            elif verdict == 'prohibited':
                it['dogs'] = False
            # 'partial' with no per-trail entry falls through to no icon.
        if entry.get('dogs_exception'):
            stop['dogsException'] = entry['dogs_exception']
    if stop.get('alltrails'):
        stop['alltrails'] = sorted(stop['alltrails'], key=item_sort_key)


# --- Global pass -----------------------------------------------------------
# Everything above needs research per stop. These rules do not: they are the
# guidelines applied mechanically to all 157 stops, using data already present.

# A trail entry must be a trail. These end a name that is really a sentence.
PROSE = re.compile(r'\.\s*$')
TRAILHEAD = re.compile(r'\btrail\s*head\b|\btrailhead\b', re.I)
# A drive filed in the hiking box. Deliberately narrow — "Rock Castle Gorge Trail
# (Blue Ridge Parkway MP 167.1)" is a hike whose name mentions a parkway, so the
# pattern must match what the entry IS, not what it is near.
IS_DRIVE = re.compile(r'\b(scenic (drive|byway)|auto (road|tour)|byway|skyway|'
                      r'scenic loop|auto toll)\b', re.I)
IS_OFFROAD = re.compile(r'\b(4x4|4wd|ohv|jeep road|primitive road)\b', re.I)


def norm_key(n):
    """For duplicate detection: lowercase, no punctuation, no leading article."""
    s = re.sub(r'[^a-z0-9 ]+', ' ', str(n or '').lower())
    s = re.sub(r'\b(the|a|an)\b', ' ', s)
    return ' '.join(s.split())


def global_pass(stops, log):
    """Sort every box, drop prose and trailheads, move drives and 4x4 routes out,
    and remove entries duplicated inside a box or across boxes."""
    counts = {'sorted': 0, 'prose': 0, 'trailhead': 0, 'drive': 0, 'offroad': 0, 'dup': 0, 'split': 0}
    for s in stops:
        box = s.get('alltrails') or []
        keep = []
        for it in box:
            n = it.get('name', '')
            # FLAG, do not delete. A first version dropped these outright and it
            # made the dashboard worse in the meantime: "Angels Landing / Grotto
            # Trailhead" is the only mention of Angels Landing on that stop, and
            # "Rim Trail, Yavapai Point to Mather Point." is a real trail whose
            # name merely ends in a full stop. Deleting information before the
            # research that replaces it exists is not a fix. These carry a marker,
            # sort to the bottom of the box, and are cleared as each leg is done.
            if not it.get('url') and (PROSE.search(n) or TRAILHEAD.search(n)):
                is_th = bool(TRAILHEAD.search(n))
                counts['trailhead' if is_th else 'prose'] += 1
                it['pending'] = True
                it['note'] = ('trailhead, not a trail — the route that leaves it is not researched yet'
                              if is_th else
                              'not a trail entry yet — needs the named route, or a move to activities')
                keep.append(it)
                continue
            if IS_DRIVE.search(n):
                dest = s.setdefault('scenicDrives', [])
                if not any(norm_key(x.get('name')) == norm_key(n) for x in dest):
                    dest.append({k: v for k, v in it.items() if k in ('name', 'url', 'note')})
                counts['drive'] += 1
                continue
            if IS_OFFROAD.search(n):
                dest = s.setdefault('offroad', [])
                if not any(norm_key(x.get('name')) == norm_key(n) for x in dest):
                    dest.append({k: v for k, v in it.items() if k in ('name', 'url', 'note')})
                counts['offroad'] += 1
                continue
            keep.append(it)
        if len(keep) != len(box):
            s['alltrails'] = keep
        # Duplicates inside each box — Great Sand Dunes carried Medano Pass twice
        # in `offroad`, once per source.
        for field in ('alltrails', 'offroad', 'scenicDrives'):
            items = s.get(field) or []
            seen, out = {}, []
            for it in items:
                k = norm_key(it.get('name'))
                if k in seen:
                    # Keep the richer entry, but do not lose the other's link.
                    first = out[seen[k]]
                    if it.get('url') and it['url'] != first.get('url'):
                        first.setdefault('alt_url', it['url'])
                    if len(json.dumps(it)) > len(json.dumps(first)):
                        it.setdefault('alt_url', first.get('url')) if first.get('url') else None
                        out[seen[k]] = it
                    counts['dup'] += 1
                    continue
                seen[k] = len(out)
                out.append(it)
            if len(out) != len(items):
                s[field] = out
        # ---- Scenic drives and offroad: name, note, rig ----------------------
        # Two fixes the strategy doc called for and nothing had applied.
        #
        # 1. The name field holds a whole sentence on 142 of 256 scenic drives —
        #    "Thousand Springs Scenic Byway (US-30) — a paved Snake River
        #    canyon-rim byway past springs and waterfalls; a relaxed truck
        #    day-drive..." That is a name and a description welded together, so
        #    the link text reads as prose. Split on the em-dash: the road keeps
        #    the name, the rest becomes the note.
        # 2. rig. Settled by the person driving — no scenic road and no 4x4
        #    route is done in the coach. It is a standing decision, not a
        #    per-entry research question, so it is applied here rather than
        #    looked up 157 times.
        for field in ('scenicDrives', 'offroad'):
            for it in (s.get(field) or []):
                n = it.get('name') or ''
                if ' — ' in n:
                    head, tail = n.split(' — ', 1)
                    # Only split when what is left is plausibly a name, not when
                    # the dash is mid-sentence in something already short.
                    if 3 < len(head) < 80 and len(tail) > 20:
                        it['name'] = head.strip()
                        extra = tail.strip()
                        it['note'] = (extra if not it.get('note')
                                      else it['note'] + ' · ' + extra)
                        counts['split'] += 1
                it['rig'] = 'truck'
        for field in ('alltrails', 'offroad', 'scenicDrives'):
            if s.get(field):
                s[field] = sorted(s[field], key=item_sort_key)
                counts['sorted'] += 1
    log.append(f"  global: sorted {counts['sorted']} boxes; flagged {counts['prose']} prose "
               f"and {counts['trailhead']} trailheads as pending research (kept, sorted last); "
               f"moved {counts['drive']} drives and {counts['offroad']} 4x4 routes to their own "
               f"box; merged {counts['dup']} duplicates; split {counts['split']} drive/offroad "
               f"names off their descriptions and set rig=truck on all of them")


def main():
    db = json.loads(DB.read_text())
    h = SRC.read_text()

    stops_raw = ex(h, 'const STOPS =')
    stops = json.loads(stops_raw)
    ext_raw = ex(h, 'const EXT_DATA =', '{', '}')
    ext = json.loads(ext_raw)

    index = {s['id']: s for s in stops}
    index.update({s['id']: s for s in ext['STOPS']})

    log, missing = [], []
    for sid, entry in db['stops'].items():
        if sid not in index:
            missing.append(sid)
            continue
        apply_stop(index[sid], entry, log)

    if missing:
        sys.exit('!! links_db.json names stops that do not exist: ' + ', '.join(missing))

    # Strip links proven not to exist, everywhere, every run. The page is MERGED
    # into rather than rebuilt, so deleting an entry from the db does not remove
    # a link that was already written into it — 29 dead Wikipedia links survived
    # exactly that way. This is the only thing that actually takes them out.
    dead = set(db.get('dead_links') or [])
    if dead:
        gone = 0
        for s in stops + ext['STOPS']:
            for a in (s.get('activities') or []):
                links = a.get('links') or []
                keep = [l for l in links if l.get('url') not in dead]
                if len(keep) != len(links):
                    gone += len(links) - len(keep)
                    if keep:
                        a['links'] = keep
                    else:
                        a.pop('links', None); a.pop('entity', None)
        if gone:
            log.append(f"  stripped {gone} link(s) proven not to exist")

    # Applies to every stop, researched or not.
    global_pass(stops + ext['STOPS'], log)

    # Park-level browse link on the trail box heading. Without an entry here the
    # heading falls back to the whole state — Caprock read "Browse Texas hikes".
    # Injected between markers and merged onto the existing const rather than
    # rewritten: a regex that matched the object's *shape* is exactly the trap
    # that left half an old block behind and appended a second copy.
    areas = {sid: e['area_browse_alltrails'] for sid, e in db['stops'].items()
             if e.get('area_browse_alltrails')}
    START = '/* links-db area pages start — build_links.py */'
    END = '/* links-db area pages end — build_links.py */'
    block = (START + '\nObject.assign(AREA_BROWSE_ALLTRAILS, '
             + json.dumps(areas, ensure_ascii=False, sort_keys=True) + ');\n' + END)
    if START in h:
        i, j = h.index(START), h.index(END) + len(END)
        h = h[:i] + block + h[j:]
    else:
        anchor = 'const AREA_BROWSE_ALLTRAILS = {'
        close = h.index('};', h.index(anchor)) + 2
        h = h[:close] + '\n' + block + h[close:]
    if areas:
        log.append(f"  area browse pages: {len(areas)} ({', '.join(sorted(areas))})")

    h = h.replace(stops_raw, json.dumps(stops, ensure_ascii=False), 1)
    h = h.replace(ext_raw, json.dumps(ext, ensure_ascii=False, indent=1), 1)
    SRC.write_text(h)

    print(f"build_links: {len(db['stops'])} stops in the db")
    for line in log:
        print(line)


if __name__ == '__main__':
    main()
