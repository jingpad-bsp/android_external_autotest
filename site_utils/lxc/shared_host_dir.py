# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os

import common
from autotest_lib.client.bin import utils
from autotest_lib.site_utils.lxc import constants
from autotest_lib.site_utils.lxc import utils as lxc_utils


class SharedHostDir(object):
    """A class that manages the shared host directory.

    Instantiating this class sets up a shared host directory at the specified
    path.  The directory is cleaned up and unmounted when cleanup is called.
    """

    def __init__(self,
                 path = constants.DEFAULT_SHARED_HOST_PATH,
                 force_delete = False):
        """Sets up the shared host directory.

        @param shared_host_path: The location of the shared host path.
        @param force_delete: If True, the host dir will be cleared and
                             reinitialized if it already exists.
        """
        self.path = os.path.realpath(path)

        # If the host dir exists and is valid and force_delete is not set, there
        # is nothing to do.  Otherwise, clear the host dir if it exists, then
        # recreate it.
        if lxc_utils.path_exists(self.path):
            if not force_delete and self._host_dir_is_valid():
                return
            else:
                self.cleanup()

        utils.run('sudo mkdir "%(path)s" && '
                  'sudo chmod 777 "%(path)s" && '
                  'sudo mount --bind "%(path)s" "%(path)s" && '
                  'sudo mount --make-shared "%(path)s"' %
                  {'path': self.path})


    def cleanup(self):
        """Removes the shared host directory.

        This should only be called after all containers have been destroyed
        (i.e. all host mounts have been disconnected and removed, so the shared
        host directory should be empty).
        """
        if not os.path.exists(self.path):
            return

        # Unmount and delete everything in the host path.
        for info in lxc_utils.get_mount_info():
            if lxc_utils.is_subdir(self.path, info.mount_point):
                utils.run('sudo umount "%s"' % info.mount_point)

        # It's possible that the directory is no longer mounted (e.g. if the
        # system was rebooted), so check before unmounting.
        utils.run('if findmnt "%(path)s" > /dev/null;'
                  '  then sudo umount "%(path)s";'
                  'fi' %
                  {'path': self.path})
        utils.run('sudo rm -r "%s"' % self.path)


    def _host_dir_is_valid(self):
        """Verifies that the shared host directory is set up correctly."""
        logging.debug('Verifying existing host path: %s', self.path)
        host_mount = list(lxc_utils.get_mount_info(self.path))

        # Check that the host mount exists and is shared
        if host_mount:
            if 'shared' in host_mount[0].tags:
                return True
            else:
                logging.debug('Host mount not shared (%r).', host_mount)
        else:
            logging.debug('Host mount not found.')

        return False
