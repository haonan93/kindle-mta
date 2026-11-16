#!/bin/sh
# Name: Subway Sign
# Author: Custom
# Icon:

killall -9 python3.11 2>/dev/null || true
killall -9 jobman 2>/dev/null || true
nohup /mnt/us/python3/bin/python3 -u /mnt/us/subway-sign/native_sign.py >/tmp/sign.log 2>&1 &
