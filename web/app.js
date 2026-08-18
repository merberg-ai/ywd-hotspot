'use strict';
(() => {
  function loadStyle(href) {
    const l = document.createElement('link');
    l.rel = 'stylesheet';
    l.href = href;
    l.onerror = () => console.error(`YWD-Hotspot failed to load ${href}`);
    document.head.appendChild(l);
  }
  function load(src, next) {
    const s = document.createElement('script');
    s.src = src;
    s.async = false;
    s.onload = () => next && next();
    s.onerror = () => console.error(`YWD-Hotspot failed to load ${src}`);
    document.head.appendChild(s);
  }
  loadStyle('/ui-polish.css?v=alpha12.2');
  loadStyle('/update.css?v=alpha12.1');
  loadStyle('/instrumentation.css?v=alpha12.1');
  loadStyle('/plugin-manager.css?v=alpha17');
  loadStyle('/backup-restore.css?v=alpha18.2.1');
  load('/app-core.js', () => load('/backup-restore.js?v=alpha18.2.1', () => load('/talkgroups.js?v=alpha12.1', () => load('/ui-polish.js?v=alpha12.2', () => load('/update.js?v=alpha12.3', () => load('/update-progress.js?v=alpha16.1', () => load('/instrumentation.js?v=alpha12.1', () => load('/instrumentation-bootstrap.js?v=alpha12.1', () => load('/plugin-manager-render.js?v=alpha18.2', () => load('/plugin-package-actions.js?v=alpha18.2', () => load('/plugin-package-upload.js?v=alpha18.2', () => load('/plugin-manager.js?v=alpha18.2', () => load('/plugin-config-actions.js?v=alpha16', () => load('/plugin-telemetry.js?v=alpha18'))))))))))))));
})();
