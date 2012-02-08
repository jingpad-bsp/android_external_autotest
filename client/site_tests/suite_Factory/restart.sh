#!/bin/sh
# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# The restart.sh is moved to ../../cros/factory/.

new_script="$(readlink -f "$(dirname "$0")/../..")/cros/factory/restart.sh"
echo "$(readlink -f "$0") is deprecated."
echo "In the future, please use $new_script instead."
sleep 3
"$new_script" "$@"
