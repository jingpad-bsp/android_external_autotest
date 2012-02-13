# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
from autotest_lib.client.common_lib import global_config
from autotest_lib.server import installable_object, autoserv_parser


config = global_config.global_config
parser = autoserv_parser.autoserv_parser


class SiteAutotest(installable_object.InstallableObject):

    def get(self, location = None):
        if not location:
            location = os.path.join(self.serverdir, '../client')
            location = os.path.abspath(location)
        installable_object.InstallableObject.get(self, location)
        self.got = True


    def _get_fetch_location_from_host_attribute(self):
        """Get repo to use for packages from host attribute, if possible.

        Hosts are tagged with an attribute containing the URL
        from which to source packages when running a test on that host.
        If self.host is set, attempt to look this attribute up by calling out
        to the AFE.

        @returns value of the 'job_repo_url' host attribute, if present.
        """
        try:
            from autotest_lib.server import frontend
            if self.host:
                afe = frontend.AFE(debug=False)
                hosts = afe.get_hosts(hostname=self.host.hostname)
                if 'job_repo_url' in hosts[0].attributes:
                    return hosts[0].attributes['job_repo_url']
                logging.warning("No job_repo_url for %s", self.host)
        except ImportError:
            logging.warning('Not attempting to look for job_repo_url')
            pass
        return None


    def get_fetch_location(self):
        """Generate list of locations where autotest can look for packages.

        Old n' busted: Autotest packages are always stored at a URL that can
        be derived from the one passed via the voodoo magic --image argument.
        New hotness: Hosts are tagged with an attribute containing the URL
        from which to source packages when running a test on that host.

        @returns the list of candidate locations to check for packages.
        """
        repos = super(SiteAutotest, self).get_fetch_location()

        # The new way.
        found_repo = self._get_fetch_location_from_host_attribute()
        if found_repo is not None:
            repos.append(found_repo)
            return repos

        # The old way.
        if parser.options.image:
            # Add our new repo to the end, the package manager will later
            # reverse the list of repositories resulting in ours being first.
            repos.append(parser.options.image.replace(
                'update', 'static/archive').rstrip('/') + '/autotest')

        return repos


    def install(self, host=None, autodir=None):
        """Install autotest.  If |host| is not None, stores it in |self.host|.

        @param host A Host instance on which autotest will be installed
        @param autodir Location on the remote host to install to
        """
        if host:
            self.host = host

        super(SiteAutotest, self).install(host=host, autodir=autodir)


class _SiteRun(object):
    pass
