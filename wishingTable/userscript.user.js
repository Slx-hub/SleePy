// ==UserScript==
// @name         SleePy Downloader
// @namespace    sleepy-downloader
// @version      1.0
// @description  Adds a button to YouTube watch pages that downloads the current video as WAV to SleePy
// @match        https://www.youtube.com/*
// @grant        GM_xmlhttpRequest
// @connect      127.0.0.1
// @run-at       document-idle
// ==/UserScript==

(function () {
  'use strict';

  const SERVER = 'http://127.0.0.1:5001';

  // ── Button ──────────────────────────────────────────────────────────────────
  const btn = document.createElement('button');
  btn.id = 'sleepy-dl-btn';
  Object.assign(btn.style, {
    position:   'fixed',
    bottom:     '80px',
    right:      '24px',
    zIndex:     '9999',
    padding:    '10px 18px',
    borderRadius: '20px',
    border:     'none',
    background: '#ff0000',
    color:      '#fff',
    fontFamily: 'Roboto, Arial, sans-serif',
    fontSize:   '14px',
    fontWeight: '600',
    cursor:     'pointer',
    boxShadow:  '0 2px 8px rgba(0,0,0,0.45)',
    display:    'none',
    userSelect: 'none',
  });
  document.body.appendChild(btn);

  // ── State helpers ────────────────────────────────────────────────────────────
  const STATES = {
    idle:    { bg: '#ff0000', label: '⬇ SleePy', disabled: false },
    loading: { bg: '#888888', label: '⏳ Downloading…', disabled: true },
    success: { bg: '#2a9d2a', label: null,             disabled: false },
    error:   { bg: '#cc0000', label: null,             disabled: false },
  };

  function setState(key, customLabel) {
    const s = STATES[key];
    btn.style.background = s.bg;
    btn.textContent      = customLabel ?? s.label;
    btn.disabled         = s.disabled;
  }

  function resetAfter(ms) {
    setTimeout(() => setState('idle'), ms);
  }

  // ── Visibility ───────────────────────────────────────────────────────────────
  function checkPage() {
    const onWatch = location.pathname === '/watch' &&
                    new URLSearchParams(location.search).has('v');
    btn.style.display = onWatch ? 'block' : 'none';
    if (onWatch) setState('idle');
  }

  // ── Click handler ────────────────────────────────────────────────────────────
  btn.addEventListener('click', () => {
    setState('loading');

    GM_xmlhttpRequest({
      method:  'POST',
      url:     `${SERVER}/download`,
      headers: { 'Content-Type': 'application/json' },
      data:    JSON.stringify({ url: location.href }),
      timeout: 660000, // 11 min — covers long videos + scp transfer

      onload(res) {
        try {
          const json = JSON.parse(res.responseText);
          if (json.status === 'ok') {
            setState('success', `✓ ${json.file}`);
            resetAfter(6000);
          } else {
            const detail = json.detail ?? 'Unknown error';
            setState('error', `✗ ${detail.slice(0, 60)}`);
            resetAfter(5000);
          }
        } catch {
          setState('error', '✗ Bad response');
          resetAfter(4000);
        }
      },

      onerror() {
        setState('error', '✗ Server unreachable — is it running?');
        resetAfter(5000);
      },

      ontimeout() {
        setState('error', '✗ Timed out');
        resetAfter(4000);
      },
    });
  });

  // ── SPA navigation detection ─────────────────────────────────────────────────
  // YouTube fires this custom event after each client-side navigation.
  window.addEventListener('yt-navigate-finish', checkPage);

  // Fallback: patch history.pushState for any navigation that doesn't fire the above.
  const _push = history.pushState.bind(history);
  history.pushState = function (...args) {
    _push(...args);
    setTimeout(checkPage, 150);
  };

  checkPage();
})();
