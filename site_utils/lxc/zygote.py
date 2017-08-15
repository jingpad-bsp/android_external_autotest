# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

import common
from autotest_lib.client.bin import utils
from autotest_lib.site_utils.lxc import Container
from autotest_lib.site_utils.lxc import constants
from autotest_lib.site_utils.lxc import lxc
from autotest_lib.site_utils.lxc import utils as lxc_utils


class Zygote(Container):
    """A Container that implements post-bringup configuration.
    """

    def __init__(self, container_path, name, attribute_values, src=None,
                 snapshot=False, host_path=None):
        """Initialize an object of LXC container with given attribute values.

        @param container_path: Directory that stores the container.
        @param name: Name of the container.
        @param attribute_values: A dictionary of attribute values for the
                                 container.
        @param src: An optional source container.  If provided, the source
                    continer is cloned, and the new container will point to the
                    clone.
        @param snapshot: Whether or not to create a snapshot clone.  By default,
                         this is false.  If a snapshot is requested and creating
                         a snapshot clone fails, a full clone will be attempted.
        @param host_path: If set to None (the default), a host path will be
                          generated based on constants.DEFAULT_SHARED_HOST_PATH.
                          Otherwise, this can be used to override the host path
                          of the new container, for testing purposes.
        """
        super(Zygote, self).__init__(container_path, name, attribute_values,
                                     src, snapshot)

        # Initialize host dir and mount
        if host_path is None:
            self.host_path = os.path.join(
                    os.path.realpath(constants.DEFAULT_SHARED_HOST_PATH),
                    self.name)
        else:
            self.host_path = host_path

        if src is not None:
            # If creating a new zygote, initialize the host dir.
            if not lxc_utils.path_exists(self.host_path):
                utils.run('sudo mkdir %s' % self.host_path)
            # Create the mount point within the container's rootfs.
            utils.run('sudo mkdir %s' %
                      os.path.join(self.rootfs,
                                   constants.CONTAINER_HOST_DIR.lstrip(
                                           os.path.sep)))
            self.mount_dir(self.host_path, constants.CONTAINER_HOST_DIR)


    def destroy(self, force=True):
        super(Zygote, self).destroy(force)
        if lxc_utils.path_exists(self.host_path):
            self._cleanup_host_mount()


    def set_hostname(self, hostname):
        """Sets the hostname within the container.

        @param hostname The new container hostname.
        """
        if self.is_running():
            self.attach_run('hostname %s' % (hostname))
            self.attach_run(constants.APPEND_CMD_FMT % {
                'content': '127.0.0.1 %s' % (hostname),
                'file': '/etc/hosts'})
        else:
            super(Zygote, self).set_hostname(hostname)


    def install_ssp(self, ssp_url):
        """Downloads and installs the given server package.

        @param ssp_url: The URL of the ssp to download and install.
        """
        # The host dir is mounted directly on /usr/local/autotest within the
        # container.  The SSP structure assumes it gets untarred into the
        # /usr/local directory of the container's rootfs.  In order to unpack
        # with the correct directory structure, create a tmpdir, mount the
        # container's host dir as ./autotest, and unpack the SSP.
        if not self.is_running():
            super(Zygote, self).install_ssp(ssp_url)
            return

        usr_local_path = os.path.join(self.host_path, 'usr', 'local')
        utils.run('sudo mkdir -p %s'% usr_local_path)

        with lxc_utils.TempDir(dir=usr_local_path) as tmpdir:
            download_tmp = os.path.join(tmpdir,
                                        'autotest_server_package.tar.bz2')
            lxc.download_extract(ssp_url, download_tmp, usr_local_path)

        container_ssp_path = os.path.join(
                constants.CONTAINER_HOST_DIR,
                constants.CONTAINER_AUTOTEST_DIR.lstrip(os.path.sep))
        self.attach_run('mkdir -p %s && mount --bind %s %s' %
                        (constants.CONTAINER_AUTOTEST_DIR,
                         container_ssp_path,
                         constants.CONTAINER_AUTOTEST_DIR))

    def copy(self, host_path, container_path):
        """Copies files into the zygote.

        @param host_path: Path to the source file/dir to be copied.
        @param container_path: Path to the destination dir (in the container).
        """
        if not self.is_running():
            super(Zygote, self).copy(host_path, container_path)
            return

        # First copy the files into the host mount, then move them from within
        # the container.
        self._do_copy(src=host_path,
                      dst=os.path.join(self.host_path,
                                       container_path.lstrip(os.path.sep)))

        src = os.path.join(constants.CONTAINER_HOST_DIR,
                         container_path.lstrip(os.path.sep))
        dst = os.path.dirname(container_path)
        self.attach_run('mkdir -p %s && mv %s %s' % (dst, src, dst))


    def _cleanup_host_mount(self):
        """Unmount and remove the host dir for this container."""
        lxc_utils.cleanup_host_mount(self.host_path);
