'use strict';
(() => {
  let modalResolve = null;
  let modalLastFocus = null;
  let modalCloseTimer = null;
  const reduceMotion = !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

  // Reuse the dashboard's existing CSP-approved modal/dialog/button styles.
  const overlay = document.createElement('div');
  overlay.className = 'modal';
  overlay.id = 'ywdConfirmModal';
  overlay.setAttribute('role', 'dialog');
  overlay.setAttribute('aria-modal', 'true');
  overlay.innerHTML = `
    <div class="dialog" id="ywdModalCard">
      <div class="card-title" id="ywdModalKicker">YWD // HOTSPOT</div>
      <div class="who" id="ywdModalTitle">CONFIRM ACTION</div>
      <p class="hint" id="ywdModalMessage"></p>
      <div class="buttonrow wrap">
        <button class="btn" id="ywdModalCancel">CANCEL</button>
        <button class="btn primary" id="ywdModalConfirm">CONFIRM</button>
      </div>
    </div>`;
  document.body.append(overlay);

  function finishModalClose(resolve, value) {
    overlay.classList.remove('on', 'closing');
    if (modalLastFocus && typeof modalLastFocus.focus === 'function') modalLastFocus.focus();
    modalLastFocus = null;
    if (resolve) resolve(value);
  }

  function closeModal(value) {
    const resolve = modalResolve;
    modalResolve = null;
    clearTimeout(modalCloseTimer);
    if (!overlay.classList.contains('on') || reduceMotion) {
      finishModalClose(resolve, value);
      return;
    }
    overlay.classList.add('closing');
    modalCloseTimer = setTimeout(() => finishModalClose(resolve, value), 125);
  }

  window.ywdConfirm = function({
    title = 'CONFIRM ACTION',
    message = '',
    confirmText = 'CONFIRM',
    cancelText = 'CANCEL',
    tone = 'normal',
    kicker = 'YWD // HOTSPOT'
  } = {}) {
    if (modalResolve) {
      const previous = modalResolve;
      modalResolve = null;
      previous(false);
    }
    clearTimeout(modalCloseTimer);
    overlay.classList.remove('closing');
    modalLastFocus = document.activeElement;
    $('ywdModalTitle').textContent = title;
    $('ywdModalMessage').textContent = message;
    $('ywdModalConfirm').textContent = confirmText;
    $('ywdModalCancel').textContent = cancelText;
    $('ywdModalKicker').textContent = kicker;
    $('ywdModalKicker').className = 'card-title' + (tone === 'danger' ? ' badtext' : tone === 'warn' ? ' warntext2' : '');
    $('ywdModalConfirm').className = 'btn ' + (tone === 'danger' || tone === 'warn' ? 'danger' : 'primary');
    overlay.classList.add('on');
    setTimeout(() => $('ywdModalConfirm').focus(), reduceMotion ? 0 : 30);
    return new Promise(resolve => { modalResolve = resolve; });
  };

  $('ywdModalCancel').onclick = () => closeModal(false);
  $('ywdModalConfirm').onclick = () => closeModal(true);
  overlay.addEventListener('click', e => {
    if (e.target === overlay) closeModal(false);
  });
  document.addEventListener('keydown', e => {
    if (!overlay.classList.contains('on')) return;
    if (e.key === 'Escape') {
      e.preventDefault();
      closeModal(false);
    }
  });

  function beginBusy(el, label = 'WORKING…') {
    if (!el || el.dataset.ywdBusy === '1') return () => {};
    const previous = {
      disabled: !!el.disabled,
      text: el.textContent,
      ariaBusy: el.getAttribute('aria-busy')
    };
    el.dataset.ywdBusy = '1';
    el.disabled = true;
    el.classList.add('ywd-working');
    el.setAttribute('aria-busy', 'true');
    if (label) el.textContent = label;
    return () => {
      delete el.dataset.ywdBusy;
      el.classList.remove('ywd-working');
      el.textContent = previous.text;
      if (previous.ariaBusy == null) el.removeAttribute('aria-busy');
      else el.setAttribute('aria-busy', previous.ariaBusy);
      el.disabled = previous.disabled;
      if (typeof setCtl === 'function') setCtl();
    };
  }

  function ensureLoginFeedback() {
    const modal = $('loginModal');
    const pw = $('loginPw');
    if (!modal || !pw) return null;
    let feedback = $('loginFeedback');
    if (!feedback) {
      feedback = document.createElement('div');
      feedback.id = 'loginFeedback';
      feedback.className = 'login-feedback';
      feedback.hidden = true;
      feedback.setAttribute('role', 'alert');
      feedback.setAttribute('aria-live', 'assertive');
      pw.insertAdjacentElement('afterend', feedback);
    }
    return feedback;
  }

  function clearLoginFeedback() {
    const feedback = ensureLoginFeedback();
    if (feedback) {
      feedback.textContent = '';
      feedback.hidden = true;
    }
    $('loginPw')?.removeAttribute('aria-invalid');
  }

  function showLoginFeedback(message) {
    const feedback = ensureLoginFeedback();
    if (!feedback) return;
    feedback.textContent = message;
    feedback.hidden = false;
    $('loginPw')?.setAttribute('aria-invalid', 'true');
  }

  // Replace the old toast-only login failure with feedback that remains visible
  // inside the unlock modal. A failed attempt clears and refocuses the password.
  ensureLoginFeedback();
  if ($('loginBtn')) $('loginBtn').onclick = () => {
    clearLoginFeedback();
    $('loginPw').value = '';
    $('loginModal').classList.add('on');
    setTimeout(() => $('loginPw').focus(), 50);
  };
  if ($('doLogin')) $('doLogin').onclick = async () => {
    clearLoginFeedback();
    const button = $('doLogin');
    const done = beginBusy(button, 'CHECKING…');
    try {
      await post('/api/login', {password: $('loginPw').value});
      $('loginModal').classList.remove('on');
      toast('Control mode unlocked');
      await getStatus();
      loadConfig(true);
    } catch (e) {
      const raw = String(e?.message || '').trim();
      const authFailure = /password|unauthorized|forbidden|invalid|authentication/i.test(raw);
      $('loginPw').value = '';
      showLoginFeedback(authFailure ? 'Incorrect password. Try again.' : (raw || 'Could not unlock controls. Try again.'));
      setTimeout(() => $('loginPw').focus(), 30);
    } finally {
      done();
    }
  };
  if ($('loginPw')) {
    $('loginPw').onkeydown = e => { if (e.key === 'Enter') { e.preventDefault(); $('doLogin').click(); } };
    $('loginPw').addEventListener('input', clearLoginFeedback);
  }
  document.querySelector('[data-close="loginModal"]')?.addEventListener('click', clearLoginFeedback);

  // Settings remain readable while the dashboard is locked, but every editable
  // control follows the same authenticated control session as the rest of the UI.
  // Preserve each non-auth control's existing disabled state so mode-specific
  // controls (for example simplex/duplex frequency fields) restore correctly.
  const settingsPage = $('settings');
  let settingsLocked = null;
  function ensureSettingsLockNotice() {
    if (!settingsPage) return null;
    let notice = $('settingsLockState');
    if (!notice) {
      notice = document.createElement('div');
      notice.id = 'settingsLockState';
      notice.className = 'notice';
      notice.setAttribute('role', 'status');
      const bar = settingsPage.querySelector('.settingsbar');
      if (bar) bar.insertAdjacentElement('afterend', notice);
      else settingsPage.prepend(notice);
    }
    return notice;
  }

  function syncSettingsLock() {
    if (!settingsPage) return;
    const locked = !(typeof state !== 'undefined' && state?.controls?.authenticated);
    const notice = ensureSettingsLockNotice();
    if (notice) {
      notice.hidden = !locked;
      notice.textContent = 'SETTINGS LOCKED · Unlock the dashboard to edit configuration.';
    }
    settingsPage.classList.toggle('settings-locked', locked);
    settingsPage.setAttribute('aria-readonly', locked ? 'true' : 'false');

    settingsPage.querySelectorAll('input,select,textarea,button').forEach(el => {
      if (locked) {
        if (!Object.prototype.hasOwnProperty.call(el.dataset, 'ywdLockDisabled')) {
          el.dataset.ywdLockDisabled = el.classList.contains('ctl') ? 'managed' : (el.disabled ? '1' : '0');
        }
        el.disabled = true;
      } else if (Object.prototype.hasOwnProperty.call(el.dataset, 'ywdLockDisabled')) {
        const previous = el.dataset.ywdLockDisabled;
        if (previous !== 'managed') el.disabled = previous === '1';
        delete el.dataset.ywdLockDisabled;
      }
    });
    settingsLocked = locked;
  }

  if (settingsPage && typeof render === 'function') {
    const baseSettingsRender = render;
    render = function(d) {
      baseSettingsRender(d);
      syncSettingsLock();
    };
    const settingsObserver = new MutationObserver(() => {
      if (settingsLocked) syncSettingsLock();
    });
    settingsObserver.observe(settingsPage, {childList:true, subtree:true});
    syncSettingsLock();
  }

  function runBusy(el, label, fn) {
    const done = beginBusy(el, label);
    let result;
    try {
      result = fn();
    } catch (e) {
      done();
      throw e;
    }
    if (result && typeof result.then === 'function') {
      return Promise.resolve(result).finally(done);
    }
    done();
    return result;
  }

  function invokeWithNativeConfirmAccepted(el, ev, busyText = null) {
    const fn = el && el.onclick;
    if (typeof fn !== 'function') return;
    const invoke = () => {
      const nativeConfirm = window.confirm;
      window.confirm = () => true;
      try {
        return fn.call(el, ev);
      } finally {
        window.confirm = nativeConfirm;
      }
    };
    return busyText ? runBusy(el, busyText, invoke) : invoke();
  }

  function wrapWorking(id, label) {
    const el = $(id);
    if (!el || el.dataset.ywdWorkingWrapped === '1' || typeof el.onclick !== 'function') return;
    const original = el.onclick;
    el.dataset.ywdWorkingWrapped = '1';
    el.onclick = function(ev) {
      return runBusy(el, label, () => original.call(el, ev));
    };
  }

  function detailsFor(el) {
    if (!el) return null;
    const id = el.id || '';
    if (id === 'dropDyn' || id === 'tgDropDynamic') return {
      title: 'DROP DYNAMIC TALKGROUPS',
      message: 'Drop every dynamic talkgroup currently linked to this hotspot?\n\nStatic talkgroups are not removed.',
      confirmText: 'DROP DYNAMIC', tone: 'warn', busyText: 'DROPPING…'
    };
    if (id === 'startRf') return {
      title: 'START RF STACK',
      message: 'Start MMDVM-Host and the BrandMeister network path now?\n\nVerify the antenna and configured frequency before transmitting.',
      confirmText: 'START RF', tone: 'warn', busyText: 'STARTING…'
    };
    if (id === 'stopRf') return {
      title: 'STOP RF STACK',
      message: 'Stop the active RF + BrandMeister stack now?\n\nThis runtime action does not rewrite unrelated configuration.',
      confirmText: 'STOP RF', tone: 'warn', busyText: 'STOPPING…'
    };
    if (id === 'restartRf') return {
      title: 'RESTART RF STACK',
      message: 'Restart the currently running RF stack?\n\nA brief DMR interruption is expected.',
      confirmText: 'RESTART', tone: 'warn', busyText: 'RESTARTING…'
    };
    if (id === 'rebootPi') return {
      title: 'REBOOT RASPBERRY PI',
      message: 'Reboot the hotspot now?\n\nThe WebUI and DMR services will be unavailable while the Pi restarts.',
      confirmText: 'REBOOT PI', tone: 'danger', busyText: 'REBOOTING…'
    };
    if (id === 'resetCal') return {
      title: 'NEW CALIBRATION SESSION',
      message: 'Clear the recorded calibration result table and start a new test?\n\nCurrent RF settings are not changed.',
      confirmText: 'START NEW TEST', tone: 'warn', busyText: 'RESETTING…'
    };
    if (id === 'restoreBaseline') return {
      title: 'RESTORE CALIBRATION BASELINE',
      message: 'Restore the saved baseline modem/RF settings and apply them now?',
      confirmText: 'RESTORE + APPLY', tone: 'warn', busyText: 'RESTORING…'
    };
    if (id === 'calUseBest') return {
      title: 'USE RECOMMENDED RX OFFSET',
      message: 'Apply the currently recommended RX offset?\n\nThe configuration will be saved/applied and the active RF stack may restart.',
      confirmText: 'USE BEST OFFSET', tone: 'warn', busyText: 'APPLYING…'
    };
    if (id === 'tgApplyPlan') {
      const d = typeof tgDiff === 'function' ? tgDiff() : {add: [], remove: []};
      const rows = [];
      if (d.add.length) rows.push('ADD: ' + d.add.join(', '));
      if (d.remove.length) rows.push('REMOVE: ' + d.remove.join(', '));
      return {
        title: 'APPLY STATIC TALKGROUP PLAN',
        message: (rows.join('\n') || 'No changes planned.') + '\n\nChanges are sent to BrandMeister on simplex slot 0.',
        confirmText: 'APPLY PLAN', tone: d.remove.length ? 'warn' : 'normal', busyText: 'APPLYING…'
      };
    }
    if (el.matches('.calAdj')) return {
      title: 'ADJUST RX OFFSET',
      message: `Change RX offset by ${el.dataset.delta} Hz and restart the active RF stack?`,
      confirmText: 'APPLY RX STEP', tone: 'warn', busyText: 'APPLYING…'
    };
    if (el.matches('.txAdj')) return {
      title: 'ADJUST TX OFFSET',
      message: `Change TX offset by ${el.dataset.delta} Hz and restart the active RF stack?`,
      confirmText: 'APPLY TX STEP', tone: 'warn', busyText: 'APPLYING…'
    };
    if (el.matches('[data-del-tg]')) return {
      title: 'REMOVE STATIC TALKGROUP',
      message: `Remove static TG ${el.dataset.delTg} from BrandMeister?`,
      confirmText: 'REMOVE TG', tone: 'warn', busyText: 'REMOVING…'
    };
    if (el.matches('[data-revert]')) return {
      title: 'RESTORE CONFIGURATION',
      message: 'Restore this saved configuration snapshot and apply it now?',
      confirmText: 'RESTORE + APPLY', tone: 'warn', busyText: 'RESTORING…'
    };
    if (el.matches('[data-set-del]')) {
      const s = typeof tgSets === 'function' ? tgSets()[Number(el.dataset.setDel)] : null;
      return {
        title: 'DELETE SAVED TG SET',
        message: `Delete saved set “${s?.name || 'this set'}”?\n\nThis does not change BrandMeister routes.`,
        confirmText: 'DELETE SET', tone: 'danger'
      };
    }
    return null;
  }

  // Apply Configuration is special: the original handler asks after the save request.
  if ($('applyConfig')) $('applyConfig').onclick = async () => {
    try {
      const c = formConfig();
      const s = await post('/api/config/save', {config: c});
      configDoc = c;
      setDirty(false);
      toast(s.changed?.length ? `Saved ${s.changed.length} change(s)` : 'No changes');
      const h = s.hints || {}, parts = [];
      if (h.rf) parts.push('RF/DMR stack');
      if (h.oled) parts.push('OLED');
      if (h.dashboard) parts.push('dashboard');
      if (h.journald) parts.push('journald');
      if (h.autostart) parts.push('boot policy');
      if (s.changed?.length && parts.length) {
        const ok = await ywdConfirm({
          title: 'SAVE + APPLY CONFIGURATION',
          message: `Apply the saved configuration now?\n\nAffected: ${parts.join(', ')}`,
          confirmText: 'APPLY NOW', tone: h.rf ? 'warn' : 'normal'
        });
        if (!ok) {
          toast('Saved; changes remain pending');
          getStatus();
          return;
        }
      }
      const a = await post('/api/config/apply', {});
      toast(a.changed?.length ? 'Configuration applied' : 'Configuration already applied');
      if (a.dashboard_restart_pending) {
        const port = a.new_port;
        toast(`Dashboard restarting${port ? ' on port ' + port : ''}…`);
        if (port && Number(port) !== Number(location.port || 80)) {
          setTimeout(() => { location.href = `${location.protocol}//${location.hostname}:${port}/`; }, 4500);
        }
      }
      setTimeout(() => { getStatus(); loadConfig(true); }, 800);
    } catch (e) {
      toast(e.message, true);
    }
  };

  // Add a small visible busy state to common async operations that do not need
  // a confirmation dialog. Confirmed operations are handled below after consent.
  [
    ['dropQso', 'DROPPING…'],
    ['addTg', 'ADDING…'],
    ['restartOled', 'RESTARTING…'],
    ['restartActivity', 'RESTARTING…'],
    ['saveConfig', 'SAVING…'],
    ['applyConfig', 'APPLYING…'],
    ['recordCal', 'RECORDING…'],
    ['saveBaseline', 'SAVING…'],
    ['tgSearchBtn', 'SEARCHING…'],
    ['tgRefreshDirectory', 'REFRESHING…']
  ].forEach(([id, label]) => wrapWorking(id, label));

  // update.js creates the confirmation modal after this file loads. Capture the
  // click so the button responds immediately while /api/update/start launches
  // the detached update service; the progress modal takes over when it is ready.
  document.addEventListener('click', e => {
    const button = e.target.closest?.('#confirmUpdate');
    if (!button || button.dataset.ywdUpdateStarting === '1') return;
    const previousText = button.textContent;
    const previousAria = button.getAttribute('aria-busy');
    button.dataset.ywdUpdateStarting = '1';
    button.classList.add('ywd-working');
    button.setAttribute('aria-busy', 'true');
    button.textContent = 'STARTING…';
    setTimeout(() => {
      const cancel = $('cancelUpdate');
      if (cancel) cancel.disabled = true;
    }, 0);

    let timer = null;
    const reset = () => {
      if (timer) clearInterval(timer);
      delete button.dataset.ywdUpdateStarting;
      button.classList.remove('ywd-working');
      button.textContent = previousText;
      if (previousAria == null) button.removeAttribute('aria-busy');
      else button.setAttribute('aria-busy', previousAria);
      const cancel = $('cancelUpdate');
      if (cancel) cancel.disabled = false;
    };
    let ticks = 0;
    timer = setInterval(() => {
      const modal = $('updateModal');
      if (!modal || !modal.classList.contains('on') || ++ticks >= 300) reset();
    }, 100);
  }, true);

  // Capture dangerous/confirming actions before their existing onclick handlers.
  document.addEventListener('click', async e => {
    const el = e.target.closest('button,[data-revert],[data-del-tg],[data-set-del]');
    if (!el || !document.body.contains(el) || overlay.contains(el)) return;

    // Talkgroup Manager owns its own confirmations because it has the authoritative
    // duplex/timeslot context. Do not intercept these controls in the generic layer.
    if (el.id === 'dropDyn' || el.id === 'tgDropDynamic' || el.id === 'tgApplyPlan' ||
        el.id === 'tgSaveSet' || el.matches('[data-set-del]')) return;

    // Leaving dirty Settings gets a themed in-app dialog. Browser close/reload
    // remains the native beforeunload prompt by browser design.
    if (el.matches('.tabs button')) {
      const current = document.querySelector('.tabs button.on')?.dataset.tab;
      if (current === 'settings' && el.dataset.tab !== 'settings' && typeof dirty !== 'undefined' && dirty) {
        e.preventDefault();
        e.stopImmediatePropagation();
        const ok = await ywdConfirm({
          title: 'DISCARD UNSAVED SETTINGS?',
          message: 'You have unsaved Settings form edits.\n\nLeave Settings and discard those edits?',
          confirmText: 'DISCARD + LEAVE', tone: 'warn'
        });
        if (ok) invokeWithNativeConfirmAccepted(el, e);
      }
      return;
    }

    // Saving an existing TG set has a conditional native confirm in the core handler.
    if (el.id === 'tgSaveSet' && typeof tgSets === 'function') {
      const name = $('tgSetName')?.value.trim().slice(0, 40) || '';
      const existing = tgSets().find(x => x.name.toLowerCase() === name.toLowerCase());
      if (existing) {
        e.preventDefault();
        e.stopImmediatePropagation();
        const ok = await ywdConfirm({
          title: 'REPLACE SAVED TG SET',
          message: `Replace saved set “${existing.name}” with the current plan?`,
          confirmText: 'REPLACE SET', tone: 'warn'
        });
        if (ok) invokeWithNativeConfirmAccepted(el, e);
      }
      return;
    }

    const d = detailsFor(el);
    if (!d) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    const ok = await ywdConfirm(d);
    if (ok) invokeWithNativeConfirmAccepted(el, e, d.busyText || null);
  }, true);
})();
