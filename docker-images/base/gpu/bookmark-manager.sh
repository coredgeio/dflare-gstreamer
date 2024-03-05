# Bookmark-manager tool helps in creating bookmarks in file managers like dolphin
# by editing the necessary files to include custom locations

# Currently this tool is tailored specificly to KDE environment
# TODO: update the script to support nautil file manager of Gnome DE when workspaces support Gnome DE

#!/bin/bash 
set -e

VERSION=0.1.0
TOOL_NAME="bookmark-manager"

# Displays about tool and its usage
cli_help() {
    cli_name=${0##*/}
    echo "
$TOOL_NAME
A small tool to create bookmarks in Desktop Environments like KDE, Gnome
Version: $VERSION

Usage: $TOOL_NAME [flag[value]]

falgs:
-f        : File location to edit, absolute path required. Defaults to '/home/user/.local/share/user-places.xbel'
-n        : Name of the bookmark. Defaults to 'bookmark'
-l        : Location of the file to which bookmark points to, absolute path required. Default to '/home/user/Desktop'
-i        : Icon for the bookmark. Defaults to 'user-home'
-s        : If it has to be system item, meaning user can not delete it via UI. Defaults to false
-h        : Display this help info

Examples:
bookmark-manager -f /home/user/.local/share/user-places.xbel -l /home/user/Desktop -s true
bookmark-manager -n storage 
bookmark-manager -f /home/user/.local/share/user-places.xbel -n storage
"
}

# Set default values
home=$HOME
# The file that will be manipulated to add bookmarks
file_location="${home}/.local/share/user-places.xbel"
# Name of the bookmark
bookmark_name="bookmark"
# The file/folder that the bookmark point to
bookmark_location="${home}/Desktop"
# Name of the icon used for the bookmark
icon="user-home"
# To make the bookmark as s system item, so that user can't delete 
# it via GUI. Accepted values are: true|false
system="false"


while getopts ":f:n:l:i:s:h:" opt; do
    case $opt in
        f)
            file_location="$OPTARG"
            ;;
        n)
            bookmark_name="$OPTARG"
            ;;
        l) 
            bookmark_location="$OPTARG"
            ;;
        i)
            icon="$OPTARG"
            ;;
        s) 
            system="$OPTARG"
            ;;
        h)
            cli_help
            exit 0
            ;;
        \?)
            echo "Invalid option: -$OPTARG" >&2
            cli_help
            exit 1
            ;;
        :)
            echo "Option -$OPTARG requires an argument." >&2
            cli_help
            exit 1
            ;;
    esac
done

# Check for file existence
if [ ! -e $file_location ]; then 
    echo "File doesn't exists at given location: $file_location"
    exit 1
fi 

# generate a unique ID for the bookmark template
get_new_id() {
    # IDs are in the format of <ID>1705669745/0</ID>. A unique number followed 
    # by index of the template.

    # parse the given file and grab the ID tags to get the current ID
    # store the latest one
    last_id=$(grep '<ID>' $file_location | \
    sed -e 's/^[ \t]*//' -e 's/[ \t]*$//' | 
    awk -F '[<>]' '/<ID>/{last_id=$3} END{print last_id}')

    # Split the last_id by '/' and store them as integers
    # The index in ID is not required as long as the major ID is unique
    IFS='/' read -r id index <<< "$last_id"

    # add a random number for uniqueness
    new_id="$((id + 2568))"
    echo $new_id
}

template_id=$(get_new_id) 
# echo "template id: $template_id"

# Create a new bookmark template 
bookmark_template="<bookmark href=\"file://$bookmark_location\">\n\
  <title>$bookmark_name</title>\n\
  <info>\n\
    <metadata owner=\"http://freedesktop.org\">\n\
     <bookmark:icon name=\"$icon\"/>\n\
    </metadata>\n\
    <metadata owner=\"http://www.kde.org\">\n\
     <ID>$template_id/1</ID>\n\
     <isSystemItem>$system</isSystemItem>\n\
    </metadata>\n\
  </info>\n\
</bookmark>"

# insert the template at the bottom of the file before the closing tag <xbel>
sed -i '$i'"$bookmark_template" $file_location

echo "Bookmark created successfully"