# How the shot list gets built

Companion to `LINKS_STRATEGY.md`, same discipline applied to the 565 shots across
155 stops. Read with `shots_db.json` (the overrides) and `build_shots.py` (the
derivation) open.

---

## 1. What the shot list is for

Not a portfolio plan. It answers one question asked at 06:40 in the cold, in the
dark, at a campground: **is this worth getting up for, and where do I stand.**

Everything below serves that. A shot the list cannot place on a map, or cannot say
the time of day for, has failed at the only job it has.

---

## 2. Tags

Tags were the missing axis. The list already carried `difficulty` — roadside,
short walk, real hike, dawn commitment — which answers *how hard is it to get
there* and nothing else. It could not tell you when to set the alarm, what the
picture is of, or what would make it fail on the day.

Three families, coloured so the family reads before the word does:

| Family | Tags | Colour |
|---|---|---|
| **When** you must be standing there | `dawn` `sunrise` `golden` `sunset` | amber |
| | `blue hour` | cyan |
| | `night` `astro` | indigo |
| | `midday` | grey |
| **What** of | `wildlife` `water` `people` | green |
| | `aurora` | bright green |
| **What can kill it** on the day | `needs clear sky` `moon-dependent` `seasonal` | rust |
| | `truck` | purple |
| | `no dogs` | red |

Tags sit **above the fold**, not inside "full notes". A tag you have to expand a
panel to read is not scannable, which was the whole point.

### Derived, then overridden

`build_shots.py` derives tags by reading each shot's own `light`, `craft`,
`subject` and `vantage` prose against a list of literal phrases — "before
sunrise", "blue hour", "star trail", "lek", "high clearance". That tags 479 of 565
shots without hand-writing 565 entries.

`shots_db.json` is where a human disagrees:

- `tags` **replaces** the derived set
- `addTags` **appends** to it
- `links` are merged by URL

Every override carries a `why`. The overrides worth having are the ones a text
scan cannot reach — that `truck` on the Caprock bison shot is a *safety*
instruction because the herd is free-ranging on the road, or that `no dogs` on the
Estes Park shots is a park-wide ban that turns a five-night stop into a roadside-
only stop for photography with the animal aboard.

**Leg 1 (9 stops, 28 shots) is hand-reviewed.** Everything else is derived only,
and says so.

---

## 3. Coordinates are links, never text

Every shot carries `lat`/`lng` from the original research — 447 of 565 have them.
Those become:

- a **📍 map** pin on the shot row, opening Google Maps at the exact spot, with
  the bearing in the tooltip where the shot has one
- **clickable coordinates inside the vantage prose**, which quoted things like
  `between Headquarters (34.4048,-101.0296) and Honey Flat` as bare text. You
  cannot tap a number. 116 vantage notes had coordinates buried this way.

**118 shots have no coordinate and get no link.** That is deliberate and is the
same rule as everywhere else in this repo: a location is never guessed from a
place name. An absent pin is a research gap to fill, not a rendering bug to paper
over.

`linkify()` refuses to touch text that already contains a Maps link, so running
the build twice does not nest anchors.

---

## 4. Where extra links come from

Same hierarchy as `LINKS_STRATEGY.md` §2 — the managing authority first, and
verified before it is written down.

Good links to attach: the park's own page for the subject (TPWD's bison herd page
on the bison shot), the rule that constrains the shot (NPS pets policy on the RMNP
and Great Sand Dunes shots), a map PDF for a trail you have to find in the dark.

`build_phonecraft.py` already attaches live-conditions links — aurora forecasts,
fire and road status — for shots that depend on something nobody can predict months
ahead. Do not duplicate those here; the two scripts merge by URL.

---

## 5. Rules

- **Never invent a coordinate**, a URL, or a time. A wrong pin sends you down a
  dirt road in the dark.
- **Tags describe the shot, not the hope.** `seasonal` on the Great Sand Dunes
  crane shot is there because the migration is essentially over by early April and
  the stop arrives 30 March — that is a real risk of arriving to nothing.
- **A negative is worth a tag.** `no dogs`, `moon-dependent` on a full-moon stay:
  knowing a shot is off is as useful as knowing one is on, and stops a wasted
  pre-dawn alarm.
- **Idempotent.** md5 stable across three consecutive runs.
- `build_shots.py` runs after `build_phonecraft.py` in the loop, so it sees the
  links and iPhone notes that script adds.

---

## 6. Working order

1. Derive first — run the build and read what it produced.
2. Review the stop's shots against the stop's own facts: dog rules, seasonal
   windows, road access, the moon on those dates from the light box.
3. Override only what the derivation got wrong or could not see, with a `why`.
4. Attach authority links for the rules that constrain the shot.
5. Fill coordinate gaps where the vantage prose names a findable place.
