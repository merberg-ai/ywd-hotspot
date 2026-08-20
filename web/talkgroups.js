'use strict';

const TG_FAVORITES_KEY = 'ywd.tgFavorites.v1';
const TG_SETS_KEY = 'ywd.tgSets.v2';
const TG_LEGACY_SETS_KEY = 'ywd.tgSets.v1';
const TG_SLOT_KEY = 'ywd.tgSelectedSlot.v1';
let tgPlan = null;
let tgPlanDirty = false;
let tgNames = new Map();
let tgDirectoryMeta = null;
let tgSearchTimer = null;
let tgSelectedSlot = Number(localStorage.getItem(TG_SLOT_KEY) || 2);

function tgLoadJson(key, fallback) {
  try {
    const v = JSON.parse(localStorage.getItem(key) || 'null');
    return v ?? fallback;
  } catch (_) { return fallback; }
}
function tgSaveJson(key, value) { localStorage.setItem(key, JSON.stringify(value)); }
function tgIsDuplex() { return String(state?.config?.radio?.mode || 'simplex').toLowerCase() === 'duplex'; }
function tgAllowedSlots() { return tgIsDuplex() ? [1, 2] : [0]; }
function tgSlotLabel(slot) { return Number(slot) === 0 ? 'SIMPLEX' : `TS${Number(slot)}`; }
function tgEnsureSelectedSlot() {
  const allowed = tgAllowedSlots();
  if (!allowed.includes(Number(tgSelectedSlot))) tgSelectedSlot = allowed[allowed.length - 1];
  return Number(tgSelectedSlot);
}
function tgSetSelectedSlot(slot) {
  slot = Number(slot);
  if (!tgAllowedSlots().includes(slot)) return;
  tgSelectedSlot = slot;
  localStorage.setItem(TG_SLOT_KEY, String(slot));
  tgRender(state);
  if ($('tgSearch')?.value.trim()) tgSearch(false);
}
function tgRouteKey(slot, talkgroup) { return `${Number(slot)}:${Number(talkgroup)}`; }
function tgRouteFromKey(key) {
  const [slotRaw, tgRaw] = String(key).split(':', 2);
  const slot = Number(slotRaw), talkgroup = Number(tgRaw);
  if (!Number.isInteger(slot) || !Number.isInteger(talkgroup) || talkgroup < 1 || talkgroup > 16777215) return null;
  return {slot, talkgroup};
}
function tgRouteSort(a, b) {
  const ra = tgRouteFromKey(a), rb = tgRouteFromKey(b);
  if (!ra || !rb) return String(a).localeCompare(String(b));
  return ra.slot - rb.slot || ra.talkgroup - rb.talkgroup;
}
function tgCurrentRoutes() {
  return new Set((state?.brandmeister?.static || []).map(x => {
    const tg = Number(x.talkgroup), slot = Number(x.slot ?? 0);
    return Number.isInteger(tg) && Number.isInteger(slot) ? tgRouteKey(slot, tg) : null;
  }).filter(Boolean));
}
function tgFavorites() {
  return (tgLoadJson(TG_FAVORITES_KEY, []) || [])
    .filter(x => Number.isInteger(Number(x?.id)))
    .map(x => ({id:Number(x.id), name:String(x.name || '')}));
}
function tgSets() {
  const saved = tgLoadJson(TG_SETS_KEY, null);
  if (Array.isArray(saved)) {
    return saved.filter(x => x && typeof x.name === 'string' && Array.isArray(x.routes)).map(x => ({
      name:x.name.slice(0,40),
      routes:x.routes.map(r => tgRouteFromKey(typeof r === 'string' ? r : tgRouteKey(r?.slot, r?.talkgroup)))
        .filter(Boolean).map(r => tgRouteKey(r.slot, r.talkgroup))
    }));
  }
  if (!state) return [];
  const legacy = tgLoadJson(TG_LEGACY_SETS_KEY, []);
  if (!Array.isArray(legacy) || !legacy.length) return [];
  const slot = tgEnsureSelectedSlot();
  const migrated = legacy.filter(x => x && typeof x.name === 'string' && Array.isArray(x.ids)).map(x => ({
    name:x.name.slice(0,40),
    routes:x.ids.map(Number).filter(Number.isInteger).map(id => tgRouteKey(slot, id))
  }));
  if (migrated.length) tgSaveJson(TG_SETS_KEY, migrated);
  return migrated;
}
function tgName(id, fallback='') { return tgNames.get(Number(id)) || fallback || ''; }
function tgRememberRows(rows) { (rows || []).forEach(x => { if (Number.isInteger(Number(x.id))) tgNames.set(Number(x.id), String(x.name || '')); }); }
function tgDiff() {
  const current = tgCurrentRoutes();
  const plan = tgPlan || new Set(current);
  return {
    add: [...plan].filter(x => !current.has(x)).sort(tgRouteSort),
    remove: [...current].filter(x => !plan.has(x)).sort(tgRouteSort),
  };
}
function tgRouteText(key) {
  const r = tgRouteFromKey(key);
  return r ? `${tgSlotLabel(r.slot)} ${r.talkgroup}` : String(key);
}
async function tgConfirm({title, message, confirmText='CONFIRM', tone='warn'}) {
  if (typeof window.ywdConfirm !== 'function') {
    toast('YWD confirmation UI is unavailable. Reload the dashboard and try again.', true);
    return false;
  }
  return window.ywdConfirm({
    title,
    message,
    confirmText,
    cancelText:'CANCEL',
    tone,
    kicker:'YWD // TALKGROUPS'
  });
}

function ensureControlSlotTools() {
  const input = $('tgInput');
  if (!input || $('tgControlSlotRow')) return;
  const field = input.closest('.field');
  if (!field) return;
  const row = document.createElement('div');
  row.id = 'tgControlSlotRow';
  row.className = 'buttonrow wrap';
  row.innerHTML = '<span class="label">STATIC TG TIMESLOT</span><button class="btn tiny" type="button" data-control-slot="1">TS1</button><button class="btn tiny" type="button" data-control-slot="2">TS2</button><span id="tgControlSimplexHint" class="hint">simplex slot 0</span>';
  field.parentElement?.insertBefore(row, field);
  $$('[data-control-slot]').forEach(b => b.onclick = () => tgSetSelectedSlot(Number(b.dataset.controlSlot)));

  $('addTg').onclick = () => {
    const tg = Number($('tgInput').value);
    if (!Number.isInteger(tg) || tg < 1 || tg > 16777215) return toast('Enter a valid talkgroup', true);
    const slot = tgEnsureSelectedSlot();
    action('/api/bm/static/add', {talkgroup:tg, slot}, `Static TG ${tg} added on ${tgSlotLabel(slot)}`);
  };
  $('dropQso').onclick = async () => {
    const slots = tgAllowedSlots();
    if (!await tgConfirm({
      title:'DROP ACTIVE QSO',
      message:`Drop the active QSO on ${tgIsDuplex() ? 'TS1 and TS2' : 'this simplex hotspot'}?`,
      confirmText:'DROP QSO',
      tone:'danger'
    })) return;
    try {
      for (const slot of slots) await post('/api/bm/drop-qso', {slot});
      toast(`Drop QSO sent${tgIsDuplex() ? ' to TS1 + TS2' : ''}`);
      setTimeout(getStatus, 700);
    } catch (e) { toast(e.message, true); }
  };
  $('dropDyn').onclick = async () => {
    const slots = tgAllowedSlots();
    if (!await tgConfirm({
      title:'DROP DYNAMIC TALKGROUPS',
      message:`Drop every dynamic/auto-static TG on ${tgIsDuplex() ? 'TS1 and TS2' : 'this hotspot'}?`,
      confirmText:'DROP DYNAMIC',
      tone:'danger'
    })) return;
    try {
      for (const slot of slots) await post('/api/bm/drop-dynamic', {slot});
      toast(`Dynamic talkgroups dropped${tgIsDuplex() ? ' on TS1 + TS2' : ''}`);
      setTimeout(getStatus, 700);
    } catch (e) { toast(e.message, true); }
  };
}

function ensureTalkgroupManager() {
  ensureControlSlotTools();
  if ($('talkgroups')) return;
  const tabs = document.querySelector('.tabs');
  const controlTab = tabs?.querySelector('[data-tab="control"]');
  if (!tabs || !controlTab) return;
  const tab = document.createElement('button');
  tab.dataset.tab = 'talkgroups';
  tab.textContent = 'TALKGROUPS';
  controlTab.after(tab);

  const page = document.createElement('section');
  page.className = 'page';
  page.id = 'talkgroups';
  page.innerHTML = `
    <article class="card">
      <div class="card-title title-row"><span>TALKGROUP MANAGER</span><span id="tgModeHint" class="hint">BrandMeister</span></div>
      <div id="tgManagerState" class="notice">Loading BrandMeister state…</div>
      <div id="tgManagerSlotRow" class="buttonrow wrap"><span class="label">PLAN TIMESLOT</span><button class="btn tiny" type="button" data-manager-slot="1">TS1</button><button class="btn tiny" type="button" data-manager-slot="2">TS2</button><span id="tgManagerSimplexHint" class="hint">simplex slot 0</span></div>
      <p class="hint">Build a desired static-TG plan first. Nothing changes on BrandMeister until you press APPLY PLAN and confirm it.</p>
    </article>
    <div class="grid two">
      <article class="card"><div class="card-title">CURRENT BRANDMEISTER ROUTES</div>
        <div class="label">STATIC</div><div id="tgCurrentStatic" class="pills"></div>
        <div class="label tg-spacer">DYNAMIC</div><div id="tgCurrentDynamic" class="pills"></div>
        <div class="buttonrow wrap tg-spacer"><button class="btn ctl" id="tgDropDynamic">DROP ALL DYNAMIC</button><button class="btn" id="tgRefreshState">REFRESH STATE</button></div>
      </article>
      <article class="card"><div class="card-title">STATIC CHANGE PLAN</div>
        <div id="tgPlanSummary" class="hint">No changes planned.</div>
        <div id="tgPlanPills" class="pills tg-spacer"></div>
        <div class="buttonrow wrap tg-spacer"><button class="btn" id="tgResetPlan">RESET TO CURRENT</button><button class="btn danger" id="tgClearPlan">PLAN REMOVE ALL</button><button class="btn primary ctl" id="tgApplyPlan">APPLY PLAN</button></div>
      </article>
    </div>
    <article class="card"><div class="card-title title-row"><span>SEARCH BRANDMEISTER DIRECTORY</span><span id="tgDirectoryMeta" class="hint">directory not loaded</span></div>
      <div class="field inline"><label>SEARCH TG ID OR NAME</label><input id="tgSearch" placeholder="California, POTA, 3106…" maxlength="80"><button class="btn" id="tgSearchBtn">SEARCH</button><button class="btn ctl" id="tgRefreshDirectory">REFRESH DIRECTORY</button></div>
      <div class="tablewrap"><table><thead><tr><th>TG</th><th>NAME</th><th>FAVORITE</th><th>PLAN</th></tr></thead><tbody id="tgSearchRows"><tr><td colspan="4">Search by talkgroup number or name.</td></tr></tbody></table></div>
    </article>
    <div class="grid two">
      <article class="card"><div class="card-title">FAVORITES</div><p class="hint">Favorites are saved in this browser and never change BrandMeister by themselves.</p><div id="tgFavoriteRows"></div></article>
      <article class="card"><div class="card-title">SAVED STATIC SETS</div><p class="hint">Saved sets include timeslots and load into the change plan only; APPLY PLAN is still required.</p>
        <div class="field inline"><label>SET NAME</label><input id="tgSetName" maxlength="40" placeholder="Local / Travel / Nets"><button class="btn" id="tgSaveSet">SAVE CURRENT PLAN</button></div><div id="tgSetRows"></div>
      </article>
    </div>`;
  document.querySelector('main')?.append(page);

  tab.onclick = () => {
    $$('.tabs button').forEach(x => x.classList.remove('on'));
    $$('.page').forEach(x => x.classList.remove('on'));
    tab.classList.add('on'); page.classList.add('on');
    tgRender(state);
    tgHydrateCurrentNames();
    setTimeout(() => $('tgSearch')?.focus(), 50);
  };

  $$('[data-manager-slot]').forEach(b => b.onclick = () => tgSetSelectedSlot(Number(b.dataset.managerSlot)));
  $('tgSearchBtn').onclick = () => tgSearch(false);
  $('tgSearch').oninput = () => { clearTimeout(tgSearchTimer); tgSearchTimer = setTimeout(() => tgSearch(false), 280); };
  $('tgSearch').onkeydown = e => { if (e.key === 'Enter') { e.preventDefault(); tgSearch(false); } };
  $('tgRefreshDirectory').onclick = () => tgSearch(true);
  $('tgRefreshState').onclick = () => { getStatus(); toast('Refreshing BrandMeister state'); };
  $('tgDropDynamic').onclick = async () => {
    if (!await tgConfirm({
      title:'DROP DYNAMIC TALKGROUPS',
      message:`Drop every dynamic talkgroup on ${tgIsDuplex() ? 'TS1 and TS2' : 'this hotspot'}?`,
      confirmText:'DROP DYNAMIC',
      tone:'danger'
    })) return;
    try {
      for (const slot of tgAllowedSlots()) await post('/api/bm/drop-dynamic', {slot});
      toast('Dynamic talkgroups dropped');
      setTimeout(getStatus, 700);
    } catch (e) { toast(e.message, true); }
  };
  $('tgResetPlan').onclick = () => { tgPlan = new Set(tgCurrentRoutes()); tgPlanDirty = false; tgRender(state); };
  $('tgClearPlan').onclick = () => { tgPlan = new Set(); tgPlanDirty = true; tgRender(state); };
  $('tgApplyPlan').onclick = tgApplyPlan;
  $('tgSaveSet').onclick = tgSaveSet;
}

async function tgApi(params) {
  const u = new URL('/api/talkgroups/search', location.origin);
  Object.entries(params || {}).forEach(([k,v]) => { if (v !== '' && v != null) u.searchParams.set(k, String(v)); });
  const r = await fetch(u, {cache:'no-store'});
  const d = await r.json().catch(() => ({error:`HTTP ${r.status}`}));
  if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);
  tgRememberRows(d.results || []);
  tgDirectoryMeta = d;
  return d;
}

async function tgHydrateCurrentNames() {
  const ids = new Set((state?.brandmeister?.static || []).map(x => Number(x.talkgroup)).filter(Number.isInteger));
  tgFavorites().forEach(x => ids.add(x.id));
  tgSets().forEach(s => s.routes.forEach(key => { const r=tgRouteFromKey(key); if(r) ids.add(r.talkgroup); }));
  if (!ids.size) return;
  try { await tgApi({ids:[...ids].join(','), limit:100}); tgRender(state); }
  catch (_) { }
}

async function tgSearch(refresh=false) {
  const q = $('tgSearch')?.value.trim() || '';
  if (!q) {
    $('tgSearchRows').innerHTML = '<tr><td colspan="4">Search by talkgroup number or name.</td></tr>';
    return;
  }
  $('tgSearchRows').innerHTML = '<tr><td colspan="4">Searching BrandMeister directory…</td></tr>';
  try {
    const d = await tgApi({q, limit:50, refresh:refresh ? 1 : 0});
    tgRenderSearch(d.results || []);
    tgRender(state);
  } catch (e) {
    $('tgSearchRows').innerHTML = `<tr><td colspan="4">${esc(e.message)}</td></tr>`;
    toast(e.message, true);
  }
}

function tgRenderSearch(rows) {
  const fav = new Set(tgFavorites().map(x=>x.id));
  const slot = tgEnsureSelectedSlot();
  $('tgSearchRows').innerHTML = rows.length ? rows.map(x => {
    const id = Number(x.id), key = tgRouteKey(slot, id), planned = tgPlan?.has(key);
    const actionText = tgIsDuplex() ? `${planned ? 'REMOVE' : 'ADD'} ${tgSlotLabel(slot)}` : `${planned ? 'REMOVE FROM' : 'ADD TO'} PLAN`;
    return `<tr><td class="tg-id">${id}</td><td>${esc(x.name || '—')}</td><td><button class="btn tiny tg-star" data-tg-fav="${id}" title="Toggle favorite">${fav.has(id) ? '★' : '☆'}</button></td><td><button class="btn tiny" data-tg-plan="${id}">${actionText}</button></td></tr>`;
  }).join('') : '<tr><td colspan="4">No matching talkgroups.</td></tr>';
  $$('[data-tg-fav]').forEach(b => b.onclick = () => tgToggleFavorite(Number(b.dataset.tgFav)));
  $$('[data-tg-plan]').forEach(b => b.onclick = () => tgTogglePlan(Number(b.dataset.tgPlan), slot));
}

function tgToggleFavorite(id) {
  let rows = tgFavorites();
  if (rows.some(x => x.id === id)) rows = rows.filter(x => x.id !== id);
  else rows.push({id, name:tgName(id)});
  rows.sort((a,b)=>a.id-b.id); tgSaveJson(TG_FAVORITES_KEY, rows);
  tgRender(state); tgSearch(false);
}
function tgTogglePlan(id, slot=tgEnsureSelectedSlot()) {
  if (!tgPlan) tgPlan = new Set(tgCurrentRoutes());
  const key = tgRouteKey(slot, id);
  tgPlan.has(key) ? tgPlan.delete(key) : tgPlan.add(key);
  tgPlanDirty = true; tgRender(state); tgSearch(false);
}

function tgRenderSlotControls() {
  const duplex = tgIsDuplex(), slot = tgEnsureSelectedSlot();
  $$('[data-control-slot], [data-manager-slot]').forEach(b => {
    const selected = Number(b.dataset.controlSlot ?? b.dataset.managerSlot) === slot;
    b.hidden = !duplex;
    b.classList.toggle('primary', selected);
  });
  if ($('tgControlSimplexHint')) $('tgControlSimplexHint').hidden = duplex;
  if ($('tgManagerSimplexHint')) $('tgManagerSimplexHint').hidden = duplex;
  if ($('tgModeHint')) $('tgModeHint').textContent = duplex ? `BrandMeister · duplex · planning ${tgSlotLabel(slot)}` : 'BrandMeister · simplex slot 0';
}

function tgRenderControlStatics(d) {
  const stat = d?.brandmeister?.static || [];
  const unlocked = ctlReady(), key = !!d?.brandmeister?.api_key_configured;
  const pill = x => `<span class="pill"><b>${tgSlotLabel(Number(x.slot ?? 0))}</b> · ${Number(x.talkgroup)}${x.name ? ' · '+esc(x.name) : ''}${unlocked && key ? ` <button data-ywd-del-tg="${Number(x.talkgroup)}" data-ywd-del-slot="${Number(x.slot ?? 0)}">×</button>` : ''}</span>`;
  if ($('staticTgsMini')) $('staticTgsMini').innerHTML = stat.length ? stat.map(pill).join('') : '<span class="hint">none</span>';
  if ($('staticTgs')) $('staticTgs').innerHTML = stat.length ? stat.map(pill).join('') : '<span class="hint">none</span>';
  $$('[data-ywd-del-tg]').forEach(b => b.onclick = async () => {
    const tg = Number(b.dataset.ywdDelTg), slot = Number(b.dataset.ywdDelSlot);
    if (!await tgConfirm({
      title:'REMOVE STATIC TALKGROUP',
      message:`Remove static ${tgSlotLabel(slot)} TG ${tg} from BrandMeister?\n\nOnly this exact timeslot route will be removed.`,
      confirmText:'REMOVE TG',
      tone:'danger'
    })) return;
    action('/api/bm/static/remove', {talkgroup:tg, slot}, `Static ${tgSlotLabel(slot)} TG ${tg} removed`);
  });
}

function tgRender(d) {
  if (!d) return;
  ensureControlSlotTools();
  tgEnsureSelectedSlot();
  tgRenderSlotControls();
  tgRenderControlStatics(d);
  if (!$('talkgroups')) return;

  const current = tgCurrentRoutes();
  if (tgPlan === null || !tgPlanDirty) tgPlan = new Set(current);
  const stat = d.brandmeister?.static || [], dyn = d.brandmeister?.dynamic || [];
  stat.forEach(x => { if (x.name) tgNames.set(Number(x.talkgroup), x.name); });
  dyn.forEach(x => { if (x.name) tgNames.set(Number(x.talkgroup), x.name); });
  const unlocked = ctlReady(), key = !!d.brandmeister?.api_key_configured;
  $('tgManagerState').textContent = !key ? 'BrandMeister API key is not configured. Search works, but route changes are locked.' : !unlocked ? 'Read-only: unlock control mode to apply talkgroup changes.' : `Control mode unlocked. ${tgIsDuplex() ? 'Choose TS1 or TS2 before adding routes to the plan.' : 'Simplex routes use slot 0.'}`;
  $('tgCurrentStatic').innerHTML = stat.length ? stat.map(x => `<span class="pill"><b>${tgSlotLabel(Number(x.slot ?? 0))}</b> · <span class="tg-id">${Number(x.talkgroup)}</span>${x.name ? ' · '+esc(x.name) : ''}</span>`).join('') : '<span class="hint">none</span>';
  $('tgCurrentDynamic').innerHTML = dyn.length ? dyn.map(x => `<span class="pill dynamic"><b>${tgSlotLabel(Number(x.slot ?? 0))}</b> · <span class="tg-id">${Number(x.talkgroup)}</span>${x.name ? ' · '+esc(x.name) : ''}</span>`).join('') : '<span class="hint">none</span>';

  const diff = tgDiff();
  const planned = [...tgPlan].sort(tgRouteSort);
  $('tgPlanPills').innerHTML = planned.length ? planned.map(key => {
    const r = tgRouteFromKey(key); if (!r) return '';
    const cls = current.has(key) ? '' : ' tg-plan-add';
    return `<span class="pill${cls}"><button data-tg-plan-remove="${r.talkgroup}" data-tg-plan-slot="${r.slot}" title="Remove from plan">×</button> <b>${tgSlotLabel(r.slot)}</b> · <span class="tg-id">${r.talkgroup}</span>${tgName(r.talkgroup) ? ' · '+esc(tgName(r.talkgroup)) : ''}</span>`;
  }).join('') : '<span class="hint">plan contains no static talkgroups</span>';
  $$('[data-tg-plan-remove]').forEach(b => b.onclick = () => tgTogglePlan(Number(b.dataset.tgPlanRemove), Number(b.dataset.tgPlanSlot)));
  const parts = [];
  if (diff.add.length) parts.push(`ADD ${diff.add.map(tgRouteText).join(', ')}`);
  if (diff.remove.length) parts.push(`REMOVE ${diff.remove.map(tgRouteText).join(', ')}`);
  $('tgPlanSummary').textContent = parts.length ? parts.join(' · ') : 'No changes planned.';
  $('tgApplyPlan').disabled = !(unlocked && key && (diff.add.length || diff.remove.length));
  $('tgApplyPlan').textContent = diff.add.length || diff.remove.length ? `APPLY PLAN · ${diff.add.length + diff.remove.length} CHANGE${diff.add.length + diff.remove.length === 1 ? '' : 'S'}` : 'APPLY PLAN';
  $('tgDropDynamic').disabled = !(unlocked && key && dyn.length);

  const meta = tgDirectoryMeta;
  $('tgDirectoryMeta').textContent = meta ? `${meta.directory_count || 0} TGs · ${meta.stale ? 'STALE CACHE' : 'cached'}${meta.cached_at ? ' · '+ago(meta.cached_at) : ''}` : 'directory loads on first search';
  tgRenderFavorites(); tgRenderSets();
}

function tgRenderFavorites() {
  const rows = tgFavorites(), slot = tgEnsureSelectedSlot();
  $('tgFavoriteRows').innerHTML = rows.length ? rows.map(x => {
    const key = tgRouteKey(slot, x.id), planned = tgPlan?.has(key);
    const label = tgIsDuplex() ? `${planned ? 'REMOVE' : 'ADD'} ${tgSlotLabel(slot)}` : `${planned ? 'REMOVE' : 'ADD'} PLAN`;
    return `<div class="row"><span><b class="tg-id">${x.id}</b>${tgName(x.id,x.name) ? ' · '+esc(tgName(x.id,x.name)) : ''}</span><span class="tg-row-actions"><button class="btn tiny" data-fav-plan="${x.id}">${label}</button><button class="btn tiny" data-fav-del="${x.id}">UNSTAR</button></span></div>`;
  }).join('') : '<div class="hint">Star search results to build a quick-access list.</div>';
  $$('[data-fav-plan]').forEach(b => b.onclick = () => tgTogglePlan(Number(b.dataset.favPlan), slot));
  $$('[data-fav-del]').forEach(b => b.onclick = () => tgToggleFavorite(Number(b.dataset.favDel)));
}
function tgRenderSets() {
  const rows = tgSets();
  $('tgSetRows').innerHTML = rows.length ? rows.map((x,i) => `<div class="row"><span><b>${esc(x.name)}</b><br><small>${esc(x.routes.sort(tgRouteSort).map(tgRouteText).join(', ') || 'empty set')}</small></span><span class="tg-row-actions"><button class="btn tiny" data-set-load="${i}">LOAD PLAN</button><button class="btn tiny" data-set-del="${i}">DELETE</button></span></div>`).join('') : '<div class="hint">Save a planned static set for quick reuse.</div>';
  $$('[data-set-load]').forEach(b => b.onclick = () => { const s=tgSets()[Number(b.dataset.setLoad)]; if(!s)return; tgPlan=new Set(s.routes); tgPlanDirty=true; tgRender(state); toast(`Loaded set: ${s.name}`); });
  $$('[data-set-del]').forEach(b => b.onclick = async () => {
    const i=Number(b.dataset.setDel), rows=tgSets(), s=rows[i];
    if (!s) return;
    if (!await tgConfirm({
      title:'DELETE SAVED TG SET',
      message:`Delete saved set "${s.name}"?\n\nThis only removes the browser-saved preset. BrandMeister routes are not changed.`,
      confirmText:'DELETE SET',
      tone:'danger'
    })) return;
    rows.splice(i,1); tgSaveJson(TG_SETS_KEY,rows); tgRender(state);
  });
}
async function tgSaveSet() {
  const name = $('tgSetName').value.trim().slice(0,40);
  if (!name) return toast('Enter a name for the saved set', true);
  const rows = tgSets();
  const routes = [...(tgPlan || tgCurrentRoutes())].sort(tgRouteSort);
  const existing = rows.findIndex(x => x.name.toLowerCase() === name.toLowerCase());
  const item = {name, routes};
  if (existing >= 0) {
    if (!await tgConfirm({
      title:'REPLACE SAVED TG SET',
      message:`Replace saved set "${rows[existing].name}" with the current plan?`,
      confirmText:'REPLACE SET',
      tone:'warn'
    })) return;
    rows[existing] = item;
  } else rows.push(item);
  rows.sort((a,b)=>a.name.localeCompare(b.name));
  tgSaveJson(TG_SETS_KEY, rows); $('tgSetName').value=''; tgRender(state); toast(`Saved static set: ${name}`);
}

async function tgApplyPlan() {
  const diff = tgDiff();
  if (!diff.add.length && !diff.remove.length) return toast('No talkgroup changes planned');
  const lines = [];
  if (diff.add.length) lines.push(`ADD: ${diff.add.map(tgRouteText).join(', ')}`);
  if (diff.remove.length) lines.push(`REMOVE: ${diff.remove.map(tgRouteText).join(', ')}`);
  if (!await tgConfirm({
    title:'APPLY STATIC TG PLAN',
    message:`Apply this BrandMeister static talkgroup plan?\n\n${lines.join('\n')}\n\n${tgIsDuplex() ? 'Duplex routes are applied to their explicit timeslots.' : 'Simplex routes use slot 0.'}`,
    confirmText:'APPLY PLAN',
    tone:'warn'
  })) return;
  $('tgApplyPlan').disabled = true;
  try {
    for (const key of diff.add) {
      const r = tgRouteFromKey(key); if (!r) continue;
      await post('/api/bm/static/add', {talkgroup:r.talkgroup, slot:r.slot});
    }
    for (const key of diff.remove) {
      const r = tgRouteFromKey(key); if (!r) continue;
      await post('/api/bm/static/remove', {talkgroup:r.talkgroup, slot:r.slot});
    }
    toast(`Applied ${diff.add.length + diff.remove.length} talkgroup change(s)`);
    tgPlanDirty = false;
    setTimeout(async () => { await getStatus(); tgHydrateCurrentNames(); }, 900);
  } catch (e) {
    toast(`Talkgroup plan stopped: ${e.message}`, true);
    tgPlanDirty = true;
    setTimeout(getStatus, 800);
  }
}

ensureTalkgroupManager();
const tgCoreRender = render;
render = function(d) { tgCoreRender(d); tgRender(d); };
tgRender(state);
