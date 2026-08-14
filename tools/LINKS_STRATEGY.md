# How each box on a stop card gets built

The method for filling the link boxes — trails, biking, scenic drives, offroad,
activities, towns, points of interest. Written down because it is being applied
to 157 stops over many sessions, and a rule that lives only in one conversation
gets applied differently the second time.

Read this with `links_db.json` (the data) and `build_links.py` (the injector) open.

---

## 1. The one rule everything else serves

**Never invent a URL, a coordinate, a length, a difficulty or a rating.**

**A URL is COPIED from a search result. It is never built from a name.** AllTrails
slugs are unpredictable — `--2` and `--3` suffixes, reworded titles, loops indexed
under a different name than the one the page displays. A slug assembled from a
trail's title looks exactly like a real one right up until it 404s in front of
you, and by then you are at a trailhead with no signal.

This is written this bluntly because it already happened here: four URLs in
`links_db.json` were constructed from trail names. Three were right and one —
City of Rocks' South Fork Circle Creek loop — was not. Three-for-four is luck,
not verification, and the one that failed did so in front of the person planning
the trip. If a search does not return the URL, the trail gets no link.

If a figure cannot be sourced, it is recorded as absent. An absence gets phoned
about; a wrong number gets acted on. A wrong RV length strands a 40 ft coach on a
road it cannot turn around on, and a wrong trail difficulty puts a dog and a
53-year-old rig owner somewhere neither should be.

This means a box is allowed to be *shorter* than it could be. It is never allowed
to be padded with a plausible guess.

---

## 2. Source hierarchy

Always work down this list. Stop at the first tier that answers the question.

| Tier | What it is | Can it be verified from the sandbox? |
|---|---|---|
| `official` | The managing authority: state park, NPS, USFS, BLM, provincial park | **Yes.** Fetch it and confirm 200 with the expected content type |
| `indexed` | Returned by web search with a matching title and a review count | Partly — the title and counts are real, the page cannot be loaded |
| `community` | Komoot, TrailLink, FATMAP/Strava, local trail associations | Usually yes — most of these are fetchable |
| `unlisted` | The authority confirms it exists; no database has it | N/A — this is a recorded absence, not a failure |

**The authority is always right about names, lengths and permitted uses.** A
crowd-sourced route name never replaces the official one. When AllTrails lists a
longer user-assembled route that *contains* the official trail, both are shown and
the card says which is which.

### Known verification limits

- **alltrails.com answers 403 to everything from this sandbox** — curl, WebFetch,
  any user agent. A 403 is bot detection, not "page missing", so it proves nothing
  either way. AllTrails facts therefore come from search results (title, distance,
  gain, difficulty, rating, review count are all in the indexed snippet) and are
  tiered `indexed`, never `official`. Loading an actual AllTrails page needs a real
  browser — Claude in Chrome — and is worth doing only for trails a day is planned
  around.
- **Google Maps is unreachable.** Ratings for campgrounds come from Google or they
  are null; they are mirrored via Wanderlog and spot-checked. This rule is about
  *campgrounds*. Trail star ratings come from the trail database they belong to —
  AllTrails ratings are the native metric there and are already used this way in
  the east-extension data.
- **Komoot, TrailLink, FATMAP, TPWD, NPS, USFS all fetch fine.** Prefer them
  whenever they can answer the question.

#### A review count read through a summarising fetch is not reliable to the digit

`WebFetch` against `lite.duckduckgo.com` does not hand back the page; a small
model reads it and reports. Ask it the same question repeatedly and the digits
move. Fairyland Loop at Bryce was asked five times across two sessions and gave
**four different answers** — 12,734, 12,559, 12,728, and 12,740 twice. Whether
the summariser is inventing the tail digits or DuckDuckGo is serving different
cached crawls cannot be told from this side, and it does not matter: the figure
is not trustworthy to the digit either way.

This matters because §3 sorts on rating and count as one signal, so a wrong
count puts a trail in the wrong place in the box.

What to do:

* For a review count, read the result text **yourself** — drive duckduckgo.com
  in the browser pane and take the AllTrails title string as displayed. That is
  a copy, not a summary.
* Treat any count already in the db as approximate unless its entry says it was
  read directly. It is good enough to ORDER trails and not good enough to quote.
* Two trails sharing an exact count is worth checking and is NOT proof of a
  copy. Bisbee's Carr Peak and Coronado Cave genuinely both sit at 397, on
  distinct URLs with different star ratings, corroborated by the national
  memorial's own page. `audit_coverage.py dupstat` flags the coincidence; a
  person resolves it.

The two figures that WERE copied, found this way: Durango's Animas River Trail
had taken Kartchner's 1,063 (it is 1,079) and Horse Gulch had taken Bertha
Lake's 586 (it is 490).

#### The browser pane is shared. Assert what you are reading.

Two separate agents on this project found the browser tab navigated out from
under them mid-read by concurrent work. One caught it because it checked
`document.title` against the query it had issued before taking any figure; the
other worked around it entirely by doing a same-origin `fetch('/html/?q=…')`
from inside the DuckDuckGo page and parsing the response in one atomic call —
which is immune to another session moving the tab, and returns real result text
and real hrefs rather than a summary.

Prefer the atomic fetch. If you drive the pane directly, assert the page is
still yours before you read a number off it.

One more trap, from the same pass: an AllTrails listing for "Baker Mountain"
showed a review count of **2,454**, which is also the mountain's height in feet.
A number that appears twice on a page for two different reasons is exactly the
kind of thing a summariser conflates.

#### Batched API calls degrade silently. Control every batch.

Four separate incidents on this project, all the same shape: a call asking about
many items returns a result that *looks* complete and is wrong for everything
past the first item. Nothing errors. The failure is always a FALSE NEGATIVE,
which is the dangerous direction — it reads as "checked, nothing there".

1. `action=query&titles=A|B|C` — MediaWiki numbers every missing title `-1`,
   `-2`, `-3`… Testing only for `-1` scored every miss after the first as a real
   article. **Shipped 32 links to articles that do not exist.**
2. The identical bug, uncaught, in a second copy of that code. Fixing one did
   not fix the other, and the second one is what put the 32 links on the page.
   Grep for the pattern, do not fix the file you happen to be in.
3. `prop=extracts` with `exlimit` — forces `exintro` and returns EMPTY text for
   every page after the first. Reads exactly like "the article never mentions
   it"; briefly made 10 parent articles look like they documented nothing.
4. `prop=extracts` **drops bulleted lists entirely.** Algonquin's extract had
   zero hits for "Booth" while the wikitext carries `'''Booth's Rock''': 5.1 km`
   — the exact figure the entry needed.

So: when the question is *"does this article mention X"*, use `action=parse` or
an `insource:` search, never `prop=extracts`. And put a known-false item in
**every** batch, in the **last** position — that is where these bugs hide.
`wiki_batch.py` tests the `missing` key and rejects disambiguation pages; run
invented names like `Qqxzptl Museum of Nonexistence` through it and confirm
`NONE` before trusting a run.

---

## 3. The trails box

### What belongs in it

A **trail**. Not a trailhead, not a trail system, not a sentence.

Rejected, with real examples from the first pass:

| Rejected | Why | Where it goes |
|---|---|---|
| `Elkhart Park / Photographer's Point Trailhead` | A car park | Replaced by the routes that leave it |
| `Arkansas Hills trail system directly above Salida.` | A system, not a trail | Activities, as prose |
| `Alluvial Fan and Horseshoe Park.` | Two place names | Activities |
| `Red Canyon rim paths for the best effort-to-view ratio.` | Prose, and duplicates the trail listed above it | Dropped |
| `Sheep Creek Loop Scenic Byway` | A 12.9-mile drive | Scenic drives |
| `O'Brien Creek Road (4x4)` | A 4x4 route | Offroad |

### Required fields

Every trail shows **distance, estimated time, difficulty, reviews**. A trail
missing one of those is incomplete, not finished — mark what is missing in the db
with `needs` rather than leaving it silently blank.

Plus attributes:

- `uses` — `hike` / `bike` / `horse`, **from the authority, never inferred**. Many
  parks are multiuse by default; Texas Parks & Wildlife states "All trails are
  multiuse unless otherwise indicated", which makes all eleven Caprock trails
  bike-legal. Use is an attribute, not a section.
- `cruise` — see §4.
- `season` / `season_conflict` — set when the stop's own dates fall outside the
  trail's usable window. Do not delete a seasonally blocked trail; show it flagged,
  so the card says what is being missed and why.

### Selection and ordering

A park may have far more trails than belong on a card — Caprock Canyons has 13.
Pick and order by what this trip will actually walk:

1. **Easy and moderate are one band, not two.** Inside that band, **rating and
   count are one signal**, not two sorts — a shrunk average that pulls a
   thinly-reviewed score toward a 4.5 prior. 4.9 from 11 people does not beat 4.6
   from 3,000; a genuinely great trail with thousands of reviews keeps nearly all
   of its score. A listing with a count but no published star falls back to the
   prior and is separated by raw count. Entries with no review data at all sort
   after everything rated — not because they are worse, because we do not know.
2. **Hard and challenging fall below that band — unless the reviews are
   outstanding**, which keeps them on the card. Outstanding means 1,000+ reviews,
   or 4.7+ from at least 300. Atalaya Mountain is Hard with 3,612 reviews and
   stays; Upper South Prong is Challenging with 277 and drops to last.
3. **Unknown difficulty rides in the easy/moderate band.** Roughly half of all
   listings publish no grade, and burying a 1,300-review trail over a missing
   field lets the field decide instead of the trail.
4. **Then by fit** — dog-permitted, near camp, short enough for an afternoon.

A route that is out of scope in every season is listed only if the stop text names
it, with a note saying so plainly — the Cirque of the Towers is a 43.8-mile,
8,208 ft backpack and will never be walked on this trip.

Six to eight trails is a full card. More is noise.

### Heading link

The box heading carries a **park-level browse link** when a verified area page
exists — `AREA_BROWSE_ALLTRAILS[stopId]` in `desktop/index.html`. Without one the
heading falls back to the whole state, which for Caprock meant "Browse Texas
hikes". Always look for the park page; the slug is often not what you would guess
(`caprock-canyons-state-park-trailway`, not `caprock-canyons-state-park`).

### When there is no listing

Keep the trail with its official name and length, carry no trail link, and say
`no AllTrails listing — official source only`. Then **widen the search** before
accepting that: Komoot, TrailLink, local trail associations. Mesa Trail at Caprock
had no AllTrails page but does have a Komoot highlight, which supplied the surface
description that AllTrails never would have.

---

## 4. The biking view, and `cruise`

The target is **gravel cruising with the dog in a bike carrier** — not mountain
biking, not road riding.

`cruise: true` requires all of:

- bike-legal per the authority
- rail-grade, packed gravel, crushed limestone or paved
- no walk-your-bike sections
- no puncture-hazard reports (goatheads, thorns, glass)
- reviews that describe cruising, not technical riding

**Bike-legal is nowhere near sufficient**, and this is the rule that earns its
keep. The Caprock Canyons Trailway is 64 miles of former rail bed and the card
described it as "a flat, packed-gravel former rail bed". Riders describe a sand
and clay mix needing 700×35c minimum, 13 rocky miles from South Plains to Clarity
Tunnel, repeated goathead punctures, and a tunnel too sandy and guano-covered to
ride. `cruise: false`, and **the reason is carried on the card** — when the verdict
is no, the reason matters more than the verdict.

MTB-only singletrack stays in the trails box with a bike badge and is kept out of
the biking view. It is not deleted.

---

## 5. `dogs`

A stop-level field, wherever the authority publishes a rule. On a 405-night trip
with an animal aboard this decides whether a stop works at all, and it is not
derivable from anything else on the card.

The first pass found the extremes immediately:

- **Rocky Mountain NP** — "Pets are prohibited on ALL Rocky Mountain National Park
  trails, tundra, and meadows." Five nights booked; eight trails on the card; none
  walkable with the dog.
- **Great Sand Dunes** — dogs welcome on Mosca Pass and Dunes Overlook and the
  Medano Pass road, banned in the dunefield past the first high ridge.

Where the authority names some trails and is silent on others, record the silence
as `needs_check`. Do not generalise from "dogs allowed in the park".

---

### The failure mode this section did not protect against

Every rule above was followed and the whole column was still invisible. `dogs`
was researched for 85% of trails, stored on each item by `build_links.py`, and
**never rendered** — `trailPillsHtml()` drew difficulty, time, distance, rating,
uses and cruise, and no dog pill existed in any commit in the repo's history.
The research was correct, auditable, and unreadable.

Two rules follow, and they generalise past dogs:

* **A field is not done when it is in the db. It is done when it is on the
  card.** Before recording a field as researched, open the page and find it.
* **The phone build is a separate renderer, not a copy.** `build_mobile.py`
  builds its own trail rows from `name` and `tag` and draws no pills at all, so
  a desktop pill reaches nobody at a trailhead. The dog answer matters MORE
  there — read with no signal, standing at the sign — so it now carries a bare
  🐕/🚫 marker of its own.

Absence stays absent in both: an item with no researched rule renders nothing,
because "we did not check" must never look like "dogs are welcome".

## 6. The other boxes

Same hierarchy, same refusal to invent. Current state from the full audit:

| Box | Items | No direct URL | Prose, not an entity |
|---|---|---|---|
| campResearch options | 415 | **0** | – |
| scenicDrives | 256 | 43 | 142 |
| alltrails | 498 | 264 | 40 |
| offroad | 208 | 165 | 53 |
| activities | 1,105 | **1,105** | 216 |
| nearbyTowns | 406 | 406 | – |
| poi | 842 | 842 | – |

**`campResearch` is the model.** 415 campground options, every one with a
`source_url`. Bring the others up to it rather than inventing a new pattern.

### Activities

The largest and most visibly broken. `moreInfoLinks()` builds a Wikipedia and a
TripAdvisor search out of the activity's *headline*, which is a verb phrase, not an
entity. "Bike or walk the Caprock Canyons Trailway" searches Wikipedia for that
whole sentence and returns **List of cycleways** and **Amarillo, Texas** — the real
article, *Caprock Canyons State Park and Trailway*, is not in the results at all.

Fix: an `entity` field per activity, resolved against the real article index, with
the link **suppressed entirely when there is no entity**. "Dawn and dusk wildlife
watching from established roads and overlooks" gets no Wikipedia link, because
there is nothing at the other end. A missing link beats a wrong one.

### Scenic drives and offroad — `rig` is the field that matters

These two boxes share a problem the trails box does not have, and it is the most
consequential attribute on the whole card: **which vehicle**. A 40 ft Class A
coach and a towed 4x4 pickup are not interchangeable, and every entry in both
boxes is one or the other.

Right now that fact is buried inside the *name*:

> `High Road to Taos is best driven in the truck, not as a coach transfer.`
> `Loaded camper: graded, dry roads only.`
> `Cottonwood Pass is seasonal and should be assumed closed this early.`

The first is a drive whose name is "High Road to Taos" carrying rig advice. The
second is not a route at all — it is a standing constraint filed as a list item.
The third is a drive plus a seasonal warning.

**Settled, by the person driving: no scenic road is done in the RV.** Both boxes
are **truck-only**, full stop. That is a standing decision, not a per-entry
research question, and it means these boxes are day-trips from camp rather than
anything routed. Where a land manager publishes a harder restriction it is still
recorded — NPS states 4WD low-range is mandatory on Medano Pass Primitive Road and
trailers are prohibited — because "truck" and "low-range 4WD only" are different
days out. But nothing here is ever a coach transfer, and an entry does not need a
`rig` verdict researched to earn its place.

Where the coach *does* go is the leg and pass data, which is a separate system.

Every entry in both boxes therefore gets:

- `name` — the road or route. Nothing else.
- `note` — the advice that used to be in the name, including any published
  restriction beyond "truck".
- `season` / `season_conflict` — checked against the stop's actual dates. Tincup
  Pass carries "snowed in Apr/May, opens ~July" and the stop arrives 3 Apr;
  `seasonalTagConflict()` in `desktop/index.html` already flags this pattern when
  the text is in a tag, so keep the phrasing it can parse.

### Deduplicate, within and across boxes

Both boxes contain the same road more than once:

- Great Sand Dunes lists **Medano Pass Primitive Road twice inside `offroad`** —
  once linking Trails Offroad, once linking NPS. One entry, two links.
- Medano Pass is **also in `scenicDrives`**. It is a 22-mile deep-sand 4x4 route.
  It belongs in offroad only.
- Flaming Gorge listed **Sheep Creek Canyon Geological Loop** and **Sheep Creek
  Loop Scenic Byway** — the same loop off UT-44 under two names. `build_links.py`
  now folds a reclassified entry into a matching one via `same_as` instead of
  appending; an earlier run of this very pass created that duplicate.

Check the destination box before moving anything into it.

### Sourcing

**Offroad** is the worst-covered box at 79% unlinked globally, though leg 1 is far
better than that average — most entries already carry Trails Offroad URLs with
distance and a rating (`5.99 mi · 4.7 (32)`). Trails Offroad's own difficulty
scale is paywalled, so difficulty usually cannot be sourced there; the official
land manager (BLM, USFS, NPS) is both the better tier and the one that publishes
the vehicle restriction that actually matters. onX is paywalled likewise.

**Scenic drives** mostly have URLs already — the work here is splitting names from
prose, setting `rig`, and deduplicating. State tourism boards, DOT byway pages and
county sites all fetch fine and outrank a trail database for a road.

### Ordering

Same principle as trails:

1. Open on the stop's actual dates.
2. Then by the combined rating-and-count score, as for trails.
3. Seasonally blocked entries stay, flagged, at the bottom.

---

## 7. The pipeline

```
links_db.json      the research, per stop, with tier and match on every claim
      |
build_links.py     merges into STOPS / EXT_DATA in desktop/index.html
      |
desktop/index.html trailPillsHtml() renders difficulty/time/distance/rating
```

Rules the injector follows, each of which exists because it broke once:

- **Merge, never replace — at the LIST level and at the FIELD level.** The db
  carries only what was researched this pass. An early version assigned the trail
  list wholesale and deleted Santa Fe's five good trails and six of Estes Park's
  eight. The same bug then reappeared one level down: matching an entry by name
  and assigning `box[hit] = item` deleted every field the injector does not know
  about, which wiped 95 `tag` notes across the east extension's offroad boxes.
  Those tags carry trip-specific judgement — "the most realistic early-May 4x4
  day of the stop" — and they live ONLY in `desktop/index.html`. **No db holds
  them, so there was nothing to rebuild from; they came back out of git history.**
  `merge_keep(old, new, owned)` now replaces only the keys each box's builder
  owns and carries everything else across. Owned keys are still cleared when
  absent, because that is how a stale `label: "search AllTrails"` gets removed
  once a trail gains a real url.
- **Anything in a card that no db can regenerate is one careless assignment from
  gone.** Before adding a field to a box, decide which side of that line it is on.
- **Dedupe on append.** Appending unconditionally grew the file by one Trailway per
  run and the md5 never settled.
- **Idempotent.** `md5` must be identical across three consecutive runs.
- **`STOPS` compact, `EXT_DATA` with `indent=1`** — matching every other script.
  Two scripts disagreeing reformat the file back and forth forever.
- Stop ids in the db that do not exist in the data are a hard error, not a warning.

`build_links.py` is **not yet in the publish loop** in `CLAUDE.md`. Add it before
the first commit, or the next full rebuild will run without it.

---

## 8. Working order

1. Authority page first — names, lengths, permitted uses, dog policy. Verify 200.
2. Match each official trail to its closest listing. Record `exact` / `contains` /
   `none`.
3. Read reviews for surface and suitability. Set `cruise` with its reason.
4. Widen to Komoot / TrailLink for anything still unlisted.
5. Reclassify drives and 4x4 routes out; drop prose and trailheads.
6. Order easy/moderate and well-reviewed first; cap at six to eight.
7. Set the park-level heading link.
8. Report the leg before committing.
