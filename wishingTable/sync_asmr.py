"""Mirror the Pi's ASMR folder onto this PC (one-way: Pi -> PC).

  new on the Pi             -> downloaded here
  size differs from the Pi  -> downloaded again
  gone from the Pi          -> deleted here

Nothing on the Pi is ever changed. Uses the `SleePy` host from ~/.ssh/config and
only the standard library, so no venv is needed.

Usage:
    python sync_asmr.py            # sync
    python sync_asmr.py --dry-run  # only show what would change
"""

import argparse
import shlex
import subprocess
import sys
from pathlib import Path

SSH_HOST = "SleePy"
REMOTE_DIR = "/home/pi/Music/local/asmr"
LOCAL_DIR = Path(r"C:\Users\Janis\Music\sleepy_download")

# Downloads land in "<name>.partial" first and are renamed once complete, so an
# aborted run never leaves a truncated file under the real name. A leftover
# .partial doesn't exist on the Pi, so the next run deletes it.
PARTIAL_SUFFIX = ".partial"
CHUNK = 1024 * 1024
SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", SSH_HOST]


def list_remote() -> dict[str, int]:
    """Relative path -> size in bytes for every file under REMOTE_DIR."""
    # NUL-separated so no filename (spaces, quotes, emoji, ...) can break parsing.
    cmd = f"find {shlex.quote(REMOTE_DIR)} -type f -printf '%P\\0%s\\0'"
    r = subprocess.run(SSH + [cmd], capture_output=True, timeout=60)
    if r.returncode != 0:
        err = r.stderr.decode(errors="replace").strip()
        sys.exit(f"Could not list {SSH_HOST}:{REMOTE_DIR}: {err}")
    fields = r.stdout.decode("utf-8").split("\0")[:-1]
    return {fields[i]: int(fields[i + 1]) for i in range(0, len(fields), 2)}


def list_local() -> dict[str, int]:
    """Relative path (with / separators) -> size in bytes for every file under LOCAL_DIR."""
    return {
        p.relative_to(LOCAL_DIR).as_posix(): p.stat().st_size
        for p in LOCAL_DIR.rglob("*")
        if p.is_file()
    }


def download(rel: str, size: int) -> None:
    target = LOCAL_DIR / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + PARTIAL_SUFFIX)

    # Stream the raw bytes over ssh rather than scp: scp's SFTP mode treats the
    # [...] in yt-dlp filenames as glob patterns.
    proc = subprocess.Popen(
        SSH + ["cat -- " + shlex.quote(f"{REMOTE_DIR}/{rel}")],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    done = 0
    with open(partial, "wb") as f:
        while chunk := proc.stdout.read(CHUNK):
            f.write(chunk)
            done += len(chunk)
            print(f"\r    {done / 1e6:7.1f} / {size / 1e6:.1f} MB", end="", flush=True)
    print()
    err = proc.stderr.read().decode(errors="replace").strip()
    proc.wait()

    if proc.returncode != 0 or done != size:
        partial.unlink(missing_ok=True)
        raise RuntimeError(err or f"received {done} of {size} bytes")
    partial.replace(target)


def main() -> None:
    parser = argparse.ArgumentParser(description="Mirror the Pi's ASMR folder onto this PC.")
    parser.add_argument("--dry-run", action="store_true", help="only show what would change")
    args = parser.parse_args()

    # Filenames are full of emoji; don't crash if output goes to a non-UTF-8 pipe.
    sys.stdout.reconfigure(errors="replace")

    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    remote = list_remote()
    local = list_local()

    if not remote and local:
        sys.exit(f"{SSH_HOST}:{REMOTE_DIR} is empty - refusing to delete all {len(local)} "
                 f"local files. Delete them by hand if that's really intended.")

    to_delete = sorted(set(local) - set(remote))
    to_fetch = sorted(rel for rel, size in remote.items() if local.get(rel) != size)

    print(f"Pi: {len(remote)} files    PC: {len(local)} files")
    for rel in to_fetch:
        if rel in local:
            print(f"  ~ {rel}  (size {local[rel]} -> {remote[rel]})")
        else:
            print(f"  + {rel}")
    for rel in to_delete:
        print(f"  - {rel}")

    if not to_fetch and not to_delete:
        print("Already in sync.")
        return
    total_mb = sum(remote[rel] for rel in to_fetch) / 1e6
    print(f"{len(to_fetch)} to download ({total_mb:.0f} MB), {len(to_delete)} to delete")
    if args.dry_run:
        print("Dry run - nothing changed.")
        return

    for rel in to_delete:
        (LOCAL_DIR / rel).unlink()
        print(f"Deleted {rel}")

    failed = []
    for i, rel in enumerate(to_fetch, 1):
        print(f"[{i}/{len(to_fetch)}] {rel}")
        try:
            download(rel, remote[rel])
        except (OSError, RuntimeError) as e:
            print(f"    FAILED: {e}")
            failed.append(rel)

    if failed:
        sys.exit(f"Done, but {len(failed)} download(s) failed:\n  " + "\n  ".join(failed))
    print("Done - PC now matches the Pi.")


if __name__ == "__main__":
    main()
