# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
from autotest_lib.client.common_lib import error, global_config
from autotest_lib.server import installable_object, autoserv_parser
from autotest_lib.server.cros import dynamic_suite


config = global_config.global_config
parser = autoserv_parser.autoserv_parser


class SiteAutotest(installable_object.InstallableObject):

    def get(self, location=None):
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
                if hosts and dynamic_suite.JOB_REPO_URL in hosts[0].attributes:
                    return hosts[0].attributes[dynamic_suite.JOB_REPO_URL]
                logging.warning("No %s for %s", dynamic_suite.JOB_REPO_URL,
                                self.host)
        except ImportError:
            logging.warning('Not attempting to look for %s',
                            dynamic_suite.JOB_REPO_URL)
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

        if parser.options.image:
            # The old way.
            # Add our new repo to the end, the package manager will later
            # reverse the list of repositories resulting in ours being first.
            repos.append(parser.options.image.replace(
                'update', 'static/archive').rstrip('/') + '/autotest')
        else:
            # The new way.
            found_repo = self._get_fetch_location_from_host_attribute()
            if found_repo is not None:
                # Add our new repo to the end, the package manager will
                # later reverse the list of repositories resulting in ours
                # being first
                repos.append(found_repo)

        return repos


    def install(self, host=None, autodir=None):
        """Install autotest.  If |host| is not None, stores it in |self.host|.

        @param host A Host instance on which autotest will be installed
        @param autodir Location on the remote host to install to
        """
        if host:
            self.host = host

        super(SiteAutotest, self).install(host=host, autodir=autodir)


class SiteClientLogger(object):
    """Overrides default client logger to allow for using a local package cache.
    """

    def _process_line(self, line):
        """Returns the package checksum file if it exists."""
        logging.debug(line)
        fetch_package_match = self.fetch_package_parser.search(line)
        if fetch_package_match:
            pkg_name, dest_path, fifo_path = fetch_package_match.groups()
            serve_packages = global_config.global_config.get_config_value(
                "PACKAGES", "serve_packages_from_autoserv", type=bool)
            if serve_packages and pkg_name == 'packages.checksum':
                package_served = False
                try:
                    checksum_file = os.path.join(
                        self.job.pkgmgr.pkgmgr_dir, 'packages', pkg_name)
                    if os.path.exists(checksum_file):
                        self.host.send_file(checksum_file, dest_path)
                        package_served = True
                except error.AutoservRunError:
                    msg = "Package checksum file not found, continuing anyway"
                    logging.exception(msg)

                if package_served:
                    try:
                        # When fetching a package, the client expects to be
                        # notified when the fetching is complete. Autotest
                        # does this pushing a B to a fifo queue to the client.
                        self.host.run("echo B > %s" % fifo_path)
                    except error.AutoservRunError:
                        msg = "Checksum installation failed, continuing anyway"
                        logging.exception(msg)
                    finally:
                      return

        # Fall through to process the line using the default method.
        super(SiteClientLogger, self)._process_line(line)


    def _send_tarball(self, pkg_name, remote_dest):
        """Uses tarballs in package manager by default."""
        try:
            server_package = os.path.join(self.job.pkgmgr.pkgmgr_dir,
                                          'packages', pkg_name)
            if os.path.exists(server_package):
              self.host.send_file(server_package, remote_dest)
              return

        except error.AutoservRunError:
            msg = ("Package %s could not be sent from the package cache." %
                   pkg_name)
            logging.exception(msg)

        # Fall through to send tarball the default method.
        super(SiteClientLogger, self)._send_tarball(pkg_name, remote_dest)


class _SiteRun(object):
    pass
