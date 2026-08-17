# What a finished stop card contains

The definitive checklist for researching one stop. Written because a one-page
card was produced for Cloudcroft, NM that looked complete and was missing the
shot list, opening hours, per-route 4x4 listings and the entire gravel-cycling
answer — every one of those omitted from the **brief**, not fumbled by the
research. A brief that forgets a box produces a card that is silently short,
and nothing downstream catches it.

If you are researching a stop, work down this file. If you are writing a brief
for someone else to research a stop, paste the relevant sections into it.

---

## 0. The context that changes every answer

State all of it in any brief, every time:

- **2005 40 ft Class A motorhome towing a 4x4 pickup.** The coach never leaves
  the campground once parked. Every drive, every 4x4 route and every trailhead
  is reached in the **truck**.
- **A dog and a cat are aboard**, for 405 nights. The dog answer is not a
  nice-to-have; at a park that bans pets it decides whether a day exists.
- **The driver is 53.** Easy and moderate lead. A trail is not better for being
  harder.
- **The dates.** Every seasonal answer depends on them. If dates are not set,
  say so on the card and give each entry its own usable window.

---

## 1. Every box, and what each one must carry

A stop is not done until each of these is filled or carries a written finding
saying why it cannot be.

### `blurb` and `note`
One paragraph on what the stop IS, and one line on anything unusual about it.

### `alltrails` — the trails box
Roughly **one good walk per night, capped around six.** Per trail:

| Field | Rule |
|---|---|
| `distance` | From the authority where it publishes one; otherwise the listing |
| `time` | Estimated time — most authorities do not publish it, so mark `needs` |
| `difficulty` | The authority's own grade beats the app's |
| `elevation_gain` | |
| `reviews` | `"4.7 (1,204)"`. Star and count are ONE signal for ordering |
| `uses` | hike / bike / horse, **from the authority's trails table**, never inferred |
| `dogs` | true/false **only where an authority says so**. Absent otherwise |
| `cruise` | See §2 — this is the one most often wrongly answered "none" |
| `season` | The usable window, and what closes it |
| `url` | **Copied from a search result. Never constructed** |
| `needs[]` | Everything that could not be sourced, one line each |

### `offroad` — 4x4 routes
**Every route gets its own listing link where one exists** — Trails Offroad,
onX, a Forest Service road page, a BLM route page. A generic "scenic drives"
index page is not a route link. This was flagged as top priority on the main
trip and is the box most often left with a placeholder.

Get the **vehicle class** right. On many districts the only motorised-trail
class is *"open to vehicles 50 inches or less in width"*, which excludes a
full-size pickup entirely. A numbered Forest **road** takes the truck; a
T-numbered **trail** usually does not. Say which, and say where you read it.

`rig` is always `"truck"` — a standing decision, never researched per entry.

### `scenicDrives`
Paved and graded touring routes, `rig: "truck"`. Distance, season, and the
managing authority's own page.

### The gravel / bike-carrier answer
See §2. It is its own research question and does not fall out of the trails
pass.

### `activities` — highlights
Each needs a headline, a `detail`, **a `when`**, and real links.

**`when` is the opening-hours and timing field and it is not optional.** Days
of the week, seasonal opening, last admission, whether it is closed the month
you arrive. A museum that shuts for the month, a tour that runs Wednesday to
Sunday, a road that opens at 08:00 — that is the difference between a plan and
a wasted morning.

### `PHOTO` — the shot list
**Four to six shots per stop**, each with:

- `title` — the picture, named
- `subject` — what it actually is and why it is worth the walk
- `vantage` — where you stand, with coordinates where they can be sourced
- `light` — the hour and the direction, worked against the stop's own dates
- `craft` — focal length, aperture, the one thing that ruins the shot

A stop with no shot list is not finished. This was the most visible omission on
the Cloudcroft card.

### `LIGHT` — sun and dark
Sunrise, sunset and azimuths, both golden hours, day length, astronomical dark,
moon phase. Generated from lat/lng/date — see `build_light.py`; it is
calculated, not researched.

### `camp` / `campNotes` / `campResearch`
`campResearch` is `{verdict, paid_options, boondock_options, caveats}`.

**A site must take 40 ft.** The truck is towed and parks in overflow or
alongside, which most parks allow — only rule a site out when the published
limit is for the coach alone. Record the **published maximum length**, hookups
and amperage, season, the reservation route and a phone number.

**Never invent a length.** A wrong one strands a 40 ft coach on a road it
cannot turn around on. No published figure is recorded as unknown, and it
becomes a phone call.

### `nearbyTowns` and `poi`
Resupply, fuel, groceries, with drive time. `poi` carries lat/lng and a type so
it maps.

### `weather` / `tempF` / `tz`
A flag with a reason, average max and min for the dates, and the IANA zone.

### `dogsException`
Where the stop-level verdict has a named exception, it goes here so it renders
separately from the trail pills.

### Getting there
Grade, length of climb, tunnels and their **vertical clearance**, and whether a
gentler approach exists. A 13′6″ coach on a 6% grade through an unmeasured
tunnel is the single most consequential unknown a card can carry.

---

## 2. The gravel / bike-carrier question, in full

The dog rides in a **bike carrier**. The question is therefore not "is there
mountain biking here" — it is: **is there a firm, reasonably flat, bike-legal
surface I can ride with a dog on the back?**

Answering "nothing here is a cruise" is a real answer, but only after checking
all of these, because they are what the answer usually turns out to be:

- **Rail-trails and old railroad grades.** Constant gentle gradient by
  construction. Search the county, the state rail-trail body, and TrailLink.
- **Paved multi-use paths** — village, county, state park, resort.
- **Graded gravel forest roads** open to bicycles. Most Forest Service roads
  are, and they are usually the answer in national-forest country. The MVUM
  road list is where to look.
- **Canal, ditch, levee and irrigation roads.**
- **State park interior roads and campground loops.**
- **The state's own cycling map** — most DOTs publish one.

Record `cruise: true` with the surface and the length, or `cruise: false` with
a `cruise_reason` naming what rules it out — sand, rock, gradient, traffic, or
not bike-legal. "Not searched" is not the same as "none exists" and must never
be written as the latter.

---

## 3. Rules that override everything

1. **Never invent a URL, a coordinate, a length, a difficulty, a rating or a
   maximum RV length.** A figure that cannot be sourced is recorded absent. An
   absence gets phoned about; a wrong number gets acted on.
2. **A URL is COPIED from a result you read.** Roughly a third of AllTrails
   slugs are not derivable from the trail name.
3. **The authority beats the app.** Names, lengths, permitted uses and dog
   rules come from whoever manages the land. AllTrails' dog flag has
   contradicted the managing authority twice on this project.
4. **No prohibition is not permission.** If an authority publishes no dog rule,
   the field stays empty. "We did not check" and "dogs are welcome" must never
   look the same at a trailhead.
5. **Review counts drift between snapshots** — one trail returned 4,747, 4,655
   and 4,504 for the same page on the same day. Good enough to order trails,
   not good enough to quote.
6. **Every unsourced item becomes a phone call**, with the number, in
   `CALLS.md`.

---

## 4. Before calling a stop finished

- [ ] Trails: about one per night, easy and moderate leading
- [ ] Every trail has distance, time, difficulty, gain, reviews, uses
- [ ] Dog answer per trail, from an authority, or deliberately absent
- [ ] Gravel/bike-carrier question answered against §2's full list
- [ ] Offroad routes each carry their OWN listing link
- [ ] Vehicle class checked — is the truck actually allowed?
- [ ] Scenic drives, `rig: truck`
- [ ] Highlights each carry `when` — hours, days, seasonal opening
- [ ] Shot list: 4–6 shots, vantage and light worked against the dates
- [ ] Light box generated for the arrival date
- [ ] Camp: published max length, hookups, amps, season, phone
- [ ] Getting there: grade, tunnels, clearances
- [ ] Nearby towns, POI, weather flag, temps, timezone
- [ ] Seasonal conflicts flagged with `CLOSED FOR THIS STOP` where they bite
- [ ] Every gap listed, and every phone number in `CALLS.md`
- [ ] `audit_coverage.py` run and clean, or each finding recorded

A card with no gaps listed is usually a card that guessed.
