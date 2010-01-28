#!/usr/bin/python

# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import common, commands, os
from autotest_lib.client.bin import utils

version = 1

def setup(top_dir):
    root = commands.getoutput('echo $GCLIENT_ROOT')

    # Make the debian package first
    autox_dir = '%s/src/platform/autox' % root
    os.chdir(autox_dir)
    utils.system('./make_pkg.sh')
    os.chdir(top_dir)

    # TODO(sosa@chromium.org) - Find out a way to figure out whether to use
    # arm vs. x86
    deb_dir = '%s/%s' % (root, 'src/build/x86/local_packages')
    package_regexp = 'chromeos-autox*'

    # Get the latest chromeos-autox package
    find_cmd = 'find %s -name %s | tail -n 1' % (deb_dir, package_regexp)
    deb_pkg = commands.getoutput(find_cmd)

    if deb_pkg == '':
        raise error.TestError('ChromeOS autox package not found')

    # The path of the dpkg script used to install debian packages
    dpkg_script = '%s/src/scripts/dpkg_no_scripts.sh' % root

    utils.system('%s --root %s --unpack %s' % (dpkg_script, top_dir, deb_pkg))

pwd = os.getcwd()
utils.update_version(pwd + '/src', False, version, setup, pwd)
