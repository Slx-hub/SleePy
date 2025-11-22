#!/bin/bash

echo "Linking systemd services..."
sudo systemctl link "$(pwd)/setup/sleepy_boot.service"

echo "Enabling services..."
sudo systemctl enable sleepy_boot.service

echo "Starting services..."
sudo systemctl start sleepy_boot.service

echo "Done."
