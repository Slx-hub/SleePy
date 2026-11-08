### Notes I will need in 2 years:

- Sounds are generated with Midi using "Whistle" sound, normalized to -10 dB
- Canned tracks are downloaded using **wishingTable**: a local FastAPI server + Violentmonkey userscript that adds a "⬇ SleePy" button to YouTube. Clicking it downloads the video's audio via yt-dlp and transfers it to `~/Music/local/input/` on the Pi over SSH.
  - Audio stays in YouTube's own format (usually Opus, ~1 MB/min). Until Nov 2026 everything was converted to WAV, which was ~10x bigger for no quality gain and too slow over the Pi's 2.4 GHz Wi-Fi (~4.5 MB/s); the old WAV library was re-encoded to Opus 160k then. On the Pi, `.wav` plays via `aplay` (UI sounds), everything else via `mpv`.
  - The second, blue "⬇ from m:ss" button does the same but cuts off everything before the current playback position — scrub to where the actual content starts, then click. Shift-click it to type an exact offset instead; the label then shows what the next click will cut. Under the hood it POSTs `start_seconds` and the server trims the file with `ffmpeg -ss` (stream copy, no re-encode; the cut lands within ~20 ms).
  - Run: `.\start.ps1` (or use the VS Code launch config)
  - Browser: install `wishingTable/userscript.user.js` via Violentmonkey
  - Requires: yt-dlp & deno & ffmpeg (via choco f.ex.), and SSH host `SleePy` configured in `~/.ssh/config`
  - Backup: `python wishingTable\sync_asmr.py` mirrors the Pi's `~/Music/local/asmr` to `C:\Users\Janis\Music\sleepy_download` (one-way: new / size-changed files get downloaded, files gone from the Pi get deleted on the PC). Add `--dry-run` to preview.
- Services are set up by `setup.sh`: the jingle is a **user** service (needs PipeWire from the autologin session), the boot health check is a system service.
- **Num Lock blinking 2x/second = bad boot.** Some boots come up with corrupted memory (random SEGV/ILL crashes, likely the no-name SD card) and have no audio. `setup/boot_healthcheck.sh` detects this ~60s after boot and reboots, max 2 times in a row; after that it just keeps blinking -> power cycle. Logs: `journalctl -u sleepy_healthcheck -b`
