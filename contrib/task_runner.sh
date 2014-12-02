#!/bin/bash
#
# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


HELP="This is a script to bootstrap a localhost cluster for testing.\n\
The following defaults are preconfigured but modifyable:\n\
  SHARD_NAME: Name of the shard to register with master\n\
  NUM_HOSTS_MASTER/SHARD: Number of hosts to add to the master/shard.\n\
  MASTER/SHARD_BOARD: Boards to add to the master/shard\n\
  POOL: Pool to use for the hosts."


# Invalidate (delete) the hosts/labels/shard instead of adding them.
# Typically used to refresh a botched cluster.
INVALIDATE_ALL=0
AT_DIR=/usr/local/autotest

# See VagrantFile for details on how these afes are setup.
AFE=localhost:8001
SHARD_NAME=localhost:8004

# Number of hosts on master and shard. They will
# get autoassigned generic names like test_hostX.
NUM_HOSTS_MASTER=50
NUM_HOSTS_SHARD=10

# A host can only have a single board. Jobs are sent
# to the shard based on the board.
MASTER_BOARD=board:link
SHARD_BOARD=board:lumpy

# All hosts need to be in a pool.
POOL=pool:bot

y_n_prompt() {
  read -r -p "Are you sure? [y/N] " response
  if [[ $response =~ ^([yY][eE][sS]|[yY])$ ]]; then
    return 0
  else
    return 1
  fi
}

while getopts ":h" opt; do
  case $opt in
    h)
      echo -e "${HELP}" >&2
      exit 0
      ;;
  esac
done


atest_hosts() {
  hosts=("${!1}")
  labels="${2}"
  hostnames=''
  for H in ${hosts[*]}; do
    if [ "$hostnames" ]; then
      hostnames="$hostnames,$H"
    else
      hostnames=$H
    fi
  done
  if [ $INVALIDATE_ALL -eq 1 ]; then
    $AT_DIR/cli/atest host delete $hostnames --web $AFE
    $AT_DIR/cli/atest label delete $labels --web $AFE
  else
    $AT_DIR/cli/atest host create $hostnames --web $AFE
    $AT_DIR/cli/atest label add -m $hostnames $labels --web $AFE
  fi
}

MASTER_HOSTS=()
for i in $(seq 0 $NUM_HOSTS_MASTER); do
  MASTER_HOSTS[$i]=test_host$i;
done

SHARD_HOSTS=()
for i in $(seq $(($NUM_HOSTS_MASTER+1)) $(($NUM_HOSTS_SHARD+$NUM_HOSTS_MASTER))); do
  SHARD_HOSTS[$i]=test_host$i;
done

operation='Adding: '
if [ $INVALIDATE_ALL -eq 1 ]; then
  operation='Removing '
fi
printf '%s following hosts to master \n\n' $operation
echo ${MASTER_HOSTS[*]}
if $(y_n_prompt); then
  atest_hosts MASTER_HOSTS[*] $POOL,$MASTER_BOARD
fi

printf '%s following hosts to shard \n\n' $operation
echo ${SHARD_HOSTS[*]}
if $(y_n_prompt); then
  atest_hosts SHARD_HOSTS[*] $POOL,$SHARD_BOARD
fi

printf '%s shard \n\n' $operation
echo $SHARD_NAME
if $(y_n_prompt); then
  if [ $INVALIDATE_ALL -eq 1 ]; then
    $AT_DIR/cli/atest shard delete $SHARD_NAME --web $AFE
  else
    $AT_DIR/cli/atest shard create $SHARD_NAME -l $SHARD_BOARD --web $AFE
  fi
fi
