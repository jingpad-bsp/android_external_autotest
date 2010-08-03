#!/bin/sh

# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

XAUTH=/usr/bin/xauth
XAUTH_FILE="/var/run/factory_ui.auth"
SERVER_READY=
DISPLAY=":0"

user1_handler () {
  echo "X server ready..." 1>&2
  SERVER_READY=y
}

trap user1_handler USR1
MCOOKIE=$(head -c 8 /dev/urandom | openssl md5)
${XAUTH} -q -f ${XAUTH_FILE} add ${DISPLAY} . ${MCOOKIE}

/bin/sh -c "\
trap '' USR1 TTOU TTIN
exec /usr/bin/X11/X -nolisten tcp vt01 -auth ${XAUTH_FILE} \
-s 0 -p 0 -dpms 2> /dev/null" &

while [ -z ${SERVER_READY} ]; do
  sleep .1
done

export DISPLAY=${DISPLAY}
export XAUTHORITY=${XAUTH_FILE}

# TODO : currently necessary as ch7036 stuff only launches if upstart ui but in
# future it will be tied to udev
if [ -e /usr/bin/ch7036_monitor ] ; then
  /sbin/modprobe i2c-dev
  /usr/bin/ch7036_monitor -v > /var/log/factory_ch7036_monitor.log &
fi

/sbin/initctl emit factory-ui-started
cat /proc/uptime > /tmp/uptime-x-started

echo "export DISPLAY=${DISPLAY}"
echo "export XAUTHORITY=${XAUTH_FILE}"
