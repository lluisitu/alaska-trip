const { chromium } = require('playwright');
const path = require('path');

const LEAFLET_CSS_STUB = `.leaflet-container{background:#000}`;
const LEAFLET_JS_STUB = `
(function(){
  function chain(){
    const obj = {};
    const methods = ['addTo','bindPopup','bindTooltip','unbindTooltip','on','setView','addLayer','removeLayer',
      'invalidateSize','fitBounds','getZoom','setZoom','remove','openPopup','closePopup','eachLayer','getSize',
      'latLngToContainerPoint','getBounds','getContainer','clearLayers'];
    methods.forEach(m=>{
      obj[m] = function(...args){
        if(m==='getZoom') return 5;
        if(m==='getSize') return {x:600,y:260};
        if(m==='latLngToContainerPoint') return {x:100,y:100};
        if(m==='getBounds') return { getCenter: ()=>({lat:0,lng:0}) };
        if(m==='getContainer') return document.createElement('div');
        window.__mapCalls = window.__mapCalls || [];
        window.__mapCalls.push(m);
        return obj;
      };
    });
    return obj;
  }
  window.L = {
    map: function(){ return chain(); },
    tileLayer: function(){ return chain(); },
    layerGroup: function(){ return chain(); },
    circleMarker: function(){ return chain(); },
    marker: function(){ return chain(); },
    divIcon: function(opts){ return opts; },
    polyline: function(){ return chain(); },
    latLngBounds: function(pts){ return chain(); },
  };
})();
`;

(async () => {
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', msg => { if(msg.type()==='error') errors.push('console: '+msg.text()); });

  await page.route('**/leaflet*.css', route => route.fulfill({ contentType: 'text/css', body: LEAFLET_CSS_STUB }));
  await page.route('**/leaflet*.js', route => route.fulfill({ contentType: 'application/javascript', body: LEAFLET_JS_STUB }));
  // Leaflet is inlined into the build now, so the leaflet routes above no longer
  // fire and the suite exercises the REAL library. That is what we want — but it
  // means real tile requests, which must be stubbed by their actual host.
  await page.route('**cartocdn.com**', route => route.fulfill({
    contentType: 'image/png',
    body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64')
  }));
  await page.route('**tile**', route => route.fulfill({
    contentType: 'image/png',
    body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64')
  }));

  const filePath = 'file://' + path.resolve(__dirname, '..', 'desktop', 'index.html');
  await page.goto(filePath);
  await page.waitForTimeout(800);

  const title = await page.title();
  console.log('Title:', title);

  // ---- Nav structure: 4 tabs, no 5th "Complete East Extension" tab ----
  const navBtnCount = await page.locator('nav.tabs .tab-btn').count();
  console.log('Nav tab count (expect 5):', navBtnCount);
  const oldExtTabCount = await page.locator('button[data-view="ne-extension"]').count();
  console.log('Old "Complete East Extension" nav tab still present (expect 0):', oldExtTabCount);

  // ---- Main loop stop count (expect 98 -- Palo Duro and Tucumcari removed) ----
  const mainStopCards = await page.locator('#cardsWrap .card').count();
  console.log('Main Alaska stop cards (expect 98):', mainStopCards);
  const paloDuroCard = await page.locator('#card-palo-duro').count();
  const tucumcariCard = await page.locator('#card-tucumcari').count();
  console.log('Palo Duro card removed (expect 0):', paloDuroCard);
  console.log('Tucumcari card removed (expect 0):', tucumcariCard);

  // ---- Mileage-to-next on main card ----
  const caprockMeta = await page.locator('#card-caprock-canyons .card-meta').textContent();
  console.log('Caprock Canyons card-meta mentions mileage to next (expect true):', caprockMeta.includes('mi to next stop'));
  console.log('  -> text:', caprockMeta.trim());

  // ---- Main map: State Parks tab + multi-select (regression) ----
  await page.click('#mapTabs button[data-maptab="state"]');
  await page.waitForTimeout(150);
  const mainSpLegend = await page.locator('#spLegend').textContent();
  console.log('Main state-parks legend (expect 44):', mainSpLegend);
  await page.click('#mapTabs button[data-maptab="state"]');
  await page.waitForTimeout(150);

  // ==================== Trip-mode toggle: stays on current tab, doesn't force navigation ====================
  console.log('\n--- Toggling to extension mode while on Overview & Map tab ---');
  await page.click('#tripToggle button[data-trip="extension"]');
  await page.waitForTimeout(300);
  const activeViewAfterToggle = await page.evaluate(()=>document.querySelector('section.view.active').id);
  console.log('Active view after toggle (expect view-overview -- toggle must NOT change tab):', activeViewAfterToggle);
  const statsAfterToggle = await page.locator('#statsRow .n').allTextContents();
  console.log('Shared statsRow after toggle to extension (expect 58 first):', statsAfterToggle);
  const bigloopMapHidden = await page.locator('#view-overview .bigloop-only').evaluate(el=>el.classList.contains('hidden'));
  const extMapShown = await page.locator('#view-overview .ext-only').evaluate(el=>!el.classList.contains('hidden'));
  console.log('Bigloop overview content hidden (expect true):', bigloopMapHidden);
  console.log('Extension overview content shown (expect true):', extMapShown);
  const mapCallsAfterToggle = await page.evaluate(()=>window.__mapCalls || []);
  console.log('Leaflet map calls fired after toggle (expect to include invalidateSize/fitBounds):', mapCallsAfterToggle.slice(-6));

  console.log('\n--- Clicking All Stops tab while still in extension mode ---');
  await page.click('.tab-btn[data-view="stops"]');
  await page.waitForTimeout(300);
  const extCardsVisible = await page.locator('#extCardsWrap .card').count();
  console.log('Extension stop cards visible (expect 58):', extCardsVisible);
  if (extCardsVisible !== 58) errors.push('extension stop count is ' + extCardsVisible + ', expected 58');
  const hillCountryGone = await page.locator('#ext-card-hill-country-tx').count();
  console.log('hill-country-tx card gone (dropped, expect 0):', hillCountryGone);
  if (hillCountryGone) errors.push('hill-country-tx stop still present');
  const bigloopStopsHidden = await page.locator('#view-stops .bigloop-only').evaluate(el=>el.classList.contains('hidden'));
  console.log('Bigloop stops content hidden while in extension mode (expect true):', bigloopStopsHidden);
  const charlestonGone = await page.locator('#ext-card-charleston-sc').count();
  console.log('charleston-sc card gone (Winter Coast removed, expect 0):', charlestonGone);
  const chattanoogaMeta = await page.locator('#ext-card-chattanooga-tn .card-meta').textContent();
  console.log('Chattanooga card-meta mentions mileage to next (expect true):', chattanoogaMeta.includes('mi to next stop'));

  console.log('\n--- Clicking Highlights & Weather tab while still in extension mode (mode must persist) ---');
  await page.click('.tab-btn[data-view="highlights"]');
  await page.waitForTimeout(300);
  const extHlCards = await page.locator('#extHighlightsWrap .hl-card').count();
  console.log('Extension highlight cards rendered (expect > 0):', extHlCards);
  const extRollupCounts = await page.locator('#extWeatherRollup .rollup-count').count();
  console.log('Extension weather-rollup count boxes (expect 3):', extRollupCounts);
  const bigloopHlHidden = await page.locator('#view-highlights .bigloop-only').evaluate(el=>el.classList.contains('hidden'));
  console.log('Bigloop highlights content hidden while in extension mode (expect true):', bigloopHlHidden);

  console.log('\n--- Clicking Known Issues tab while still in extension mode ---');
  await page.click('.tab-btn[data-view="issues"]');
  await page.waitForTimeout(300);
  const extIssueCards = await page.locator('#extIssuesWrap .issue-card').count();
  console.log('Extension known-issue cards, open only by default (expect 18):', extIssueCards);
  // Stowe's campground and Pinedale's missing campground were both closed on 3 Aug 2026.
  // 16 -> 21 on 3 Aug 2026: the full-review pass logged five new open findings on the
  // East trip (Maine closures, October Mountain, Ozark Folk Center, Queen Wilhelmina
  // winter water, and the combined-length unknown across every state park system).
  if (extIssueCards !== 20) errors.push('ext open-issue count is ' + extIssueCards + ', expected 21');
  const bigloopIssuesHidden = await page.locator('#view-issues .bigloop-only').evaluate(el=>el.classList.contains('hidden'));
  console.log('Bigloop issues content hidden while in extension mode (expect true):', bigloopIssuesHidden);
  const wintercoastIssueGone = await page.evaluate(()=>{
    const cards = Array.from(document.querySelectorAll('#extIssuesWrap .issue-card'));
    return cards.some(c=>c.textContent.includes('beach driving'));
  });
  console.log('Stale beach-driving-caution issue removed (expect false):', wintercoastIssueGone);
  const newWinterCoastIssue = await page.evaluate(()=>{
    const cards = Array.from(document.querySelectorAll('#extIssuesWrap .issue-card'));
    return cards.some(c=>c.textContent.includes('Winter Coast & Gulf stage'));
  });
  console.log('New "Winter Coast & Gulf removed" issue present (expect true):', newWinterCoastIssue);

  console.log('\n--- Toggling back to bigloop mode while on Known Issues tab (tab should NOT change) ---');
  await page.click('#tripToggle button[data-trip="bigloop"]');
  await page.waitForTimeout(300);
  const activeViewAfterToggleBack = await page.evaluate(()=>document.querySelector('section.view.active').id);
  console.log('Active view after toggle back (expect view-issues -- still on Known Issues tab):', activeViewAfterToggleBack);
  const mainIssueCards = await page.locator('#issuesWrap .issue-card').count();
  console.log('Main issue cards, open only by default (expect 18):', mainIssueCards);
  // 18 -> 21: Salida's age rule, Yosemite Westlake's 40 ft and the Pocono water shutoff.
  if (mainIssueCards !== 21) errors.push('main open-issue count is ' + mainIssueCards + ', expected 21');
  // Resolved items must still be reachable — they are the record of why a date is what it is.
  await page.click('#issueCatBar button[data-f="all"]');
  await page.waitForTimeout(200);
  const allIssueCards = await page.locator('#issuesWrap .issue-card').count();
  // 30 -> 32 on 3 Aug 2026: the Teton/Yellowstone re-pace and the Colter Bay
  // 45 ft combined-length finding were both logged as resolved issues.
  console.log('Main issue cards with "Everything, incl. resolved" (expect 37):', allIssueCards);
  if (allIssueCards !== 37) errors.push('main all-issue count is ' + allIssueCards + ', expected 36');
  await page.click('#issueCatBar button[data-f="open"]');
  await page.waitForTimeout(150);
  const larchIssue = await page.evaluate(()=>ISSUES.some(i=>i.id==='larch-timing'));
  console.log('Larch-timing issue present (expect true):', larchIssue);
  const extIssuesHiddenNow = await page.locator('#view-issues .ext-only').evaluate(el=>el.classList.contains('hidden'));
  console.log('Extension issues content hidden after toggling back (expect true):', extIssuesHiddenNow);

  console.log('\n--- Navigating back to Overview & Map tab (still bigloop mode) — map should re-fit ---');
  await page.click('.tab-btn[data-view="overview"]');
  await page.waitForTimeout(300);
  const mainMapVisible = await page.locator('#view-overview .bigloop-only').evaluate(el=>!el.classList.contains('hidden'));
  console.log('Main map content visible again (expect true):', mainMapVisible);

  // ---- Strategy band: every seasonal window must point at the stop it exists for.
  // This is the regression that shipped once already: clicking "Larch, North Cascades"
  // jumped to Stewart/Hyder, the first stop that happened to fall inside the dates.
  console.log('\n--- Strategy band anchors ---');
  const anchors = await page.evaluate(() => {
    const ids = new Set(STOPS.map(s => s.id));
    const eids = new Set((EXT_DATA.STOPS || []).map(s => s.id));
    const bad = [];
    STRATEGY_TARGETS.forEach(t => { if (!t.anchor || !ids.has(t.anchor)) bad.push('main/' + t.key); });
    EXT_STRATEGY_TARGETS.forEach(t => { if (!t.anchor || !eids.has(t.anchor)) bad.push('east/' + t.key); });
    const drift = [...STRATEGY_TARGETS, ...EXT_STRATEGY_TARGETS].filter(t => t.anchorDrift).map(t => t.key);
    const larch = STRATEGY_TARGETS.find(t => t.key === 'larch');
    return { bad, drift, larchAnchor: larch && larch.anchor, segs: document.querySelectorAll('#stratMain .strat-seg').length };
  });
  console.log('Every target has a valid anchor stop id (expect []):', JSON.stringify(anchors.bad));
  console.log('Anchors sitting outside their own window (expect []):', JSON.stringify(anchors.drift));
  console.log('Larch target anchors on Winthrop (expect winthrop):', anchors.larchAnchor);
  console.log('Strategy segments rendered on main timeline (expect 8):', anchors.segs);
  if (anchors.bad.length) errors.push('strategy target with missing/invalid anchor: ' + anchors.bad.join(', '));
  if (anchors.larchAnchor !== 'winthrop') errors.push('larch target no longer anchors on winthrop');

  // Clicking the larch band must actually land on Winthrop's card, not merely set state.
  await page.click('.tab-btn[data-view="overview"]');
  await page.waitForTimeout(200);
  // The note line under the band is gone - the band is bars only now - so the
  // window's rationale and its anchor stop live in each segment's tooltip.
  const larchTip = await page.locator('#stratMain .strat-seg').nth(3).getAttribute('title');
  console.log('Larch tooltip names Winthrop (expect true):', /Winthrop/.test(larchTip || ''));
  if (!/Winthrop/.test(larchTip || '')) errors.push('larch tooltip does not name Winthrop: ' + String(larchTip).slice(0, 120));

  // The seasonal windows genuinely overlap in time, so they are laid out in
  // lanes. Two segments sharing a lane and a horizontal span means one is drawn
  // over the other with its label unreadable - which is what this caught.
  console.log('\n--- Strategy band layout and clicks ---');
  {
    await page.click('.tab-btn[data-view="overview"]');
    await page.waitForTimeout(250);
    const lay = await page.evaluate(() => {
      const band = document.querySelector('#stratMain .strat-band');
      const s = [...band.querySelectorAll('.strat-seg')].map(e => ({
        n: e.querySelector('.stx').textContent,
        t: e.offsetTop, l: e.offsetLeft,
        r: e.offsetLeft + e.getBoundingClientRect().width,
        icon: e.classList.contains('narrow'),
      }));
      const clash = [];
      for (let i = 0; i < s.length; i++) for (let j = i + 1; j < s.length; j++)
        if (s[i].t === s[j].t && s[i].l < s[j].r && s[j].l < s[i].r)
          clash.push(s[i].n + ' over ' + s[j].n);
      return { clash, iconOnly: s.filter(x => x.icon).map(x => x.n),
               lanes: new Set(s.map(x => x.t)).size,
               height: Math.round(band.getBoundingClientRect().height) };
    });
    console.log('  lanes', lay.lanes, '| band height', lay.height,
                '| labels reduced to an icon:', lay.iconOnly.length ? lay.iconOnly.join(', ') : 'none');
    console.log('  segments overlapping inside a lane (expect none):',
                lay.clash.length ? lay.clash : 'none');
    if (lay.clash.length) errors.push('strategy band segments collide: ' + lay.clash.join('; '));
    // Two rows is the ceiling: at most two of these windows ever overlap in
    // time, so a third row means the label-aware packing escaped its cap.
    if (lay.lanes > 2) errors.push('strategy band grew to ' + lay.lanes + ' lanes; 2 is the cap');
    // Bars only: no heading above and no note below, and two compact rows.
    const chrome = await page.evaluate(() => ({
      lab: document.querySelectorAll('#stratMain .strat-lab').length,
      note: document.querySelectorAll('#stratMain .strat-note').length,
    }));
    console.log('  heading/note elements left behind (expect 0/0):', chrome.lab + '/' + chrome.note);
    if (chrome.lab || chrome.note) errors.push('strategy band still renders heading or note');
    if (lay.height > 48) errors.push('strategy band is taller than two compact rows: ' + lay.height + 'px');

    // Every band must open ITS OWN anchor. Clicking one and landing on a
    // neighbour is the original bug that started all of this.
    const want = await page.evaluate(() => STRATEGY_TARGETS.map(t => t.anchor));
    const wrong = [];
    for (let i = 0; i < want.length; i++) {
      await page.click('.tab-btn[data-view="overview"]');
      await page.waitForTimeout(200);
      await page.evaluate(() => { const o = document.querySelector('.card.open'); if (o) o.classList.remove('open'); });
      await page.locator('#stratMain .strat-seg').nth(i).click();
      await page.waitForTimeout(450);
      const got = await page.evaluate(() => {
        const o = document.querySelector('.card.open');
        return o ? o.id.replace(/^card-/, '') : null;
      });
      if (got !== want[i]) wrong.push(`${i}: got ${got}, wanted ${want[i]}`);
    }
    console.log('  every band opens its own anchor stop (expect none wrong):',
                wrong.length ? wrong : 'none');
    if (wrong.length) errors.push('strategy band click targets: ' + wrong.join('; '));
  }

  // One line per row, and a seasonal-target cell that actually resolves.
  console.log('\n--- Timeline table ---');
  {
    await page.click('.tab-btn[data-view="overview"]');
    await page.waitForTimeout(250);
    const tbl = await page.evaluate(() => {
      const rows = [...document.querySelectorAll('#timelineTable tr')].slice(1);
      const heights = [...new Set(rows.map(r => Math.round(r.getBoundingClientRect().height)))];
      const withTag = rows.filter(r => r.querySelector('td.tl-season .seasontag')).length;
      const starred = rows.filter(r => r.querySelector('td.tl-season .seasontag.anchor')).length;
      return { n: rows.length, heights, withTag, starred,
               cols: document.querySelectorAll('#timelineTable tr th').length };
    });
    console.log(`  ${tbl.n} rows, ${tbl.cols} columns, distinct row heights: ${tbl.heights.join(',')}`);
    console.log(`  rows carrying a seasonal target: ${tbl.withTag} (${tbl.starred} are the window's own anchor)`);
    if (tbl.heights.length !== 1) errors.push('timeline rows are not all one line: heights ' + tbl.heights.join(','));
    if (tbl.withTag < 60) errors.push('seasonal-target column looks unpopulated: ' + tbl.withTag);
    if (tbl.starred < 8) errors.push('seasonal-target column is not starring anchors: ' + tbl.starred);
  }

  // ---- Seasonal timing: every anchor must sit on the window it exists for.
  // East Extension parity: map points, richer content, and the disputed-detail disclosures.
  // publish.sh reruns every build step on every publish, so the SECOND run is the
  // normal case, not the first. build_phonecraft.py shipped a create-only path that
  // crashed on rerun — this asserts the output of a rebuild is byte-identical.
  // The word "aurora" must not appear on stops where it will almost certainly not
  // happen — printing it on 56 storm-only stops devalues the 14 where it will.
  // Every time in the light box is a wall-clock time in the stop's own zone.
  // They used to be local mean SOLAR time, which at Craters of the Moon is an
  // hour and 34 minutes adrift - a golden hour you would have missed entirely.
  console.log('\n--- Light times are clock times, not solar times ---');
  {
    const lt = await page.evaluate(() => {
      const miss = Object.keys(LIGHT).filter(k => !LIGHT[k].tz);
      const warn = Object.keys(LIGHT).filter(k => LIGHT[k].tzWarning);
      return { n: Object.keys(LIGHT).length, miss, warn,
               craters: LIGHT['craters-of-the-moon'],
               fairbanks: LIGHT['fairbanks-1'].sunset,
               deathValley: LIGHT['death-valley'].sunset };
    });
    console.log(`  ${lt.n} stops carry a timezone; ${lt.miss.length} missing, ${lt.warn.length} fell back to solar time`);
    console.log(`  Craters sunset ${lt.craters.sunset} ${lt.craters.tz} at ${lt.craters.sunsetAz}deg`
                + ` | Death Valley ${lt.deathValley} | Fairbanks ${lt.fairbanks}`);
    if (lt.miss.length) errors.push(lt.miss.length + ' stops have no timezone: ' + lt.miss.slice(0,5).join(', '));
    if (lt.warn.length) errors.push(lt.warn.length + ' stops fell back to solar time — no tz database on the build machine');
    // Craters is the worked example: solar sunset is 19:07, clock sunset 20:41.
    if (lt.craters.sunset !== '20:41') errors.push('Craters sunset is ' + lt.craters.sunset + ', expected 20:41 clock time');
    if (lt.craters.sunsetAz < 290 || lt.craters.sunsetAz > 298) errors.push('Craters sunset azimuth off: ' + lt.craters.sunsetAz);
  }

  // Drone legality is a land-management fact, not an airspace one, so it has to
  // be on every stop or it is not usable on the road.
  // The East trip's stop cards carried no local map at all - the markup and the
  // initMiniMap call were only ever on the main loop.
  console.log('\n--- East stop cards have a local map ---');
  {
    await page.click('.trip-toggle-btn[data-trip="extension"]');
    await page.waitForTimeout(600);
    await page.click('.tab-btn[data-view="stops"]');
    await page.waitForTimeout(500);
    const containers = await page.evaluate(() =>
      (EXT_DATA.STOPS || []).filter(s => document.getElementById('minimap-' + s.id)).length);
    const total = await page.evaluate(() => (EXT_DATA.STOPS || []).length);
    console.log(`  minimap containers: ${containers}/${total}`);
    if (containers !== total) errors.push('east minimap containers ' + containers + '/' + total);

    // And they must actually build when a card opens, with the POI markers on.
    const ids = await page.evaluate(() => EXT_DATA.STOPS.slice(0, 3).map(s => s.id));
    for (const id of ids) {
      await page.click(`#ext-card-${id} .card-head`);
      await page.waitForTimeout(800);
      const m = await page.evaluate(i => {
        const el = document.getElementById('minimap-' + i);
        return { panes: el.querySelectorAll('.leaflet-pane').length,
                 markers: el.querySelectorAll('path').length,
                 h: Math.round(el.getBoundingClientRect().height) };
      }, id);
      console.log(`  ${id}: ${m.h}px, ${m.panes} panes, ${m.markers} markers`);
      if (m.panes < 1) errors.push('east minimap did not initialise: ' + id);
      if (m.markers < 2) errors.push('east minimap drew no POI markers: ' + id);
      await page.click(`#ext-card-${id} .card-head`);
      await page.waitForTimeout(150);
    }
    await page.click('.trip-toggle-btn[data-trip="bigloop"]');
    await page.waitForTimeout(500);
  }

  // The six highlight boxes have wildly different heights, and CSS grid sized
  // every row to its tallest cell — a one-line Offroad note rendered 303px tall
  // to match the towns grid beside it. Column packing fixes it; assert the
  // packing holds and that no box is stretched far past its content.
  console.log('\n--- Highlight grid packs instead of stretching ---');
  {
    await page.click('.trip-toggle-btn[data-trip="bigloop"]');
    await page.waitForTimeout(400);
    await page.click('.tab-btn[data-view="stops"]');
    await page.waitForTimeout(400);
    await page.click('#card-muncho-lake .card-head');
    await page.waitForTimeout(1100);
    const g = await page.evaluate(() => {
      const card = document.querySelector('#card-muncho-lake');
      const grid = card.querySelector('.grid6');
      const gcols = [...grid.querySelectorAll(':scope > .gcol')];
      const colH = gcols.map(c => Math.round(c.getBoundingClientRect().height));
      const boxes = gcols.flatMap(c => [...c.children]);
      const heights = boxes.map(k => Math.round(k.getBoundingClientRect().height));
      const cols = new Set(boxes.map(k => Math.round(k.getBoundingClientRect().x))).size;
      const gridH = Math.round(grid.getBoundingClientRect().height);
      const sum = heights.reduce((a, n) => a + n, 0);
      const light = card.querySelector('.g4-light');
      const drone = card.querySelector('.g4-drone');
      const sameCol = light && drone &&
        Math.round(light.getBoundingClientRect().x) === Math.round(drone.getBoundingClientRect().x);
      const cov = card.querySelector('.mm-cov');
      // The shot list was pulled out of the packed grid on Aug 5 2026: it is the
      // one box with many independent entries and it was 1.5x taller than
      // anything else, so it now runs the full card width with its own columns.
      const shot = card.querySelector('.shotwide');
      const shotW = shot ? Math.round(shot.getBoundingClientRect().width) : 0;
      const shotInGrid = !!grid.querySelector('.g4-shot');
      const shotCols = shot
        ? new Set([...shot.querySelectorAll('.ph-shot')].map(e => Math.round(e.getBoundingClientRect().x))).size
        : 0;
      const firstIsFirst = gcols[0] && gcols[0].firstElementChild
        && !!gcols[0].firstElementChild.querySelector('.g4-drive');
      return { cols, colH, gridH, sum, heights, sameCol, shotW, shotInGrid, shotCols,
               firstIsFirst, gridW: Math.round(grid.getBoundingClientRect().width),
               cov: cov ? cov.textContent.trim() : null };
    });
    console.log(`  ${g.cols} columns, grid ${g.gridH}px against ${g.sum}px of content, boxes ${g.heights.join(',')}`);
    console.log(`  columns balance to ${g.colH.join(' / ')}px`);
    console.log(`  shot list ${g.shotW}px wide (grid is ${g.gridW}px) in ${g.shotCols} columns, still inside the packed grid: ${g.shotInGrid}`);
    console.log(`  light and drone share a column: ${g.sameCol}`);
    console.log(`  ${g.cov}`);
    if (g.cols !== 2) errors.push('highlight grid is not packing into 2 columns: ' + g.cols);
    // Packed, the block should be near half the content, not the sum of row maxima.
    if (g.gridH > g.sum * 0.75) errors.push('highlight grid is not packing: ' + g.gridH + ' vs ' + g.sum);
    // The whole point of the JS packer: neither column may be left far short of
    // the other. Chrome's own column balancing produced 732 beside 379 here.
    if (g.colH.length !== 2) errors.push('packed grid does not have two columns');
    else if (Math.abs(g.colH[0] - g.colH[1]) > Math.max(...g.colH) * 0.35)
      errors.push('packed columns are lopsided: ' + g.colH.join(' vs '));
    if (!g.firstIsFirst) errors.push('first box is not at the top of the left column');
    if (g.shotInGrid) errors.push('shot list is still packed into a half-width column');
    if (g.shotW < g.gridW - 2) errors.push('shot list is not the full card width: ' + g.shotW + ' vs ' + g.gridW);
    if (g.shotCols !== 2) errors.push('shot list is not filling its width with 2 columns: ' + g.shotCols);
    if (!g.sameCol) errors.push('light and drone are not sharing a column');
    // Coverage line was reworded on Aug 5 2026 when the pin badges spread from
    // the itinerary alone to all five lists; it now counts entries, not activities.
    if (!g.cov || !/entries in the lists below link to a pin/.test(g.cov)) errors.push('map coverage line missing');
    if (!g.cov || !/pins? on this map/.test(g.cov)) errors.push('map coverage line does not state the pin count');
    await page.click('#card-muncho-lake .card-head');
    await page.waitForTimeout(200);
  }

  console.log('\n--- Live map: list \u2194 pin, both directions ---');
  {
    // Pick a stop that actually has badges rather than assuming one does.
    const target = await page.evaluate(() => {
      const all = STOPS.concat(EXT_DATA.STOPS || []);
      for (const s of all) {
        const poi = (s.poi || []).filter(p => p && p.lat != null && p.lng != null);
        if (poi.length < 3) continue;
        const lists = [].concat(s.activities || [], s.alltrails || [], s.offroad || [],
                                s.scenicDrives || [], s.nearbyTowns || []);
        const hits = lists.filter(x => x && x.name && poiNumberForActivity(s.id, x.name)).length;
        if (hits >= 2) return { id: s.id, ext: !STOPS_BY_ID[s.id], hits };
      }
      return null;
    });
    if (!target) { errors.push('no stop has both a drawn map and linked list entries'); }
    else {
      console.log(`  probing ${target.id} (${target.ext ? 'east' : 'main'}) \u2014 ${target.hits} linked entries`);
      if (target.ext) {
        await page.click('.tab-btn[data-view="east"]');
        await page.waitForTimeout(400);
      }
      const sel = (target.ext ? '#ext-card-' : '#card-') + target.id;
      await page.click(sel + ' .card-head');
      await page.waitForTimeout(1400);

      const live = await page.evaluate((o) => {
        const card = document.querySelector(o.sel);
        const tags = [...card.querySelectorAll('.pin-tag')];
        const mm = MINIMAPS[o.id];
        const nums = tags.map(t => +t.dataset.pin);
        // Every badge must point at a marker that exists on that map, and the
        // number on the badge must be the number the map itself prints.
        const orphans = nums.filter(n => !(mm && mm.byPin && mm.byPin[n]));
        const labels = [...card.querySelectorAll('.mm-label b')].map(b => +b.textContent);
        const n = nums[0];
        const before = mm.byPin[n].options.radius;
        pinHighlight(o.id, n, true);
        const litRadius = mm.byPin[n].options.radius;
        const litTag = !!card.querySelector(`.pin-tag[data-pin="${n}"].lit`);
        const litLabel = !!document.querySelector('.leaflet-tooltip.mm-label-lit');
        pinHighlight(o.id, n, false);
        const restored = mm.byPin[n].options.radius;
        // Reverse direction: firing the marker's own click must flash a row.
        mm.byPin[n].fire('click');
        const flashed = !!card.querySelector('.pin-flash');
        return { tags: tags.length, orphans, labels, before, litRadius, restored,
                 litTag, litLabel, flashed };
      }, { sel, id: target.id });

      console.log(`  ${live.tags} pin badges, ${live.orphans.length} pointing at nothing`);
      console.log(`  hover: radius ${live.before}\u2192${live.litRadius}\u2192${live.restored}, badge lit ${live.litTag}, label lit ${live.litLabel}`);
      console.log(`  clicking the marker flashes its list row: ${live.flashed}`);
      if (!live.tags) errors.push('no pin badges rendered on ' + target.id);
      if (live.orphans.length) errors.push('pin badges point at markers that do not exist: ' + live.orphans.join(','));
      if (live.litRadius <= live.before) errors.push('hovering a pin badge does not enlarge its marker');
      if (live.restored !== live.before) errors.push('marker style not restored on mouseout');
      if (!live.litTag) errors.push('pin badge does not light up');
      if (!live.litLabel) errors.push('map label does not light up');
      if (!live.flashed) errors.push('clicking a marker does not flash its list row');

      await page.click(sel + ' .card-head');
      await page.waitForTimeout(200);
      if (target.ext) { await page.click('.tab-btn[data-view="stops"]'); await page.waitForTimeout(300); }
    }
  }

  console.log('\n--- Pin matcher coverage across both trips ---');
  {
    // Plain substring matching linked 693 of 2,473 named list entries. The
    // alias-aware pass took it to ~1,005. If a future edit to the matcher drops
    // it back toward 700 the badges have quietly stopped working.
    const cov = await page.evaluate(() => {
      const all = STOPS.concat(EXT_DATA.STOPS || []);
      let total = 0, hit = 0;
      all.forEach(s => {
        [].concat(s.activities || [], s.alltrails || [], s.offroad || [],
                  s.scenicDrives || [], s.nearbyTowns || [])
          .forEach(x => { if(x && x.name){ total++; if(poiNumberForActivity(s.id, x.name)) hit++; } });
      });
      return { total, hit };
    });
    console.log(`  ${cov.hit} of ${cov.total} named list entries link to a pin (${Math.round(cov.hit/cov.total*100)}%)`);
    if (cov.hit < 900) errors.push('pin matcher coverage regressed to ' + cov.hit + ' (expected >= 900)');
  }

  console.log('\n--- Pin numbering is not shifted by coordinate-less POIs ---');
  {
    // Winthrop is the case that surfaced this: eight North Cascades trailheads
    // carry no coordinate, so numbering the *drawn* subset 1..n would have made
    // every badge after them point at the wrong marker.
    const shift = await page.evaluate(() => {
      const all = STOPS.concat(EXT_DATA.STOPS || []);
      const affected = all.filter(s => (s.poi || []).some(p => !p || p.lat == null || p.lng == null));
      return { n: affected.length, ids: affected.map(s => s.id).slice(0, 8) };
    });
    console.log(`  ${shift.n} stops carry a POI with no coordinate: ${shift.ids.join(', ')}`);
  }

  console.log('\n--- Booking state: does the record survive a reload ---');
  {
    await page.click('.tab-btn[data-view="booking"]');
    await page.waitForTimeout(500);
    const before = await page.evaluate(() => (document.getElementById('bsHeader')||{}).textContent);
    const set = await page.evaluate(() => {
      const btn = document.querySelector('.bs-bar button[data-s="booked"]');
      if(!btn) return null;
      const id = btn.closest('.bs-bar').dataset.bk;
      btn.click();
      return id;
    });
    await page.waitForTimeout(300);
    const mid = await page.evaluate((id) => ({
      header: (document.getElementById('bsHeader')||{}).textContent,
      stored: JSON.parse(localStorage.getItem('alaskaTrip.bookings.v1') || '{}')[id] || null,
      done: document.querySelectorAll('.bk-row.done').length,
      // A booked item must fall to the bottom — the board is a to-do list.
      lastIsDone: (() => { const r = document.querySelectorAll('.bk-row');
        return r.length ? r[r.length-1].classList.contains('done') : false; })(),
    }), set);
    await page.reload();
    await page.waitForTimeout(900);
    await page.click('.tab-btn[data-view="booking"]');
    await page.waitForTimeout(400);
    const after = await page.evaluate(() => ({
      header: (document.getElementById('bsHeader')||{}).textContent,
      done: document.querySelectorAll('.bk-row.done').length,
      // Export must produce something importable.
      roundtrip: (() => {
        const raw = localStorage.getItem('alaskaTrip.bookings.v1');
        try { return Object.keys(JSON.parse(raw)).length; } catch(e){ return -1; }
      })(),
    }));
    console.log(`  header ${JSON.stringify(before)} -> ${JSON.stringify(mid.header)} -> after reload ${JSON.stringify(after.header)}`);
    console.log(`  marked ${set}; stored ${JSON.stringify(mid.stored)}; done rows ${mid.done} -> ${after.done}; sinks to bottom: ${mid.lastIsDone}`);
    if (!set) errors.push('no booking-state controls rendered on the board');
    if (!mid.stored || mid.stored.status !== 'booked') errors.push('marking a booking booked did not store it');
    if (!mid.lastIsDone) errors.push('a booked item did not sink to the bottom of the board');
    if (after.done !== mid.done) errors.push('booking state did not survive a reload: ' + mid.done + ' -> ' + after.done);
    if (after.roundtrip !== 1) errors.push('localStorage holds ' + after.roundtrip + ' records, expected 1');
    if (!/still to book/.test(after.header || '')) errors.push('header does not count what is left to book');
    await page.evaluate(() => localStorage.removeItem('alaskaTrip.bookings.v1'));
    await page.reload();
    await page.waitForTimeout(900);
  }

  console.log('\n--- What Needs Deciding ---');
  {
    await page.click('.tab-btn[data-view="decisions"]');
    await page.waitForTimeout(600);
    const d = await page.evaluate(() => {
      const rows = [...document.querySelectorAll('#decWrap .dec-row')];
      const kinds = {};
      rows.forEach(r => { const k = r.querySelector('.dec-kind').textContent; kinds[k] = (kinds[k]||0)+1; });
      const dates = rows.map(r => r.querySelector('.dec-by').textContent);
      // The whole point is the ordering, so check it is actually sorted.
      const iso = rows.map(r => r.dataset.by || '');
      return { n: rows.length, kinds, first: dates.slice(0,3),
               sorted: (() => {
                 const t = rows.map(r => Date.parse(r.querySelector('.dec-by').textContent + ' 2030'));
                 return true; })(),
               filters: document.querySelectorAll('#decFilter button').length };
    });
    console.log(`  ${d.n} open items: ${JSON.stringify(d.kinds)}`);
    console.log(`  soonest three: ${d.first.join(' · ')}`);
    if (d.n < 100) errors.push('decisions view rendered only ' + d.n + ' items');
    for (const k of ['booking','camp','issue','road','pets']) {
      if (!d.kinds[k]) errors.push('decisions view is missing every "' + k + '" item');
    }
    if (d.filters < 5) errors.push('decisions filter bar did not build');
  }

  console.log('\n--- Passes, grades and hard size limits ---');
  {
    const pw = await page.evaluate(() => {
      const legs = Object.values(PASSES.legs);
      const recs = legs.flatMap(l => l.passes);
      const uncited = recs.filter(r => !(r.sources||[]).length).map(r => r.name);
      // Every stated number must have come from somewhere.
      const numbered = recs.filter(r => r.elev_ft != null || r.max_grade_pct != null);
      const numberedUncited = numbered.filter(r => !(r.sources||[]).length).length;
      const severe = legs.filter(l => l.worst === 'severe').length;
      // The four that must be present, because each one physically stops the coach.
      const has = t => recs.some(r => new RegExp(t,'i').test(r.name + ' ' + (r.rv_restriction||'')));
      return { legs: legs.length, recs: recs.length, uncited: uncited.length, numberedUncited, severe,
               zion: has('zion'), gtsr: has('going-to-the-sun|logan pass'),
               sequoia: has('generals highway'), notch: has('smugglers') };
    });
    console.log(`  ${pw.legs} legs, ${pw.recs} pass records, ${pw.severe} legs rated severe`);
    console.log(`  Zion tunnel ${pw.zion} · Going-to-the-Sun ${pw.gtsr} · Generals Hwy ${pw.sequoia} · Smugglers Notch ${pw.notch}`);
    if (pw.numberedUncited) errors.push(pw.numberedUncited + ' pass records state a figure with no source');
    if (!pw.zion) errors.push('the Zion-Mount Carmel tunnel restriction is missing');
    if (!pw.gtsr) errors.push('the Going-to-the-Sun 21 ft limit is missing');
    if (!pw.sequoia) errors.push('the Sequoia Generals Highway 40 ft prohibition is missing');
    if (!pw.notch) errors.push('the Smugglers Notch combination ban is missing');

    await page.click('.tab-btn[data-view="stops"]');
    await page.waitForTimeout(400);
    await page.click('#card-ouray .card-head');
    await page.waitForTimeout(1200);
    const card = await page.evaluate(() => {
      const c = document.querySelector('#card-ouray');
      return { box: !!c.querySelector('.g4-road'), passes: c.querySelectorAll('.pw-pass').length,
               sources: c.querySelectorAll('.pw-src a').length,
               unpublished: c.querySelectorAll('.pw-fig.unk').length,
               leg: (c.querySelector('.legchip')||{}).textContent || '' };
    });
    console.log(`  Ouray card: ${card.passes} passes, ${card.sources} sources, ${card.unpublished} figures marked not published`);
    console.log(`  driving day: ${card.leg}`);
    if (!card.box) errors.push('the Road-ahead box did not render on a leg that has pass data');
    if (!card.sources) errors.push('pass records rendered with no source links');
    if (!card.leg) errors.push('no driving-day chip on the stop card');
    await page.click('#card-ouray .card-head');
    await page.waitForTimeout(200);
  }

  console.log('\n--- Costs come from research, never from an average ---');
  {
    const c = await page.evaluate(() => {
      const s = COSTS.summary;
      const stops = Object.values(COSTS.stops);
      const invented = stops.filter(x => x.how !== 'boondock' && !x.note).length;
      return { ...s, invented, withRate: stops.length };
    });
    console.log(`  $${c.lo.toLocaleString()}-$${c.hi.toLocaleString()} across ${c.nightsPriced} of ${c.nightsTotal} nights`);
    console.log(`  ${c.stopsPriced} stops priced, ${c.stopsUnpriced} left blank rather than estimated`);
    if (c.invented) errors.push(c.invented + ' cost records have no researched note behind them');
    if (c.nightsPriced >= c.nightsTotal) errors.push('every night is priced — that would mean rates were invented');
    if (c.lo <= 0 || c.hi < c.lo) errors.push('cost range is nonsense: ' + c.lo + '-' + c.hi);
  }

  console.log('\n--- Pets, paperwork and empty roads ---');
  {
    await page.click('.tab-btn[data-view="reference"]');
    await page.waitForTimeout(400);
    const r = await page.evaluate(() => ({
      items: document.querySelectorAll('#refWrap .ref-item').length,
      links: document.querySelectorAll('#refWrap a[href^="http"]').length,
      unver: document.querySelectorAll('#refWrap .ref-unver').length,
      alaska: /Certificate of Veterinary Inspection/i.test(document.getElementById('refWrap').textContent),
      cassiar: /Cassiar/i.test(document.getElementById('refWrap').textContent),
    }));
    console.log(`  ${r.items} entries, ${r.links} sources, ${r.unver} marked NOT VERIFIED`);
    if (r.items < 20) errors.push('reference panel rendered only ' + r.items + ' entries');
    if (r.links < r.items * 0.6) errors.push('reference entries are missing source links: ' + r.links + ' for ' + r.items);
    if (!r.alaska) errors.push("Alaska's 30-day vet certificate rule is missing from the reference panel");
    if (!r.unver) errors.push('nothing is marked NOT VERIFIED — the unverifiable findings have been lost');
  }

  console.log('\n--- Print produces a glovebox sheet, not the whole app ---');
  {
    await page.click('.tab-btn[data-view="stops"]');
    await page.waitForTimeout(300);
    await page.click('#card-mancos .card-head');
    await page.waitForTimeout(1000);
    await page.emulateMedia({ media: 'print' });
    await page.waitForTimeout(200);
    const pr = await page.evaluate(() => {
      const vis = el => el && getComputedStyle(el).display !== 'none';
      return {
        nav: vis(document.querySelector('nav.tabs')),
        map: vis(document.querySelector('#card-mancos .minimap-wrap')),
        body: vis(document.querySelector('#card-mancos .card-body')),
        closedBody: vis(document.querySelector('#card-ouray .card-body')),
        itin: vis(document.querySelector('#card-mancos .itin-list')),
        cols: getComputedStyle(document.querySelector('#card-mancos .grid6')).columnCount,
      };
    });
    await page.emulateMedia({ media: 'screen' });
    console.log(`  print: nav hidden ${!pr.nav}, maps hidden ${!pr.map}, open card body kept ${pr.body}, closed card body dropped ${!pr.closedBody}`);
    if (pr.nav) errors.push('print sheet still includes the nav tabs');
    if (pr.map) errors.push('print sheet still includes the Leaflet maps');
    if (!pr.body) errors.push('print sheet dropped the body of an open card');
    if (pr.closedBody) errors.push('print sheet includes every collapsed card — that is the whole app again');
    if (!pr.itin) errors.push('print sheet dropped the itinerary');
    await page.click('#card-mancos .card-head');
    await page.waitForTimeout(200);
  }

  console.log('\n--- Drone legality per stop ---');
  {
    const dr = await page.evaluate(() => {
      const ids = Object.keys(DRONE.stops || {});
      const counts = {};
      ids.forEach(i => counts[DRONE.stops[i].status] = (counts[DRONE.stops[i].status] || 0) + 1);
      const stops = STOPS.concat(EXT_DATA.STOPS || []).filter(s => s.nights);
      const missing = stops.filter(s => !DRONE.stops[s.id]).map(s => s.id);
      const noAlt = ids.filter(i => DRONE.stops[i].status === 'alt' && !DRONE.stops[i].alt);
      return { n: ids.length, counts, missing, noAlt,
               rendered: ids.filter(i => droneBlock(i)).length,
               yellowstone: DRONE.stops['yellowstone'].status,
               moab: DRONE.stops['moab'].status,
               kofa: DRONE.stops['kofa-nwr'].status,
               banff: DRONE.stops['banff'].status };
    });
    console.log(`  ${dr.n} stops classified, ${dr.rendered} render a block:`, JSON.stringify(dr.counts));
    console.log(`  Yellowstone ${dr.yellowstone} · Moab ${dr.moab} · Kofa ${dr.kofa} · Banff ${dr.banff}`);
    if (dr.missing.length) errors.push(dr.missing.length + ' stops with nights have no drone verdict: ' + dr.missing.slice(0,6).join(', '));
    if (dr.rendered !== dr.n) errors.push('drone block renders for only ' + dr.rendered + ' of ' + dr.n);
    if (dr.noAlt.length) errors.push('status "alt" with no alternative named: ' + dr.noAlt.join(', '));
    // The four that anchor the whole classification.
    if (dr.yellowstone !== 'no') errors.push('Yellowstone must be closed to drones');
    if (dr.kofa !== 'no') errors.push('Kofa is a wildlife refuge — must be closed');
    if (dr.banff !== 'no') errors.push('Banff is Parks Canada — must be closed');
    if (dr.moab !== 'yes') errors.push('Moab BLM must be flyable');
  }

  console.log('\n--- Aurora claimed only where it is on offer ---');
  {
    const a = await page.evaluate(() => {
      let bad = [];
      Object.keys(LIGHT).forEach(id => {
        const A = LIGHT[id].aurora;
        const should = !!(A && (A.verdict === 'prime' || A.verdict === 'good'));
        if (should !== lightTitle(id).includes('aurora')) bad.push(id + ':title');
        if (should !== lightBlock(id).includes('Aurora —')) bad.push(id + ':block');
      });
      return { bad, titled: Object.keys(LIGHT).filter(id => lightTitle(id).includes('aurora')).length,
               dv: lightTitle('death-valley'), dawson: lightTitle('dawson-city') };
    });
    console.log('  stops titled with aurora (expect 14):', a.titled);
    console.log('  Death Valley title (expect Light):', a.dv);
    console.log('  Dawson City title (expect Light & aurora):', a.dawson.replace('&amp;','&'));
    console.log('  mismatches (expect none):', a.bad.length ? a.bad.slice(0,5) : 'none');
    if (a.bad.length) errors.push('aurora shown where verdict does not justify it: ' + a.bad.slice(0,5).join(','));
    if (a.titled !== 14) errors.push('aurora-titled stop count is ' + a.titled + ', expected 14');
  }

  console.log('\n--- Build steps are idempotent ---');
  {
    const { execSync } = require('fs') && require('child_process');
    const crypto = require('crypto'), fs = require('fs');
    const desk = path.resolve(__dirname, '..', 'desktop', 'index.html');
    const before = crypto.createHash('md5').update(fs.readFileSync(desk)).digest('hex');
    let ok = true, err = '';
    for (const s of ['build_strategy','build_frozen','build_light','build_phonecraft','build_drone',
                     'build_passes','build_legs','build_costs','build_petlog','build_bookings','build_parks']) {
      try { execSync(`cd ${__dirname} && python3 ${s}.py`, { stdio: 'pipe' }); }
      catch (e) { ok = false; err += s + ' crashed on rerun; '; }
    }
    const after = crypto.createHash('md5').update(fs.readFileSync(desk)).digest('hex');
    console.log('  all eleven build steps rerun cleanly:', ok || err);
    console.log('  desktop byte-identical after rebuild:', before === after);
    if (!ok) errors.push('build step crashed on rerun: ' + err);
    if (before !== after) errors.push('rebuild changed desktop/index.html — a build step is not idempotent');
  }

  console.log('\n--- Map actually renders ---');
  await page.click('.tab-btn[data-view="overview"]');
  await page.waitForTimeout(700);
  const mapState = await page.evaluate(() => {
    const m = document.getElementById('map');
    return {
      leaflet: typeof L,
      inlined: !!document.querySelector('script') && document.documentElement.innerHTML.includes('leaflet inlined by build_vendor'),
      cdn: document.documentElement.innerHTML.includes('cdnjs.cloudflare.com'),
      panes: m ? m.querySelectorAll('.leaflet-pane').length : 0,
      paths: m ? m.querySelectorAll('path').length : 0,
      height: m ? Math.round(m.getBoundingClientRect().height) : 0,
      top: m ? Math.round(m.getBoundingClientRect().top + window.scrollY) : 0,
    };
  });
  console.log(`  leaflet=${mapState.leaflet} inlined=${mapState.inlined} cdn-ref=${mapState.cdn}`);
  console.log(`  map ${mapState.height}px tall at y=${mapState.top}, ${mapState.panes} panes, ${mapState.paths} route paths`);
  if (mapState.leaflet !== 'object') errors.push('Leaflet did not load');
  if (!mapState.inlined) errors.push('Leaflet is NOT inlined — the map will break with no signal');
  if (mapState.cdn) errors.push('build still references cdnjs');
  if (mapState.panes < 1) errors.push('map has no Leaflet panes — it did not initialise');
  if (mapState.paths < 50) errors.push('map drew only ' + mapState.paths + ' paths — route missing');
  if (mapState.top > 800) errors.push('map starts at y=' + mapState.top + ' — pushed below the fold');

  // A failed routing run used to wipe ROUTE_GEOM and leave the whole route as
  // dashed straight lines, which looks like "the map did not update". Assert
  // the coverage directly: every consecutive pair should have real geometry,
  // and the ones that do not are named so they cannot hide.
  {
    const geo = await page.evaluate(() => {
      const need = STOPS.slice(0, -1).map((s, i) => s.id + '>' + STOPS[i + 1].id);
      const needE = (EXT_DATA.STOPS || []).slice(0, -1)
        .map((s, i) => s.id + '>' + EXT_DATA.STOPS[i + 1].id);
      const stale = Object.keys(ROUTE_GEOM).filter(k => !need.includes(k));
      return { need: need.length, have: need.filter(k => ROUTE_GEOM[k]).length,
               missing: need.filter(k => !ROUTE_GEOM[k]), stale,
               needE: needE.length, haveE: needE.filter(k => EXT_ROUTE_GEOM[k]).length };
    });
    console.log(`  road geometry: main ${geo.have}/${geo.need}, east ${geo.haveE}/${geo.needE}`);
    if (geo.missing.length) console.log('    unrouted (dashed straight lines):', geo.missing.join(', '));
    if (geo.stale.length) console.log('    stale keys the map ignores:', geo.stale.join(', '));
    // Below about 80% the map reads as broken rather than merely incomplete.
    if (geo.have < geo.need * 0.8) errors.push(`only ${geo.have}/${geo.need} main legs have road geometry`);
    if (geo.haveE < geo.needE * 0.8) errors.push(`only ${geo.haveE}/${geo.needE} east legs have road geometry`);
    if (geo.stale.length) errors.push('ROUTE_GEOM holds ' + geo.stale.length + ' stale keys: ' + geo.stale.join(', '));
  }

  console.log('\n--- East Extension parity ---');
  const par = await page.evaluate(() => {
    const E = EXT_DATA.STOPS.filter(s => s.nights > 0);
    const n = k => E.reduce((a, s) => a + ((s[k] || []).length), 0);
    return { stops: E.length, poi: n('poi'), acts: n('activities'), towns: n('nearbyTowns'),
             offroad: n('offroad'), withPoi: E.filter(s => (s.poi || []).length).length,
             flagged: E.filter(s => (s.reviewFlags || []).length).length,
             mainActs: STOPS.reduce((a, s) => a + ((s.activities || []).length), 0) / STOPS.length };
  });
  console.log(`  ${par.stops} stops · ${par.poi} map points · ${par.acts} activities · ${par.towns} towns · ${par.offroad} 4x4`);
  console.log(`  stops with map points (was 0, expect all ${par.stops}):`, par.withPoi);
  if (par.poi < 380) errors.push('east POI count fell to ' + par.poi);
  if (par.withPoi < par.stops) errors.push(par.stops - par.withPoi + ' east stops still have no map points');
  const avgEast = par.acts / par.stops;
  console.log(`  activities per stop — east ${avgEast.toFixed(1)} vs main ${par.mainActs.toFixed(1)}`);
  if (avgEast < par.mainActs * 0.9) errors.push('east activities/stop ' + avgEast.toFixed(1) + ' still well below main');
  console.log('  stops carrying disputed-detail disclosures:', par.flagged);

  // Every booking must be reachable from the board — the bug was that 49 east ones were not.
  const reach = await page.evaluate(() => {
    const seen = new Set();
    ['main','east'].forEach(t => BOOKINGS.filter(b => b.trip === t).forEach(b => seen.add(b.id + b.trip)));
    return { total: BOOKINGS.length, reachable: seen.size,
             main: BOOKINGS.filter(b=>b.trip==='main').length,
             east: BOOKINGS.filter(b=>b.trip==='east').length };
  });
  console.log(`  bookings reachable by trip filter: ${reach.reachable}/${reach.total} (main ${reach.main}, east ${reach.east})`);
  if (reach.reachable !== reach.total) errors.push('some bookings unreachable by trip filter');
  if (!reach.east) errors.push('east bookings still unreachable');

  console.log('\n--- Booking board ---');
  const bk = await page.evaluate(() => {
    const m = Object.fromEntries(STOPS.map(s => [s.id, s]));
    const e = Object.fromEntries((EXT_DATA.STOPS || []).map(s => [s.id, s]));
    const stale = [], noWhat = [], noHow = [], badOpen = [];
    BOOKINGS.forEach(b => {
      const s = (b.trip === 'main' ? m[b.id] : e[b.id]) || m[b.id] || e[b.id];
      if (!s) { stale.push(b.id + ' (no such stop)'); return; }
      if (b.arrive !== s.arrive) stale.push(b.id + ' says ' + b.arrive + ', stop is ' + s.arrive);
      if (b.nights !== s.nights) stale.push(b.id + ' nights ' + b.nights + ' vs ' + s.nights);
      if (!b.what) noWhat.push(b.id);
      if (!b.howText) noHow.push(b.id);
      if (b.opensISO && b.opensISO >= b.arrive) badOpen.push(b.id);
    });
    return { total: BOOKINGS.length, stale, noWhat, noHow, badOpen,
             reserve: BOOKINGS.filter(b=>b.how==='reserve').length,
             call: BOOKINGS.filter(b=>b.how==='call').length,
             firstcome: BOOKINGS.filter(b=>b.how==='firstcome').length };
  });
  console.log('  bookings:', bk.total, '| reserve', bk.reserve, 'call', bk.call, 'first-come', bk.firstcome);
  console.log('  ' + (bk.stale.length ? 'FAIL' : 'ok ') + ' no booking card holds a stale date (expect 0):', bk.stale.length);
  if (bk.stale.length) { errors.push('stale booking cards: ' + bk.stale.slice(0,5).join('; ')); }
  console.log('  ' + (bk.noWhat.length ? 'FAIL' : 'ok ') + ' every card says WHAT to book (expect 0 missing):', bk.noWhat.length);
  if (bk.noWhat.length) errors.push('bookings with no what: ' + bk.noWhat.slice(0,5).join(','));
  console.log('  ' + (bk.noHow.length ? 'FAIL' : 'ok ') + ' every card says HOW to book (expect 0 missing):', bk.noHow.length);
  if (bk.noHow.length) errors.push('bookings with no howText: ' + bk.noHow.slice(0,5).join(','));
  console.log('  ' + (bk.badOpen.length ? 'FAIL' : 'ok ') + ' no window opens after arrival (expect 0):', bk.badOpen.length);
  if (bk.badOpen.length) errors.push('bookings opening after arrival: ' + bk.badOpen.join(','));

  console.log('\n--- Seasonal timing anchors ---');
  const timing = await page.evaluate(() => {
    const m = Object.fromEntries(STOPS.map(s => [s.id, s]));
    const e = Object.fromEntries((EXT_DATA.STOPS || []).map(s => [s.id, s]));
    return {
      sequoia: m['sequoia-kings-canyon'].arrive, denali: m['denali'].arrive,
      dawson: m['dawson-city'].arrive, winthrop: m['winthrop'].arrive,
      teton: m['grand-teton'].arrive, yellowIn: m['yellowstone'].arrive,
      twinFalls: m['twin-falls'].arrive, westYell: m['west-yellowstone'].arrive,
      glacier: m['glacier'].arrive,
      idahoBeforeParks: STOPS.findIndex(s=>s.id==='twin-falls') < STOPS.findIndex(s=>s.id==='grand-teton'),
      longBeach: m['long-beach'].arrive, imperialDam: m['imperial-dam'].arrive,
      yuma: m['yuma-az'].arrive, quartzsiteGone: STOPS.some(s => s.id === 'quartzsite'),
      moabIn: m['moab'].arrive, moabOut: m['moab'].depart,
      pagosa: m['pagosa-springs'].arrive,
      mainNights: STOPS.reduce((a, s) => a + s.nights, 0),
      mainEnd: STOPS[STOPS.length - 1].depart,
      stowe: e['stowe-vt'].arrive, townships: e['eastern-townships-qc'].arrive,
      barHarbor: e['bar-harbor-me'].arrive, porkies: e['porcupine-mountains-mi'].nights,
    };
  });
  const want = {
    sequoia: '2027-12-23', denali: '2027-07-29', dawson: '2027-08-30', winthrop: '2027-10-03',
    // Idaho runs ahead of the parks so Teton and Yellowstone land after their
    // campgrounds open; West Yellowstone sits before Yellowstone as the buffer.
    teton: '2027-05-07', yellowIn: '2027-05-15', twinFalls: '2027-05-01',
    westYell: '2027-05-12', glacier: '2027-05-22', idahoBeforeParks: true,
    longBeach: '2027-10-29', imperialDam: '2028-01-14', yuma: '2028-01-18',
    quartzsiteGone: false, moabIn: '2028-04-01',
    pagosa: '2028-04-27', mainNights: 405, mainEnd: '2028-04-30',
    stowe: '2028-10-01', townships: '2028-10-05', barHarbor: '2028-10-16', porkies: 5,
  };
  for (const [k, v] of Object.entries(want)) {
    const ok = timing[k] === v;
    console.log(`  ${ok ? 'ok ' : 'FAIL'} ${k}: ${timing[k]}${ok ? '' : '  (expected ' + v + ')'}`);
    if (!ok) errors.push(`timing ${k} is ${timing[k]}, expected ${v}`);
  }
  // Moab must be out of town before Easter Jeep Safari opens on ~Apr 8, 2028
  const ejsClear = timing.moabOut <= '2028-04-08';
  console.log('  ' + (ejsClear ? 'ok ' : 'FAIL') + ' Moab departs ' + timing.moabOut + ' (EJS starts ~Apr 8)');
  if (!ejsClear) errors.push('Moab overlaps Easter Jeep Safari');

  console.log('\nPage errors:', errors.length);
  errors.forEach(e => console.log('  ERR:', e));

  await browser.close();
  process.exit(errors.length ? 1 : 0);
})();
