#!/bin/sh
SERVER="http://YOUR_SERVER_IP:8080"
LAST_VER=""

# Stop Kindle UI framework, turn off frontlight, and prevent screensaver
/etc/init.d/framework stop
lipc-set-prop com.lab126.powerd preventScreenSaver 1
lipc-set-prop com.lab126.powerd flIntensity 0

while true; do
    # 1. Check if train, direction, or theme config changed via /admin
    CUR_VER=$(wget -q -T 5 -O - "$SERVER/version")

    if [ -n "$CUR_VER" ] && [ "$CUR_VER" != "$LAST_VER" ]; then
        # Config changed (or first boot): Fetch and flash-draw the static base layout (1236x1648)
        if wget -q -T 10 -O /tmp/base.png "$SERVER/base.png"; then
            eips -f -g /tmp/base.png
            LAST_VER="$CUR_VER"
        fi
    fi

    # 2. Fetch and stamp ONLY the countdown minutes & top-right timestamp (M2L3EK 1236x1648 coordinates)
    if wget -q -T 8 -O /tmp/row1.png "$SERVER/row1.png"; then
        eips -g /tmp/row1.png -x 290 -y 53
    fi

    if wget -q -T 8 -O /tmp/row2.png "$SERVER/row2.png"; then
        eips -g /tmp/row2.png -x 885 -y 53
    fi

    if wget -q -T 8 -O /tmp/updated.png "$SERVER/updated.png"; then
        eips -g /tmp/updated.png -x 20 -y 40
    fi

    sleep 60
done
