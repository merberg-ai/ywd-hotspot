'use strict';
(() => {
  let installed = false;
  let control = null;
  let directoryMeta = null;
  let searchRows = [];
  let searchTimer = null;
  let pollTimer = null;

  const el = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({
    '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'
  }[c]));
  const notify = (message, bad=false) => {
    if (typeof toast === 'function') toast(message, bad);
    else (bad ? console.error : console.log)(message);
  };
  const authenticated = () => !!(typeof state !== 'undefined' && state?.controls?.authenticated);
  const tgifEnabled = () => !!(typeof state !== 'undefined' && state?.config?.tgif?.enabled);
  const radioMode = () => String((typeof state !== 'undefined' && state?.config?.radio?.mode) || 'simplex').toLowerCase();

  async function apiGet(path) {
    const response = await fetch(path, {cache:'no-store', credentials:'same-origin'});
    const data = await response.json().catch(() => ({error:`HTTP ${response.status}`}));
    if (!response.ok || data.ok === false) throw new Error(data.error || `HTTP ${response.status}`);
    return data;
  }

  async function apiPost(path, body={}) {
    const response = await fetch(path, {
      method:'POST', credentials:'same-origin',
      headers:{'Content-Type':'application/json'}, body:JSON.stringify(body || {})
    });
    const data = await response.json().catch(() => ({error:`HTTP ${response.status}`}));
    if (!response.ok || data.ok === false) throw new Error(data.error || `HTTP ${response.status}`);
    return data;
  }

  function clone(value) { return JSON.parse(JSON.stringify(value)); }

  function prefs() {
    return clone(control?.preferences || {
      schema:1, favorites:[], watchlist:[], dwell_s:5, hold_s:3, slot:2
    });
  }

  function normalizeOrder(rows) {
    return (rows || []).slice(0,10).map((row, index) => ({
      id:Number(row.id), name:String(row.name || ''), priority:index + 1, enabled:row.enabled !== false
    }));
  }

  function currentFormPrefs() {
    const p = prefs();
    const dwell = Number(el('tgifCcDwell')?.value ?? p.dwell_s);
    const hold = Number(el('tgifCcHold')?.value ?? p.hold_s);
    const slot = Number(el('tgifCcSlot')?.value ?? p.slot);
    p.dwell_s = Number.isFinite(dwell) ? Math.max(2, Math.min(60, Math.round(dwell))) : 5;
    p.hold_s = Number.isFinite(hold) ? Math.max(0, Math.min(30, Math.round(hold))) : 3;
    p.slot = radioMode() === 'duplex' && [1,2].includes(slot) ? slot : 2;
    p.watchlist = normalizeOrder(p.watchlist);
    return p;
  }

  async function savePrefs(next=currentFormPrefs(), quiet=false) {
    if (!authenticated()) throw new Error('Unlock WebUI controls first');
    const data = await apiPost('/api/tgif/control/save', {preferences:next});
    control = {...(control || {}), preferences:data.preferences, service_active:data.service_active};
    renderAll();
    if (!quiet) notify('TGIF watchlist settings saved');
    return data.preferences;
  }

  async function scannerAction(operation, body={}) {
    if (!authenticated()) return notify('Unlock WebUI controls first', true);
    try {
      if (operation === 'start') await savePrefs(currentFormPrefs(), true);
      const data = await apiPost(`/api/tgif/control/${operation}`, body);
      if (data.preferences || data.runtime || Object.prototype.hasOwnProperty.call(data,'service_active')) control = data;
      await refreshControl();
      const labels = {
        start:'TGIF scanner started', stop:'TGIF scanner stopped', hold:'TGIF scanner hold requested',
        resume:'TGIF scanner resumed', next:'Skipping to next TGIF watch entry', disconnect:'TGIF session disconnected'
      };
      notify(labels[operation] || 'TGIF control updated');
    } catch (err) { notify(err.message, true); }
  }

  async function tuneNow(row) {
    if (!authenticated()) return notify('Unlock WebUI controls first', true);
    const tg = Number(row?.id ?? row);
    if (!Number.isInteger(tg)) return;
    try {
      const data = await apiPost('/api/tgif/control/tune', {talkgroup:tg});
      notify(`TGIF pinned to TG ${tg} · RF ${data.rf_talkgroup}`);
      await refreshControl();
    } catch (err) { notify(err.message, true); }
  }

  function isFavorite(id) { return (prefs().favorites || []).some(row => Number(row.id) === Number(id)); }
  function isWatched(id) { return (prefs().watchlist || []).some(row => Number(row.id) === Number(id)); }

  async function toggleFavorite(row) {
    const p = currentFormPrefs();
    const id = Number(row.id);
    const index = p.favorites.findIndex(item => Number(item.id) === id);
    if (index >= 0) p.favorites.splice(index,1);
    else p.favorites.push({id, name:String(row.name || '')});
    try { await savePrefs(p, true); notify(index >= 0 ? `Removed TG ${id} from favorites` : `Saved TG ${id} as a favorite`); }
    catch (err) { notify(err.message, true); }
  }

  async function toggleWatch(row) {
    const p = currentFormPrefs();
    const id = Number(row.id);
    const index = p.watchlist.findIndex(item => Number(item.id) === id);
    if (index >= 0) p.watchlist.splice(index,1);
    else {
      if (p.watchlist.length >= 10) return notify('TGIF scanner watchlist is limited to 10 talkgroups', true);
      p.watchlist.push({id, name:String(row.name || ''), priority:p.watchlist.length + 1, enabled:true});
    }
    p.watchlist = normalizeOrder(p.watchlist);
    try { await savePrefs(p, true); notify(index >= 0 ? `Removed TG ${id} from watchlist` : `Added TG ${id} to scanner watchlist`); }
    catch (err) { notify(err.message, true); }
  }

  async function moveWatch(index, delta) {
    const p = currentFormPrefs();
    const next = index + delta;
    if (index < 0 || next < 0 || next >= p.watchlist.length) return;
    [p.watchlist[index], p.watchlist[next]] = [p.watchlist[next], p.watchlist[index]];
    p.watchlist = normalizeOrder(p.watchlist);
    try { await savePrefs(p, true); } catch (err) { notify(err.message, true); }
  }

  async function removeWatch(index) {
    const p = currentFormPrefs();
    const row = p.watchlist[index];
    if (!row) return;
    p.watchlist.splice(index,1);
    p.watchlist = normalizeOrder(p.watchlist);
    try { await savePrefs(p, true); notify(`Removed TG ${row.id} from scanner watchlist`); }
    catch (err) { notify(err.message, true); }
  }

  async function copyRf(row) {
    if (row?.rf_talkgroup == null) return notify('This TGIF talkgroup is outside the current RF namespace', true);
    const value = String(row.rf_talkgroup);
    try {
      if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(value);
      else {
        const input = document.createElement('textarea'); input.value = value; input.style.position='fixed'; input.style.opacity='0';
        document.body.appendChild(input); input.select(); document.execCommand('copy'); input.remove();
      }
      notify(`Copied RF TG ${value}`);
    } catch (_) { notify(`RF destination: ${value}`); }
  }

  async function directoryApi(params) {
    const url = new URL('/api/tgif/talkgroups/search', location.origin);
    Object.entries(params || {}).forEach(([key,value]) => {
      if (value !== '' && value != null) url.searchParams.set(key,String(value));
    });
    const data = await apiGet(url.toString());
    directoryMeta = data;
    return data;
  }

  async function searchDirectory(refresh=false) {
    const q = el('tgifCcSearch')?.value.trim() || '';
    const body = el('tgifCcSearchRows');
    if (!q) {
      if (body) body.innerHTML = '<tr><td colspan="4">Search by TGIF talkgroup number or name.</td></tr>';
      return;
    }
    if (body) body.innerHTML = '<tr><td colspan="4">Searching TGIF directory…</td></tr>';
    try {
      const data = await directoryApi({q,limit:50,refresh:refresh?1:0});
      searchRows = data.results || [];
      renderDirectory();
      if (refresh) notify(`TGIF directory refreshed · ${data.directory_count || 0} talkgroups`);
    } catch (err) {
      if (body) body.innerHTML = `<tr><td colspan="4">${esc(err.message)}</td></tr>`;
      notify(err.message,true);
    }
  }

  function renderDirectory() {
    const body = el('tgifCcSearchRows');
    if (!body) return;
    body.innerHTML = searchRows.length ? searchRows.map((row,index) => {
      const supported = row.supported !== false && row.rf_talkgroup != null;
      return `<tr>
        <td class="tg-id">${esc(row.id)}</td>
        <td>${esc(row.name || '')}</td>
        <td>${supported ? `<span class="tg-id">${esc(row.rf_talkgroup)}</span>` : '<span class="hint">routing limit</span>'}</td>
        <td><div class="tgif-dir-actions">
          <button class="btn tiny ctl" data-cc-fav="${index}" type="button">${isFavorite(row.id)?'★':'☆'} FAV</button>
          ${supported ? `<button class="btn tiny ctl" data-cc-watch="${index}" type="button">${isWatched(row.id)?'− WATCH':'+ WATCH'}</button><button class="btn tiny ctl" data-cc-tune="${index}" type="button">TUNE</button><button class="btn tiny" data-cc-copy="${index}" type="button">COPY RF</button>` : ''}
        </div></td>
      </tr>`;
    }).join('') : '<tr><td colspan="4">No matching TGIF talkgroups.</td></tr>';
    body.querySelectorAll('[data-cc-fav]').forEach(b => b.onclick=()=>toggleFavorite(searchRows[Number(b.dataset.ccFav)]));
    body.querySelectorAll('[data-cc-watch]').forEach(b => b.onclick=()=>toggleWatch(searchRows[Number(b.dataset.ccWatch)]));
    body.querySelectorAll('[data-cc-tune]').forEach(b => b.onclick=()=>tuneNow(searchRows[Number(b.dataset.ccTune)]));
    body.querySelectorAll('[data-cc-copy]').forEach(b => b.onclick=()=>copyRf(searchRows[Number(b.dataset.ccCopy)]));
    if (el('tgifCcDirectoryMeta')) {
      const age = directoryMeta?.cached_at && typeof ago === 'function' ? ago(directoryMeta.cached_at) : 'cached';
      el('tgifCcDirectoryMeta').textContent = directoryMeta ? `${directoryMeta.directory_count || 0} TGs · ${directoryMeta.stale?'stale':'cached'} · ${age}` : 'directory not loaded';
    }
    syncLockedControls();
  }

  function renderWatchlist() {
    const host = el('tgifCcWatchRows'); if (!host) return;
    const rows = prefs().watchlist || [];
    host.innerHTML = rows.length ? rows.map((row,index) => `<div class="tgif-watch-row">
      <div class="tgif-watch-priority">P${index+1}</div>
      <div class="tgif-watch-name"><b>TG ${esc(row.id)}</b>${row.name?` · ${esc(row.name)}`:''}<small>RF ${5_000_000 + Number(row.id)}</small></div>
      <div class="tgif-watch-actions"><button class="btn tiny ctl" data-watch-up="${index}" type="button">↑</button><button class="btn tiny ctl" data-watch-down="${index}" type="button">↓</button><button class="btn tiny ctl" data-watch-tune="${index}" type="button">TUNE</button><button class="btn tiny danger ctl" data-watch-remove="${index}" type="button">×</button></div>
    </div>`).join('') : '<div class="hint">No TGIF scan talkgroups yet. Add up to 10 from the directory below.</div>';
    host.querySelectorAll('[data-watch-up]').forEach(b=>b.onclick=()=>moveWatch(Number(b.dataset.watchUp),-1));
    host.querySelectorAll('[data-watch-down]').forEach(b=>b.onclick=()=>moveWatch(Number(b.dataset.watchDown),1));
    host.querySelectorAll('[data-watch-tune]').forEach(b=>b.onclick=()=>tuneNow(rows[Number(b.dataset.watchTune)]));
    host.querySelectorAll('[data-watch-remove]').forEach(b=>b.onclick=()=>removeWatch(Number(b.dataset.watchRemove)));
  }

  function renderFavorites() {
    const host = el('tgifCcFavorites'); if (!host) return;
    const rows = prefs().favorites || [];
    host.innerHTML = rows.length ? `<div class="tgif-favorite-grid">${rows.map((row,index)=>`<div class="tgif-favorite-chip"><span><b>${esc(row.id)}</b>${row.name?`<br><small>${esc(row.name)}</small>`:''}</span><span><button class="btn tiny ctl" data-fav-watch="${index}" type="button">${isWatched(row.id)?'WATCHED':'+ WATCH'}</button> <button class="btn tiny ctl" data-fav-tune="${index}" type="button">TUNE</button> <button class="btn tiny danger ctl" data-fav-remove="${index}" type="button">×</button></span></div>`).join('')}</div>` : '<div class="hint">No appliance TGIF favorites yet.</div>';
    host.querySelectorAll('[data-fav-watch]').forEach(b=>b.onclick=()=>toggleWatch(rows[Number(b.dataset.favWatch)]));
    host.querySelectorAll('[data-fav-tune]').forEach(b=>b.onclick=()=>tuneNow(rows[Number(b.dataset.favTune)]));
    host.querySelectorAll('[data-fav-remove]').forEach(b=>b.onclick=()=>toggleFavorite(rows[Number(b.dataset.favRemove)]));
  }

  function renderScanner() {
    if (!control) return;
    const runtime = control.runtime || {};
    const active = !!control.service_active;
    const inactiveState = ['tuned','disconnected'].includes(String(runtime.state || '').toLowerCase())
      ? String(runtime.state).toUpperCase()
      : 'STOPPED';
    let scannerState = active ? String(runtime.state || 'starting').toUpperCase() : inactiveState;
    const stateNode = el('tgifCcScannerState');
    if (stateNode) {
      stateNode.textContent = scannerState;
      stateNode.className = `scanner-state ${scannerState.includes('HOLD')?'holding':''} ${scannerState.includes('ERROR')?'error':''}`;
    }
    const tg = runtime.current_tg;
    if (el('tgifCcScannerTg')) el('tgifCcScannerTg').textContent = tg ? `TG ${tg}${runtime.current_name?' · '+runtime.current_name:''}` : 'No talkgroup selected';
    if (el('tgifCcScannerRf')) el('tgifCcScannerRf').textContent = runtime.current_rf_tg ? `Radio destination ${runtime.current_rf_tg} · TS${runtime.slot || control.preferences?.slot || 2}` : 'Scanner is idle';
    if (el('tgifCcScannerDetail')) {
      let detail;
      if (!active && String(runtime.state || '').toLowerCase() === 'tuned') detail = 'TGIF session pinned · scanner stopped';
      else if (!active && String(runtime.state || '').toLowerCase() === 'disconnected') detail = 'TGIF session disconnected with TG 4000';
      else detail = runtime.hold_reason ? `Hold: ${String(runtime.hold_reason).replace('-',' ')}` : active ? `${Math.ceil(Number(runtime.dwell_remaining_s || 0))}s dwell remaining` : 'Start scan when ready';
      if (runtime.error) detail = runtime.error;
      el('tgifCcScannerDetail').textContent = detail;
    }
    if (el('tgifCcDwell') && document.activeElement !== el('tgifCcDwell')) el('tgifCcDwell').value = control.preferences?.dwell_s ?? 5;
    if (el('tgifCcHold') && document.activeElement !== el('tgifCcHold')) el('tgifCcHold').value = control.preferences?.hold_s ?? 3;
    if (el('tgifCcSlot') && document.activeElement !== el('tgifCcSlot')) el('tgifCcSlot').value = control.preferences?.slot ?? 2;
    if (el('tgifCcSlotField')) el('tgifCcSlotField').hidden = radioMode() !== 'duplex';
    ['tgifCcStart','tgifCcHoldBtn','tgifCcResume','tgifCcNext','tgifCcStop'].forEach(id => { const b=el(id); if(b) b.dataset.runtimeActive=active?'1':'0'; });
  }

  function renderNetwork(data) {
    const tg = data?.tgif || {};
    if (el('tgifCcLink')) el('tgifCcLink').textContent = String(tg.state || (tgifEnabled()?'connecting':'disabled')).replace(/-/g,' ').toUpperCase();
    if (el('tgifCcMaster')) el('tgifCcMaster').textContent = tg.master || data?.config?.tgif?.master || 'tgif.network';
    if (el('tgifCcHotspotId')) el('tgifCcHotspotId').textContent = data?.config?.station?.hotspot_id || control?.hotspot_id || '—';
    if (el('tgifCcNamespace')) el('tgifCcNamespace').textContent = '5000001–5999999';
    const current = data?.activity?.current || {};
    const dst = current.destination || {};
    const live = current.active && dst.network === 'tgif';
    if (el('tgifCcLive')) {
      if (live) {
        const src = current.source?.display || '?';
        el('tgifCcLive').innerHTML = `<span class="dot good"></span><b>${esc(src)}</b> → TG ${esc(dst.network_id)}${dst.name?' · '+esc(dst.name):''}`;
      } else el('tgifCcLive').innerHTML = '<span class="dot"></span>Waiting for TGIF network traffic';
    }

    const rows = (data?.activity?.lastheard || []).filter(row => row?.destination?.network === 'tgif').slice(0,20);
    const body = el('tgifCcHeardRows');
    if (body) body.innerHTML = rows.length ? rows.map(row => {
      const dst2 = row.destination || {};
      const when = typeof ago === 'function' ? ago(row.started_at) : '—';
      const duration = typeof dur === 'function' ? dur(row.duration_s) : (row.duration_s ?? '—');
      return `<tr><td>${esc(when)}</td><td>${esc(row.source?.display || '?')}</td><td>TG ${esc(dst2.network_id || '?')}${dst2.name?' · '+esc(dst2.name):''}</td><td>RF ${esc(dst2.rf_id || '?')}</td><td>${esc(duration)}</td></tr>`;
    }).join('') : '<tr><td colspan="5">No TGIF calls captured yet.</td></tr>';
  }

  function syncLockedControls() {
    const locked = !authenticated();
    document.querySelectorAll('#tgifControlPage .ctl').forEach(node => { node.disabled = locked; });
    const active = !!control?.service_active;
    if (el('tgifCcStart')) el('tgifCcStart').disabled = locked || active || !(prefs().watchlist || []).length;
    if (el('tgifCcHoldBtn')) el('tgifCcHoldBtn').disabled = locked || !active;
    if (el('tgifCcResume')) el('tgifCcResume').disabled = locked || !active;
    if (el('tgifCcNext')) el('tgifCcNext').disabled = locked || !active;
    if (el('tgifCcStop')) el('tgifCcStop').disabled = locked || !active;
    if (el('tgifCcDirectoryRefresh')) el('tgifCcDirectoryRefresh').disabled = locked;
  }

  function renderAll() {
    renderScanner(); renderWatchlist(); renderFavorites(); renderDirectory();
    if (typeof state !== 'undefined' && state) renderNetwork(state);
    syncLockedControls();
  }

  async function refreshControl() {
    if (!tgifEnabled()) return;
    try {
      control = await apiGet('/api/tgif/control/status');
      renderAll();
    } catch (err) {
      if (el('tgifCcScannerDetail')) el('tgifCcScannerDetail').textContent = err.message;
    }
  }

  function openPage() {
    document.querySelectorAll('.tabs button').forEach(node => node.classList.remove('on'));
    document.querySelectorAll('.page').forEach(node => node.classList.remove('on'));
    el('tgifControlTab')?.classList.add('on');
    el('tgifControlPage')?.classList.add('on');
    refreshControl();
    renderNetwork(typeof state !== 'undefined' ? state : null);
  }

  function showStatusPage() {
    const button = document.querySelector('.tabs [data-tab="status"]');
    const page = el('status');
    if (!button || !page) return;
    document.querySelectorAll('.tabs button').forEach(node => node.classList.remove('on'));
    document.querySelectorAll('.page').forEach(node => node.classList.remove('on'));
    button.classList.add('on'); page.classList.add('on');
  }

  function syncVisibility(data) {
    const enabled = !!data?.config?.tgif?.enabled;
    const tab = el('tgifControlTab'), page = el('tgifControlPage');
    if (!tab || !page) return;
    tab.hidden = !enabled;
    page.hidden = !enabled;
    if (!enabled && page.classList.contains('on')) showStatusPage();
    if (enabled && !pollTimer) pollTimer = setInterval(() => { if (el('tgifControlPage')?.classList.contains('on')) refreshControl(); }, 1000);
  }

  function install() {
    if (installed) return true;
    const tabs = document.querySelector('.tabs');
    const main = document.querySelector('main');
    if (!tabs || !main) return false;

    const tab = document.createElement('button');
    tab.id = 'tgifControlTab'; tab.dataset.tab = 'tgif-control'; tab.textContent = 'TGIF'; tab.hidden = true;
    const tgTab = tabs.querySelector('[data-tab="talkgroups"]');
    const controlTab = tabs.querySelector('[data-tab="control"]');
    (tgTab || controlTab)?.insertAdjacentElement('afterend', tab);

    const page = document.createElement('section');
    page.className='page'; page.id='tgifControlPage'; page.hidden=true;
    page.innerHTML = `
      <div class="tgif-control-note"><strong>TGIF WATCHLIST SCANNER</strong> changes the TGIF network session without keying RF. To hear arbitrary scanned destinations, your radio must accept them with Open RX / Promiscuous / Digital Monitor or equivalent.</div>
      <div class="grid two">
        <article class="card"><div class="card-title title-row"><span>TGIF NETWORK</span><span id="tgifCcLink" class="badge">—</span></div><div class="tgif-network-grid"><div class="kv"><span>Master</span><b id="tgifCcMaster">—</b></div><div class="kv"><span>Hotspot ID</span><b id="tgifCcHotspotId">—</b></div><div class="kv"><span>RF namespace</span><b id="tgifCcNamespace">5000001–5999999</b></div><div class="kv"><span>Scanner limit</span><b>10 TGs</b></div></div><hr><div id="tgifCcLive" class="tgif-mini-active"><span class="dot"></span>Waiting for TGIF network traffic</div></article>
        <article class="card"><div class="card-title">WATCHLIST SCANNER</div><div class="tgif-control-hero"><div><div id="tgifCcScannerState" class="scanner-state">STOPPED</div><div id="tgifCcScannerTg" class="scanner-tg">No talkgroup selected</div><div id="tgifCcScannerRf" class="scanner-rf">Scanner is idle</div><div id="tgifCcScannerDetail" class="hint">Start scan when ready</div></div><div><p class="hint">P1 is checked first; reorder the watchlist to change scan priority/order. Traffic automatically holds the current TG through the configured post-call delay.</p></div></div><div class="tgif-scanner-settings"><div class="field"><label>DWELL SEC</label><input id="tgifCcDwell" type="number" min="2" max="60" value="5"></div><div class="field"><label>POST-CALL HOLD SEC</label><input id="tgifCcHold" type="number" min="0" max="30" value="3"></div><div class="field" id="tgifCcSlotField"><label>SCAN TIMESLOT</label><select id="tgifCcSlot"><option value="1">TS1</option><option value="2" selected>TS2</option></select></div></div><div class="tgif-scanner-controls"><button class="btn ctl" id="tgifCcSave" type="button">SAVE SETTINGS</button><button class="btn good ctl" id="tgifCcStart" type="button">START SCAN</button><button class="btn ctl" id="tgifCcHoldBtn" type="button">HOLD</button><button class="btn ctl" id="tgifCcResume" type="button">RESUME</button><button class="btn ctl" id="tgifCcNext" type="button">NEXT</button><button class="btn danger ctl" id="tgifCcStop" type="button">STOP</button><button class="btn danger ctl" id="tgifCcDisconnect" type="button">DISCONNECT TGIF</button></div></article>
      </div>
      <div class="grid two"><article class="card"><div class="card-title title-row"><span>SCAN WATCHLIST</span><span class="hint">max 10</span></div><div id="tgifCcWatchRows"></div></article><article class="card"><div class="card-title">APPLIANCE FAVORITES</div><p class="hint">These favorites live on the hotspot, not in this browser.</p><div id="tgifCcFavorites"></div></article></div>
      <article class="card"><div class="card-title title-row"><span>TGIF TALKGROUP DIRECTORY</span><span id="tgifCcDirectoryMeta" class="hint">directory not loaded</span></div><div class="field inline"><label>SEARCH TG ID OR NAME</label><input id="tgifCcSearch" placeholder="TGIF, DX, 31665…" maxlength="80"><button class="btn" id="tgifCcSearchBtn" type="button">SEARCH</button><button class="btn ctl" id="tgifCcDirectoryRefresh" type="button">REFRESH</button></div><div class="tablewrap"><table><thead><tr><th>TGIF TG</th><th>NAME</th><th>RADIO TG</th><th>ACTIONS</th></tr></thead><tbody id="tgifCcSearchRows"><tr><td colspan="4">Search by TGIF talkgroup number or name.</td></tr></tbody></table></div></article>
      <article class="card"><div class="card-title">RECENT TGIF ACTIVITY</div><div class="tablewrap"><table><thead><tr><th>WHEN</th><th>SOURCE</th><th>TGIF DEST</th><th>RF DEST</th><th>DURATION</th></tr></thead><tbody id="tgifCcHeardRows"><tr><td colspan="5">No TGIF calls captured yet.</td></tr></tbody></table></div></article>`;
    main.appendChild(page);

    tab.onclick = openPage;
    el('tgifCcSave').onclick = () => savePrefs(currentFormPrefs()).catch(err=>notify(err.message,true));
    el('tgifCcStart').onclick = () => scannerAction('start');
    el('tgifCcHoldBtn').onclick = () => scannerAction('hold');
    el('tgifCcResume').onclick = () => scannerAction('resume');
    el('tgifCcNext').onclick = () => scannerAction('next');
    el('tgifCcStop').onclick = () => scannerAction('stop');
    el('tgifCcDisconnect').onclick = () => scannerAction('disconnect');
    el('tgifCcSearchBtn').onclick = () => searchDirectory(false);
    el('tgifCcDirectoryRefresh').onclick = () => searchDirectory(true);
    el('tgifCcSearch').oninput = () => { clearTimeout(searchTimer); searchTimer=setTimeout(()=>searchDirectory(false),280); };
    el('tgifCcSearch').onkeydown = event => { if(event.key==='Enter'){event.preventDefault();searchDirectory(false);} };

    if (typeof render === 'function' && !render.__ywdTgifControlWrapped) {
      const baseRender = render;
      const wrapped = function(data) {
        const out = baseRender(data);
        syncVisibility(data); renderNetwork(data); syncLockedControls();
        return out;
      };
      wrapped.__ywdTgifControlWrapped = true;
      render = wrapped;
    }

    installed=true;
    syncVisibility(typeof state !== 'undefined' ? state : null);
    if (tgifEnabled()) refreshControl();
    return true;
  }

  const timer=setInterval(()=>{if(install())clearInterval(timer);},120);
  setTimeout(()=>clearInterval(timer),15000);
})();
