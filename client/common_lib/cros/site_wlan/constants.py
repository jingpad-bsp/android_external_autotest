# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Connection manager constants.

Includes DBus interface and error names, important file paths, etc.
"""

# DBus Interface names.
SUPPLICANT_INTERFACE = 'fi.w1.wpa_supplicant1.Interface'
CONNECTION_MANAGER = 'org.chromium.flimflam'
CONNECTION_MANAGER_DEVICE = '.'.join([CONNECTION_MANAGER, 'Device'])
CONNECTION_MANAGER_MANAGER = '.'.join([CONNECTION_MANAGER, 'Manager'])
CONNECTION_MANAGER_SERVICE = '.'.join([CONNECTION_MANAGER, 'Service'])
