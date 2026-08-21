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
    padding:      '10px 18px',
    borderRadius: '20px',
    border:       'none',
    background:   '#ff0000',
    color:        '#fff',
    fontFamily:   'Roboto, Arial, sans-serif',
    fontSize:     '14px',
    fontWeight:   '600',
    cursor:       'pointer',
    marginLeft:   '8px',
    alignSelf:    'center',
    userSelect:   'none',
    flexShrink:   '0',
  });

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

  // ── Injection ────────────────────────────────────────────────────────────────
  let observer = null;

  function inject() {
    const anchor = document.querySelector('ytd-subscribe-button-renderer')?.parentElement;
    if (!anchor || anchor.contains(btn)) return false;
    anchor.insertAdjacentElement('afterend', btn);
    return true;
  }

  function waitAndInject() {
    if (inject()) return;
    if (observer) observer.disconnect();
    observer = new MutationObserver(() => {
      if (inject()) {
        observer.disconnect();
        observer = null;
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  // ── Visibility ───────────────────────────────────────────────────────────────
  function checkPage() {
    const onWatch = location.pathname === '/watch' &&
                    new URLSearchParams(location.search).has('v');
    if (!onWatch) {
      btn.remove();
      return;
    }
    setState('idle');
    waitAndInject();
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
            const label = json.files?.length > 1
              ? `✓ ${json.files.length} files`
              : `✓ ${json.file}`;
            setState('success', label);
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
