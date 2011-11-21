#!/bin/bash

# Copyright (c) 2009 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# Author: truty@google.com (Mike Truty)
#
# This script copies needed files to allow Autotest CLI access from nfs.

declare -r BASE_DIR="/usr/local/autotest"

declare -r TARGET_DIR="/home/build/static/projects-rw/chromeos/autotest"

function checktarget() {
  [[ -d "${TARGET_DIR}" ]] || mkdir -p "${TARGET_DIR}"
}

function copyfiles() {
  local norecurse_copy_dirs="\
    . \
    client \
    site-packages/simplejson"
  echo "Copying directories..."
  for d in ${norecurse_copy_dirs}; do
    echo Copying "$d"...
    [[ -d ${TARGET_DIR}/$d ]] || mkdir -p ${TARGET_DIR}/$d
    cp -f ${BASE_DIR}/$d/* ${TARGET_DIR}/$d
    # Ignore errors - warnings abound.
  done

  local recurse_copy_dirs="\
    cli \
    client/common_lib \
    database \
    frontend"
  for d in ${recurse_copy_dirs}; do
    echo Copying "$d"...
    [[ -d ${TARGET_DIR}/$d ]] || mkdir -p ${TARGET_DIR}/$d
    cp -rf ${BASE_DIR}/$d/* ${TARGET_DIR}/$d
    if [[ "$?" -ne 0 ]]; then
      echo Unable to copy ${BASE_DIR}/$d to ${TARGET_DIR}/$d
      exit 1
    fi
  done
  echo "Done."
}

function main() {
  checktarget
  copyfiles
  echo "The previous Autotest directory has a btuils folder"
  echo "that needs to be copied here. These utilities are"
  echo "used to archive (btcp) results files and serve"
  echo "them (btfsserver). Please create ${TARGET_DIR}/btuils"
  echo "and copy the contents of the previous btuils folder there."
}

main
