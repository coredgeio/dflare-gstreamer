#!/bin/bash

distro_version=$(grep VERSION_CODENAME /etc/os-release | cut -f2 -d=)
echo "Ditro verion is $distro_version"

# For ubuntu jammy the arc-darker isn't getting set propery, so for now going with dark theme
# also the icon theme should be set explicitly
if [ "$distro_version" == "jammy" ]; then
    kwriteconfig5 --file ~/.config/kdeglobals --group 'KDE' --key 'LookAndFeelPackage' 'com.github.varlesh.arc-dark'
    kwriteconfig5 --file ~/.config/kdeglobals --group 'Icons' --key 'Theme' 'ePapirus-Dark'
else 
    kwriteconfig5 --file ~/.config/kdeglobals --group 'KDE' --key 'LookAndFeelPackage' 'com.github.varlesh.arc-darker'
fi

latte-dock &

# wait for the file to be available
while [ ! -f ~/.config/plasma-org.kde.plasma.desktop-appletsrc ]; do sleep 0.5s; done;

if [ "$distro_version" == "jammy" ]; then 
    kwriteconfig5 --file ~/.config/plasma-org.kde.plasma.desktop-appletsrc --group 'Containments' --group '1' --group 'Wallpaper' --group 'org.kde.image' --group 'General' --key 'Image' '/usr/share/wallpapers/Arc-Mountains/'
    kwriteconfig5 --file ~/.config/plasma-org.kde.plasma.desktop-appletsrc --group 'Containments' --group '1' --group 'Wallpaper' --group 'org.kde.image' --group 'General' --key 'SlidePaths' '/usr/share/wallpapers'
else 
    kwriteconfig5 --file ~/.config/plasma-org.kde.plasma.desktop-appletsrc --group 'Containments' --group '1' --group 'Wallpaper' --group 'org.kde.image' --group 'General' --key 'Image' 'file:///usr/share/wallpapers/Arc-Mountains/contents/images/8000x4500.png'
fi 

sleep 1s
plasmashell --replace &

# Remove the default bottom panel 
sed -i '/^\[Containments\]\[2\]/,/^$/d' ~/.config/plasma-org.kde.plasma.desktop-appletsrc
kwriteconfig5 --file ~/.config/latte/Plasma.layout.latte --group 'Containments' --group '1' --group 'General' --key 'maxLength' --delete

# For Ubuntu jammy iconsize and margin need to configured
if [ "$distro_version" == "jammy" ]; then 
    kwriteconfig5 --file ~/.config/latte/Plasma.layout.latte --group 'Containments' --group '1' --group 'General' --key 'iconSize' '42'
    kwriteconfig5 --file ~/.config/latte/Plasma.layout.latte --group 'Containments' --group '1' --group 'General' --key 'thickMargin' '5'
fi

kwriteconfig5 --file ~/.config/latte/Plasma.layout.latte --group 'Containments' --group '1' --group 'General' --key 'splitterPosition' '0'
kwriteconfig5 --file ~/.config/latte/Plasma.layout.latte --group 'Containments' --group '1' --group 'General' --key 'splitterPosition2' '4'

# use Plasma dock layout for bottom panel
latte-dock --layout 'Plasma' --replace &