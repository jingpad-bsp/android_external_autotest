#!/bin/bash

. "$(dirname "$0")/common.sh"

KSUBKEY_VERSION=$1

# TODO(ctchang) Modify this after adding dumpRSAPublicKey to image
PATH=$PATH:/usr/local/sbin/firmware/saft
export PATH

pushd /var/tmp/faft/autest/keys

make_pair "kernel_subkey" $KERNEL_SUBKEY_ALGOID $KSUBKEY_VERSION

popd
