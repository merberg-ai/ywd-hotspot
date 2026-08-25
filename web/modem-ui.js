'use strict';
(() => {
  const esc = value => String(value ?? '—').replace(/[&<>"']/g, c => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[c]));
  const short = (value, n = 16) => {
    const text = String(value || '');
    return text ? text.slice(0, n) : '—';
  };
  const yesno = value => value === true ? 'YES' : value === false ? 'NO' : '—';
  const date = value => {
    const n = Number(value);
    return Number.isFinite(n) && n > 0 ? new Date(n * 1000).toLocaleString() : '—';
  };
  const bytes = value => {
    const n = Number(value);
    if (!Number.isFinite(n) || n < 0) return '—';
    if (n < 1024) return `${Math.round(n)} B`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KiB`;
    return `${(n / (1024 * 1024)).toFixed(1)} MiB`;
  };

  function installStyle() {
    if (document.getElementById('ywdModemUiStyle')) return;
    const style = document.createElement('style');
    style.id = 'ywdModemUiStyle';
    style.textContent = `
      .system-modem-card{grid-column:1/-1;border-color:#1b5260;background:linear-gradient(180deg,#06151bee,#041016ee)}
      .system-modem-card .modem-badge{font-size:10px;letter-spacing:.08em;font-weight:700}
      .modem-intro{margin:4px 0 14px}
      .modem-section{margin-top:14px;padding-top:12px;border-top:1px solid #17343d}
      .modem-section-title{margin:0 0 8px;color:var(--accent);font-size:10px;font-weight:700;letter-spacing:.12em;text-transform:uppercase}
      .modem-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 20px;border-top:1px solid #132f38}
      .modem-grid>div{display:flex;justify-content:space-between;align-items:flex-start;gap:14px;padding:8px 0;border-bottom:1px solid #102a32;min-width:0}
      .modem-grid span{color:var(--muted);font-size:9px;letter-spacing:.06em;text-transform:uppercase;flex:0 0 auto}
      .modem-grid b{font-size:10px;text-align:right;overflow-wrap:anywhere;word-break:break-word;min-width:0}
      .modem-wide{grid-column:1/-1}
      .modem-wide b{max-width:74%}
      .modem-capabilities{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
      .modem-capability{border:1px solid #1a5767;border-radius:999px;padding:4px 7px;background:#071820;color:#86eaff;font-size:9px;letter-spacing:.04em}
      .modem-details{margin-top:12px;border:1px solid #173b45;border-radius:9px;background:#051016}
      .modem-details summary{cursor:pointer;padding:10px 12px;color:var(--muted);font-size:10px;letter-spacing:.08em;user-select:none}
      .modem-details[open] summary{border-bottom:1px solid #17343d;color:var(--accent)}
      .modem-details-body{padding:4px 12px 12px}
      .modem-journal{margin:0;white-space:pre-wrap;overflow-wrap:anywhere;font-size:9px;line-height:1.45;color:var(--muted)}
      .modem-maintenance{margin-top:14px;padding:12px;border:1px dashed #24505b;border-radius:9px;background:#061117}
      .modem-maintenance .hint{margin:0 0 10px}
      .modem-maintenance .btn[disabled]{opacity:.42;cursor:not-allowed;filter:none}
      .modem-refresh{min-width:130px}
      @media(max-width:620px){
        .modem-grid{grid-template-columns:1fr}
        .modem-wide{grid-column:auto}
        .modem-wide b{max-width:62%}
        .modem-maintenance .buttonrow{display:grid;grid-template-columns:1fr}
        .modem-maintenance .btn{width:100%}
      }
    `;
    document.head.appendChild(style);
  }

  function row(label, value, wide = false, title = '') {
    return `<div${wide ? ' class="modem-wide"' : ''}><span>${esc(label)}</span><b${title ? ` title="${esc(title)}"` : ''}>${esc(value)}</b></div>`;
  }

  function toolText(tools = {}) {
    return ['git','make','g++'].map(name => `${name}:${tools[name]?.available ? 'yes' : 'no'}`).join(' · ');
  }

  function cacheText(cache = {}) {
    const rows = Array.isArray(cache.namespaces) ? cache.namespaces : [];
    if (!rows.length) return 'none';
    return rows.map(item => `${item.namespace || '?'}=${item.entries ?? 0}`).join(' · ');
  }

  function render(doc) {
    const card = document.getElementById('mmdvmInfoCard');
    if (!card) return;
    const hat = doc?.hat || {};
    const serial = doc?.serial || {};
    const cfg = doc?.configuration || {};
    const service = doc?.service || {};
    const runtime = doc?.runtime || {};
    const binary = doc?.binary || {};
    const build = doc?.build || {};
    const pins = build.pins || {};
    const provenance = build.provenance || {};
    const source = build.source || {};
    const capabilities = Array.isArray(runtime.capabilities) ? runtime.capabilities : [];
    const active = String(service.ActiveState || '').toLowerCase() === 'active';
    const verified = runtime.installed && runtime.in_sync;
    const badge = document.getElementById('mmdvmInfoState');
    if (badge) {
      badge.textContent = verified ? 'VERIFIED' : runtime.upgrade_required ? 'REFRESH NEEDED' : active ? 'CHECK' : 'OFFLINE';
      badge.className = `modem-badge ${verified ? 'goodtext' : runtime.upgrade_required ? 'warntext' : active ? 'warntext' : 'badtext'}`;
    }

    const hatBody = document.getElementById('mmdvmHatInfo');
    if (hatBody) hatBody.innerHTML = [
      row('Board / firmware', hat.description || 'Not reported yet', true),
      row('MMDVM protocol', hat.protocol || '—'),
      row('Last identified', date(hat.activity_seen_at)),
      row('Configured UART', serial.configured || '—'),
      row('Resolved device', serial.resolved || '—'),
      row('UART speed', cfg.uart_speed || '—'),
      row('RF mode', String(cfg.rf_mode || '—').toUpperCase()),
      row('TX / RX invert', `${cfg.tx_invert ?? '—'} / ${cfg.rx_invert ?? '—'}`),
      row('Color code', cfg.color_code ?? '—'),
      row('Service', `${service.ActiveState || 'unknown'} / ${service.SubState || 'unknown'}`),
      row('PID / restarts', `${service.MainPID ?? '—'} / ${service.NRestarts ?? '—'}`),
      row('Last result', `${service.Result || 'unknown'} · exit ${service.ExecMainStatus ?? '—'}`),
    ].join('');

    const runtimeBody = document.getElementById('mmdvmRuntimeInfo');
    if (runtimeBody) runtimeBody.innerHTML = [
      row('Runtime variant', runtime.variant || 'unknown'),
      row('Generation', runtime.runtime_generation || 'unknown'),
      row('Extension API', runtime.extension_api ?? '—'),
      row('Observed / saved sync', yesno(runtime.in_sync)),
      row('Upgrade required', yesno(runtime.upgrade_required)),
      row('Legacy release', runtime.legacy_release || '—'),
      row('Upstream commit', short(runtime.upstream_commit, 16), false, runtime.upstream_commit || ''),
      row('Binary SHA-256', short(runtime.binary_sha256, 16), false, runtime.binary_sha256 || ''),
      row('Patch SHA-256', short(runtime.patch_sha256, 16), false, runtime.patch_sha256 || ''),
      row('Marker status', runtime.marker_status || '—'),
    ].join('');

    const caps = document.getElementById('mmdvmCapabilities');
    if (caps) caps.innerHTML = capabilities.length
      ? capabilities.map(item => `<span class="modem-capability">${esc(item)}</span>`).join('')
      : '<span class="hint">No YWD extension capabilities reported.</span>';

    const buildBody = document.getElementById('mmdvmBuildDetails');
    if (buildBody) buildBody.innerHTML = [
      row('Binary path', binary.path || '—', true),
      row('Binary size', bytes(binary.size)),
      row('Binary modified', date(binary.mtime)),
      row('Binary format', binary.format || '—', true),
      row('Full binary SHA-256', runtime.binary_sha256 || binary.sha256 || '—', true),
      row('Pinned repository', pins.repository || '—', true),
      row('Pinned upstream commit', pins.upstream_commit || '—', true),
      row('Pinned patch API', pins.patch_api || '—'),
      row('Pinned patch SHA-256', pins.patch_sha256 || '—', true),
      row('Build architecture', build.architecture || '—'),
      row('Build tools', toolText(build.tools)),
      row('Source checkout', source.present ? source.path : 'not present', true),
      row('Source HEAD', source.head || '—', true),
      row('Source dirty', source.dirty === null || source.dirty === undefined ? '—' : yesno(source.dirty)),
      row('Changed source files', source.changed_files ?? '—'),
      row('Built at', date(provenance.built_at)),
      row('Installed at', date(provenance.installed_at)),
      row('Build cache hit', provenance.cached === undefined ? '—' : yesno(provenance.cached)),
      row('Cache key', provenance.cache_key || '—', true),
      row('Cache inventory', cacheText(build.cache), true),
      row('Persisted generation', runtime.persisted_generation || '—'),
      row('Persisted selected', date(runtime.persisted_selected_at)),
    ].join('');

    const journal = document.getElementById('mmdvmJournalIdentity');
    if (journal) journal.textContent = Array.isArray(hat.journal_lines) && hat.journal_lines.length
      ? hat.journal_lines.join('\n')
      : 'No modem identification lines were found in the current-boot MMDVMHost journal.';

    const reason = document.getElementById('mmdvmUpgradeReason');
    if (reason) {
      reason.hidden = !runtime.upgrade_required;
      reason.textContent = runtime.upgrade_required
        ? `Runtime refresh recommended: ${runtime.upgrade_reason || 'installed runtime is not the current accepted YWD Extended generation.'}`
        : '';
    }
    const collected = document.getElementById('mmdvmCollectedAt');
    if (collected) collected.textContent = `Inventory refreshed ${date(doc?.collected_at)}`;
  }

  async function load(showError = false) {
    const badge = document.getElementById('mmdvmInfoState');
    if (badge) {
      badge.textContent = 'CHECKING…';
      badge.className = 'modem-badge';
    }
    try {
      const r = await fetch('/api/system/modem', {credentials:'same-origin', cache:'no-store'});
      const doc = await r.json().catch(() => ({}));
      if (!r.ok || doc?.error) throw new Error(doc?.error || `HTTP ${r.status}`);
      render(doc);
      return doc;
    } catch (err) {
      if (badge) {
        badge.textContent = 'UNAVAILABLE';
        badge.className = 'modem-badge badtext';
      }
      const collected = document.getElementById('mmdvmCollectedAt');
      if (collected) collected.textContent = `Could not read modem inventory: ${err.message || err}`;
      if (showError && typeof toast === 'function') toast(`MMDVM inventory failed: ${err.message || err}`, true);
      return null;
    }
  }

  function install() {
    if (document.getElementById('mmdvmInfoCard')) return true;
    const page = document.getElementById('system');
    const runtime = page && Array.from(page.querySelectorAll('article.card')).find(card =>
      card.querySelector(':scope > .card-title')?.textContent?.trim() === 'RUNTIME'
    );
    const grid = runtime?.parentElement;
    if (!page || !runtime || !grid) return false;

    installStyle();
    const card = document.createElement('article');
    card.className = 'card system-modem-card';
    card.id = 'mmdvmInfoCard';
    card.innerHTML = `
      <div class="card-title title-row"><span>MODEM / MMDVM</span><span id="mmdvmInfoState" class="modem-badge">CHECKING…</span></div>
      <p class="hint modem-intro">Passive inventory of the physical MMDVM HAT/firmware and the compiled MMDVM-Host runtime. These are separate layers: rebuilding YWD-Extended does not flash the HAT firmware.</p>

      <section class="modem-section">
        <div class="modem-section-title">HAT / MODEM FIRMWARE</div>
        <div id="mmdvmHatInfo" class="modem-grid"></div>
      </section>

      <section class="modem-section">
        <div class="modem-section-title">MMDVM-HOST RUNTIME</div>
        <div id="mmdvmRuntimeInfo" class="modem-grid"></div>
        <div id="mmdvmCapabilities" class="modem-capabilities"></div>
        <div id="mmdvmUpgradeReason" class="notice" hidden></div>
      </section>

      <details class="modem-details">
        <summary>BUILD / PROVENANCE DETAILS</summary>
        <div class="modem-details-body"><div id="mmdvmBuildDetails" class="modem-grid"></div></div>
      </details>

      <details class="modem-details">
        <summary>MODEM JOURNAL IDENTITY LINES</summary>
        <div class="modem-details-body"><pre id="mmdvmJournalIdentity" class="modem-journal">Checking current-boot MMDVMHost journal…</pre></div>
      </details>

      <div class="modem-maintenance">
        <div class="modem-section-title">RUNTIME MAINTENANCE</div>
        <p class="hint">Reserved for future guarded maintenance. RC3 UI polish is read-only here: no compile/install, RF restart, or HAT firmware flash is exposed yet.</p>
        <div class="buttonrow wrap">
          <button id="mmdvmRefreshInfo" class="btn modem-refresh" type="button">REFRESH INFO</button>
          <button class="btn primary" type="button" disabled title="Planned for a future guarded runtime-maintenance workflow">BUILD / UPDATE YWD-EXTENDED</button>
          <button class="btn" type="button" disabled title="Physical HAT firmware maintenance is a separate future workflow">HAT FIRMWARE TOOLS</button>
        </div>
        <div id="mmdvmCollectedAt" class="hint">Collecting modem inventory…</div>
      </div>`;

    const dmr = document.getElementById('dmridCard');
    const host = document.getElementById('hostPowerCard');
    grid.insertBefore(card, dmr || host || runtime.nextSibling);

    document.getElementById('mmdvmRefreshInfo').onclick = async event => {
      const button = event.currentTarget;
      if (button.dataset.busy === '1') return;
      const old = button.textContent;
      button.dataset.busy = '1';
      button.disabled = true;
      button.textContent = 'REFRESHING…';
      try {
        await load(true);
      } finally {
        delete button.dataset.busy;
        button.disabled = false;
        button.textContent = old;
      }
    };
    load(false);
    return true;
  }

  let tries = 0;
  const timer = setInterval(() => {
    tries += 1;
    if (install() || tries >= 120) clearInterval(timer);
  }, 100);
  if (install()) clearInterval(timer);
})();
