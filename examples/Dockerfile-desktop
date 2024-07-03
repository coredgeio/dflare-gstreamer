ARG UBUNTU_RELEASE=20.04
FROM ubuntu:${UBUNTU_RELEASE}
ARG UBUNTU_RELEASE

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y \
        # System dependencies
        build-essential \
        curl \
        gnupg \
        software-properties-common \
        sudo 

# Installing KDE(Kate Desktop Environment) and other GUI packages
ENV XDG_CURRENT_DESKTOP=KDE
ENV KWIN_COMPOSE=N
RUN mkdir -pm755 /etc/apt/preferences.d && echo "Package: firefox*\n\
Pin: version 1:1snap*\n\
Pin-Priority: -1" > /etc/apt/preferences.d/firefox-nosnap && \
    mkdir -pm755 /etc/apt/trusted.gpg.d && curl -fsSL "https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x0AB215679C571D1C8325275B9BDB3D89CE49EC21" | gpg --dearmor -o /etc/apt/trusted.gpg.d/mozillateam-ubuntu-ppa.gpg && \
    mkdir -pm755 /etc/apt/sources.list.d && echo "deb https://ppa.launchpadcontent.net/mozillateam/ppa/ubuntu $(grep UBUNTU_CODENAME= /etc/os-release | cut -d= -f2 | tr -d '\"') main" > "/etc/apt/sources.list.d/mozillateam-ubuntu-ppa-$(grep UBUNTU_CODENAME= /etc/os-release | cut -d= -f2 | tr -d '\"').list" && \
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
        systemsettings \
        xdg-desktop-portal-kde \
        xkb-data \
        x11-xkb-utils \
        x11-xserver-utils \
        x11-utils \
        x11-apps \
        xauth \
        xbitmaps \
        xinit \
        xfonts-base \
        pulseaudio \
        libpulse0 \
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

ENV DISPLAY=:0
RUN echo 'export DISPLAY=${DISPLAY}' \
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
    
# Add Tini init script - take care of runaway processes
ENV TINI_VERSION=v0.7.0
ADD https://github.com/krallin/tini/releases/download/${TINI_VERSION}/tini /tini
RUN chmod +x /tini

# Install ARC Theme
RUN sudo add-apt-repository ppa:papirus/papirus-dev
RUN sudo apt-get update
RUN sudo apt-get install -y --install-recommends arc-kde

RUN sudo apt-get update && apt-get install latte-dock

# Remove lock screen
RUN echo "[Daemon]\n Autolock=false\n LockOnResume=false" > /etc/xdg/kscreenlockerrc

# Clear up the apt cache
RUN rm -rf /var/lib/apt/lists/*

COPY configure_ui.sh /
COPY bookmark-manager.sh /
COPY ./dstreamer_agent/dstreamer-agent /usr/bin/dstreamer-agent

ENV XDG_RUNTIME_DIR=/tmp/runtime-user
ENV HOSTNAME=Workspace-test
ENV SHELL=/bin/bash
ENV USER=${USERR}

RUN apt-get update && apt-get install -y netcat

# Disable the always-sink module and explicity create sinks for speakers 
# and microphone (see the entryscript where pulseaudio server is being initiated)
RUN sed -i 's/load-module module-always-sink/#load-module module-always-sink/' /etc/pulse/system.pa

RUN echo "#!/bin/bash\n\
export DISPLAY=\${DISPLAY}\n\
export XDG_RUNTIME_DIR=/tmp/runtime-user\n\
sudo Xvfb \${DISPLAY} -screen :0 8192x4096x24 +extension RANDR +extension GLX +render -noreset 2>&1 >/tmp/Xvfb.log &\n\
until [[ -S /tmp/.X11-unix/X\${DISPLAY:1} ]]; do sleep 1; done && echo 'X Server is ready'\n\
export PULSE_SERVER=unix:/run/pulse/native\n\
sudo /usr/bin/pulseaudio -k >/dev/null 2>&1\n\
sudo /usr/bin/pulseaudio --daemonize --verbose --system --log-target=file:/tmp/pulseaudio.log --disallow-exit --realtime=true\
    -L 'module-native-protocol-tcp auth-ip-acl=127.0.0.0/8 port=4713 auth-anonymous=1'\
    -L 'module-null-sink sink_name=virtmic sink_properties=device.description=Virtual_Microphone_Sink'\
    -L 'module-remap-source master=virtmic.monitor source_name=virtmic source_properties=device.description=Virtual_Microphone'\
    -L 'module-null-sink sink_name=output sink_properties=device.description=Output_speakers'\n\
pactl set-default-sink output\n\
sudo -u user mkdir -pm700 /tmp/runtime-user\n\
sudo chown user:user /tmp/runtime-user\n\
sudo -u user chmod 700 /tmp/runtime-user\n\
# This symbolic link enables running Xorg inside a container with `-sharevts`\n\
sudo ln -snf /dev/ptmx /dev/tty7 \n\
sudo /etc/init.d/dbus start \n\
/usr/bin/startplasma-x11 &\n\
bash /configure_ui.sh\n\
sudo mkdir /my-space\n\
sudo bash /usr/bin/dstreamer-agent &\n\
# The file manager process needs to run in order for config file ~/.local/share/user-places.xbel to get generated\n\
if [[ \${DF_WKS_STORAGE} == 'true' ]]; then dolphin & dolphin_pid=\$!; sleep 1s; bash /bookmark-manager.sh -n 'My Space' -l /my-space && kill \$dolphin_pid; fi\n\
sleep infinity \n\
" > /entrypoint.sh && chmod +x /entrypoint.sh

USER ${USERR}
WORKDIR /home/${USERR}

ENTRYPOINT ["/tini", "--"]
CMD ["/entrypoint.sh"]