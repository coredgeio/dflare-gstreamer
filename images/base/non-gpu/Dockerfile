# Supported base images: ubuntu:22.04, ubuntu:20.04

ARG UBUNTU_RELEASE=20.04
ARG GSTREAMER_BASE_IMAGE=ghcr.io/selkies-project/selkies-gstreamer/gstreamer
ARG GSTREAMER_BASE_IMAGE_RELEASE=v1.5.2
# The latest tag points to v1.1.0
ARG DFLARE_STREAMER_RELEASE=latest
ARG PY_BUILD_IMAGE=mohanj7/python-build:${DFLARE_STREAMER_RELEASE}
ARG WEB_IMAGE=mohanj7/web-img:${DFLARE_STREAMER_RELEASE}
FROM ${GSTREAMER_BASE_IMAGE}:${GSTREAMER_BASE_IMAGE_RELEASE}-ubuntu${UBUNTU_RELEASE} as selkies-gstreamer
FROM ${PY_BUILD_IMAGE} as selkies-build
FROM ${WEB_IMAGE} as selkies-web
FROM ubuntu:${UBUNTU_RELEASE}
ARG UBUNTU_RELEASE

# Insdtall Selkies-GStreamer system dependencies
RUN \
    apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y \
        # System dependencies
        build-essential \
        curl \
        gnupg \
        software-properties-common \
        sudo \
        tzdata \
        # GStreamer dependencies
        python3-pip \
        python3-dev \
        python3-gi \
        python3-setuptools \
        python3-wheel \
        udev \
        wmctrl \
        jq \
        gdebi-core \
        libgdk-pixbuf2.0-0 \
        libgtk2.0-bin \
        libgl-dev \
        libgles-dev \
        libglvnd-dev \
        libgudev-1.0-0 \
        xclip \
        x11-utils \
        xdotool \
        x11-xserver-utils \
        xserver-xorg-core \
        wayland-protocols \
        libwayland-dev \
        libwayland-egl1 \
        libx11-xcb1 \
        libxkbcommon0 \
        libxdamage1 \
        libsoup2.4-1 \
        libsoup-gnome2.4-1 \
        libsrtp2-1 \
        lame \
        libopus0 \
        libwebrtc-audio-processing1 \
        pulseaudio \
        libpulse0 \
        libcairo-gobject2 \
        libpangocairo-1.0-0 \
        libgirepository-1.0-1 \
        libopenjp2-7 \
        libjpeg-dev \
        libwebp-dev \
        libvpx-dev \
        zlib1g-dev \
        x264 \
        git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /opt

# Installing KDE(Kate Desktop Environment) and other GUI packages
ENV XDG_CURRENT_DESKTOP KDE
ENV KWIN_COMPOSE N
# Use sudoedit to change protected files instead of using sudo on kate
ENV SUDO_EDITOR kate
RUN mkdir -pm755 /etc/apt/preferences.d && \
    echo "Package: firefox*\n\
Pin: release o=Ubuntu*\n\
Pin-Priority: -1" > /etc/apt/preferences.d/firefox-ppa && \
    add-apt-repository -y ppa:mozillateam/ppa && \
    apt-get update && apt-get install --no-install-recommends -y \
        vim \
        curl \
        jq \
        xvfb \
        dbus-x11 \
        xdg-utils \
        firefox \
    kde-plasma-desktop \
        kwin-addons \
        kwin-x11 \
        kdeadmin \
        akregator \
        ark \
        baloo-kf5 \
        breeze-cursor-theme \
        breeze-icon-theme \
        debconf-kde-helper \
        colord-kde \
        desktop-file-utils \
        filelight \
        gwenview \
        hspell \
        kaddressbook \
        kaffeine \
        kate \
        kcalc \
        kcharselect \
        kdeconnect \
        kde-spectacle \
        kdf \
        kget \
        kgpg \
        khelpcenter \
        khotkeys \
        kimageformat-plugins \
        kinfocenter \
        kio-extras \
        kleopatra \
        kmail \
        kmenuedit \
        kmix \
        knotes \
        kontact \
        kopete \
        korganizer \
        krdc \
        ktimer \
        kwalletmanager \
        librsvg2-common \
        okular \
        okular-extra-backends \
        plasma-dataengines-addons \
        plasma-discover \
        plasma-runners-addons \
        plasma-wallpapers-addons \
        plasma-widgets-addons \
        plasma-workspace-wallpapers \
        qtvirtualkeyboard-plugin \
        sonnet-plugins \
        sweeper \
        systemsettings \
        xdg-desktop-portal-kde \
        kubuntu-restricted-extras \
        kubuntu-wallpapers \
        pavucontrol-qt \
        transmission-qt \
        xkb-data \
        x11-xkb-utils \
        x11-xserver-utils \
        x11-utils \
        x11-apps \
        xauth \
        xbitmaps \
        xinit \
        xfonts-base \
        libxrandr-dev && \
        rm -rf /var/lib/apt/lists/* && \
        cp -f /usr/lib/x86_64-linux-gnu/libexec/kf5/start_kdeinit /tmp/ && \
        rm -f /usr/lib/x86_64-linux-gnu/libexec/kf5/start_kdeinit && \
        cp -r /tmp/start_kdeinit /usr/lib/x86_64-linux-gnu/libexec/kf5/start_kdeinit && \
        rm -f /tmp/start_kdeinit

# Install locales to prevent X11 errors
RUN apt-get clean && \
    apt-get update && apt-get install --no-install-recommends -y locales && \
    rm -rf /var/lib/apt/lists/* && \
    locale-gen en_US.UTF-8

# Install Ubuntu 22.04 specific packages
RUN if [ "${UBUNTU_RELEASE}" = "22.04" ]; then apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y xcvt; fi && \
    rm -rf /var/lib/apt/lists/*

# Install gstreamer distribution
COPY --from=selkies-gstreamer /opt/gstreamer ./gstreamer

# Install web app
COPY --from=selkies-web /usr/share/nginx/html ./gst-web

# Update PWA manifest.json with app info and route.
ARG PWA_APP_NAME="Dflare"
ARG PWA_APP_SHORT_NAME="Dflare"
ARG PWA_START_URL="/index.html"
RUN \
    sed -i \
        -e "s|PWA_APP_NAME|${PWA_APP_NAME}|g" \
        -e "s|PWA_APP_SHORT_NAME|${PWA_APP_SHORT_NAME}|g" \
        -e "s|PWA_START_URL|${PWA_START_URL}|g" \
    /opt/gst-web/manifest.json && \
    sed -i \
        -e "s|PWA_CACHE|${PWA_APP_SHORT_NAME}-webrtc-pwa|g" \
    /opt/gst-web/app/sw.js

# Install selkies-gstreamer Python app
ARG PYPI_PACKAGE=selkies_gstreamer
ARG PACKAGE_VERSION=1.0.0
COPY --from=selkies-build /opt/pypi/dist/${PYPI_PACKAGE}-${PACKAGE_VERSION}-py3-none-any.whl .
RUN pip3 install /opt/${PYPI_PACKAGE}-${PACKAGE_VERSION}-py3-none-any.whl

# Setup global bashrc to configure GStreamer environment
RUN echo 'export DISPLAY=:0' \
        >> /etc/bash.bashrc && \
    echo 'export GST_DEBUG=*:2' \
        >> /etc/bash.bashrc && \
    echo 'export GSTREAMER_PATH=/opt/gstreamer' \
        >> /etc/bash.bashrc && \
    echo 'source /opt/gstreamer/gst-env' \
        >> /etc/bash.bashrc
    
ARG USERR="user"

# add user 
ARG TZ=Asia/Kolkata
RUN groupadd -g 1000 ${USERR} && \
    useradd -u 1000 -g 1000 -m -s /bin/bash ${USERR} && \
    usermod -a -G adm,audio,cdrom,dialout,dip,fax,floppy,input,plugdev,pulse-access,sudo,tape,tty,video,voice ${USERR} && \
    echo "${USERR} ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers && \
    chown -R ${USERR}:${USERR} /home/${USERR} && \
    echo "${USERR}:${USERR}" | chpasswd  && \
    passwd -d ${USERR} 
    # ln -snf "/usr/share/zoneinfo/$TZ" /etc/localtime && echo "$TZ" > /etc/timezone

# Add Tini init script - take care of runaway processes
ENV TINI_VERSION v0.7.0
ADD https://github.com/krallin/tini/releases/download/${TINI_VERSION}/tini /tini
RUN chmod +x /tini

# Set the shared memory to 256MB instead of default 64MB 
RUN sudo echo "tmpfs /dev/shm tmpfs defaults,size=1024M 0 0" >> /etc/fstab

# By setting up the env variable we can access the 
# user name in shell scripts
ENV USER=${USERR}

RUN sudo apt-get update && apt-get install latte-dock

# Remove lock screen
RUN echo "[Daemon]\n Autolock=false\n LockOnResume=false" > /etc/xdg/kscreenlockerrc

# Install ARC Theme
RUN sudo add-apt-repository ppa:papirus/papirus-dev
RUN sudo apt-get update
RUN sudo apt-get install -y --install-recommends arc-kde
RUN apt-get install -y nginx 

RUN echo "server { \n\
    listen 80;   \n\
    listen [::]:80; \n\
    location / { \n\
        alias /usr/share/nginx/html/; \n\ 
        index  index.html index.htm; \n\
    } \n\
    location /turn { \n\
        proxy_pass http://localhost:8080; \n\ 
		proxy_http_version 1.1; \n\ 
    } \n\ 
    location /webrtc/signalling { \n\ 
        proxy_pass http://localhost:8080; \n\
		proxy_http_version 1.1; \n\ 
        proxy_set_header Upgrade \$http_upgrade; \n\
        proxy_set_header Connection 'Upgrade'; \n\
        proxy_set_header Host \$host; \n\ 
    } \n\
    location /metrics { \n\
        proxy_pass http://localhost:8000; \n \
        proxy_http_version 1.1; \n\
    } \n\
    error_page   500 502 503 504  /50x.html; \n\
    location = /50x.html { \n\
        alias /usr/share/nginx/html/; \n\
    } \n\
}" > /etc/nginx/conf.d/default.conf

ENV GST_WEB_PORT 80 
ENV PATH_PREFIX /
RUN cp -r /opt/gst-web/* /usr/share/nginx/html
RUN rm /etc/nginx/sites-enabled/default

ENV XDG_RUNTIME_DIR /tmp/runtime-user
ENV HOSTNAME Workspace-test
ENV SHELL /bin/bash

COPY bookmark-manager.sh /
COPY configure_ui.sh /

RUN echo "#!/bin/bash\n\
export DISPLAY=:0\n\
export GST_DEBUG=*:2\n\
export GSTREAMER_PATH=/opt/gstreamer\n\
export XDG_RUNTIME_DIR=/tmp/runtime-user\n\
source /opt/gstreamer/gst-env\n\
sudo mount -o remount /dev/shm\n\
Xvfb -screen :0 8192x4096x24 +extension RANDR +extension GLX +extension MIT-SHM -nolisten tcp -noreset -shmem 2>&1 >/tmp/Xvfb.log &\n\
until [[ -S /tmp/.X11-unix/X0 ]]; do sleep 1; done && echo 'X Server is ready'\n\
export PULSE_SERVER=unix:/run/pulse/native\n\
sudo /usr/bin/pulseaudio -k >/dev/null 2>&1\n\
sudo /usr/bin/pulseaudio --daemonize --system --verbose --log-target=file:/tmp/pulseaudio.log --realtime=true --disallow-exit -L 'module-native-protocol-tcp auth-ip-acl=127.0.0.0/8 port=4713 auth-anonymous=1'\n\
sudo -u user mkdir -pm700 /tmp/runtime-user\n\
sudo chown user:user /tmp/runtime-user\n\
sudo -u user chmod 700 /tmp/runtime-user\n\
# This symbolic link enables running Xorg inside a container with `-sharevts` \n\
sudo ln -snf /dev/ptmx /dev/tty7 \n\
sudo /etc/init.d/dbus start \n\
startplasma-x11 &\n\
bash /configure_ui.sh\n\
export WEBRTC_ENCODER=\${WEBRTC_ENCODER:-x264enc}\n\
export WEBRTC_ENABLE_RESIZE=\${WEBRTC_ENABLE_RESIZE:-true}\n\
sudo chown -R \$USER:\$USER /home/\$USER \n\
sudo mkdir /my-space\n\
# The file manager process needs to run in order for config file ~/.local/share/user-places.xbel to get generated\n\
if [[ \${DF_WKS_STORAGE} == 'true' ]]; then dolphin & dolphin_pid=\$!; sleep 1s; bash /bookmark-manager.sh -n 'My Space' -l /my-space && kill \$dolphin_pid; fi\n\
sudo service nginx start\n\
selkies-gstreamer-resize 1280x720\n\
selkies-gstreamer\n\ \n\
" > /entrypoint.sh && chmod +x /entrypoint.sh

USER ${USERR}
WORKDIR /home/${USERR}

ENTRYPOINT ["/tini", "--"]
CMD ["/entrypoint.sh"]