#!/usr/bin/env python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# This utility allows for easy update to chromium os tree status, with proper
# password protected authorization.
#
# Example usage:
# ./set_tree_status.py "a quoted space separated message."

import getpass
import os
import sys
import urllib

CHROMEOS_STATUS_SERVER = 'https://chromiumos-status.appspot.com'


def get_status():
    response = urllib.urlopen(CHROMEOS_STATUS_SERVER + '/current?format=raw')
    return response.read()


def get_pwd():
    password_file = os.path.join('/home', getpass.getuser(),
                                 '.status_password.txt')
    if os.path.isfile(password_file):
        return open(password_file, 'r').read().strip()
    return getpass.getpass()


def post_status(message):
    status = get_status()
    if 'tree is closed' in status.lower():
        print >> sys.stderr, 'Tree is already closed for some other reason.'
        print >> sys.stderr, status
        return -1
    data = {
        'message': message,
        'username': getpass.getuser(),
        'password': get_pwd(),
    }
    urllib.urlopen(CHROMEOS_STATUS_SERVER + '/status', urllib.urlencode(data))
    return 0


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: set_tree_status.py "message"')
        sys.exit(1)

    sys.exit(post_status(sys.argv[1]))
