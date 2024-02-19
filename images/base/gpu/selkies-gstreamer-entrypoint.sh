#!/bin/bash -e

# Source environment for GStreamer
source /opt/gstreamer/gst-env

# Set default display
export DISPLAY="${DISPLAY:-:0}"

# Show debug logs for GStreamer
export GST_DEBUG="${GST_DEBUG:-*:2}"
# Set password for basic authentication
if [ "${ENABLE_BASIC_AUTH,,}" = "true" ] && [ -z "$BASIC_AUTH_PASSWORD" ]; then export BASIC_AUTH_PASSWORD="$PASSWD"; fi

# Wait for X11 to start
echo "Waiting for X socket"
until [ -S "/tmp/.X11-unix/X${DISPLAY/:/}" ]; do sleep 1; done
echo "X socket is ready"

# Write Progressive Web App (PWA) configuration
export PWA_APP_NAME="Dflare WebRTC"
export PWA_APP_SHORT_NAME="Dflare"
export PWA_START_URL="/index.html"
sudo sed -i \
    -e "s|PWA_APP_NAME|${PWA_APP_NAME}|g" \
    -e "s|PWA_APP_SHORT_NAME|${PWA_APP_SHORT_NAME}|g" \
    -e "s|PWA_START_URL|${PWA_START_URL}|g" \
/opt/gst-web/manifest.json && \
sudo sed -i \
    -e "s|PWA_CACHE|${PWA_APP_SHORT_NAME}-webrtc-pwa|g" \
/opt/gst-web/app/sw.js

# Clear the cache registry
rm -rf "${HOME}/.cache/gstreamer-1.0"

# Start the selkies-gstreamer WebRTC HTML5 remote desktop application
selkies-gstreamer \
    --addr="0.0.0.0" \
    --port="8080" \
    $@