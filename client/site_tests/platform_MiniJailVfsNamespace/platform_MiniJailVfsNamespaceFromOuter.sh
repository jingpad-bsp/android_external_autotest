#!/bin/sh
# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# This script runs two processes to check the mount visibility.  On start, the
# first process waits for the MOUNT command on stdin.  Upon receiving the
# command, it will mount $MOUNT_FROM to $MOUNT_TO as a bind mount, and then
# create the file named $MOUNT_TO/$FILE_TO_TEST.  The second process waits the
# command CHECK on stdin, and upon receipt, it checks to see if it can open
# $MOUNT_TO/$FILE_TO_TEST and reports success or failure.  UMOUNT is sent to the
# first process, which then deletes the file and removes the mount.
# Finally, both processes are sent the EXIT command on stdin.

# In this test, the mount is done outside of minijail, but after the minijail
# process starts.  So the jailed process should not be able to see the mount
# because it's copy of the vfs namespace was made before the mount was created.

PREFIX=platform_MiniJailVfsNamespace_$$
PROG=${1}

PIPER_MOUNTER=/tmp/${PREFIX}_mounter_r
PIPEW_MOUNTER=/tmp/${PREFIX}_mounter_w
PIPER_CHECKER=/tmp/${PREFIX}_checker_r
PIPEW_CHECKER=/tmp/${PREFIX}_checker_w
MOUNT_FROM=/tmp/${PREFIX}_mountfrom
MOUNT_TO=/tmp/${PREFIX}_mountto
FILE_TO_TEST=file_to_test.txt

mkfifo ${PIPER_MOUNTER}
mkfifo ${PIPEW_MOUNTER}
mkfifo ${PIPER_CHECKER}
mkfifo ${PIPEW_CHECKER}

exec 6<>${PIPER_MOUNTER}
exec 7<>${PIPEW_MOUNTER}
exec 8<>${PIPER_CHECKER}
exec 9<>${PIPEW_CHECKER}

mkdir ${MOUNT_FROM}
mkdir ${MOUNT_TO}

${PROG} --doMountOnSignal \
  --fromDir=${MOUNT_FROM} \
  --toDir=${MOUNT_TO} \
  --fileName=${FILE_TO_TEST} \
  <&7 >&6 \
  7<&- 6<&- 9<&- 8<&- &

/sbin/minijail --namespace-vfs -- \
  ${PROG} --checkMountOnSignal \
    --filePath=${MOUNT_TO}/${FILE_TO_TEST} \
    <&9 >&8 \
    7<&- 6<&- 9<&- 8<&- &

read <&6 PID_MOUNTER
read <&8 PID_CHECKER
sleep 1

echo Mounter PID: ${PID_MOUNTER}
echo Checker PID: ${PID_CHECKER}

# Tell the mounter to do the bind mount and create the file
echo "MOUNT" >${PIPEW_MOUNTER}
LINE=""
while [ "${LINE}" != "DONE_CMD: MOUNT" ]
do
  read <&6 LINE
  echo ${LINE}
done
sleep 1

# Tell the checker to see if the file is visible
echo "CHECK" >${PIPEW_CHECKER}
LINE=""
while [ "${LINE}" != "DONE_CMD: CHECK" ]
do
  read <&8 LINE
  echo ${LINE}
done
sleep 1

# Tell the mounter to delete the file and unmount
echo "UMOUNT" >${PIPEW_MOUNTER}
LINE=""
while [ "${LINE}" != "DONE_CMD: UMOUNT" ]
do
  read <&6 LINE
  echo ${LINE}
done
sleep 1

echo "EXIT" >${PIPEW_MOUNTER}
echo "EXIT" >${PIPEW_CHECKER}
sleep 1

exec 6<&-
exec 7<&-
exec 8<&-
exec 9<&-

rm -fR ${MOUNT_FROM}
rm -fR ${MOUNT_TO}

rm -f ${PIPER_MOUNTER}
rm -f ${PIPEW_MOUNTER}
rm -f ${PIPER_CHECKER}
rm -f ${PIPEW_CHECKER}
