#!/bin/bash
# Runs once per boot as root (sleepy_healthcheck.service).
#
# Some boots come up with corrupted memory (most likely the SD card): random daemons
# die with SEGV/ILL/BUS in the first ~25s, PipeWire among them, so there's no sound at all.
# On such a boot: blink the numpad's Num Lock LED twice per second and reboot.
# After MAX_REBOOTS bad boots in a row, stop rebooting and just keep blinking.

SETTLE_SECONDS=60
MAX_REBOOTS=2
COUNT_FILE=/var/lib/sleepy/bad_boot_count

blink_numlock() {
    for led in /sys/class/leds/input*::numlock; do
        [ -e "$led/trigger" ] || continue
        echo timer > "$led/trigger"
        echo 250 > "$led/delay_on"
        echo 250 > "$led/delay_off"
    done
}

uptime_s=$(cut -d. -f1 /proc/uptime)
if [ "$uptime_s" -lt "$SETTLE_SECONDS" ]; then
    sleep $((SETTLE_SECONDS - uptime_s))
fi

problems=()
crashes=$(journalctl -b -q --no-pager -o cat | grep -E "code=killed, status=(4/ILL|7/BUS|11/SEGV)")
if [ -n "$crashes" ]; then
    problems+=("crashed processes this boot:"$'\n'"$crashes")
fi
if ! runuser -u pi -- env XDG_RUNTIME_DIR=/run/user/1000 pactl info >/dev/null 2>&1; then
    problems+=("PipeWire/PulseAudio server not reachable")
fi

mkdir -p "$(dirname "$COUNT_FILE")"

if [ ${#problems[@]} -eq 0 ]; then
    echo "Boot looks healthy"
    echo 0 > "$COUNT_FILE"
    exit 0
fi

printf 'Bad boot detected: %s\n' "${problems[@]}"
blink_numlock

count=$(( $(cat "$COUNT_FILE" 2>/dev/null || echo 0) + 1 ))
if [ "$count" -gt "$MAX_REBOOTS" ]; then
    echo "Already rebooted $MAX_REBOOTS times in a row, giving up (Num Lock keeps blinking)"
    # reset so a manual power cycle gets a fresh set of tries
    echo 0 > "$COUNT_FILE"
    exit 1
fi

echo "$count" > "$COUNT_FILE"
echo "Rebooting (attempt $count/$MAX_REBOOTS)"
sleep 10
systemctl reboot
