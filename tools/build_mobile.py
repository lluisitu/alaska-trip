import json, re, pathlib

# ---------------------------------------------------------------------------
# The phone build has to work with no signal — that is most of the point of it.
# Leaflet is inlined into the desktop file by build_vendor.py; lift those blocks
# across rather than pointing the phone at a CDN it will not be able to reach on
# the Dempster.
LEAFLET_MARK = '/* leaflet inlined by build_vendor.py */'


def inlined_leaflet(desktop_html):
    """Return (css_block, js_block) from the desktop build, or (None, None)."""
    out = []
    for tag in ('style', 'script'):
        m = re.search(r'<%s>%s.*?</%s>' % (tag, re.escape(LEAFLET_MARK), tag),
                      desktop_html, re.S)
        out.append(m.group(0) if m else None)
    return out[0], out[1]

# Repo-relative: desktop/index.html is the MASTER; mobile/index.html is generated from it.
_ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = _ROOT/'desktop'/'index.html'
OUT = _ROOT/'mobile'/'index.html'
h=open(SRC).read()

def ex(h,decl,o,c):
    i=h.index(decl); s=h.index(o,i); d=0; ins=False; esc=False
    for j in range(s,len(h)):
        ch=h[j]
        if ins:
            if esc: esc=False
            elif ch=='\\': esc=True
            elif ch=='"': ins=False
        else:
            if ch=='"': ins=True
            elif ch==o: d+=1
            elif ch==c:
                d-=1
                if d==0: return h[s:j+1]
    raise ValueError(decl)

def grab(decl,o,c):
    try: return json.loads(ex(h,decl,o,c))
    except Exception as e: print("  (skip",decl,e,")"); return None

STOPS   = grab('const STOPS =','[',']')
EXT     = grab('const EXT_DATA =','{','}')
ISSUES  = grab('const ISSUES =','[',']')
EXTISS  = grab('const EXT_ISSUES =','[',']')
# The phone build is the one that goes offline, and the Cassiar and the Alcan
# are exactly where a pass restriction or a 450-mile dead zone matters most —
# so the road data and the off-grid reference ride along.
PASSES  = grab('const PASSES =','{','}')
LEGINFO = grab('const LEGINFO =','{','}')
PETLOG  = grab('const PETLOG =','{','}')
def kv(decl):
    # LEG_NAMES uses JS literal syntax (unquoted keys), so JSON.parse fails — regex it.
    try:
        raw = ex(h,decl,'{','}')
        return dict(re.findall(r"([\w-]+)\s*:\s*'((?:[^'\\]|\\.)*)'", raw)) or \
               dict(re.findall(r'([\w-]+)\s*:\s*"((?:[^"\\]|\\.)*)"', raw))
    except Exception as e:
        print("  (kv skip",decl,e,")"); return {}
# The Cloudcroft trip is shaped once, in build_cloudcroft.py, and emitted as a
# plain const so this build can read it. It used to be assembled in JavaScript
# at page-load time, which is invisible from here — the tab existed on the
# desktop and simply was not on the phone.
CCDATA  = grab('const CC_DATA =','{','}') or {}
# Same story for Barcelona: shaped once in build_barcelona.py and emitted as a
# plain const so this build can see it.
BCNDATA = grab('const BCN_DATA =','{','}') or {}
RGEOM       = grab('const ROUTE_GEOM =','{','}')
EXTRGEOM    = grab('const EXT_ROUTE_GEOM =','{','}')
LEGALERT    = grab('const LEG_ALERTS =','{','}')
EXTLEGALERT = grab('const EXT_LEG_ALERTS =','{','}')
LEGN    = kv('const LEG_NAMES =')
EXTLEGN = kv('const EXT_LEG_NAMES =')

def colors(decl):
    try:
        raw = ex(h,decl,'{','}')
        return dict(re.findall(r"(\w[\w-]*)\s*:\s*['\"]([^'\"]+)['\"]", raw))
    except Exception: return {}
LEGC    = colors('const LEG_COLORS =')
EXTLEGC = colors('const EXT_LEG_COLORS =')

DATA = {
 'stops': STOPS, 'ext': (EXT or {}).get('STOPS', []),
 'issues': ISSUES or [], 'extIssues': EXTISS or [],
 'legNames': LEGN or {}, 'extLegNames': EXTLEGN or {},
 'legColors': LEGC, 'extLegColors': EXTLEGC,
 'legAlerts': LEGALERT or {}, 'extLegAlerts': EXTLEGALERT or {},
 'routeGeom': RGEOM or {}, 'extRouteGeom': EXTRGEOM or {},
 'passes': (PASSES or {}).get('legs', {}), 'legInfo': (LEGINFO or {}).get('legs', {}),
 'petlog': PETLOG or {},
 'cc': [CCDATA['stop']] if CCDATA.get('stop') else [],
 'ccIssues': CCDATA.get('issues') or [],
 'ccLegNames': {'cloudcroft': CCDATA.get('legName', 'Cloudcroft, NM')},
 'ccLegColors': {'cloudcroft': CCDATA.get('legColor', '#7ec488')},
 'bcn': [BCNDATA['stop']] if BCNDATA.get('stop') else [],
 'bcnIssues': BCNDATA.get('issues') or [],
 'bcnLegNames': {'barcelona': BCNDATA.get('legName', 'Barcelona & Catalonia')},
 'bcnLegColors': {'barcelona': BCNDATA.get('legColor', '#d98a3c')},
}
print(f"stops={len(DATA['stops'])} ext={len(DATA['ext'])} issues={len(DATA['issues'])} extIssues={len(DATA['extIssues'])}")
print(f"legColors={len(LEGC)} extLegColors={len(EXTLEGC)}")
print(f"legAlerts={len(LEGALERT or {})} extLegAlerts={len(EXTLEGALERT or {})}")
print(f"routeGeom={len(RGEOM or {})} extRouteGeom={len(EXTRGEOM or {})} routed legs")
print(f"passes={len(DATA['passes'])} legs with pass data \u00b7 legInfo={len(DATA['legInfo'])} driving days")
print(f"petlog: {len(DATA['petlog'].get('cell_gaps',[]))} cell gaps, {len(DATA['petlog'].get('supplies',[]))} supply notes")
print(f"cloudcroft: {len(DATA['cc'])} stop, {len(DATA['ccIssues'])} gaps")
print(f"barcelona: {len(DATA['bcn'])} stop, {len(DATA['bcnIssues'])} gaps")

BLOB = json.dumps(DATA, ensure_ascii=False, separators=(',',':'))

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover, maximum-scale=5">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Alaska Trip">
<meta name="theme-color" content="#0f1216">
<title>Alaska Trip — Mobile</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css">
<style>
:root{
  --bg:#0f1216; --panel:#171b21; --panel2:#1e232b; --border:#2a3038;
  --text:#e8ebef; --muted:#9aa4b2; --accent:#e8b04b; --accent2:#5fb4d6;
  --safe-t:env(safe-area-inset-top,0px); --safe-b:env(safe-area-inset-bottom,0px);
  --nav-h:56px;
}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent;}
html{-webkit-text-size-adjust:100%;}
body{margin:0;background:var(--bg);color:var(--text);
  font:16px/1.5 -apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",Roboto,sans-serif;
  overscroll-behavior-y:none;padding-bottom:calc(var(--nav-h) + var(--safe-b));}
a{color:var(--accent2);}
/* ---------- header ---------- */
header{position:sticky;top:0;z-index:60;background:rgba(15,18,22,.94);
  -webkit-backdrop-filter:saturate(180%) blur(14px);backdrop-filter:saturate(180%) blur(14px);
  border-bottom:1px solid var(--border);padding:calc(var(--safe-t) + 8px) 12px 8px;}
.h-title{font-size:1.02rem;font-weight:700;margin:0 0 7px;letter-spacing:-.01em;}
.h-sub{font-size:.72rem;color:var(--muted);margin:0 0 8px;}
.seg{display:flex;background:var(--panel2);border-radius:9px;padding:3px;gap:3px;margin-bottom:8px;}
.seg button{flex:1;min-height:44px;border:none;border-radius:7px;background:none;color:var(--muted);
  font-size:.8rem;font-weight:600;font-family:inherit;cursor:pointer;}
.seg button.active{background:var(--accent);color:#161a1f;}
.searchrow{display:flex;align-items:center;gap:7px;background:var(--panel2);
  border:1px solid var(--border);border-radius:9px;padding:7px 11px;}
.searchrow input{flex:1;background:none;border:none;outline:none;color:var(--text);
  font-size:16px;font-family:inherit;min-width:0;}
.searchrow input::placeholder{color:var(--muted);}
.searchrow input::-webkit-search-cancel-button{display:none;}
#mClear{background:none;border:none;color:var(--muted);font-size:1.3rem;padding:0 3px;display:none;}
/* ---------- stats ---------- */
.stats{display:flex;gap:7px;overflow-x:auto;padding:11px 12px 3px;-webkit-overflow-scrolling:touch;
  scrollbar-width:none;}
.stats::-webkit-scrollbar{display:none;}
.stat{flex:0 0 auto;background:var(--panel);border:1px solid var(--border);border-radius:10px;
  padding:9px 13px;min-width:88px;}
.stat .n{font-size:1.12rem;font-weight:700;}
.stat .l{font-size:.63rem;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;}
/* ---------- views ---------- */
main{padding:0 12px 20px;}
.view{display:none;}
.view.active{display:block;}
.sechead{font-size:.68rem;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);
  font-weight:700;margin:16px 2px 8px;}
/* ---------- per-leg alerts ---------- */
/* The desktop's single "read this first" box was split so each warning sits on
   the stage it applies to. Orange stays reserved for coach-damage risks. */
.legalerts{margin:10px 2px;display:none;flex-direction:column;gap:7px;}
.legalerts.open{display:flex;}
.legalert{display:flex;gap:8px;align-items:flex-start;font-size:.79rem;line-height:1.45;
  padding:9px 11px;border-radius:8px;background:rgba(232,176,75,.10);color:#e6cf9a;
  border-left:2px solid rgba(232,176,75,.55);}
.legalert .la-ic{flex:0 0 auto;}
.legalert.la-rig{background:rgba(217,119,87,.13);color:#e8b49a;border-left-color:rgba(217,119,87,.7);}
.legalert.la-book{background:rgba(95,180,214,.12);color:#a8d4e8;border-left-color:rgba(95,180,214,.6);}
.legalert b{color:#fff;font-weight:700;}
.leglabel{font-size:.68rem;text-transform:uppercase;letter-spacing:.07em;font-weight:800;
  margin:18px 2px 0;display:flex;align-items:center;gap:7px;min-height:34px;}
.leglabel.tap{cursor:pointer;}
.leglabel .lcount{margin-left:auto;font-weight:700;font-size:.64rem;opacity:.75;
  display:flex;align-items:center;gap:5px;}
.leglabel .lcar{transition:transform .15s;display:inline-block;}
.leglabel.open .lcar{transform:rotate(90deg);}
.leglabel .ldot{width:9px;height:9px;border-radius:50%;flex:0 0 auto;}
/* ---------- cards ---------- */
.card{background:var(--panel);border:1px solid var(--border);border-radius:12px;margin-bottom:9px;overflow:hidden;}
.chead{display:flex;align-items:flex-start;gap:9px;padding:13px;cursor:pointer;min-height:56px;}
.dot{width:9px;height:9px;border-radius:50%;flex:none;margin-top:5px;}
.cbody-t{flex:1;min-width:0;}
.cname{font-size:.94rem;font-weight:700;line-height:1.3;}
.cmeta{font-size:.74rem;color:var(--muted);margin-top:3px;}
.chev{color:var(--muted);font-size:1.25rem;transition:transform .2s;flex:none;align-self:center;}
.card.open .chev{transform:rotate(90deg);}
.cbody{display:none;padding:0 13px 14px;border-top:1px solid var(--border);}
.card.open .cbody{display:block;}
.blurb{font-size:.86rem;color:#cfd6de;margin:12px 0;line-height:1.55;}
.note{font-size:.82rem;background:rgba(232,176,75,.09);border-left:3px solid var(--accent);
  padding:9px 11px;border-radius:0 7px 7px 0;margin:10px 0;color:#d8dee6;}
/* Option C — every section is its own box with a tinted, icon-led header strip,
   colour-coded by kind so you can find "camping notes" without reading. */
.sec{margin-top:13px;border:1px solid var(--border);border-radius:11px;overflow:hidden;}
.sec-t{font-size:.66rem;text-transform:uppercase;letter-spacing:.07em;font-weight:800;
  padding:9px 12px;display:flex;align-items:center;gap:7px;
  background:rgba(154,164,178,.13);color:var(--muted);}
.sec-t .ic{font-size:.86rem;line-height:1;}
.sec-b{padding:11px 12px;background:var(--panel2);}
.sec ul{list-style:none;margin:0;padding:0;}
.sec li{padding:7px 0;border-bottom:1px solid rgba(255,255,255,.06);font-size:.84rem;}
.sec li:last-child{border-bottom:none;padding-bottom:0;}
.sec li:first-child{padding-top:0;}
.sec.camp   .sec-t{background:rgba(126,196,136,.14);color:#7ec488;}
.sec.itin   .sec-t{background:rgba(232,176,75,.14);color:#e8b04b;}
.sec.drive  .sec-t{background:rgba(180,142,232,.14);color:#b48ee8;}
.sec.trail  .sec-t{background:rgba(95,180,214,.14);color:#5fb4d6;}
.sec.off    .sec-t{background:rgba(217,119,87,.14);color:#e0906d;}
.sec.cruise .sec-t{background:rgba(126,196,136,.14);color:#7ec488;}
/* Esri Dark Gray Base is lighter than the CARTO layer it replaces; dim it
   to sit on the dark phone build the same way. */
.leaflet-tile{filter:brightness(.6) contrast(1.06);}
.sec.holiday .sec-t{background:rgba(201,80,107,.15);color:#f0a8b6;}
.sec.warn   .sec-t{background:rgba(217,119,87,.16);color:#e0906d;}
.sec.audit  .sec-t{background:rgba(95,180,214,.12);color:#8ecbe6;}
.sec.verdict .sec-t{background:rgba(126,196,136,.11);color:#9ed4a8;}
.iname{font-weight:600;}
.idet{font-size:.79rem;color:var(--muted);margin-top:3px;line-height:1.5;}
.dogok{color:#7ec488;} .dogno{color:#e0384d;}
/* Road ahead + off-grid. Both exist on the phone precisely because the phone
   is what you have when there is no signal to look anything up. */
.dchip{display:inline-block;font-size:.68rem;font-weight:700;padding:0 6px;border-radius:99px;
  background:rgba(95,180,214,.16);color:#5fb4d6;}
.dchip.mid{background:rgba(232,176,75,.18);color:#e8b04b;}
.dchip.far{background:rgba(217,119,87,.22);color:#d97757;}
.pass{border-top:1px solid var(--border);padding:7px 0;}
.pass:first-child{border-top:none;}
.sev{font-size:.62rem;text-transform:uppercase;letter-spacing:.04em;font-weight:800;
  padding:1px 6px;border-radius:99px;vertical-align:middle;}
.sev.easy{background:rgba(126,196,136,.18);color:#7ec488;}
.sev.moderate{background:rgba(232,176,75,.18);color:#e8b04b;}
.sev.hard{background:rgba(217,119,87,.20);color:#d97757;}
.sev.severe{background:rgba(201,80,107,.24);color:#e2718c;}
.pfig{font-size:.72rem;color:var(--muted);margin-top:2px;}
.prest{font-size:.79rem;line-height:1.5;margin-top:3px;color:#e2718c;font-weight:600;}
.chip{display:inline-block;font-size:.66rem;padding:2px 8px;border-radius:20px;margin-left:5px;
  vertical-align:1px;white-space:nowrap;}
.chip.green{background:rgba(126,196,136,.16);color:#7ec488;}
.chip.yellow{background:rgba(232,176,75,.16);color:#e8b04b;}
.chip.red{background:rgba(201,80,107,.18);color:#e5849a;}
.camp{background:var(--panel2);border-radius:9px;padding:10px 12px;font-size:.84rem;margin-top:6px;}
.holiday{background:linear-gradient(180deg,rgba(201,80,107,.10),rgba(126,196,136,.05));
  border:1px solid rgba(201,80,107,.30);border-radius:10px;padding:11px 12px;margin-top:14px;}
.holiday-t{font-size:.68rem;text-transform:uppercase;letter-spacing:.05em;color:#f0a8b6;
  font-weight:700;margin-bottom:7px;}
.audit{background:rgba(95,180,214,.07);border:1px solid rgba(95,180,214,.24);
  border-radius:9px;padding:10px 12px;margin-top:12px;font-size:.79rem;color:#c3cdd8;line-height:1.55;}
.audit b{color:var(--accent2);}
/* ---------- map ---------- */
#mapWrap{height:58vh;min-height:320px;border-radius:12px;overflow:hidden;border:1px solid var(--border);
  margin-top:10px;}
#mMap{height:100%;width:100%;background:#000;}
#mapFallback{display:none;height:100%;width:100%;background:#0b0e12;}
#mapFallback svg{width:100%;height:100%;display:block;}
#mapWrap.offline #mMap{display:none;}
#mapWrap.offline #mapFallback{display:block;}
#mapNote{font-size:.75rem;color:var(--muted);margin:9px 2px;line-height:1.5;}
#mapNote.warn{background:rgba(232,176,75,.1);border:1px solid rgba(232,176,75,.3);
  border-radius:9px;padding:10px 12px;color:#e2c98d;}
#mapLegend{display:flex;flex-wrap:wrap;gap:9px;margin:10px 2px 0;}
#mapLegend span{font-size:.68rem;color:var(--muted);display:flex;align-items:center;gap:5px;}
#mapLegend i{width:9px;height:9px;border-radius:50%;display:inline-block;}
.leaflet-tile-pane{filter:brightness(1.9) contrast(1.15) saturate(1.05);}
.leaflet-popup-content-wrapper{background:var(--panel2);color:var(--text);border-radius:10px;}
.leaflet-popup-tip{background:var(--panel2);}
.leaflet-popup-content{font-size:.85rem;}
.leaflet-popup-content a{color:var(--accent2);}
/* ---------- issues ---------- */
.iss{background:var(--panel);border:1px solid var(--border);border-left-width:4px;
  border-radius:10px;padding:12px 13px;margin-bottom:9px;}
.iss.orange{border-left-color:var(--accent);}
.iss.red{border-left-color:#c9506b;}
.iss.green{border-left-color:#7ec488;}
.iss-s{font-size:.68rem;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;}
.iss-t{font-weight:700;font-size:.9rem;margin:5px 0 7px;line-height:1.35;}
.iss-b{font-size:.82rem;color:#c8d0d9;line-height:1.55;}
.iss-sol{background:rgba(126,196,136,.08);border:1px solid rgba(126,196,136,.22);
  border-radius:8px;padding:9px 11px;margin-top:9px;font-size:.81rem;color:#cfd8e0;line-height:1.55;}
/* ---------- search results ---------- */
.sr{background:var(--panel);border:1px solid var(--border);border-radius:11px;padding:11px 13px;
  margin-bottom:8px;cursor:pointer;}
.sr-n{font-weight:700;font-size:.89rem;}
.sr-m{font-size:.72rem;color:var(--muted);margin-top:3px;}
.sr-w{font-size:.76rem;color:var(--muted);margin-top:5px;line-height:1.45;}
.sr mark{background:rgba(232,176,75,.3);color:var(--text);border-radius:3px;padding:0 2px;}
.trip-tag{display:inline-block;font-size:.6rem;font-weight:700;text-transform:uppercase;
  padding:2px 6px;border-radius:20px;margin-right:6px;vertical-align:1px;}
.trip-tag.bigloop{background:rgba(232,176,75,.16);color:#e8b04b;}
.trip-tag.ext{background:rgba(180,142,232,.16);color:#b48ee8;}
.trip-tag.cloudcroft{background:rgba(126,196,136,.16);color:#7ec488;}
.empty{padding:26px 14px;text-align:center;color:var(--muted);font-size:.86rem;line-height:1.6;}
/* ---------- bottom nav ---------- */
nav.tabbar{position:fixed;left:0;right:0;bottom:0;z-index:70;display:flex;
  background:rgba(15,18,22,.96);-webkit-backdrop-filter:blur(14px);backdrop-filter:blur(14px);
  border-top:1px solid var(--border);padding-bottom:var(--safe-b);}
nav.tabbar button{flex:1;border:none;background:none;color:var(--muted);font-family:inherit;
  padding:7px 0 5px;min-height:max(44px,var(--nav-h));display:flex;flex-direction:column;align-items:center;
  justify-content:center;gap:3px;font-size:.62rem;font-weight:600;cursor:pointer;}
nav.tabbar button.active{color:var(--accent);}
nav.tabbar svg{width:21px;height:21px;}
.backtop{position:fixed;right:14px;bottom:calc(var(--nav-h) + var(--safe-b) + 14px);z-index:65;
  width:42px;height:42px;border-radius:50%;background:var(--panel2);border:1px solid var(--border);
  color:var(--text);font-size:1.1rem;display:none;align-items:center;justify-content:center;}
.backtop.show{display:flex;}
</style>
</head>
<body>
<noscript><div style="background:#7a2d2d;color:#fff;padding:20px;font-size:15px;">
This trip dashboard builds itself with JavaScript, so file previews show a blank page.
Open it in Safari or Chrome on your phone and it will load normally.</div></noscript>

<header>
  <div class="h-title" id="hTitle">Austin → Alaska Big Loop</div>
  <div class="h-sub" id="hSub"></div>
  <div class="seg" id="tripSeg">
    <button data-trip="bigloop" class="active">Alaska Loop</button>
    <button data-trip="ext">East Trip</button>
    <button data-trip="cloudcroft">Cloudcroft</button>
  </div>
  <div class="searchrow">
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#9aa4b2" stroke-width="2.4"
      stroke-linecap="round"><circle cx="11" cy="11" r="7"></circle><path d="M20 20l-3.5-3.5"></path></svg>
    <input type="search" id="mSearch" placeholder="Search a town, park, trail…" autocomplete="off" spellcheck="false">
    <button id="mClear" aria-label="Clear">&times;</button>
  </div>
</header>

<div class="stats" id="mStats"></div>

<main>
  <section class="view active" id="v-stops"><div id="stopsWrap"></div></section>
  <section class="view" id="v-map">
    <div id="mapWrap"><div id="mMap"></div><div id="mapFallback"></div></div>
    <div id="mapNote"></div>
    <div id="mapLegend"></div>
  </section>
  <section class="view" id="v-issues"><div id="issuesWrap"></div></section>
  <section class="view" id="v-offgrid"><div id="offgridWrap"></div></section>
  <section class="view" id="v-search"><div id="srWrap"><div class="empty">Type at least two letters to search every stop, campground, trail and scenic drive across every trip.</div></div></section>
</main>

<button class="backtop" id="backTop" aria-label="Back to top">↑</button>

<nav class="tabbar" id="tabbar">
  <button data-view="stops" class="active">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 6h16M4 12h16M4 18h16"/></svg>Stops</button>
  <button data-view="map">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 21s7-6.5 7-11a7 7 0 1 0-14 0c0 4.5 7 11 7 11z"/><circle cx="12" cy="10" r="2.5"/></svg>Map</button>
  <button data-view="issues">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 9v5M12 17.5v.5"/><path d="M10.3 3.9 2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/></svg>Issues</button>
  <button data-view="offgrid">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M2 8.8a16 16 0 0 1 20 0"/><path d="M5 12.3a11 11 0 0 1 14 0"/><path d="M8.5 15.8a6 6 0 0 1 7 0"/><path d="M12 19.5v.01"/><path d="M3 3l18 18"/></svg>Off-grid</button>
  <button data-view="search">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>Search</button>
</nav>

<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<script>
const D = __DATA__;
let trip = 'bigloop';
const esc = s => String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
/* Three trips now, so these are lookups rather than either/or. A third arm on
   each ternary is how one of them quietly keeps returning the Alaska data. */
const TRIPS = {
  bigloop:    {stops:'stops', names:'legNames',   colors:'legColors',
               issues:'issues',    alerts:'legAlerts',    geom:'routeGeom',
               title:'Austin \u2192 Alaska Big Loop',
               sub:'40ft coach + towed 4x4 \u00b7 dog & cat \u00b7 departs Mar 22, 2027'},
  ext:        {stops:'ext',   names:'extLegNames', colors:'extLegColors',
               issues:'extIssues', alerts:'extLegAlerts', geom:'extRouteGeom',
               title:'Northeast & Ozarks Extension',
               sub:'40ft coach + towed 4x4 \u00b7 dog & cat \u00b7 departs Apr 30, 2028'},
  cloudcroft: {stops:'cc',    names:'ccLegNames',  colors:'ccLegColors',
               issues:'ccIssues',  alerts:null,           geom:null,
               title:'Cloudcroft, NM',
               sub:'40ft coach + towed 4x4 \u00b7 dog & cat \u00b7 Aug 22\u201329 \u00b7 dates fixed'},

  // 4th of the four hand-edits NEW_TRIP.md lists. Without this entry the trip
  // has no phone build at all — it exists on the desktop and silently not on
  // the phone, which this repo has already shipped once.
  barcelona:  {stops:'bcn',   names:'bcnLegNames', colors:'bcnLegColors',
               issues:'bcnIssues', alerts:null,           geom:null,
               title:'Barcelona & Catalonia',
               sub:'rental car \u00b7 no rig, no pets \u00b7 Sep 26 \u2013 Oct 11, 2026'},
};
const T = () => TRIPS[trip] || TRIPS.bigloop;
const pick = k => { const n = T()[k]; return n ? (D[n] || {}) : {}; };
const stops = () => D[T().stops] || [];
const legNames = () => pick('names');
const legColors = () => pick('colors');
const issues = () => D[T().issues] || [];

const MON=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
function fmt(d){ if(!d) return ''; const p=String(d).split('-');
  if(p.length<3) return d; return MON[+p[1]-1]+' '+(+p[2]); }
function chip(w){ if(!w||!w.flag) return '';
  return '<span class="chip '+w.flag+'">'+(w.flag==='green'?'On track':w.flag==='yellow'?'Check season':'Conflict')+'</span>'; }

function sec(kind, icon, title, inner){
  if(!inner) return '';
  return '<div class="sec '+kind+'"><div class="sec-t"><span class="ic">'+icon+'</span>'+title+
         '</div><div class="sec-b">'+inner+'</div></div>';
}
function listBlock(kind, icon, title, arr, nameKey, detKey){
  if(!arr || !arr.length) return '';
  let out = '<ul>'; let n = 0;
  arr.forEach(it=>{
    const nm = typeof it==='string' ? it : (it[nameKey]||it.name||'');
    if(!nm) return;
    n++;
    const det = typeof it==='string' ? '' : (it[detKey]||it.detail||it.tag||'');
    const url = typeof it==='object' && it.url ? ' <a href="'+esc(it.url)+'" target="_blank" rel="noopener">↗</a>' : '';
    /* The phone build is the one read AT the trailhead, with no signal, so the
       dog answer matters more here than on the desktop card. It renders no
       pills at all, so this is a bare marker rather than a badge. Absence stays
       absent: an item with no researched rule shows nothing, because "we did
       not check" must not look like "dogs are welcome". */
    const dog = (typeof it==='object' && it.dogs===true) ? ' <span class="dogok">🐕</span>'
              : (typeof it==='object' && it.dogs===false) ? ' <span class="dogno">🚫</span>' : '';
    out += '<li><div class="iname">'+esc(nm)+dog+url+'</div>'+(det?'<div class="idet">'+esc(det)+'</div>':'')+'</li>';
  });
  return n ? sec(kind, icon, title, out+'</ul>') : '';
}

function cardHTML(s,i){
  const col = legColors()[s.leg] || '#e8b04b';
  const nm  = legNames()[s.leg] || s.leg || '';
  let b = '<div class="blurb">'+esc(s.blurb||'')+'</div>';
  if(s.note) b += '<div class="note">'+esc(s.note)+'</div>';
  if(s.camp) b += sec('camp','\u26fa','Camp','<div class="iname">'+esc(s.camp)+'</div>');
  b += listBlock('itin','\ud83e\udd7e','Itinerary', s.activities, 'name', 'detail');
  b += listBlock('drive','\ud83d\ude99','Scenic drives (truck)', s.scenicDrives, 'name', 'tag');
  b += listBlock('trail','\u26f0\ufe0f','Trails', s.alltrails, 'name', 'tag');
  b += listBlock('off','\ud83d\udede','Offroad / 4x4 (truck)', s.offroad, 'name', 'tag');
  b += listBlock('cruise','\ud83d\udeb2','Gravel & the bike carrier', s.cruise, 'name', 'tag');
  if(s.holidayEvents && s.holidayEvents.length){
    let hv = '<ul>';
    s.holidayEvents.forEach(e=>{
      const u = e.url ? ' <a href="'+esc(e.url)+'" target="_blank" rel="noopener">info \u2197</a>' : '';
      hv += '<li><div class="iname">'+esc(e.name)+u+'</div>'+
            (e.detail?'<div class="idet">'+e.detail.replace(/<[^>]+>/g,'')+'</div>':'')+'</li>';
    });
    b += sec('holiday','\u2744\ufe0f','Holiday events', hv+'</ul>');
  }
  if(s.campNotes && s.campNotes.length){
    let cn = '<ul>';
    s.campNotes.forEach(n=> cn += '<li><div class="idet">'+esc(n)+'</div></li>');
    b += sec('warn','\u26a0\ufe0f','Camping notes (40ft rig)', cn+'</ul>');
  }
  const cr = s.campResearch || {};
  ['audit_2026_07','canada_audit_2026_07'].forEach(k=>{
    if(cr[k] && cr[k].finding)
      b += sec('audit','\ud83d\udd0e','Campground audit \u2014 '+esc(cr[k].verdict),
               '<div class="idet">'+esc(cr[k].finding)+'</div>');
  });
  if(cr.verdict) b += sec('verdict','\ud83d\udccb','Booking verdict','<div class="idet">'+esc(cr.verdict)+'</div>');
  b += roadAheadHTML(s.id);
  return '<div class="card" id="mc-'+esc(s.id)+'"><div class="chead" onclick="tog(\''+s.id+'\')">'+
    '<span class="dot" style="background:'+col+'"></span><div class="cbody-t"><div class="cname">'+esc(s.name)+'</div>'+
    '<div class="cmeta">'+fmt(s.arrive)+' – '+fmt(s.depart)+' · '+(s.nights||0)+'n · '+esc(nm)+chip(s.weather)+drivingChip(s.id)+'</div></div>'+
    '<div class="chev">›</div></div><div class="cbody">'+b+'</div></div>';
}
function tog(id){ const c=document.getElementById('mc-'+id); if(c) c.classList.toggle('open'); }

/* The leg leaving this stop. On a phone with no signal in the middle of the
   Cassiar, "9.8 h of driving and a 40 ft prohibition ahead" is the single most
   useful thing the screen can say. */
function nextId(id){
  const a = stops(); const i = a.findIndex(s=>s.id===id);
  return (i>=0 && i<a.length-1) ? a[i+1].id : null;
}
function drivingChip(id){
  const n = nextId(id); if(!n) return '';
  const l = (D.legInfo||{})[id+'>'+n]; if(!l) return '';
  const cls = l.split ? 'far' : l.long ? 'mid' : '';
  return ' \u00b7 <span class="dchip '+cls+'">\ud83d\ude90 '+l.mi+' mi \u00b7 ~'+l.hours+' h</span>';
}
function roadAheadHTML(id){
  const n = nextId(id); if(!n) return '';
  const leg = (D.passes||{})[id+'>'+n]; if(!leg) return '';
  const real = t => t && !/^no posted|^none found|^unknown/i.test(String(t).trim());
  let v = leg.verdict ? '<div class="idet"><b>'+esc(leg.verdict)+'</b></div>' : '';
  v += (leg.passes||[]).map(function(pp){
    let x = '<div class="pass"><div class="iname">'+esc(pp.name)+
      (pp.severity?' <span class="sev '+esc(pp.severity)+'">'+esc(pp.severity)+'</span>':'')+'</div>';
    const figs = [];
    if(pp.elev_ft) figs.push(pp.elev_ft.toLocaleString()+' ft');
    if(pp.max_grade_pct) figs.push(pp.max_grade_pct+'% grade');
    if(figs.length) x += '<div class="pfig">'+figs.join(' \u00b7 ')+'</div>';
    if(real(pp.rv_restriction)) x += '<div class="prest">\u26a0 '+esc(pp.rv_restriction)+'</div>';
    if(pp.direction_note) x += '<div class="idet">'+esc(pp.direction_note)+'</div>';
    return x + '</div>';
  }).join('');
  const worst = leg.worst ? ' \u2014 worst '+leg.worst : '';
  return sec('road','\u26f0\ufe0f','Road ahead'+worst, v);
}
/* Off-grid: where the phone stops working and where the propane runs out.
   Rendered from the same researched data as the desktop, and it is on the
   phone precisely because you cannot look it up when you need it. */
function offgridHTML(){
  const pl = D.petlog || {};
  if(!pl.cell_gaps) return '';
  const src = u => u ? ' <a href="'+esc(u)+'" target="_blank" rel="noopener">source \u2197</a>' : '';
  let out = '<div class="sechead">No signal, no propane, no dump</div>';
  out += '<div class="card open"><div class="cbody">';
  out += sec('warn','\ud83d\udcf5','Where the phone stops working',
    (pl.cell_gaps||[]).map(g=>'<div class="pass"><div class="iname">'+esc(g.road)+
      (g.approx_miles?' <span class="sev hard">~'+g.approx_miles+' mi</span>':'')+'</div>'+
      (g.gap?'<div class="pfig">'+esc(g.gap)+'</div>':'')+
      '<div class="idet">'+esc(g.note||'')+src(g.source)+'</div></div>').join(''));
  out += sec('camp','\u26fd','Fuel, propane, water and dump',
    (pl.supplies||[]).map(s=>'<div class="pass"><div class="iname">'+esc(s.topic)+' \u2014 '+esc(s.where)+'</div>'+
      '<div class="idet">'+esc(s.note||'')+src(s.source)+'</div></div>').join(''));
  if(pl.pets){
    const req = l => (l||[]).map(r=>'<div class="pass"><div class="iname">'+
      esc(r.applies_to==='both'?'Dog and cat':r.applies_to==='dog'?'Dog':'Cat')+'</div>'+
      '<div class="idet">'+esc(r.requirement)+'<br><b>When:</b> '+esc(r.lead_time||'\u2014')+src(r.source)+'</div></div>').join('');
    out += sec('itin','\ud83d\udc15','Pets into Canada', req(pl.pets.into_canada));
    out += sec('itin','\ud83c\uddfa\ud83c\uddf8','Pets back into the US', req(pl.pets.back_into_us));
  }
  return out + '</div></div>';
}

const legAlerts = () => pick('alerts');
function legAlertHTML(leg){
  const list = legAlerts()[leg];
  if(!list || !list.length) return '';
  return '<div class="legalerts">' + list.map(function(a){
    return '<div class="legalert la-'+esc(a.kind||'plan')+'"><span class="la-ic">'+esc(a.icon||'')+
           '</span><span>'+(a.text||'')+'</span></div>';
  }).join('') + '</div>';
}
function togAlerts(el){
  const box = el.nextElementSibling;
  if(box && box.classList.contains('legalerts')){ box.classList.toggle('open'); el.classList.toggle('open'); }
}
function renderStops(){
  // Stage headers carry that stage's alerts, so a Denali closure shows up on
  // the Alaska leg rather than in one wall of text at the top of the trip.
  const arr = stops(), ln = legNames(), lc = legColors();
  let out = '<div class="sechead">'+arr.length+' stops</div>', prev = null;
  arr.forEach(function(s,i){
    if(s.leg !== prev){
      prev = s.leg;
      const al = (legAlerts()[s.leg]||[]).length;
      out += '<div class="leglabel'+(al?' tap':'')+'"'+(al?' onclick="togAlerts(this)"':'')+
             '><span class="ldot" style="background:'+(lc[s.leg]||'#e8b04b')+'"></span>'+
             esc(ln[s.leg]||s.leg||'')+
             (al?'<span class="lcount">'+al+' alert'+(al>1?'s':'')+'<span class="lcar">\u203a</span></span>':'')+
             '</div>' + legAlertHTML(s.leg);
    }
    out += cardHTML(s,i);
  });
  document.getElementById('stopsWrap').innerHTML = out;
}
function renderOffgrid(){
  const w = document.getElementById('offgridWrap');
  if(w) w.innerHTML = offgridHTML() ||
    '<div class="empty">No off-grid reference data in this build.</div>';
}
function renderIssues(){
  const a=issues();
  document.getElementById('issuesWrap').innerHTML = '<div class="sechead">'+a.length+' known issues</div>' +
    a.map(i=>'<div class="iss '+esc(i.severity||'orange')+'">'+
      '<div class="iss-s">'+esc(i.category||'')+' · '+esc(i.stop_name||'')+'</div>'+
      '<div class="iss-t">'+esc(i.issue||'')+'</div>'+
      '<div class="iss-b">'+esc(i.analysis||'')+'</div>'+
      (i.solution?'<div class="iss-sol"><b>Fix:</b> '+esc(i.solution)+'</div>':'')+'</div>').join('');
}
function renderStats(){
  const a=stops(); const n=a.reduce((x,s)=>x+(s.nights||0),0);
  const st=[[a.length, a.length===1?'Stop':'Stops'],[n, n===1?'Night':'Nights'],[fmt(a[0]&&a[0].arrive),'Start'],[fmt(a[a.length-1]&&a[a.length-1].depart),'End']];
  document.getElementById('mStats').innerHTML = st.map(s=>'<div class="stat"><div class="n">'+s[0]+'</div><div class="l">'+s[1]+'</div></div>').join('');
  document.getElementById('hTitle').textContent = T().title;
  document.getElementById('hSub').textContent = T().sub;
}

/* ---------------- map ---------------- */
let map=null, layer=null;
const routeGeom = () => pick('geom');
/* Encoded-polyline decoder. The real driving geometry is baked in by
   tools/build_routes.py, so this needs no network — the road shape survives
   offline, which is the whole point on the Cassiar and the Alcan. */
function decodePolyline(str){
  let index=0, lat=0, lng=0; const out=[];
  while(index < str.length){
    let shift=0, result=0, byte;
    do { byte=str.charCodeAt(index++)-63; result|=(byte&0x1f)<<shift; shift+=5; } while(byte>=0x20);
    lat += (result&1) ? ~(result>>1) : (result>>1);
    shift=0; result=0;
    do { byte=str.charCodeAt(index++)-63; result|=(byte&0x1f)<<shift; shift+=5; } while(byte>=0x20);
    lng += (result&1) ? ~(result>>1) : (result>>1);
    out.push([lat/1e5, lng/1e5]);
  }
  return out;
}
/* Full coordinate path for the current trip: real roads where we have them,
   a straight hop where we don't. Used by both the Leaflet map and the SVG. */
function routePath(){
  const a = stops().filter(s=>typeof s.lat==='number' && typeof s.lng==='number');
  const g = routeGeom(), out = [];
  for(let i=0;i<a.length;i++){
    out.push([a[i].lat, a[i].lng]);
    const b = a[i+1]; if(!b) break;
    const enc = g[a[i].id+'>'+b.id];
    if(enc){ const pts = decodePolyline(enc); for(let k=0;k<pts.length;k++) out.push(pts[k]); }
  }
  return out;
}
function legendHTML(){
  const ln=legNames(), lc=legColors(), seen={};
  stops().forEach(s=>{ if(s.leg) seen[s.leg]=1; });
  return Object.keys(seen).map(k=>'<span><i style="background:'+(lc[k]||'#e8b04b')+'"></i>'+esc(ln[k]||k)+'</span>').join('');
}
/* Offline fallback: draw the route as an inline SVG straight from the stop
   coordinates. No tiles, no Leaflet, no network — so on the Cassiar or the
   Alcan with no bars you still get the route shape and where each stop sits. */
function drawSvgFallback(){
  const a = stops().filter(s=>typeof s.lat==='number' && typeof s.lng==='number');
  const el = document.getElementById('mapFallback');
  if(!a.length){ el.innerHTML=''; return; }
  const W=1000, H=760, P=42;
  const lats=a.map(s=>s.lat), lngs=a.map(s=>s.lng);
  const minLa=Math.min(...lats), maxLa=Math.max(...lats);
  const minLo=Math.min(...lngs), maxLo=Math.max(...lngs);
  // widen longitude by cos(lat) so the shape isn't stretched at high latitude
  const midLa=(minLa+maxLa)/2, k=Math.cos(midLa*Math.PI/180)||1;
  const spanLo=Math.max((maxLo-minLo)*k, 1e-6), spanLa=Math.max(maxLa-minLa, 1e-6);
  const sc=Math.min((W-2*P)/spanLo, (H-2*P)/spanLa);
  const ox=(W-spanLo*sc)/2, oy=(H-spanLa*sc)/2;
  const X=s=>ox+((s.lng-minLo)*k)*sc, Y=s=>oy+((maxLa-s.lat))*sc;
  // follow the baked road geometry when it's there, stop-to-stop otherwise
  const path = routePath();
  const pts=(path.length>1 ? path.map(p=>({lat:p[0],lng:p[1]})) : a)
    .map(s=>X(s).toFixed(1)+','+Y(s).toFixed(1)).join(' ');
  const lc=legColors();
  let dots='';
  a.forEach(s=>{ dots += '<circle cx="'+X(s).toFixed(1)+'" cy="'+Y(s).toFixed(1)+'" r="5.5" fill="'+
    (lc[s.leg]||'#e8b04b')+'" stroke="#fff" stroke-width="1.6"><title>'+esc(s.name)+'</title></circle>'; });
  const first=a[0], last=a[a.length-1];
  el.innerHTML='<svg viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="xMidYMid meet">'+
    '<polyline points="'+pts+'" fill="none" stroke="#5fb4d6" stroke-width="2.4" stroke-opacity=".55" '+
    'stroke-linejoin="round" stroke-linecap="round"/>'+dots+
    '<text x="'+X(first).toFixed(1)+'" y="'+(Y(first)-13).toFixed(1)+'" fill="#e8ebef" font-size="19" '+
    'text-anchor="middle" font-family="-apple-system,sans-serif">start</text>'+
    '<text x="'+X(last).toFixed(1)+'" y="'+(Y(last)+27).toFixed(1)+'" fill="#e8ebef" font-size="19" '+
    'text-anchor="middle" font-family="-apple-system,sans-serif">end</text></svg>';
}
function goOffline(msg){
  document.getElementById('mapWrap').classList.add('offline');
  drawSvgFallback();
  const n=document.getElementById('mapNote');
  n.className='warn';
  n.innerHTML='<b>Offline — showing the schematic route.</b><br>'+msg+
    ' Every stop is plotted from its real coordinates, so the route shape and each stop\'s position are accurate; '+
    'there is just no terrain or road detail until you have a connection.';
  document.getElementById('mapLegend').innerHTML = legendHTML();
}
function drawMap(){
  document.getElementById('mapLegend').innerHTML = legendHTML();
  if(typeof L==='undefined'){
    goOffline('The map library could not load, so the interactive map is unavailable.');
    return;
  }
  document.getElementById('mapWrap').classList.remove('offline');
  const n=document.getElementById('mapNote');
  n.className=''; n.textContent='Tap a pin for the stop name and dates. Pinch to zoom.';
  if(!map){
    map = L.map('mMap',{scrollWheelZoom:false, attributionControl:false}).setView([55,-120],3);
    const tl = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',{maxZoom:12});
    let tileErr=0, tileOk=false;
    tl.on('tileload', ()=>{ tileOk=true; });
    tl.on('tileerror', ()=>{ if(++tileErr>=4 && !tileOk)
      goOffline('Map tiles could not be downloaded, which usually means no data signal.'); });
    tl.addTo(map);
  }
  if(layer) map.removeLayer(layer);
  const pts=[], marks=[];
  stops().forEach(s=>{
    if(typeof s.lat!=='number'||typeof s.lng!=='number') return;
    pts.push([s.lat,s.lng]);
    marks.push(L.circleMarker([s.lat,s.lng],{radius:6,weight:2,color:'#fff',
      fillColor:legColors()[s.leg]||'#e8b04b',fillOpacity:1})
      .bindPopup('<b>'+esc(s.name)+'</b><br>'+fmt(s.arrive)+' – '+fmt(s.depart)+' · '+(s.nights||0)+' nights'));
  });
  const path = routePath();
  if(path.length>1) marks.push(L.polyline(path,{color:'#5fb4d6',weight:2,opacity:.5,lineJoin:'round'}));
  layer = L.layerGroup(marks).addTo(map);
  setTimeout(()=>{ map.invalidateSize(); if(pts.length) map.fitBounds(pts,{padding:[26,26]}); },80);
}

/* ---------------- search ---------------- */
const IDX=[];
function buildIndex(){
  Object.keys(TRIPS).forEach(t=>{
    const arr = D[TRIPS[t].stops], ln = D[TRIPS[t].names];
    (arr||[]).forEach(s=>{
      const f=[];
      const push=(k,v)=>{ if(!v) return;
        const txt = typeof v==='string'? v : (v.name||v.detail||v.tag||'');
        if(txt) f.push({k:k,t:String(txt)}); };
      push('stop name',s.name); push('campground',s.camp);
      (s.activities||[]).forEach(x=>push('activity',x));
      (s.alltrails||[]).forEach(x=>push('trail',x));
      (s.scenicDrives||[]).forEach(x=>push('scenic drive',x));
      (s.offroad||[]).forEach(x=>push('off-road route',x));
      (s.cruise||[]).forEach(x=>push('gravel ride',x));
      (s.nearbyTowns||[]).forEach(x=>push('nearby town',x));
      (s.poi||[]).forEach(x=>push('point of interest',x));
      push('description',s.blurb); push('note',s.note);
      (s.campNotes||[]).forEach(x=>push('camp note',x));
      f.forEach(o=>o.n=o.t.toLowerCase());
      IDX.push({trip:t,id:s.id,name:s.name,leg:(ln&&ln[s.leg])||'',arrive:s.arrive,depart:s.depart,f:f});
    });
  });
}
function doSearch(q){
  q=(q||'').trim().toLowerCase();
  const w=document.getElementById('srWrap');
  if(q.length<2){ w.innerHTML='<div class="empty">Type at least two letters to search every stop, campground, trail and scenic drive across every trip.</div>'; return; }
  const hits=[];
  IDX.forEach(e=>{
    let best=null,bs=-1;
    e.f.forEach(f=>{ const i=f.n.indexOf(q); if(i<0) return;
      let sc=(f.k==='stop name'?1000:400)-Math.min(i,90); if(i===0) sc+=200;
      if(sc>bs){bs=sc;best=f;} });
    if(best) hits.push({e:e,f:best,s:bs});
  });
  hits.sort((a,b)=>b.s-a.s);
  if(!hits.length){ w.innerHTML='<div class="empty"><b>No match on any trip.</b><br>This searches planned stops, so a town you only drive through may not be listed.</div>'; return; }
  w.innerHTML='<div class="sechead">'+hits.length+' result'+(hits.length>1?'s':'')+'</div>' +
    hits.slice(0,40).map(hit=>{
      const e=hit.e,f=hit.f; const i=f.n.indexOf(q);
      const from=Math.max(0,i-40), to=Math.min(f.t.length,i+q.length+50);
      const snip=(from>0?'…':'')+esc(f.t.slice(from,i))+'<mark>'+esc(f.t.slice(i,i+q.length))+'</mark>'+
        esc(f.t.slice(i+q.length,to))+(to<f.t.length?'…':'');
      return '<div class="sr" onclick="goTo(\''+e.trip+'\',\''+e.id+'\')">'+
        '<div class="sr-n"><span class="trip-tag '+e.trip+'">'+
        ({bigloop:'Alaska',ext:'East',cloudcroft:'Cloudcroft'}[e.trip]||e.trip)+'</span>'+esc(e.name)+'</div>'+
        '<div class="sr-m">'+esc(e.leg)+' · '+fmt(e.arrive)+' – '+fmt(e.depart)+'</div>'+
        '<div class="sr-w"><i>'+esc(f.k)+':</i> '+snip+'</div></div>';
    }).join('');
}
function goTo(t,id){
  if(trip!==t){ setTrip(t); }
  setView('stops');
  setTimeout(()=>{
    const c=document.getElementById('mc-'+id);
    if(c){ if(!c.classList.contains('open')) c.classList.add('open');
      c.scrollIntoView({behavior:'smooth',block:'start'}); }
  },90);
}

/* ---------------- nav ---------------- */
function setView(v){
  document.querySelectorAll('.view').forEach(s=>s.classList.toggle('active','v-'+v===s.id));
  document.querySelectorAll('#tabbar button').forEach(b=>b.classList.toggle('active',b.dataset.view===v));
  if(v==='map') drawMap();
  window.scrollTo({top:0});
}
function setTrip(t){
  trip=t;
  document.querySelectorAll('#tripSeg button').forEach(b=>b.classList.toggle('active',b.dataset.trip===t));
  renderStats(); renderStops(); renderIssues(); renderOffgrid();
  if(document.getElementById('v-map').classList.contains('active')) drawMap();
}
document.getElementById('tabbar').addEventListener('click',e=>{
  const b=e.target.closest('button'); if(b) setView(b.dataset.view); });
document.getElementById('tripSeg').addEventListener('click',e=>{
  const b=e.target.closest('button'); if(b) setTrip(b.dataset.trip); });
let st=null;
document.getElementById('mSearch').addEventListener('input',e=>{
  document.getElementById('mClear').style.display = e.target.value?'block':'none';
  clearTimeout(st); st=setTimeout(()=>{ setView('search'); doSearch(e.target.value); },140);
});
document.getElementById('mClear').addEventListener('click',()=>{
  const i=document.getElementById('mSearch'); i.value=''; document.getElementById('mClear').style.display='none'; doSearch('');
});
const bt=document.getElementById('backTop');
window.addEventListener('scroll',()=>bt.classList.toggle('show',window.scrollY>700),{passive:true});
bt.addEventListener('click',()=>window.scrollTo({top:0,behavior:'smooth'}));

buildIndex(); renderStats(); renderStops(); renderIssues(); renderOffgrid();
window.__mobileReady = {stops:D.stops.length, ext:D.ext.length, idx:IDX.length};
</script>
</body>
</html>
"""
OUT_HTML = HTML.replace('__DATA__', BLOB)

# Swap the CDN tags for the Leaflet already inlined in the desktop build, so the
# phone works with no signal. This is the build that gets used on the Dempster.
_CSS_URL = 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css'
_JS_URL = 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js'
_lc, _lj = inlined_leaflet(SRC.read_text())
if _lc and _lj:
    OUT_HTML = OUT_HTML.replace('<link rel="stylesheet" href="%s">' % _CSS_URL, _lc, 1)
    OUT_HTML = OUT_HTML.replace('<script src="%s"></script>' % _JS_URL, _lj, 1)
    print("   leaflet inlined into the phone build — map works offline")
else:
    print("   !! desktop build has no inlined leaflet; phone build still needs a CDN")

open(OUT,'w').write(OUT_HTML)
print("wrote", OUT, len(OUT_HTML), "bytes")
