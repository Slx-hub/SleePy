// ==UserScript==
// @name         SleePy Downloader
// @namespace    sleepy-downloader
// @version      1.2
// @description  Adds buttons to YouTube watch pages that download the current video's audio to SleePy, optionally cutting off everything before the current playback position
// @match        https://www.youtube.com/*
// @grant        GM_xmlhttpRequest
// @connect      127.0.0.1
// @run-at       document-idle
// ==/UserScript==

(function () {
  'use strict';

  const SERVER = 'http://127.0.0.1:5001';

  // ── Time helpers ─────────────────────────────────────────────────────────────
  function formatTime(total) {
    const s = Math.max(0, Math.floor(total));
    const pad = n => String(n).padStart(2, '0');
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    return h ? `${h}:${pad(m)}:${pad(s % 60)}` : `${m}:${pad(s % 60)}`;
  }

  // Accepts "90", "1:30" and "1:02:03". Blank fields are rejected rather than
  // coerced to 0, so an empty prompt does not quietly mean "cut nothing".
  function parseTime(text) {
    const parts = text.trim().split(':');
    if (parts.some(p => p.trim() === '')) return null;
    const nums = parts.map(Number);
    if (nums.some(n => !Number.isFinite(n) || n < 0)) return null;
    return nums.reduce((acc, n) => acc * 60 + n, 0);
  }

  function playerTime() {
    const v = document.querySelector('video.html5-main-video') ||
              document.querySelector('video');
    return v && Number.isFinite(v.currentTime) ? Math.floor(v.currentTime) : 0;
  }

  // A shift-click sets an explicit offset that overrides the live player
  // position until the next navigation.
  let manualStart = null;

  const startAt = () => manualStart ?? playerTime();

  // ── Buttons ──────────────────────────────────────────────────────────────────
  const BASE_STYLE = {
    padding:      '10px 18px',
    borderRadius: '20px',
    border:       'none',
    color:        '#fff',
    fontFamily:   'Roboto, Arial, sans-serif',
    fontSize:     '14px',
    fontWeight:   '600',
    cursor:       'pointer',
    marginLeft:   '8px',
    alignSelf:    'center',
    userSelect:   'none',
    flexShrink:   '0',
  };

  function makeButton(id, idleBg, title) {
    const b = document.createElement('button');
    b.id = id;
    b.title = title;
    b.idleBg = idleBg;
    Object.assign(b.style, BASE_STYLE);
    return b;
  }

  const fullBtn = makeButton('sleepy-dl-btn', '#ff0000',
    'Download the whole video as WAV to SleePy');
  const trimBtn = makeButton('sleepy-dl-trim-btn', '#065fd4',
    'Download, cutting off everything before this point.\nShift-click to type an exact offset.');

  const bar = document.createElement('span');
  Object.assign(bar.style, {
    display: 'inline-flex', alignItems: 'center', flexShrink: '0',
  });
  bar.append(fullBtn, trimBtn);

  // ── State ────────────────────────────────────────────────────────────────────
  // Locked while a download runs and while its result is still on screen, so the
  // live-position ticker below does not overwrite the outcome.
  let uiLocked = false;

  const idleLabel = b =>
    b === fullBtn ? '⬇ SleePy' : `⬇ from ${formatTime(startAt())}`;

  function refreshTrimBtn() {
    trimBtn.textContent = idleLabel(trimBtn);
    // Nothing to cut at the very start of the video.
    trimBtn.style.display = startAt() > 0 ? '' : 'none';
  }

  function setIdle() {
    uiLocked = false;
    for (const b of [fullBtn, trimBtn]) {
      b.style.background = b.idleBg;
      b.textContent      = idleLabel(b);
      b.disabled         = false;
    }
    refreshTrimBtn();
  }

  function setBusy(b, label) {
    uiLocked = true;
    b.style.background = '#888888';
    b.textContent      = label;
    fullBtn.disabled = trimBtn.disabled = true;
  }

  function setResult(b, bg, label, ms) {
    uiLocked = true;
    b.style.background = bg;
    b.textContent      = label;
    fullBtn.disabled = trimBtn.disabled = false;
    setTimeout(setIdle, ms);
  }

  // Keep the trim button's label in step with the player as you scrub.
  setInterval(() => {
    if (!uiLocked && trimBtn.isConnected) refreshTrimBtn();
  }, 500);

  // ── Injection ────────────────────────────────────────────────────────────────
  let observer = null;

  function inject() {
    const anchor = document.querySelector('ytd-subscribe-button-renderer')?.parentElement;
    if (!anchor || anchor.contains(bar)) return false;
    anchor.insertAdjacentElement('afterend', bar);
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
      bar.remove();
      return;
    }
    manualStart = null;
    setIdle();
    waitAndInject();
  }

  // ── Download ─────────────────────────────────────────────────────────────────
  function download(button, startSeconds) {
    setBusy(button, startSeconds > 0
      ? `⏳ from ${formatTime(startSeconds)}…`
      : '⏳ Downloading…');

    GM_xmlhttpRequest({
      method:  'POST',
      url:     `${SERVER}/download`,
      headers: { 'Content-Type': 'application/json' },
      data:    JSON.stringify({ url: location.href, start_seconds: startSeconds }),
      // Backstop only: the server times out each step itself (yt-dlp 10 min,
      // trim 5 min, scp scaled to file size) and always answers. Giving up
      // here first would just hide that answer.
      timeout: 3600000, // 60 min

      onload(res) {
        try {
          const json = JSON.parse(res.responseText);
          if (json.status === 'ok') {
            const label = json.files?.length > 1
              ? `✓ ${json.files.length} files`
              : `✓ ${json.file}`;
            setResult(button, '#2a9d2a', label, 6000);
          } else {
            const detail = json.detail ?? 'Unknown error';
            const text = typeof detail === 'string'
              ? detail
              : (detail[0]?.msg ?? 'Invalid request');
            setResult(button, '#cc0000', `✗ ${text.slice(0, 60)}`, 5000);
          }
        } catch {
          setResult(button, '#cc0000', '✗ Bad response', 4000);
        }
      },

      onerror() {
        setResult(button, '#cc0000', '✗ Server unreachable — is it running?', 5000);
      },

      ontimeout() {
        setResult(button, '#cc0000', '✗ Timed out', 4000);
      },
    });
  }

  fullBtn.addEventListener('click', () => download(fullBtn, 0));

  trimBtn.addEventListener('click', ev => {
    // Shift-click only *sets* the offset — the label then shows exactly what
    // the next plain click will cut.
    if (ev.shiftKey) {
      const answer = prompt('Cut everything before (mm:ss):', formatTime(startAt()));
      if (answer === null) return;
      const secs = parseTime(answer);
      if (secs === null) {
        setResult(trimBtn, '#cc0000', '✗ Bad time', 3000);
        return;
      }
      manualStart = secs;
      setIdle();
      return;
    }
    download(trimBtn, startAt());
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
