# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# This file incorporates work covered by the following copyright and
# permission notice:
#
#   Copyright 2019 Google LLC
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import argparse
import asyncio
import http.client
import json
import logging
import os
import signal
import socket
import sys
import time
import urllib.parse
import traceback

from watchdog.observers import Observer
from watchdog.events import FileClosedEvent, FileSystemEventHandler
from webrtc_input import WebRTCInput
from webrtc_signalling import WebRTCSignalling, WebRTCSignallingErrorNoPeer
from gstwebrtc_app import GSTWebRTCApp
from gpu_monitor import GPUMonitor
from system_monitor import SystemMonitor
from metrics import Metrics
from resize import resize_display, get_new_res
from signalling_web import WebRTCSimpleServer, generate_rtc_config
from dstreamer_agent import DstreamerAgentClient

logger = logging.getLogger("main")
logger.setLevel(logging.INFO)

DEFAULT_RTC_CONFIG = """{
  "lifetimeDuration": "86400s",
  "iceServers": [
    {
      "urls": [
        "stun:stun.l.google.com:19302"
      ]
    }
  ],
  "blockStatus": "NOT_BLOCKED",
  "iceTransportPolicy": "all"
}"""

class HMACRTCMonitor:
    def __init__(self, turn_host, turn_port, turn_shared_secret, turn_username, turn_protocol='udp', turn_tls=False, stun_host=None, stun_port=None, period=60, enabled=True):
        self.turn_host = turn_host
        self.turn_port = turn_port
        self.turn_username = turn_username
        self.turn_shared_secret = turn_shared_secret
        self.turn_protocol = turn_protocol
        self.turn_tls = turn_tls
        self.stun_host = stun_host
        self.stun_port = stun_port
        self.period = period
        self.enabled = enabled

        self.running = False

        self.on_rtc_config = lambda stun_servers, turn_servers, rtc_config: logger.warning("unhandled on_rtc_config")

    def start(self):
        if self.enabled:
            self.running = True
            while self.running:
                if self.enabled and int(time.time()) % self.period == 0:
                    try:
                        hmac_data = generate_rtc_config(self.turn_host, self.turn_port, self.turn_shared_secret, self.turn_username, self.turn_protocol, self.turn_tls, self.stun_host, self.stun_port)
                        stun_servers, turn_servers, rtc_config = parse_rtc_config(hmac_data)
                        self.on_rtc_config(stun_servers, turn_servers, rtc_config)
                    except Exception as e:
                        logger.warning("could not fetch TURN HMAC config in periodic monitor: {}".format(e))
                time.sleep(0.5)
            logger.info("HMAC RTC monitor stopped")

    def stop(self):
        self.running = False

class RESTRTCMonitor:
    def __init__(self, turn_rest_uri, turn_rest_username, turn_rest_username_auth_header, turn_protocol='udp', turn_rest_protocol_header='x-turn-protocol', turn_tls=False, turn_rest_tls_header='x-turn-tls', period=60, enabled=True):
        self.period = period
        self.enabled = enabled
        self.running = False

        self.turn_rest_uri = turn_rest_uri
        self.turn_rest_username = turn_rest_username.replace(":", "-")
        self.turn_rest_username_auth_header = turn_rest_username_auth_header
        self.turn_protocol = turn_protocol
        self.turn_rest_protocol_header = turn_rest_protocol_header
        self.turn_tls = turn_tls
        self.turn_rest_tls_header = turn_rest_tls_header

        self.on_rtc_config = lambda stun_servers, turn_servers, rtc_config: logger.warning("unhandled on_rtc_config")

    def start(self):
        if self.enabled:
            self.running = True
            while self.running:
                if self.enabled and int(time.time()) % self.period == 0:
                    try:
                        stun_servers, turn_servers, rtc_config = fetch_turn_rest(self.turn_rest_uri, self.turn_rest_username, self.turn_rest_username_auth_header, self.turn_protocol, self.turn_rest_protocol_header, self.turn_tls, self.turn_rest_tls_header)
                        self.on_rtc_config(stun_servers, turn_servers, rtc_config)
                    except Exception as e:
                        logger.warning("could not fetch TURN REST config in periodic monitor: {}".format(e))
                time.sleep(0.5)
            logger.info("TURN REST RTC monitor stopped")

    def stop(self):
        self.running = False

class RTCConfigFileMonitor:
    def __init__(self, rtc_file, enabled=True):
        self.enabled = enabled
        self.running = False
        self.rtc_file = rtc_file

        self.on_rtc_config = lambda stun_servers, turn_servers, rtc_config: logger.warning("unhandled on_rtc_config")
        
        self.observer = Observer()
        self.file_event_handler = FileSystemEventHandler()
        self.file_event_handler.on_closed = self.event_handler
        self.observer.schedule(self.file_event_handler, self.rtc_file, recursive=False)

    def event_handler(self, event):
        if type(event) is FileClosedEvent:
            print("Detected RTC JSON file change: {}".format(event.src_path))
            try:
                with open(self.rtc_file, 'rb') as f:
                    data = f.read()
                    stun_servers, turn_servers, rtc_config = parse_rtc_config(data)
                    self.on_rtc_config(stun_servers, turn_servers, rtc_config)
            except Exception as e:
                logger.warning("could not read RTC JSON file: {}: {}".format(self.rtc_file, e))
            
    def start(self):
        if self.enabled:
            self.observer.start()
            self.running = True

    def stop(self):
        self.observer.stop()
        self.running = False
        logger.info("RTC config file monitor stopped")

class CoturnEnvVarMonitor:
    def __init__(self, stun_host, stun_port, turn_host, turn_port, turn_username, turn_password, turn_protocol='udp', turn_tls=False, using_stunner=False, period=15):
        self.stun_host = stun_host
        self.stun_port = stun_port
        self.turn_host = turn_host
        self.turn_port = turn_port
        self.turn_username = turn_username
        self.turn_password = turn_password
        self.turn_protocol = turn_protocol
        self.turn_tls = "true" if turn_tls else "false"
        self.stunner = "true" if using_stunner else "false"
        self.running = False
        self.period = period

        self.on_rtc_config = lambda stun_server, turn_servers, rtc_config: logger.warning(
            "unhandled on_rtc_config")

    def start(self):
        self.running = True
        while self.running:
            # get the current values
            up_turn_host = os.environ.get("TURN_HOST", '')
            up_turn_port = os.environ.get("TURN_PORT", '')
            up_turn_username = os.environ.get("TURN_USERNAME", '')
            up_turn_password = os.environ.get("TURN_PASSWORD", '')
            up_turn_protocol = os.environ.get("TURN_PROTOCOL", "udp")
            up_turn_tls = os.environ.get("TURN_TLS", "false")
            up_stunner = os.environ.get("STUNNER", "false")
            up_stun_host = os.environ.get("STUN_HOST", "stun.l.google.com")
            up_stun_port = os.environ.get("STUN_PORT", "19302")

            # if any environment variable changes/updates
            if (self.turn_host != up_turn_host or self.turn_port != up_turn_port or self.turn_username != up_turn_username
                    or self.turn_password != up_turn_password or self.turn_protocol != up_turn_protocol or self.turn_tls != up_turn_tls 
                    or self.stunner != up_stunner or self.stun_host != up_stun_host or self.stun_port != up_stun_port):
                data = make_turn_rtc_config_json_legacy(up_turn_host, up_turn_port, up_turn_username, up_turn_password, up_turn_protocol, 
                                                        up_turn_tls, up_stunner, up_stun_host, up_stun_port)
                stun_servers, turn_servers, rtc_config = parse_rtc_config(data)
                self.on_rtc_config(stun_servers, turn_servers, rtc_config)

                self.turn_host = up_turn_host
                self.turn_port = up_turn_port
                self.turn_username = up_turn_username
                self.turn_password = up_turn_password
                self.turn_protocol = up_turn_protocol
                self.turn_tls = up_turn_tls
                self.stunner = up_stunner
                self.stun_host = up_stun_host
                self.stun_port = up_stun_port

            time.sleep(self.period)
        logger.info("CoturnEnvVar monitor stopped")

    def stop(self):
        self.running = False


def make_turn_rtc_config_json_legacy(turn_host, turn_port, username, password, protocol='udp', turn_tls=False, stunner=False, stun_host=None, stun_port=None):
    stun_list = ["stun:{}:{}".format(turn_host, turn_port)]
    if stun_host is not None and stun_port is not None and (stun_host != turn_host or str(stun_port) != str(turn_port)):
        stun_list.insert(0, "stun:{}:{}".format(stun_host, stun_port))
    if stun_host != "stun.l.google.com" or (str(stun_port) != "19302"):
        stun_list.append("stun:stun.l.google.com:19302")

    rtc_config = {}
    rtc_config["lifetimeDuration"] = "86400s"
    rtc_config["blockStatus"] = "NOT_BLOCKED"
    rtc_config["iceTransportPolicy"] = "all" if not stunner else 'relay'
    rtc_config["iceServers"] = []

    # As STUNner is primarily used for TURN functinality, we skip STUN servers
    if not stunner:
        rtc_config["iceServers"].append({
            "urls": stun_list
        })

    rtc_config["iceServers"].append({
        "urls": [
            "{}:{}:{}?transport={}".format('turns' if turn_tls else 'turn', turn_host, turn_port, protocol)
        ],
        "username": username,
        "credential": password
    })

    return json.dumps(rtc_config, indent=2)

def parse_rtc_config(data):
    ice_servers = json.loads(data)['iceServers']
    stun_uris = []
    turn_uris = []
    for server in ice_servers:
        for url in server.get("urls", []):
            if url.startswith("stun:"):
                stun_host = url.split(":")[1]
                stun_port = url.split(":")[2].split("?")[0]
                stun_uri = "stun://%s:%s" % (
                    stun_host,
                    stun_port
                )
                stun_uris.append(stun_uri)
            elif url.startswith("turn:"):
                turn_host = url.split(':')[1]
                turn_port = url.split(':')[2].split('?')[0]
                turn_user = server['username']
                turn_password = server['credential']
                turn_uri = "turn://%s:%s@%s:%s" % (
                    urllib.parse.quote(turn_user, safe=""),
                    urllib.parse.quote(turn_password, safe=""),
                    turn_host,
                    turn_port
                )
                turn_uris.append(turn_uri)
            elif url.startswith("turns:"):
                turn_host = url.split(':')[1]
                turn_port = url.split(':')[2].split('?')[0]
                turn_user = server['username']
                turn_password = server['credential']
                turn_uri = "turns://%s:%s@%s:%s" % (
                    urllib.parse.quote(turn_user, safe=""),
                    urllib.parse.quote(turn_password, safe=""),
                    turn_host,
                    turn_port
                )
                turn_uris.append(turn_uri)
    return stun_uris, turn_uris, data

def fetch_turn_rest(uri, user, auth_header_username='x-auth-user', protocol='udp', header_protocol='x-turn-protocol', turn_tls=False, header_tls='x-turn-tls'):
    """Fetches TURN uri from a REST API

    Arguments:
        uri {string} -- uri of REST API service, example: http://localhost:8081/
        user {string} -- username used to generate TURN credential, for example: <hostname>

    Raises:
        Exception -- if response http status code is >= 400

    Returns:
        [string] -- TURN URI used with gstwebrtcbin in the form of:
                        turn://<user>:<password>@<host>:<port>
                    NOTE that the user and password are URI encoded to escape special characters like '/'
    """

    parsed_uri = urllib.parse.urlparse(uri)

    conn = http.client.HTTPConnection(parsed_uri.netloc)
    if parsed_uri.scheme == "https":
        conn = http.client.HTTPSConnection(parsed_uri.netloc)
    auth_headers = {
        auth_header_username: user,
        header_protocol: protocol,
        header_tls: 'true' if turn_tls else 'false'
    }

    conn.request("GET", parsed_uri.path, headers=auth_headers)
    resp = conn.getresponse()
    data = resp.read()
    if resp.status >= 400:
        raise Exception("error fetching REST API config. Status code: {}. {}, {}".format(resp.status, resp.reason, data))
    if not data:
        raise Exception("data from REST API service was empty")
    return parse_rtc_config(data)

def wait_for_app_ready(ready_file, app_wait_ready=False):
    """Wait for streaming app ready signal.

    returns when either app_wait_ready is True OR the file at ready_file exists.

    Keyword Arguments:
        app_wait_ready {bool} -- skip wait for appready file (default: {False})
    """

    logger.info("Waiting for streaming app ready")
    logging.debug("app_wait_ready=%s, ready_file=%s" % (app_wait_ready, ready_file))

    while not (app_wait_ready or os.path.exists(ready_file)):
        time.sleep(0.2)

def set_json_app_argument(config_path, key, value):
    """Writes kv pair to json argument file

    Arguments:
        config_path {string} -- path to json config file, example: /tmp/selkies_config.json
        key {string} -- the name of the argument to set
        value {any} -- the value of the argument to set
    """

    if not os.path.exists(config_path):
        # Create new file
        with open(config_path, 'w') as f:
            json.dump({}, f)

    # Read current config JSON
    json_data = json.load(open(config_path))

    # Set the new value for the argument.
    json_data[key] = value

    # Save the json file
    json.dump(json_data, open(config_path, 'w'))

    return True

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--json_config',
                        default=os.environ.get(
                            'JSON_CONFIG', '/tmp/selkies_config.json'),
                        help='Path to the JSON file containing argument key-value pairs that are overlayed with CLI arguments or environment variables, this path must be writable.')
    parser.add_argument('--addr',
                        default=os.environ.get(
                            'LISTEN_HOST', '0.0.0.0'),
                        help='Host to listen on for the signaling and web server, default: "0.0.0.0"')
    parser.add_argument('--port',
                        default=os.environ.get(
                            'LISTEN_PORT', '8080'),
                        help='Port to listen on for the signaling and web server, default: "8080"')
    parser.add_argument('--web_root',
                        default=os.environ.get(
                            'WEB_ROOT', '/opt/gst-web'),
                        help='Path to directory containing web app source, default: "/opt/gst-web"')
    parser.add_argument('--enable_https',
                        default=os.environ.get(
                            'ENABLE_HTTPS', 'false'),
                        help='Enable or disable HTTPS for the web application, specifying a valid server certificate is recommended')
    parser.add_argument('--https_cert',
                        default=os.environ.get(
                            'HTTPS_CERT', '/etc/ssl/certs/ssl-cert-snakeoil.pem'),
                        help='Path to the TLS server certificate file when HTTPS is enabled')
    parser.add_argument('--https_key',
                        default=os.environ.get(
                            'HTTPS_KEY', '/etc/ssl/private/ssl-cert-snakeoil.key'),
                        help='Path to the TLS server private key file when HTTPS is enabled, set to an empty value if the private key is included in the certificate')
    parser.add_argument('--enable_basic_auth',
                        default=os.environ.get(
                            'ENABLE_BASIC_AUTH', 'false'),
                        help='Enable Basic authentication on server. Must set basic_auth_password and optionally basic_auth_user to enforce Basic authentication.')
    parser.add_argument('--basic_auth_user',
                        default=os.environ.get(
                            'BASIC_AUTH_USER', os.environ.get('USER', '')),
                        help='Username for Basic authentication, default is to use the USER environment variable or a blank username if it does not exist. Must also set basic_auth_password to enforce Basic authentication.')
    parser.add_argument('--basic_auth_password',
                        default=os.environ.get(
                            'BASIC_AUTH_PASSWORD', ''),
                        help='Password used when Basic authentication is set.')
    parser.add_argument('--rtc_config_json',
                        default=os.environ.get(
                            'RTC_CONFIG_JSON', '/tmp/rtc.json'),
                        help='JSON file with RTC config to use as alternative to coturn service, read periodically')
    parser.add_argument('--turn_rest_uri',
                        default=os.environ.get(
                            'TURN_REST_URI', ''),
                        help='URI for TURN REST API service, example: http://localhost:8008')
    parser.add_argument('--turn_rest_username',
                        default=os.environ.get(
                            'TURN_REST_USERNAME', "selkies-{}".format(socket.gethostname())),
                        help='URI for TURN REST API service, default set to system hostname')
    parser.add_argument('--turn_rest_username_auth_header',
                        default=os.environ.get(
                            'TURN_REST_USERNAME_AUTH_HEADER', 'x-auth-user'),
                        help='Header to pass user to TURN REST API service')
    parser.add_argument('--turn_rest_protocol_header',
                        default=os.environ.get(
                            'TURN_REST_PROTOCOL_HEADER', 'x-turn-protocol'),
                        help='Header to pass desired TURN protocol to TURN REST API service')
    parser.add_argument('--turn_rest_tls_header',
                        default=os.environ.get(
                            'TURN_REST_TLS_HEADER', 'x-turn-tls'),
                        help='Header to pass TURN (D)TLS usage to TURN REST API service')
    parser.add_argument('--turn_shared_secret',
                        default=os.environ.get(
                            'TURN_SHARED_SECRET', ''),
                        help='Shared TURN secret used to generate HMAC credentials, also requires TURN_HOST and TURN_PORT.')
    parser.add_argument('--turn_username',
                        default=os.environ.get(
                            'TURN_USERNAME', ''),
                        help='Legacy non-HMAC TURN credential username, also requires TURN_HOST and TURN_PORT.')
    parser.add_argument('--turn_password',
                        default=os.environ.get(
                            'TURN_PASSWORD', ''),
                        help='Legacy non-HMAC TURN credential password, also requires TURN_HOST and TURN_PORT.')
    parser.add_argument('--turn_host',
                        default=os.environ.get(
                            'TURN_HOST', ''),
                        help='TURN host when generating RTC config from shared secret or legacy credentials.')
    parser.add_argument('--turn_port',
                        default=os.environ.get(
                            'TURN_PORT', ''),
                        help='TURN port when generating RTC config from shared secret or legacy credentials.')
    parser.add_argument('--turn_protocol',
                        default=os.environ.get(
                            'TURN_PROTOCOL', 'udp'),
                        help='TURN protocol for the client to use ("udp" or "tcp"), set to "tcp" without the quotes if "udp" is blocked on the network.')
    parser.add_argument('--turn_tls',
                        default=os.environ.get(
                            'TURN_TLS', 'false'),
                        help='Enable or disable TURN over TLS (for the TCP protocol) or TURN over DTLS (for the UDP protocol), valid TURN server certificate required.')
    parser.add_argument('--stun_host',
                        default=os.environ.get(
                            'STUN_HOST', 'stun.l.google.com'),
                        help='STUN host for NAT hole punching with WebRTC, change to your internal STUN/TURN server for local networks without internet, defaults to "stun.l.google.com"')
    parser.add_argument('--stun_port',
                        default=os.environ.get(
                            'STUN_PORT', '19302'),
                        help='STUN port for NAT hole punching with WebRTC, change to your internal STUN/TURN server for local networks without internet, defaults to "19302"')
    parser.add_argument('--app_wait_ready',
                        default=os.environ.get('APP_WAIT_READY', 'true'),
                        help='Waits for --app_ready_file to exist before starting stream if set to "true"')
    parser.add_argument('--app_ready_file',
                        default=os.environ.get('APP_READY_FILE', '/tmp/selkies-appready'),
                        help='File set by sidecar used to indicate that app is initialized and ready')
    parser.add_argument('--uinput_mouse_socket',
                        default=os.environ.get('UINPUT_MOUSE_SOCKET', ''),
                        help='Path to uinput mouse socket provided by uinput-device-plugin, if not provided, uinput is used directly.')
    parser.add_argument('--js_socket_path',
                        default=os.environ.get('JS_SOCKET_PATH', '/tmp'),
                        help='Directory to write the Selkies Joystick Interposer communication sockets to, default: /tmp, results in socket files: /tmp/selkies_js{0-3}.sock')
    parser.add_argument('--encoder',
                        default=os.environ.get('ENCODER', 'x264enc'),
                        help='GStreamer video encoder to use')
    parser.add_argument('--gpu_id',
                        default=os.environ.get('GPU_ID', '0'),
                        help='GPU ID for GStreamer hardware video encoders, will use enumerated GPU ID (0, 1, ..., n) for NVIDIA and /dev/dri/renderD{128 + n} for VA-API')
    parser.add_argument('--framerate',
                        default=os.environ.get('FRAMERATE', '60'),
                        help='Framerate of the streamed remote desktop')
    parser.add_argument('--video_bitrate',
                        default=os.environ.get('VIDEO_BITRATE', '8000'),
                        help='Default video bitrate in kilobits per second')
    parser.add_argument('--keyframe_distance',
                        default=os.environ.get('KEYFRAME_DISTANCE', '-1'),
                        help='Distance between video keyframes/GOP-frames in seconds, defaults to "-1" for infinite keyframe distance (ideal for low latency and preventing periodic blurs)')
    parser.add_argument('--congestion_control',
                        default=os.environ.get('CONGESTION_CONTROL', 'false'),
                        help='Enable Google Congestion Control (GCC), suggested if network conditions fluctuate and when bandwidth is >= 2 mbps but may lead to lower quality and microstutter due to adaptive bitrate in some encoders')
    parser.add_argument('--video_packetloss_percent',
                        default=os.environ.get('IDEO_PACKETLOSS_PERCENT', '0'),
                        help='Expected packet loss percentage (%%) for ULP/RED Forward Error Correction (FEC) in video, use "0" to disable FEC, less effective because of other mechanisms including NACK/PLI, enabling not recommended if Google Congestion Control is enabled')
    parser.add_argument('--enable_audio',
                        default=os.environ.get('ENABLE_AUDIO', 'true'),
                        help='Enable or disable audio stream')
    parser.add_argument('--audio_bitrate',
                        default=os.environ.get('AUDIO_BITRATE', '128000'),
                        help='Default audio bitrate in bits per second')
    parser.add_argument('--audio_channels',
                        default=os.environ.get('AUDIO_CHANNELS', '2'),
                        help='Number of audio channels, defaults to stereo (2 channels)')
    parser.add_argument('--audio_packetloss_percent',
                        default=os.environ.get('AUDIO_PACKETLOSS_PERCENT', '0'),
                        help='Expected packet loss percentage (%%) for ULP/RED Forward Error Correction (FEC) in audio, use "0" to disable FEC')
    parser.add_argument('--enable_clipboard',
                        default=os.environ.get('ENABLE_CLIPBOARD', 'true'),
                        help='Enable or disable the clipboard features, supported values: true, false, in, out')
    parser.add_argument('--enable_resize',
                        default=os.environ.get('ENABLE_RESIZE', 'true'),
                        help='Enable dynamic resizing to match browser size')
    parser.add_argument('--enable_cursors',
                        default=os.environ.get('ENABLE_CURSORS', 'true'),
                        help='Enable passing remote cursors to client')
    parser.add_argument('--debug_cursors',
                        default=os.environ.get('DEBUG_CURSORS', 'false'),
                        help='Enable cursor debug logging')
    parser.add_argument('--enable_webrtc_statistics',
                        default=os.environ.get('ENABLE_WEBRTC_STATISTICS', 'false'),
                        help='Enable WebRTC Statistics CSV dumping to the directory --webrtc_statistics_dir with filenames selkies-stats-video-[timestamp].csv and selkies-stats-audio-[timestamp].csv')
    parser.add_argument('--webrtc_statistics_dir',
                        default=os.environ.get('WEBRTC_STATISTICS_DIR', '/tmp'),
                        help='Directory to save WebRTC Statistics CSV from client with filenames selkies-stats-video-[timestamp].csv and selkies-stats-audio-[timestamp].csv')
    parser.add_argument('--enable_metrics_http',
                        default=os.environ.get('ENABLE_METRICS_HTTP', 'true'),
                        help='Enable the Prometheus HTTP metrics port')
    parser.add_argument('--metrics_http_port',
                        default=os.environ.get('METRICS_HTTP_PORT', '8000'),
                        help='Port to start the Prometheus metrics server on')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug logging')
    parser.add_argument('--cursor_size',
                        default=os.environ.get('WEBRTC_CURSOR_SIZE', os.environ.get('XCURSOR_SIZE', '24')),
                        help='Cursor size in points for the local cursor, set instead XCURSOR_SIZE without of this argument to configure the cursor size for both the local and remote cursors')
    parser.add_argument('--hostname',
                        default=os.environ.get('HOSTNAME', ''),
                        help='Hostname of the system')
    parser.add_argument('--enable_webcam',
                        default=os.environ.get('ENABLE_WEBCAM', 'false'),
                        help='Enable webcam feature')
    parser.add_argument('--video_device',
                        default=os.environ.get("VIDEO_DEVICE", "/dev/video0"),
                        help='Virtual video device to stream the webcam video media to')
    parser.add_argument('--asymmetric_ice_mode',
                        default=os.environ.get('ASYMMETRIC_ICE_MODE', 'false'),
                        help='Only generates host type ice candidates from server side; relevant when STUNner is being used')
    parser.add_argument('--stunner',
                        default=os.environ.get("STUNNER", 'false'),
                        help='Set it to true if STUNner is being used, which forces a relay connection')
    args = parser.parse_args()

    if os.path.exists(args.json_config):
        # Read and overlay args from json file
        # Note that these are explicit overrides only.
        try:
            json_args = json.load(open(args.json_config))
            for k, v in json_args.items():
                if k == "framerate":
                    args.framerate = int(v)
                if k == "video_bitrate":
                    args.video_bitrate = int(v)
                if k == "audio_bitrate":
                    args.audio_bitrate = int(v)
                if k == "enable_audio":
                    args.enable_audio = str((str(v).lower() == 'true')).lower()
                if k == "enable_resize":
                    args.enable_resize = str((str(v).lower() == 'true')).lower()
                if k == "encoder":
                    args.encoder = v.lower()
        except Exception as e:
            logger.error("failed to load json config from %s: %s" % (args.json_config, str(e)))

    logging.warning(args)

    # Set log level
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    # Wait for streaming app to initialize
    wait_for_app_ready(args.app_ready_file, args.app_wait_ready.lower() == "true")

    # Peer id for this app, default is 0, expecting remote peer id to be 1
    my_id = 0
    peer_id = 1
    my_webcam_id = 2
    peer_webcam_id =3

    # Initialize metrics server.
    using_metrics_http = args.enable_metrics_http.lower() == 'true'
    using_webrtc_csv = args.enable_webrtc_statistics.lower() == 'true'
    metrics = Metrics(int(args.metrics_http_port), using_webrtc_csv)

    # Initialize the signalling client
    using_https = args.enable_https.lower() == 'true'
    using_basic_auth = args.enable_basic_auth.lower() == 'true'
    ws_protocol = 'wss' if using_https else 'ws'
    signalling = WebRTCSignalling('%s://127.0.0.1:%s/ws' % (ws_protocol, args.port), my_id, peer_id,
        enable_https=using_https,
        enable_basic_auth=using_basic_auth,
        basic_auth_user=args.basic_auth_user,
        basic_auth_password=args.basic_auth_password)
    
    webcam_signalling = WebRTCSignalling('%s://127.0.0.1:%s/ws' % (ws_protocol, args.port), my_webcam_id, peer_webcam_id,
        enable_https=using_https,
        enable_basic_auth=using_basic_auth,
        basic_auth_user=args.basic_auth_user,
        basic_auth_password=args.basic_auth_password)

    # Handle errors from the signalling server.
    async def on_signalling_error(e):
       if isinstance(e, WebRTCSignallingErrorNoPeer):
           # Waiting for peer to connect, retry in 2 seconds.
           time.sleep(2)
           await signalling.setup_call()
       else:
           logger.error("signalling error: %s", str(e))
           app.stop_pipeline()
    
    async def on_webcam_signalling_error(e):
       if isinstance(e, WebRTCSignallingErrorNoPeer):
           # Waiting for peer to connect, retry in 2 seconds.
           time.sleep(2)
           await webcam_signalling.setup_call()
       else:
           logger.error("webcam signalling error: %s", str(e))
           webcam_app.stop_pipeline()

    signalling.on_error = on_signalling_error
    webcam_signalling.on_error = on_webcam_signalling_error

    signalling.on_disconnect = lambda: app.stop_pipeline()
    webcam_signalling.on_disconnect = lambda: webcam_app.stop_pipeline()

    # After connecting, attempt to setup call to peer.
    signalling.on_connect = signalling.setup_call
    webcam_signalling.on_connect = webcam_signalling.setup_call

    # [START main_setup]
    # Fetch the TURN server and credentials
    turn_rest_username = args.turn_rest_username.replace(":", "-")
    rtc_config = None
    turn_protocol = 'tcp' if args.turn_protocol.lower() == 'tcp' else 'udp'
    using_turn_tls = args.turn_tls.lower() == 'true'
    using_turn_rest = False
    using_hmac_turn = False
    using_rtc_config_json = False
    using_stunner = args.stunner.lower() == "true"
    if os.path.exists(args.rtc_config_json):
        logger.warning("using JSON file from argument for RTC config, overrides all other STUN/TURN configuration")
        with open(args.rtc_config_json, 'r') as f:
            stun_servers, turn_servers, rtc_config = parse_rtc_config(f.read())
        using_rtc_config_json = True
    else:
        if args.turn_rest_uri:
            try:
                stun_servers, turn_servers, rtc_config = fetch_turn_rest(
                    args.turn_rest_uri, turn_rest_username, args.turn_rest_username_auth_header, turn_protocol, args.turn_rest_protocol_header, using_turn_tls, args.turn_rest_tls_header)
                logger.info("using TURN REST API RTC configuration, overrides long-term username/password or short-term shared secret STUN/TURN configuration")
                using_turn_rest = True
            except Exception as e:
                logger.warning("error fetching TURN REST API RTC configuration, falling back to other methods: {}".format(str(e)))
                using_turn_rest = False
        if not using_turn_rest:
            if (args.turn_username and args.turn_password) and (args.turn_host and args.turn_port):
                config_json = make_turn_rtc_config_json_legacy(args.turn_host, args.turn_port, args.turn_username, args.turn_password, turn_protocol, using_turn_tls, using_stunner, args.stun_host, args.stun_port)
                stun_servers, turn_servers, rtc_config = parse_rtc_config(config_json)
                logger.info("using TURN long-term username/password credentials, prioritized over short-term shared secret configuration")
            elif args.turn_shared_secret and (args.turn_host and args.turn_port):
                hmac_data = generate_rtc_config(args.turn_host, args.turn_port, args.turn_shared_secret, turn_rest_username, turn_protocol, using_turn_tls, args.stun_host, args.stun_port)
                stun_servers, turn_servers, rtc_config = parse_rtc_config(hmac_data)
                logger.info("using TURN short-term shared secret HMAC credentials")
                using_hmac_turn = True
            else:
                stun_servers, turn_servers, rtc_config = parse_rtc_config(DEFAULT_RTC_CONFIG)
                logger.warning("missing TURN server information, using DEFAULT_RTC_CONFIG")

    logger.info("initial server RTC configuration fetched")

    # Extract args
    enable_audio = args.enable_audio.lower() == "true"
    enable_resize = args.enable_resize.lower() == "true"
    audio_channels = int(args.audio_channels)
    curr_fps = int(args.framerate)
    gpu_id = int(args.gpu_id)
    curr_video_bitrate = int(args.video_bitrate)
    curr_audio_bitrate = int(args.audio_bitrate)
    enable_cursors = args.enable_cursors.lower() == "true"
    cursor_debug = args.debug_cursors.lower() == "true"
    cursor_size = int(args.cursor_size)
    keyframe_distance = float(args.keyframe_distance)
    congestion_control = args.congestion_control.lower() == "true"
    video_packetloss_percent = float(args.video_packetloss_percent)
    audio_packetloss_percent = float(args.audio_packetloss_percent)
    hostname = args.hostname
    enable_webcam = args.enable_webcam.lower() == "true"
    video_device = args.video_device
    asymmetric_ice_mode = args.asymmetric_ice_mode.lower() == "true"

    # Create instance of app
    app = GSTWebRTCApp(asymmetric_ice_mode, stun_servers, turn_servers, enable_audio, audio_channels, curr_fps, args.encoder, gpu_id, curr_video_bitrate,
            curr_audio_bitrate, keyframe_distance, congestion_control, video_packetloss_percent, audio_packetloss_percent, hostname)
    webcam_app = GSTWebRTCApp(asymmetric_ice_mode, stun_servers, turn_servers, enable_audio, audio_channels, curr_fps, args.encoder, gpu_id, curr_video_bitrate,
            curr_audio_bitrate, keyframe_distance, congestion_control, video_packetloss_percent, audio_packetloss_percent, hostname, enable_webcam, video_device)

    # [END main_setup]

    # Send the local sdp to signalling when offer is generated.
    app.on_sdp = signalling.send_sdp
    webcam_app.on_sdp = webcam_signalling.send_sdp

    # Send ICE candidates to the signalling server.
    app.on_ice = signalling.send_ice
    webcam_app.on_ice = webcam_signalling.send_ice

    # Set the remote SDP when received from signalling server.
    signalling.on_sdp = app.set_sdp
    webcam_signalling.on_sdp = webcam_app.set_sdp

    # Set ICE candidates received from signalling server.
    signalling.on_ice = app.set_ice
    webcam_signalling.on_ice = webcam_app.set_ice

    # TODO: If DPI part is implemented update the func accordingly.
    # Start the pipeline once the session is established.
    def on_session_handler(session_peer_id):
        logger.info("starting session for peer id {}".format(session_peer_id))
        if str(session_peer_id) == str(peer_id):
            logger.info("starting video pipeline")
            app.start_pipeline()
        elif str(session_peer_id) == str(peer_webcam_id):
            logger.info("starting webcam pipeline")
            webcam_app.start_pipeline()
        else:
            logger.error("failed to start pipeline for peer_id: %s" % peer_id)

    signalling.on_session = lambda peer_id: on_session_handler(peer_id)
    webcam_signalling.on_session = lambda peer_id: on_session_handler(peer_id)

    # Initialize the Xinput instance
    webrtc_input = WebRTCInput(args.uinput_mouse_socket, args.enable_clipboard.lower(), enable_cursors, cursor_size, cursor_debug)

    # Handle changed cursors
    webrtc_input.on_cursor_change = lambda data: app.send_cursor_data(data)

    # Log message when data channel is open
    def data_channel_ready():
        logger.info(
            "opened peer data channel for user input to X11")

        app.send_framerate(app.framerate)
        app.send_video_bitrate(app.video_bitrate)
        app.send_audio_bitrate(app.audio_bitrate)
        app.send_audio_enabled(app.audio)
        app.send_resize_enabled(enable_resize)
        app.send_encoder(app.encoder)
        app.send_cursor_data(app.last_cursor_sent)
        app.send_hostname(app.hostname)
        app.send_webcam_enabled(webcam_app.webcam)

    app.on_data_open = lambda: data_channel_ready()

    # Send incomming messages from data channel to input handler
    app.on_data_message = webrtc_input.on_message

    # Send video bitrate messages to app
    def set_video_bitrate_handler(bitrate):
        set_json_app_argument(args.json_config, "video_bitrate", bitrate) 
        app.set_video_bitrate(int(bitrate))
        
        # Bitrate being received from client is kbps, convert it to mbps
        metrics.selected_video_bitrate = int(bitrate) / 1000 

    webrtc_input.on_video_encoder_bit_rate = set_video_bitrate_handler

    # Send audio bitrate messages to app
    def set_audio_bitrate_handler(bitrate):
        set_json_app_argument(args.json_config, "audio_bitrate", bitrate) 
        app.set_audio_bitrate(int(bitrate))

        # Bitrate being received from client is kbps, convert it to mbps
        metrics.selected_audio_bitrate = int(bitrate) / 1000 

    webrtc_input.on_audio_encoder_bit_rate = set_audio_bitrate_handler

    # Send pointer visibility setting to app
    webrtc_input.on_mouse_pointer_visible = lambda visible: app.set_pointer_visible(visible)

    # Send clipboard contents when requested
    webrtc_input.on_clipboard_read = lambda data: app.send_clipboard_data(data)

    # Write framerate arg to local config and then tell client to reload.
    def set_fps_handler(fps):
        set_json_app_argument(args.json_config, "framerate", fps)
        curr_fps = app.framerate
        app.set_framerate(fps)
        metrics.selected_fps = fps
        if fps != curr_fps:
            logger.warning("sending window reload to restart pipeline with new framerate")
            app.send_reload_window()

    webrtc_input.on_set_fps = lambda fps: set_fps_handler(fps)

    # Write audio enabled arg to local config and then tell client to reload.
    def enable_audio_handler(enabled):
        set_json_app_argument(args.json_config, "enable_audio", enabled)
        curr_audio = app.audio
        app.set_enable_audio(enabled)
        if enabled != curr_audio:
            app.send_reload_window()
    webrtc_input.on_set_enable_audio = lambda enabled: enable_audio_handler(enabled)

    # Handle webcam pipeline
    def enable_webcam_handler(enabled):
        if enabled:
            # Webcam pipeline initialisation is handled by on_session handler of websocket connection
            logger.info("Webcam enabled")
        else:
            webcam_app.stop_pipeline()
            logger.info("Webcam disabled")
    webrtc_input.on_set_enable_webcam = lambda enabled: enable_webcam_handler(enabled)

    # Handler for resize events.
    app.last_resize_success = True
    def on_resize_handler(res):
        # Trigger resize and reload if it changed.
        curr_res, new_res, _, __, ___ = get_new_res(res)
        if curr_res != new_res:
            if not app.last_resize_success:
                logger.warning("skipping resize because last resize failed.")
                return
            logger.warning("resizing display from {} to {}".format(curr_res, new_res))
            if resize_display(res):
                pass
                #app.send_remote_resolution(res)

    # Initial binding of enable resize handler.
    if enable_resize:
        webrtc_input.on_resize = on_resize_handler
    else:
        webrtc_input.on_resize = lambda res: logger.warning("remote resize is disabled, skipping resize to %s" % res)

    webrtc_input.on_ping_response = lambda latency: app.send_latency_time(latency)

    # Enable resize with resolution handler
    def enable_resize_handler(enabled, enable_res):
        set_json_app_argument(args.json_config, "enable_resize", enabled)
        if enabled:
            # Bind the handler
            webrtc_input.on_resize = on_resize_handler

            # Trigger resize and reload if it changed.
            on_resize_handler(enable_res)
        else:
            logger.info("removing handler for on_resize")
            webrtc_input.on_resize = lambda res: logger.warning("remote resize is disabled, skipping resize to %s" % res)

    webrtc_input.on_set_enable_resize = enable_resize_handler

    # Send client FPS to metrics
    webrtc_input.on_client_fps = lambda fps: metrics.set_fps(fps)

    # Send client latency to metrics
    webrtc_input.on_client_latency = lambda latency_ms: metrics.set_latency(latency_ms)

    # Send client video bitrate to metrics
    webrtc_input.on_client_video_bitrate = lambda bitrate: metrics.set_video_bitrate(bitrate)

    # Send client audio bitrate to metrics
    webrtc_input.on_client_audio_bitrate = lambda bitrate: metrics.set_audio_bitrate(bitrate)

    # Send client available receive bandwidth to metrics 
    webrtc_input.on_client_available_bandwidth = lambda bandwidth: metrics.set_available_bandwidth(bandwidth)

    # Send client resolution to metrics
    webrtc_input.on_client_resolution = lambda resolution: metrics.set_resolution(resolution)

    # Send WebRTC stats to metrics
    webrtc_input.on_client_webrtc_stats = lambda webrtc_stat_type, webrtc_stats: metrics.set_webrtc_stats(webrtc_stat_type, webrtc_stats)

    # Initialize GPU monitor
    gpu_mon = GPUMonitor(enabled=args.encoder.startswith("nv"))

    # Send the GPU stats when available.
    def on_gpu_stats(load, memory_total, memory_used):
        app.send_gpu_stats(load, memory_total, memory_used)
        metrics.set_gpu_utilization(load * 100)

    gpu_mon.on_stats = on_gpu_stats

    # Initialize the system monitor
    system_mon = SystemMonitor()

    def on_sysmon_timer(t):
        webrtc_input.ping_start = t
        app.send_system_stats(system_mon.cpu_percent, system_mon.mem_total, system_mon.mem_used)
        app.send_ping(t)

        # send the stats to metrics
        metrics.set_cpu_utilization(int(system_mon.cpu_percent))
        metrics.set_memory_utilization(round(system_mon.mem_used / (1024 ** 3), 2)) # converting bytes to GB

    system_mon.on_timer = on_sysmon_timer

    # [START main_start]
    # Connect to the signalling server and process messages.
    loop = asyncio.get_event_loop()
    # Handle SIGINT and SIGTERM where KeyboardInterrupt has issues with asyncio
    loop.add_signal_handler(signal.SIGINT, lambda: sys.exit(1))
    loop.add_signal_handler(signal.SIGTERM, lambda: sys.exit(1))

    # Initialize the signaling and web server
    options = argparse.Namespace()
    options.addr = args.addr
    options.port = args.port
    options.enable_basic_auth = args.enable_basic_auth
    options.basic_auth_user = args.basic_auth_user
    options.basic_auth_password = args.basic_auth_password
    options.enable_https = using_https
    options.https_cert = args.https_cert
    options.https_key = args.https_key
    options.health = "/health"
    options.web_root = os.path.abspath(args.web_root)
    options.keepalive_timeout = 30
    options.cert_restart = False # using_https
    options.rtc_config_file = args.rtc_config_json
    options.rtc_config = rtc_config
    options.turn_shared_secret = args.turn_shared_secret if using_hmac_turn else ''
    options.turn_host = args.turn_host if using_hmac_turn else ''
    options.turn_port = args.turn_port if using_hmac_turn else ''
    options.turn_protocol = turn_protocol
    options.turn_tls = using_turn_tls
    options.turn_auth_header_name = args.turn_rest_username_auth_header
    options.stun_host = args.stun_host
    options.stun_port = args.stun_port
    server = WebRTCSimpleServer(loop, options)
        

   # Intialize the Dstreamer agent
    dstreamer_agent = DstreamerAgentClient('/run/dstreamer/agent.sock')

    def dstreamer_agent_action_handler(action):
        if action != "":
            reponse = dstreamer_agent.send_command(action)

            # if action is to shutdown then stop gstreamer pipeline
            if action == "shutdown":
                app.stop_pipeline()

        return reponse
    server.on_action = lambda action: dstreamer_agent_action_handler(action)

    # Callback method to update TURN servers of a running pipeline.
    def mon_rtc_config(stun_servers, turn_servers, rtc_config):
        if app.webrtcbin:
            # We only need STUN/TURN servers when using symmetric mode
            if not asymmetric_ice_mode:
                logger.info("updating STUN server")
                app.webrtcbin.set_property("stun-server", stun_servers[0])
                for i, turn_server in enumerate(turn_servers):
                    logger.info("updating TURN server")
                    if i == 0:
                         app.webrtcbin.set_property("turn-server", turn_server)
                    else:
                        app.webrtcbin.emit("add-turn-server", turn_server)
        server.set_rtc_config(rtc_config)

    # Initialize periodic monitor to refresh TURN RTC config when using shared secret.
    hmac_turn_mon = HMACRTCMonitor(
        args.turn_host,
        args.turn_port,
        args.turn_shared_secret,
        turn_rest_username,
        turn_protocol=turn_protocol,
        turn_tls=using_turn_tls,
        stun_host=args.stun_host,
        stun_port=args.stun_port,
        period=60, enabled=using_hmac_turn)
    hmac_turn_mon.on_rtc_config = mon_rtc_config

    # Initialize REST API RTC config monitor to periodically refresh the REST API RTC config.
    turn_rest_mon = RESTRTCMonitor(
        args.turn_rest_uri,
        turn_rest_username,
        args.turn_rest_username_auth_header,
        turn_protocol=turn_protocol,
        turn_rest_protocol_header=args.turn_rest_protocol_header,
        turn_tls=using_turn_tls,
        turn_rest_tls_header=args.turn_rest_tls_header,
        period=60, enabled=using_turn_rest)
    turn_rest_mon.on_rtc_config = mon_rtc_config

    # Initialize file watcher for RTC config JSON file.
    rtc_file_mon = RTCConfigFileMonitor(
        rtc_file=args.rtc_config_json,
        enabled=using_rtc_config_json)
    rtc_file_mon.on_rtc_config = mon_rtc_config

    # Initialise CoturnEnvVarConfig to periodically refresh the conturn config
    coturn_env_mon = CoturnEnvVarMonitor(
        args.stun_host,
        args.stun_port,
        args.turn_host, 
        args.turn_port, 
        args.turn_username, 
        args.turn_password, 
        turn_protocol, 
        using_turn_tls,
        using_stunner)
    coturn_env_mon.on_rtc_config = mon_rtc_config

    async def desktop_pipeline():
        asyncio.ensure_future(app.handle_bus_calls(), loop=loop)
        await signalling.connect()
        task = asyncio.create_task(signalling.start())
        return task

    async def webcam_pipeline():
        asyncio.ensure_future(webcam_app.handle_bus_calls(), loop=loop)
        await webcam_signalling.connect()

        task = asyncio.create_task(webcam_signalling.start())
        return task
    
    async def run_the_loop():
        desktop_task = await desktop_pipeline()

        if enable_webcam:
            webcam_task = await webcam_pipeline()

        # TODO: done() method only returns boolean value, even for exceptions, 
        # need to handle exceptions if we encounter any
        while True:

            # If the task is finished for any reason(completed, or exception raised) reinstantiate them again.
            # This is done to facilitate the session(especially for webcam connection) to server multiple number
            # of times, as, a user can enable/disable the webcam 'n' number of times in a single session of desktop streaming.
            if desktop_task.done():
                app.stop_pipeline()
                webrtc_input.release_keys()
                desktop_task = await desktop_pipeline()

            if enable_webcam:
                if webcam_task.done():
                    webcam_app.stop_pipeline()
                    webcam_task = await webcam_pipeline()
            await asyncio.sleep(0.5)

    try:
        asyncio.ensure_future(server.run(), loop=loop)
        if using_metrics_http:
            metrics.start_http()
        loop.run_until_complete(webrtc_input.connect())
        loop.run_in_executor(None, lambda: webrtc_input.start_clipboard())
        loop.run_in_executor(None, lambda: webrtc_input.start_cursor_monitor())
        loop.run_in_executor(None, lambda: gpu_mon.start())
        loop.run_in_executor(None, lambda: hmac_turn_mon.start())
        loop.run_in_executor(None, lambda: turn_rest_mon.start())
        loop.run_in_executor(None, lambda: rtc_file_mon.start())
        loop.run_in_executor(None, lambda: system_mon.start())
        loop.run_in_executor(None, lambda: coturn_env_mon.start())
        loop.run_in_executor(None, lambda: webrtc_input.handle_key_repeat())

        loop.run_until_complete(run_the_loop())
            
    except Exception as e:
        logger.error("Caught exception: %s" % e)
        traceback.print_exc()
        sys.exit(1)
    finally:
        app.stop_pipeline()
        if enable_webcam:
            webcam_app.stop_pipeline()

        webrtc_input.stop_clipboard()
        webrtc_input.stop_cursor_monitor()
        webrtc_input.disconnect()
        gpu_mon.stop()
        hmac_turn_mon.stop()
        turn_rest_mon.stop()
        rtc_file_mon.stop()
        system_mon.stop()
        coturn_env_mon.stop()
        loop.run_until_complete(server.stop())
        sys.exit(0)
    # [END main_start]

if __name__ == '__main__':
    main()
