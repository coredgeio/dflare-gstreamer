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

from prometheus_client import start_http_server, Summary
from prometheus_client import Gauge, Histogram
import logging
import random
import time

logger = logging.getLogger("metrics")

FPS_HIST_BUCKETS = (0, 20, 40, 60)

class Metrics:
    def __init__(self, port=8000):
        self.port = port
        
        self.gpu_utilization = Gauge('gpu_utilization', 'Utilization percentage reported by GPU')
        self.fps = Gauge('fps', 'Frames per second observed by client', ['fps'])
        self.fps_hist = Histogram('fps_hist', 'Histogram of FPS observed by client', buckets=FPS_HIST_BUCKETS)
        self.selected_fps = 30 # The default fps is 30
        self.latency = Gauge('latency', 'Latency observed by client')
        self.video_bitrate = Gauge('video_bitrate', 'Video bitrate observed by client', ['video_bitrate'])
        self.selected_video_bitrate = 2  # The default video_bitrate is 2MBps
        self.audio_bitrate = Gauge('audio_bitrate', 'Audio bitrate observed by client', ['audio_bitrate'])
        self.selected_audio_bitrate = 64 # The default audio_bitrate is 64KBps
        self.cpu_utilization = Gauge('cpu_utilization', 'Utilization percentage reported by CPU')
        self.memory_utilization = Gauge('mem_utilization', 'Memory utilization percentage reported by system')
        self.available_receive_bandwidth = Gauge('bandwidth', 'Available receive bandwith of browser observed by client')
        self.resolution = Gauge('resolution', 'Resolution observed by client', ['resolution'])

    def set_gpu_utilization(self, utilization):
        self.gpu_utilization.set(utilization)

    def set_fps(self, fps):
        # The values of the label 'fps' are 'client' and 'selected' which represents
        # the fps observed by client and user selected fps
        self.fps.labels(fps="client").set(fps)
        self.fps.labels(fps="selected").set(self.selected_fps)
        self.fps_hist.observe(fps)
    
    def set_latency(self, latency_ms):
        self.latency.set(latency_ms)
    
    def set_video_bitrate(self, video_bitrate):
        self.video_bitrate.labels(video_bitrate="client").set(video_bitrate)
        self.video_bitrate.labels(video_bitrate="selected").set(self.selected_video_bitrate)
    
    def set_audio_bitrate(self, audio_bitrate):
        self.audio_bitrate.labels(audio_bitrate="client").set(audio_bitrate)
        self.audio_bitrate.labels(audio_bitrate="selected").set(self.selected_audio_bitrate)

    def set_cpu_utilization(self, utilization):
        self.cpu_utilization.set(utilization)

    def set_memory_utilization(self, utilization):
        self.memory_utilization.set(utilization)

    def set_available_bandwidth(self, bandwidth):
        self.available_receive_bandwidth.set(bandwidth)

    def set_resolution(self, resolution):
        width, height = resolution.split("x")
        self.resolution.labels(resolution="width").set(width)
        self.resolution.labels(resolution="height").set(height)

    def start(self):
        start_http_server(self.port)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    port = 8000

    m = Metrics(port)
    m.start()

    logger.info("Started metrics server on port %d" % port)
    
    # Generate some metrics.
    while True:
        m.set_fps(int(random.random() * 100 % 60))
        m.set_gpu_utilization(int(random.random() * 100))
        time.sleep(1)