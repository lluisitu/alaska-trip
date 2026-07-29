# Alaska Trip dashboards

Two static sites, both deployed from this repo by Netlify. Austin → Alaska → back in a 2005
40ft motorhome towing a 4x4 pickup, with a dog and cat aboard, plus the Northeast/Ozarks
extension that continues from Pagosa Springs.

## Layout

```
desktop/index.html   ← THE MASTER. All data lives here. Edit this.
mobile/index.html    ← GENERATED from desktop/index.html. Never hand-edit.
tools/build_mobile.py         regenerates mobile/index.html from desktop/index.html
tools/test_alaska_ext_v3.js   Playwright suite, runs against desktop/index.html
```

Both `booking-windows.ics` files are the same calendar of reservation-release dates, published
from each site so it's downloadable either way.

## Netlify wiring

Two sites, both linked to this repo, distinguished only by publish directory:

| Netlify project | Publish directory | Build command | Live |
|---|---|---|---|
| `alaskalluis` | `mobile` | *(none)* | https://alaskalluis.netlify.app |
| `alaskalluislaptop` | `desktop` | *(none)* | https://alaskalluislaptop.netlify.app |

No build command — the HTML is committed already built. Pushing to the default branch
redeploys both.

## Changing anything

```bash
# 1. edit desktop/index.html  (the data lives in the STOPS / EXT_DATA / ISSUES arrays)
# 2. regenerate the phone build
cd tools && python3 build_mobile.py
# 3. test
node test_alaska_ext_v3.js      # requires "Page errors: 0"
# 4. commit + push -> Netlify deploys both sites
```

Never edit `mobile/index.html` directly; step 2 overwrites it.

## Why it's built this way

- **One master file.** The mobile build is derived, so the two sites can't drift apart.
- **Phone build is not the desktop page shrunk.** It's a separate phone-first UI: bottom tab
  bar, 44px touch targets, sticky search, and an offline SVG route map that renders from stop
  coordinates when there's no signal — which matters on the Cassiar and the Alaska Highway.
- **Both files carry a `<noscript>` banner.** Everything renders via JavaScript, so file
  previews (Quick Look, Gmail, Drive) look blank. That's expected, not a bug.
- **Section styling is colour-coded by kind** and identical across desktop and mobile: camp
  green, itinerary amber, scenic drives purple, trails blue, holiday pink, rig warnings orange.
  Orange is deliberately reserved for anything that could damage the coach.
