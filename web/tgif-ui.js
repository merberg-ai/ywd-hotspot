'use strict';
(() => {
  const RF_PREFIX = 5_000_000;
  const TGIF_FAVORITES_KEY = 'ywd.tgifFavorites.v1';
  let installed = false;
  let passwordModal = null;
  let directoryInstalled = false;
  let directoryMeta = null;
  let searchTimer = null;
  let lastSearchRows = [];

  const el = id => document.getElementById(id);
  const safe = value => String(value ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
  const notify = (message, bad = false) => {
    if (typeof toast === 'function') toast(message, bad);
    else if (bad) console.error(message);
    else console.log(message);
  };

  async function apiPost(path, body) {
    const response = await fetch(path, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body || {}),
    });
    let data = {};
    try { data = await response.json(); } catch (_) {}
    if (!response.ok || data.error || data.ok === false) {
      throw new Error(data.error || `Request failed (${response.status})`);
    }
    return data;
  }

  function currentConfig() {
    if (typeof state !== 'undefined' && state?.config?.tgif) return state.config.tgif;
    if (typeof configDoc !== 'undefined' && configDoc?.tgif) return configDoc.tgif;
    return null;
  }

  function authenticated() {
    return !!(typeof state !== 'undefined' && state?.controls?.authenticated);
  }

  function settingsDirty() {
    return !!(typeof dirty !== 'undefined' && dirty);
  }

  function markSettingsDirty() {
    if (typeof setDirty === 'function') setDirty(true);
  }

  function linkDot(linkState, enabled = true) {
    if (!enabled || linkState === 'disabled') return '';
    if (linkState === 'connected') return 'good';
    if (linkState === 'connecting') return 'warn';
    return 'bad';
  }

  function stateText(linkState, enabled = true) {
    if (!enabled) return 'DISABLED';
    return String(linkState || 'unknown').replace(/-/g, ' ').toUpperCase();
  }

  function destinationText(dst, includeRf = false) {
    dst = dst || {};
    if (!dst.group) return dst.label || `PRIVATE ${dst.display || '?'}`;
    let text;
    if (dst.network === 'tgif') {
      text = `TGIF · TG ${dst.network_id ?? '?'}`;
      if (dst.name) text += ` · ${dst.name}`;
      if (includeRf && dst.rf_id != null) text += ` · RF ${dst.rf_id}`;
      return text;
    }
    if (dst.network === 'brandmeister') {
      text = `BM · TG ${dst.network_id ?? dst.display ?? '?'}`;
      if (dst.name) text += ` · ${dst.name}`;
      return text;
    }
    return `TG ${dst.display || '?'}`;
  }

  function renderNetworkPresentation(data) {
    if (!data || !el('strip')) return;
    const rf = data.services?.mmdvmhost === 'active';
    const bm = data.brandmeister || {};
    const tg = data.tgif || {};
    const w = data.system?.wifi || {};
    const temp = data.system?.temp_c;
    const throttle = data.system?.throttled || {};
    const tgEnabled = !!data.config?.tgif?.enabled;

    el('strip').innerHTML = `
      <span title="MMDVMHost service: ${safe(data.services?.mmdvmhost || 'unknown')}"><i class="dot ${rf ? 'good' : 'bad'}"></i> RF ${rf ? 'READY' : 'DOWN'}</span>
      <span title="${safe(bm.detail || 'BrandMeister link state')}"><i class="dot ${linkDot(bm.state, bm.enabled !== false)}"></i> BM ${safe(stateText(bm.state, bm.enabled !== false))}</span>
      <span title="${safe(tg.detail || 'TGIF link state')}"><i class="dot ${linkDot(tg.state, tgEnabled)}"></i> TGIF ${safe(stateText(tg.state, tgEnabled))}</span>
      <span title="SSID ${safe(w.ssid || 'unknown')} · RX errors ${safe(w.rx_errors ?? '—')} · TX errors ${safe(w.tx_errors ?? '—')}"><i class="dot ${w.connected ? 'good' : 'bad'}"></i> WIFI ${safe(w.signal_dbm ?? '—')} dBm</span>
      <span title="Throttle/power: ${safe(throttle.raw || throttle.value || '0x0')}">TEMP ${safe(temp ?? '—')}°C</span>`;

    const activity = data.activity || {};
    const current = activity.current || {};
    if (current.active) {
      const dst = current.destination || {};
      if (el('activityDest')) el('activityDest').textContent = `→ ${destinationText(dst, true)}`;
    } else {
      const last = (activity.lastheard || [])[0];
      if (last && el('activityWho')) {
        const src = (last.source || {}).display || '?';
        el('activityWho').textContent = `Last: ${src} → ${destinationText(last.destination || {}, false)}`;
      }
    }

    const heard = activity.lastheard || [];
    if (el('heardSummary')) {
      const first = heard[0];
      if (!first) el('heardSummary').textContent = 'no calls captured';
      else {
        const src = (first.source || {}).display || '?';
        const when = typeof ago === 'function' ? ago(first.started_at) : '';
        el('heardSummary').textContent = `${src} → ${destinationText(first.destination || {}, false)}${when ? ' · ' + when : ''}`;
      }
    }

    if (el('heardRows')) {
      el('heardRows').innerHTML = heard.slice(0, 30).map(row => {
        const src = (row.source || {}).display || '?';
        const dst = row.destination || {};
        let quality = `BER ${row.ber_pct ?? '—'}%`;
        if (row.packet_loss_pct != null) quality += ` / loss ${row.packet_loss_pct}%`;
        else if (row.rssi_dbm != null) quality += ` / ${row.rssi_dbm} dBm`;
        const when = typeof ago === 'function' ? ago(row.started_at) : '—';
        const duration = typeof dur === 'function' ? dur(row.duration_s) : (row.duration_s ?? '—');
        const path = `${row.path || '?'}${dst.network_label ? ' · ' + dst.network_label : ''}`;
        return `<tr><td>${safe(when)}</td><td>${safe(path)}</td><td>${safe(src)}</td><td>${safe(destinationText(dst, true))}</td><td>${safe(duration)}</td><td>${safe(quality)}</td></tr>`;
      }).join('') || '<tr><td colspan="6">No DMR calls captured yet.</td></tr>';
    }
  }

  function ensurePasswordModal() {
    if (passwordModal) return passwordModal;
    const overlay = document.createElement('div');
    overlay.className = 'modal';
    overlay.id = 'tgifPasswordModal';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.innerHTML = `
      <div class="dialog">
        <div class="card-title">TGIF SECURITY PASSWORD</div>
        <p class="hint">Use the secured hotspot/network password from TGIF User Security. It is stored on the Pi and is never returned to the browser.</p>
        <div class="field"><label>NEW TGIF PASSWORD</label><input id="tgifPasswordValue" type="password" autocomplete="new-password" maxlength="128"></div>
        <div class="field"><label>CONFIRM PASSWORD</label><input id="tgifPasswordConfirm" type="password" autocomplete="new-password" maxlength="128"></div>
        <div class="buttonrow"><button class="btn" id="tgifPasswordCancel" type="button">CANCEL</button><button class="btn primary" id="tgifPasswordSave" type="button">SAVE PASSWORD</button></div>
      </div>`;
    document.body.appendChild(overlay);
    el('tgifPasswordCancel').onclick = () => overlay.classList.remove('on');
    el('tgifPasswordSave').onclick = savePassword;
    passwordModal = overlay;
    return overlay;
  }

  function openPassword() {
    if (!authenticated()) return notify('Unlock WebUI controls first', true);
    const modal = ensurePasswordModal();
    el('tgifPasswordValue').value = '';
    el('tgifPasswordConfirm').value = '';
    modal.classList.add('on');
    setTimeout(() => el('tgifPasswordValue').focus(), 50);
  }

  async function savePassword() {
    const value = el('tgifPasswordValue').value;
    const confirm = el('tgifPasswordConfirm').value;
    if (!value) return notify('TGIF password cannot be empty', true);
    if (value !== confirm) return notify('TGIF passwords do not match', true);
    const button = el('tgifPasswordSave');
    button.disabled = true;
    try {
      await apiPost('/api/tgif/password', {password: value, apply: true});
      passwordModal.classList.remove('on');
      notify('TGIF security password saved');
      if (typeof getStatus === 'function') await getStatus();
      sync();
    } catch (err) {
      notify(err.message, true);
    } finally {
      button.disabled = false;
    }
  }

  function updateHelper() {
    const input = el('tgifTalkgroupHelper');
    const output = el('tgifRadioDestination');
    if (!input || !output) return;
    const tg = Number(input.value);
    if (!Number.isInteger(tg) || tg < 1 || tg > 999999) {
      output.textContent = 'Enter TGIF TG 1-999999';
      return;
    }
    output.textContent = `Radio group-call destination: ${RF_PREFIX + tg}`;
  }

  function favorites() {
    try {
      const rows = JSON.parse(localStorage.getItem(TGIF_FAVORITES_KEY) || '[]');
      return Array.isArray(rows)
        ? rows.filter(row => Number.isInteger(Number(row?.id))).map(row => ({
            id: Number(row.id),
            name: String(row.name || ''),
            rf_talkgroup: row.rf_talkgroup == null ? null : Number(row.rf_talkgroup),
            supported: row.supported !== false,
          }))
        : [];
    } catch (_) {
      return [];
    }
  }

  function saveFavorites(rows) {
    localStorage.setItem(TGIF_FAVORITES_KEY, JSON.stringify(rows.slice(0, 100)));
  }

  function favoriteIds() {
    return new Set(favorites().map(row => Number(row.id)));
  }

  function toggleFavorite(row) {
    const rows = favorites();
    const id = Number(row.id);
    const index = rows.findIndex(item => Number(item.id) === id);
    if (index >= 0) rows.splice(index, 1);
    else rows.push({
      id,
      name: String(row.name || ''),
      rf_talkgroup: row.rf_talkgroup == null ? null : Number(row.rf_talkgroup),
      supported: row.supported !== false,
    });
    saveFavorites(rows);
    renderSearch(lastSearchRows);
    renderFavorites();
  }

  async function directoryApi(params) {
    const url = new URL('/api/tgif/talkgroups/search', location.origin);
    Object.entries(params || {}).forEach(([key, value]) => {
      if (value !== '' && value != null) url.searchParams.set(key, String(value));
    });
    const response = await fetch(url, {cache:'no-store', credentials:'same-origin'});
    const data = await response.json().catch(() => ({error:`HTTP ${response.status}`}));
    if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    directoryMeta = data;
    return data;
  }

  function directoryMetaText() {
    if (!directoryMeta) return 'directory not loaded';
    const count = Number(directoryMeta.directory_count || 0);
    const cached = directoryMeta.cached_at && typeof ago === 'function' ? ago(directoryMeta.cached_at) : 'cached';
    return `${count} TGs · ${directoryMeta.stale ? 'stale cache' : 'cached'} · ${cached}`;
  }

  async function copyRadioTalkgroup(row) {
    if (!row?.supported || row.rf_talkgroup == null) {
      notify('This TGIF talkgroup is outside the current 5xxxxxx routing range', true);
      return;
    }
    const text = String(row.rf_talkgroup);
    try {
      if (typeof copyText === 'function') await copyText(text);
      else if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(text);
      else throw new Error('Clipboard helper unavailable');
      notify(`Copied RF TG ${text}`);
    } catch (_) {
      notify(`Radio destination: ${text}`);
    }
  }

  function renderSearch(rows) {
    lastSearchRows = Array.isArray(rows) ? rows : [];
    const body = el('tgifSearchRows');
    if (!body) return;
    const fav = favoriteIds();
    body.innerHTML = lastSearchRows.length ? lastSearchRows.map((row, index) => {
      const supported = row.supported !== false && row.rf_talkgroup != null;
      const rf = supported ? row.rf_talkgroup : 'unsupported';
      const note = supported ? '' : '<small class="hint">current routing supports TGIF 1–999999</small>';
      return `<tr>
        <td class="tg-id">${safe(row.id)}</td>
        <td>${safe(row.name || '')}</td>
        <td><span class="tg-id">${safe(rf)}</span>${note}</td>
        <td><button class="btn tiny tgif-star" type="button" data-tgif-fav="${index}" title="${fav.has(Number(row.id)) ? 'Remove favorite' : 'Add favorite'}">${fav.has(Number(row.id)) ? '★' : '☆'}</button></td>
        <td>${supported ? `<button class="btn tiny" type="button" data-tgif-copy="${index}">COPY RF TG</button>` : '<span class="hint">—</span>'}</td>
      </tr>`;
    }).join('') : '<tr><td colspan="5">No matching TGIF talkgroups.</td></tr>';
    body.querySelectorAll('[data-tgif-fav]').forEach(button => {
      button.onclick = () => toggleFavorite(lastSearchRows[Number(button.dataset.tgifFav)]);
    });
    body.querySelectorAll('[data-tgif-copy]').forEach(button => {
      button.onclick = () => copyRadioTalkgroup(lastSearchRows[Number(button.dataset.tgifCopy)]);
    });
    if (el('tgifDirectoryMeta')) el('tgifDirectoryMeta').textContent = directoryMetaText();
  }

  function renderFavorites() {
    const host = el('tgifFavoriteRows');
    if (!host) return;
    const rows = favorites().sort((a, b) => a.id - b.id);
    host.innerHTML = rows.length ? rows.map((row, index) => {
      const supported = row.supported !== false && row.rf_talkgroup != null;
      return `<div class="row">
        <span><b>${safe(row.id)}</b>${row.name ? `<br><small>${safe(row.name)}</small>` : ''}</span>
        <span class="tg-row-actions">${supported ? `<button class="btn tiny" type="button" data-tgif-fav-copy="${index}">RF ${safe(row.rf_talkgroup)}</button>` : '<span class="hint">routing limit</span>'}<button class="btn tiny danger" type="button" data-tgif-fav-remove="${index}">×</button></span>
      </div>`;
    }).join('') : '<div class="hint">No TGIF favorites saved in this browser.</div>';
    host.querySelectorAll('[data-tgif-fav-copy]').forEach(button => {
      button.onclick = () => copyRadioTalkgroup(rows[Number(button.dataset.tgifFavCopy)]);
    });
    host.querySelectorAll('[data-tgif-fav-remove]').forEach(button => {
      button.onclick = () => toggleFavorite(rows[Number(button.dataset.tgifFavRemove)]);
    });
  }

  async function hydrateFavorites() {
    const ids = favorites().map(row => row.id).filter(Number.isInteger);
    if (!ids.length) return renderFavorites();
    try {
      const data = await directoryApi({ids:ids.join(','), limit:100});
      const byId = new Map((data.results || []).map(row => [Number(row.id), row]));
      const hydrated = favorites().map(row => byId.get(Number(row.id)) || row);
      saveFavorites(hydrated);
    } catch (_) {}
    renderFavorites();
  }

  async function searchDirectory(refresh=false) {
    const input = el('tgifDirectorySearch');
    const body = el('tgifSearchRows');
    const q = input?.value.trim() || '';
    if (!q) {
      if (body) body.innerHTML = '<tr><td colspan="5">Search by TGIF talkgroup number or name.</td></tr>';
      return;
    }
    if (body) body.innerHTML = '<tr><td colspan="5">Searching TGIF directory…</td></tr>';
    try {
      const data = await directoryApi({q, limit:50, refresh:refresh ? 1 : 0});
      renderSearch(data.results || []);
      if (refresh) notify(`TGIF directory refreshed · ${data.directory_count || 0} talkgroups`);
    } catch (err) {
      if (body) body.innerHTML = `<tr><td colspan="5">${safe(err.message)}</td></tr>`;
      notify(err.message, true);
    }
  }

  function installDirectoryTools() {
    if (directoryInstalled) return true;
    const page = el('talkgroups');
    if (!page) return false;
    const bmSearch = Array.from(page.querySelectorAll('article.card')).find(card =>
      card.querySelector(':scope > .card-title')?.textContent?.includes('SEARCH BRANDMEISTER DIRECTORY')
    );
    if (!bmSearch) return false;

    const searchCard = document.createElement('article');
    searchCard.className = 'card';
    searchCard.id = 'tgifDirectoryCard';
    searchCard.innerHTML = `
      <div class="card-title title-row"><span>SEARCH TGIF DIRECTORY</span><span id="tgifDirectoryMeta" class="hint">directory not loaded</span></div>
      <p class="hint">TGIF does not use BrandMeister-style static talkgroups. Search the TGIF directory here, then program/use the shown RF destination. YWD removes the RF 5-prefix before sending the call to TGIF.</p>
      <div class="field inline tgif-directory-search"><label>SEARCH TG ID OR NAME</label><input id="tgifDirectorySearch" placeholder="TGIF, DX, 31665…" maxlength="80"><button class="btn" id="tgifDirectorySearchBtn" type="button">SEARCH</button><button class="btn ctl" id="tgifDirectoryRefresh" type="button">REFRESH DIRECTORY</button></div>
      <div class="tablewrap"><table><thead><tr><th>TGIF TG</th><th>NAME</th><th>RADIO TG</th><th>FAVORITE</th><th>ACTION</th></tr></thead><tbody id="tgifSearchRows"><tr><td colspan="5">Search by TGIF talkgroup number or name.</td></tr></tbody></table></div>`;
    bmSearch.insertAdjacentElement('afterend', searchCard);

    const favoriteCard = document.createElement('article');
    favoriteCard.className = 'card';
    favoriteCard.id = 'tgifFavoritesCard';
    favoriteCard.innerHTML = `
      <div class="card-title">TGIF FAVORITES</div>
      <p class="hint">Favorites are saved in this browser. They do not change network routing or hotspot configuration.</p>
      <div id="tgifFavoriteRows"></div>`;
    searchCard.insertAdjacentElement('afterend', favoriteCard);

    el('tgifDirectorySearchBtn').onclick = () => searchDirectory(false);
    el('tgifDirectoryRefresh').onclick = () => searchDirectory(true);
    el('tgifDirectorySearch').oninput = () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => searchDirectory(false), 280);
    };
    el('tgifDirectorySearch').onkeydown = event => {
      if (event.key === 'Enter') {
        event.preventDefault();
        searchDirectory(false);
      }
    };

    const talkgroupTab = document.querySelector('.tabs [data-tab="talkgroups"]');
    if (talkgroupTab) talkgroupTab.addEventListener('click', () => {
      renderFavorites();
      hydrateFavorites();
      setTimeout(() => el('tgifDirectorySearch')?.focus(), 80);
    });

    directoryInstalled = true;
    renderFavorites();
    hydrateFavorites();
    return true;
  }

  function sync() {
    const cfg = currentConfig();
    if (!cfg || !el('tgifSettingsCard')) return;
    if (!settingsDirty()) {
      el('tgifMaster').value = cfg.master || 'tgif.network';
      el('tgifPort').value = cfg.port || 62031;
      el('tgifEnabled').checked = !!cfg.enabled;
    }
    el('tgifPasswordStatus').textContent = cfg.password_configured ? 'configured' : 'missing';
    const runtime = (typeof state !== 'undefined' && state?.tgif) ? state.tgif : null;
    el('tgifRuntimeIntent').textContent = cfg.enabled
      ? stateText(runtime?.state || 'connecting', true)
      : 'DISABLED';
    el('tgifRuntimeIntent').title = runtime?.detail || '';
    const locked = !authenticated();
    ['tgifEnabled','tgifMaster','tgifPort','tgifChangePassword'].forEach(id => {
      const node = el(id); if (node) node.disabled = locked;
    });
    if (el('tgifDirectoryRefresh')) el('tgifDirectoryRefresh').disabled = locked;
  }

  function install() {
    if (installed) return true;
    const settings = el('settings');
    if (!settings) return false;
    const firstGrid = settings.querySelector(':scope > .grid.two');
    if (!firstGrid) return false;

    const card = document.createElement('article');
    card.className = 'card';
    card.id = 'tgifSettingsCard';
    card.innerHTML = `
      <div class="card-title title-row"><span>TGIF NETWORK — EXPERIMENTAL</span><span id="tgifRuntimeIntent" class="badge">DISABLED</span></div>
      <p class="hint">Runs alongside BrandMeister through DMRGateway. TGIF group calls use the reserved 5xxxxxx RF namespace; normal talkgroup numbers continue to go to BrandMeister.</p>
      <div class="formgrid four">
        <div class="field span2"><label>MASTER HOSTNAME</label><input id="tgifMaster" data-cfg="tgif.master" value="tgif.network" maxlength="128"></div>
        <div class="field"><label>UDP PORT</label><input id="tgifPort" data-cfg="tgif.port" type="number" min="1" max="65535" value="62031"></div>
        <div class="field check"><label><input id="tgifEnabled" data-cfg="tgif.enabled" type="checkbox"> NETWORK ENABLED</label></div>
      </div>
      <div class="secretrow"><span>TGIF security password: <b id="tgifPasswordStatus">—</b></span><button class="btn ctl" id="tgifChangePassword" type="button">CHANGE</button></div>
      <p class="hint">TGIF enable/master/port are saved with the normal Settings SAVE / SAVE &amp; APPLY controls. The security password remains a separate protected credential.</p>
      <hr>
      <div class="field inline"><label>TGIF TG HELPER</label><input id="tgifTalkgroupHelper" inputmode="numeric" placeholder="31665" maxlength="6"><span id="tgifRadioDestination" class="hint">Example: TGIF 31665 → radio TG 5031665</span></div>
      <p class="hint">The prefix exists only on RF. DMRGateway removes the leading 5 before sending to TGIF and restores it on TGIF traffic sent back to the hotspot.</p>`;
    firstGrid.insertAdjacentElement('afterend', card);

    el('tgifChangePassword').onclick = openPassword;
    el('tgifTalkgroupHelper').addEventListener('input', updateHelper);
    ['tgifEnabled','tgifMaster','tgifPort'].forEach(id => {
      const node = el(id);
      node.addEventListener('input', markSettingsDirty);
      node.addEventListener('change', markSettingsDirty);
    });

    if (typeof render === 'function' && !render.__ywdTgifWrapped) {
      const baseRender = render;
      const wrapped = function(data) {
        const out = baseRender(data);
        sync();
        renderNetworkPresentation(data);
        return out;
      };
      wrapped.__ywdTgifWrapped = true;
      render = wrapped;
    }

    installed = true;
    installDirectoryTools();
    sync();
    if (typeof state !== 'undefined' && state) renderNetworkPresentation(state);
    return true;
  }

  const settingsTimer = setInterval(() => {
    if (install()) clearInterval(settingsTimer);
  }, 100);
  const directoryTimer = setInterval(() => {
    if (installDirectoryTools()) clearInterval(directoryTimer);
  }, 120);
  setTimeout(() => { clearInterval(settingsTimer); clearInterval(directoryTimer); }, 15000);
})();
