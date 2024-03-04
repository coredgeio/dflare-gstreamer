# Some information regarding base images

Base images are the absolute minimum images that comes with all the required components for remote access of a container desktop.

## Components

- Dflare-streamer
  - Python build
  - Web interface
  - Gstreamer
- Desktop Environment

## Categories of base images

1. Non-GPU images
2. GPU enabled images

### Non-GPU images
 
These images do not support any GPU devices. Suitable for both development and non-development use cases.

### GPU enabled images

GPU enabled images consists of all the packages and drivers realted to GPUs (only supporting Nvidia as of now). Suitable for AI/ML driven use cases.


## Current work
 
Decoupling dflare-stremaer component from desktop environment for both business and security reasons. Here the decoupling is achieved by sharing the Unix sockets of X11 server and Pulseaudio server between the both containers. This sharing of sockets between the containers is done by mounting the a common directory between the two containers. [Check this dir](./slim-workspace/)
