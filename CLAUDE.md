# Alaska Trip — what you need to know before changing anything

Read this first. It is the context that does not survive in code: what the trip is, what must
not break, and which mistakes have already been made here so they are not made twice.

## The trip

Austin, TX → Alaska → back, in a **2005 40 ft Class A motorhome towing a 4x4 pickup**, with a dog
and a cat aboard. LLuis is the driver and the only person who has to live with these decisions.

- **Main loop** — 99 stops, 405 nights. Departs **22 Mar 2027**, ends **30 Apr 2028**.
- **Complete East Extension** — 57 stops, continues from Pagosa Springs, Apr 2028 → Mar 2029.

Published to **https://lluisitu.github.io/alaska-trip/** (`/desktop/` and `/mobile/`). The README
still describes a Netlify deploy; that is stale — GitHub Pages serves it from `main`.

## The rule that breaks the most work

**`desktop/index.html` is the master, but the data inside it is GENERATED.**

`STOPS`, `EXT_DATA`, `BOOKINGS`, `ISSUES`, `LIGHT`, `PASSES`, `LEGINFO`, `COSTS`, `PETLOG`,
`RIGFIT`, `CAMPFACTS`, `KEPT_CAMPS`, `DRONE`, `FROZEN`, `ROUTE_GEOM` are all written by scripts in
`tools/`. Editing a const by hand looks like it worked and is silently overwritten by the next
build. Change the source instead — the relevant `tools/<name>_db.json` **plus** its build script.

Page structure, CSS and behaviour are different: those live in `desktop/index.html` directly. Two
conventions exist for patching them idempotently, and both work — `build_vendor.py` checks for a
single sentinel string before injecting, and `build_phonecraft.py` regexes the declaration and falls
back to a named anchor when it is absent. For injecting a block of CSS or JS, prefer explicit
start/end marker comments and replace between them; see the trap below for why.

`mobile/index.html` is regenerated from the desktop file by `build_mobile.py` on every publish. Never
hand-edit it. A hand-delivered phone build was overwritten once and shipped without a whole tab.

## Building and publishing

```bash
cd tools
python3 apply_overrides.py          # bakes road changes into real dates, then empties overrides.json
for p in 1 2; do for s in build_strategy build_frozen build_light build_phonecraft build_drone \
  build_passes build_legs build_costs build_petlog build_staynotes build_rigfit build_campfacts \
  build_swaps build_bookings build_parks build_askbox build_links build_shots; do python3 $s.py; done; done
python3 build_routes.py && python3 build_mobile.py && python3 build_vendor.py
cd .. && node tools/test_alaska_ext_v3.js     # must print "Page errors: 0"
```

**Twice is not paranoia.** Some steps read what earlier steps wrote — `build_bookings` rebuilds its
cards from stops `build_swaps` has just rewritten — so one pass leaves the file a step behind itself.
The property that matters is convergence, and the test asserts it.

`.github/workflows/rebuild.yml` runs all of this on GitHub. It fires on any push to `overrides.json`
or `tools/**`, and from the **Run workflow** button on the Actions tab. It commits nothing if the
test fails. The runner has real network, so it can fetch road geometry that a laptop behind a
filter cannot.

`./publish.sh` does the same thing locally and pushes. A token needs the **`workflow`** scope to push
anything under `.github/workflows/`, or the push is rejected and publish.sh misreports it as expired.

## How changes reach the site

Four routes in. Roughly in the order you will want them:

1. **The dashboard's Publish button** — a night more or less, a stop skipped, a different campground.
   Writes `overrides.json` through github.com's editor, entirely from a phone. Committing it fires
   `rebuild.yml`, which bakes the change into real dates and republishes in about a minute. The only
   route that needs no conversation with anyone.
2. **The dashboard's Ask Claude tab** — anything needing research or judgement: is this still the
   right campground, what happens if the tundra is late, find somewhere near Tok that takes the coach.
   It assembles a brief carrying everything already known about the stop, so the answer starts from
   the research rather than from a blank page. *Make the change* opens Claude Code on the repo and it
   can finish the job; *Talk it through* opens a conversation that changes nothing.
3. **The Code tab directly** — when you already know what needs doing and it is more than a night
   count. Claude Code clones, edits the db and the build script, runs the loop and the suite, and
   pushes; the workflow republishes.
4. **`./publish.sh`** — the fallback, not the normal route. It exists for when GitHub itself is
   unreachable, or when something has to be built and inspected before it goes anywhere. It needs the
   laptop, a working credential and network to the outside world, and it does by hand what the runner
   does for free.

**Cowork cannot push.** It has no write path to this repository at all, so it is for discussion,
planning and reading — whatever it concludes still has to travel by one of the four routes above.

**When a build goes wrong: Actions tab → "Put the dashboard back" → Run workflow, no arguments.**
Every rebuild that passes moves a `last-good` tag onto the commit that passed, so `last-good` always
means the most recent dashboard that actually worked. The restore returns `desktop/`, `mobile/`,
`tools/` and `overrides.json` to it and pushes. It deliberately does **not** rebuild — nothing new
can break while you are trying to get back to safety. `restore.yml`, written to be read in a panic.

## What must not break

The itinerary is not a list of places, it is a **sequence of dated windows**, most of which exist for
a reason that does not move. `FROZEN` carries these with their rationale; the test asserts them by
date. The hard ones:

| Stop | Window | Why it cannot move |
|---|---|---|
| Dawson City, YT | arrive 30 Aug 2027 | Dempster tundra peaks 25 Aug–5 Sep **and** the Top of the World border closes 15 Sep for good |
| Winthrop, WA | arrive 3 Oct 2027 | Alpine larch prime is 29 Sep–8 Oct; by 10–15 Oct it is already fading |
| Long Beach, WA | arrive 29 Oct 2027 | Razor-clam digs only happen on negative evening tides — this is the 27 Oct–1 Nov series |
| Sequoia, CA | arrive 23 Dec 2027 | Christmas Day has to fall inside the stay |
| Moab, UT | depart 8 Apr 2028 | Must be out before Easter Jeep Safari closes seven trails |
| Stowe, VT | arrive 1 Oct 2028 | Northern Vermont peaks late Sep–first week Oct; 7–9 Oct is the holiday weekend |
| Bar Harbor, ME | arrive 16 Oct 2028 | Maine Forest Service puts Zone 2 at 14–20 Oct |
| Asheville, NC | arrive 23 Dec 2028 | Christmas Day inside the stay |

Denali (late Jul, past mosquito peak) and Banff (Parks Canada booking window) are soft — they can
shift several days. A change that crosses a hard anchor should fail loudly, not be absorbed quietly.

## Research rules — these are not style preferences

- **Never invent a URL, a coordinate, or a maximum RV length.** A wrong length can strand a 40 ft
  coach on a road it cannot turn around on. If a figure cannot be sourced, record it as unknown —
  an absence gets phoned about, a wrong number gets acted on.
- **A site must take 40 ft.** The truck is towed and parks in overflow or on the side, which most
  parks allow. Only rule a site out when the limit is for the coach alone, not the combined length.
  `RIGFIT` distinguishes these; `combined-tight` means the limit really is for both.
- **Ratings come from Google or they are null.** Not Campendium, not Good Sam — different user pools.
  Google Maps is unreachable from the sandbox, so figures are mirrored via Wanderlog and spot-checked.
- **The site is public.** Never copy or embed third-party photographs; publishing them is republication.
- Prefer applying a fix to flagging it. Four campgrounds were shut on the arrival date and one could
  not be shown to exist; leaving that on a card and the itinerary still pointing at them is half an
  answer. `build_swaps.py` applies replacements and records the two deliberate non-swaps and why.

## Traps already hit here

- **Temporal dead zone.** `typeof` on a `const` declared later *throws*. Hit three times. Use the
  `later(fn, fallback)` helper and the `extStops()` / `allBookings()` / `allIssues()` accessors.
- **Patching HTML by shape.** A regex that matched a block's *shape* terminated at the first blank
  line after a closing brace, left half the old copy and appended a second. Delimit injected CSS/JS
  with explicit start/end marker comments and verify the md5 is stable across three runs.
- **Not every field in a card is generated.** The offroad and scenic-drive `tag` notes live *only*
  in `desktop/index.html` — no db holds them. `build_links.py` matched an entry by name and assigned
  over it, which deleted 95 of them silently; the cards still looked fine and read worse, and they
  had to be recovered from git history. It now merges field by field via `merge_keep()`. Before
  putting anything in a card, know whether a rebuild can reproduce it.
- **`indent=1`.** `build_parks.py` writes `EXT_DATA` with `indent=1`; any other script touching it
  must match or the two reformat each other forever.
- **Applying an override twice.** Would shift eighteen months of dates twice and look plausible.
  `apply_overrides.py` empties `overrides.json` after applying; the test proves a re-run is a no-op.
- **Stale scripts regressing data.** An out-of-date `build_light.py` ran and stripped the timezone
  from 155 stops and returned wrong sunset clock times. Before trusting a local tree, diff it against
  a fresh clone.

## Open, as of Aug 2026

- Camden, ME — campground undecided, four options researched.
- Three phone calls nobody has made: Salida RV Resort's 20-year rule (719-882-1569), Yosemite
  Westlake 40 ft (209-878-3847), Wrangell View 32 ft vs 70 ft conflict (907-823-2265).
- 26 stops still have no published length for the booked campground.
- ~~10 main-loop legs drawn as dashed straight lines~~ — fixed. `build_routes.py` ran on the runner
  and every leg now has road geometry; the suite reports main 98/98, east 57/57.
- `build_routes.py` in the repo lags the version that was verified green. `build_vendor.py` no longer
  does — it was rewritten and verified against the pins.

## Where the rest of the reasoning lives

Every `tools/build_*.py` opens with a docstring explaining *why* it exists — roughly 24,000
characters of rationale, and usually the fastest way to understand a decision.

The long-form narrative — seasonal audits, the re-pace analyses, the leg-by-leg research, the
Epic Pass and drone questions — lives in the **claude.ai Project "Alaska Trip"**, about 42 documents.
Those are *not* in this repository. If a decision here looks arbitrary, the reasoning is probably
there, and it is worth asking LLuis rather than guessing.

## Working with LLuis

He is planning a year on the road, not shipping software. Answer in terms of what it means for the
trip — which dates move, what has to be phoned, what breaks — and put the mechanics second. Say
plainly when something cannot be sourced or verified; a confident wrong answer about a campground
length is worse than no answer.
