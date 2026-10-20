#!/bin/bash
# Run from ~/Music

echo "Linking + enabling boot health check (system service)..."
sudo systemctl link "$(pwd)/setup/sleepy_healthcheck.service"
sudo systemctl enable sleepy_healthcheck.service

# The jingle has to be a user service: it plays through PipeWire, which only exists in the login session
echo "Linking + enabling startup jingle (user service)..."
systemctl --user link "$(pwd)/setup/startup_jingle.service"
systemctl --user enable startup_jingle.service

echo "Done."
