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
  console.log('Extension known-issue cards, open only by default (expect 15):', extIssueCards);
  if (extIssueCards !== 15) errors.push('ext open-issue count is ' + extIssueCards + ', expected 15');
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
  if (mainIssueCards !== 18) errors.push('main open-issue count is ' + mainIssueCards + ', expected 18');
  // Resolved items must still be reachable — they are the record of why a date is what it is.
  await page.click('#issueCatBar button[data-f="all"]');
  await page.waitForTimeout(200);
  const allIssueCards = await page.locator('#issuesWrap .issue-card').count();
  console.log('Main issue cards with "Everything, incl. resolved" (expect 30):', allIssueCards);
  if (allIssueCards !== 30) errors.push('main all-issue count is ' + allIssueCards + ', expected 30');
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
  const larchSeg = page.locator('#stratMain .strat-seg').nth(3);
  await larchSeg.hover();
  await page.waitForTimeout(120);
  const noteText = await page.locator('#stratMainNote').innerText();
  console.log('Hover note names Winthrop (expect true):', /Winthrop/.test(noteText));
  if (!/Winthrop/.test(noteText)) errors.push('larch hover note does not name Winthrop: ' + noteText.slice(0, 120));

  // ---- Seasonal timing: every anchor must sit on the window it exists for.
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
      longBeach: m['long-beach'].arrive, quartzsite: m['quartzsite'].arrive,
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
    longBeach: '2027-10-29', quartzsite: '2028-01-14', moabIn: '2028-04-01',
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
