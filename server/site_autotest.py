# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
from autotest_lib.client.common_lib import global_config
from autotest_lib.server import autoserv_parser, installable_object


config = global_config.global_config
parser = autoserv_parser.autoserv_parser


class SiteAutotest(installable_object.InstallableObject):

    def get(self, location = None):
        if not location:
            location = os.path.join(self.serverdir, '../client')
            location = os.path.abspath(location)
        installable_object.InstallableObject.get(self, location)
        self.got = True


    def get_fetch_location(self):
        """Autotest packages are always stored under the image URL."""
        repos = super(SiteAutotest, self).get_fetch_location()
        if parser.options.image:
            # Add our new repo to the end, the package manager will later
            # reverse the list of repositories resulting in ours being first.
            repos.append(parser.options.image.replace(
                'update', 'static/archive').rstrip('/') + '/autotest')

        return repos


class _SiteRun(object):
    pass
