# Dstreamer-agent

Dstreamer-agent runs in workspaces containers with a unix domain socket opened as `/run/dstreamer-agent.sock`. This socket is used by dstreamer to communicate with dstreamer-agent. Dstreamer-agent is used to perform dstreamer related tasks in workspace container like notifications, shutdown, etc.

```
+----------------------------------+       +---------------+     +-----------------------------+
|              Browser             |       |               |     |          Workspace          |
|                                  |<----->|   Dstreamer   |---->|                             |
|    [dstreamer-webrtc-client]     |       |               |     |      [dstreamer-agent]      |
+----------------------------------+       +---------------+     +-----------------------------+
```

### Setup
* In workspace container image: `COPY dstreamer-agent /usr/bin/dstreamer-agent`
* Run `/usr/bin/dstreamer-agent &` on workspace container startup.
* Share `/run/dstreamer/agent.sock` in workspace container with dstreamer container using volume mounts.

