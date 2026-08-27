# Adding a new trip

The recipe for a self-contained trip with its own tab, the way Cloudcroft was
built. Read this with [`STOP_SPEC.md`](STOP_SPEC.md) — that one says what a
finished stop *contains*; this one says how a trip gets *made*.

In a new session, this is the whole briefing:

> Build a new trip for **&lt;place&gt;**, **&lt;dates&gt;**, **&lt;n&gt;** nights.
> Follow `tools/NEW_TRIP.md`.

---

## 0. What has to be asked before any research

Get these from LLuis. Guessing any of them wastes the whole pass:

- **Place, dates, nights** — and **whether the dates can move**. Cloudcroft's
  could not, which turned the card from a comparison into a timetable.
- **Campground**, or "find one". A site must take 40 ft; see STOP_SPEC.
- **The radius.** Default is **30 minutes from camp**. Anything further is not a
  choice and does not go on the card.
- **Anything he already rates.** Pumphouse Ridge only became the best carrier
  ride at Cloudcroft because he named it. Ask before researching, not after.

## 1. The two files a trip is

**`tools/<trip>_db.json`** — all the research, nothing rendered. Copy
`cloudcroft_db.json`'s shape: `stop, trails, dogs, cruise, offroad,
scenicDrives, highlights, hours, shots, campgrounds, light, tempF, events,
plan`, plus the stop's own unknowns and calls.

**`tools/build_<trip>.py`** — copy `build_cloudcroft.py`. It is the template and
it already solves the traps:

- The shaping is **Python, not JavaScript**, and is emitted as a plain
  `const <TRIP>_DATA`. `build_mobile.py` reads consts out of the built desktop
  file; anything computed at page-load time is invisible to it, and the trip
  ends up on the desktop and silently not on the phone.
- The stop is shaped as a **`STOPS` entry** so the dashboard's own
  `renderCards()` / `renderHighlights()` / `renderIssues()` draw it. Never write
  a second renderer — that is why the first Cloudcroft card looked nothing like
  an Alaska stop and why its shot list ended up in the wrong tab.
- Injection is by **marker comments, replaced whole**. Inside the card template
  use `<!-- HTML comments -->`: the template is one big JS template literal, so
  `/* … */` is not a comment there, it prints.
- Blocks are spliced **by offset**, not by anchoring on `</section>` — that
  string is every section in the file.

## 2. The hand-edits that are NOT generated

Page structure. A rebuild will not reproduce them:

1. `desktop/index.html` — the toggle button, `<button class="trip-toggle-btn"
   data-trip="<trip>">`
2. `desktop/index.html` — the `TRIP_MODES` entry (use a **getter** for
   `statsHTML`, or the temporal dead zone bites)
3. `desktop/index.html` — the `MODE_CLASS` map in `setTripMode`
4. `tools/build_mobile.py` — the `TRIPS` table, **or the trip has no phone
   build at all**
5. `tools/build_mobile.py` again — and this is NOT the same edit. The `TRIPS`
   table only names keys; something has to *put those keys into `DATA`*. Add a
   `grab('const <TRIP>_DATA =','{','}')` beside `CCDATA`, and the four `DATA`
   entries next to the `cc*` ones. Barcelona was first built with a correct
   `TRIPS` row pointing at keys nothing ever wrote — a phone build that loads
   and shows an empty trip, which is the exact failure item 4 exists to
   prevent, one level further down.
6. `desktop/index.html` — `poiNumberForActivity()`. It resolves a stop through
   `STOPS_BY_ID` and `EXT_DATA` only, so a trip whose stop lives in its own
   const scores **zero pin badges** however well its lists match its map.
   Cloudcroft had shipped that way (0 of 37) and nobody noticed; adding the arm
   took it to 6 of 37, and Barcelona to 32 of 36. Use `later(() =>
   <TRIP>_DATA.stop…)` — never a bare `typeof`, because the const is declared
   further down the file and `typeof` on it throws.

### Two things the shared renderer does that you must undo

**The Offroad / 4x4 box is drawn whether or not you filled it**, and when the
array is empty it still prints "Search for 4x4/off-road trails near here". On a
trip with no 4x4 that is not an unanswered question — the question does not
exist — and an empty box reads as *nobody checked*, which is the one thing a
card must never say. The gravel box beside it is already guarded by
`s.cruise && s.cruise.length`. **Do not simply guard the offroad one to match:**
eleven Alaska stops have an empty offroad box on purpose and that browse link is
the right research prompt for them. Strip it in your own trip's render block,
with a `MutationObserver` — the card body is built when the card is *expanded*,
not when it is rendered, so a one-shot strip runs before the box exists.

**`.subhead` uppercases.** It is a heading class. A blurb of more than a dozen
words put through it is a wall of capitals nobody reads. Short labels only.

## 3. Curate, then build

The card is a curated list, not an inventory. Filter to the radius, sort
nearest-first, and end each box with one line naming what was held back and why.
Held-back research stays in the db so nobody looks it up twice. A do-not-drive
vehicle-class entry is pinned regardless — it is a warning, not a choice.

```bash
cd tools
python3 build_<trip>.py && python3 build_mobile.py && python3 build_vendor.py
```

Then, before believing any of it:

- Run the three scripts **three times** and check `md5 -q ../desktop/index.html`
  is stable. A non-idempotent injection grows the file every run.
- `node tools/test_alaska_ext_v3.js` — must print `Page errors: 0`.
  (One pre-existing failure, `timeline rows are not all one line`, predates this
  work and is not yours.)
- **Open the page in a browser and look at it.** Every single defect that
  reached LLuis in this project — an empty tab, a leaked `/* comment */`, a wall
  of repeated text, a two-hour drive listed as local — passed the test suite.

## 4. The checks that answer questions

| | |
|---|---|
| `audit_coverage.py` | whether the right research EXISTS. `progress.py` cannot see a missing box: empty is 0 of 0, which renders as 100% |
| `open_items.py` | what is left to do |
| `build_calls.py --write` | regenerates `CALLS.md` in arrival order |

## 5. Publishing

Commit and push. `.github/workflows/rebuild.yml` runs the loop and the suite on
the runner and republishes; it commits nothing if the test fails. Confirm it
went green rather than assuming — `gh run list --limit 1`.
