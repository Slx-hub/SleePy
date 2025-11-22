#!/bin/bash
# Raspberry Pi USB audio configuration script

set -e

echo "=== Raspberry Pi USB Audio Setup ==="

# Enable USB audio device (run once during setup)
sudo raspi-config nonint do_audio 2
echo "USB audio device set as primary"

# Set alsamixer levels to reduce noise
echo "Configuring ALSA mixer..."
amixer -D pulse sset Master 85%
amixer -D pulse sset PCM 90%

# Disable analog jack if using USB speaker
sudo amixer cset numid=3 1

# Test audio
echo "Playing test sound..."
speaker-test -t sine -f 1000 -l 1 -c 2 -s 10000

echo "=== Audio setup complete ==="
echo "Adjust these values if needed:"
echo "  - amixer -D pulse sset Master <0-100>  (overall volume)"
echo "  - amixer -D pulse sset PCM <0-100>     (playback volume)"