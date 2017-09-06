# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

import common
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.site_utils.lxc import constants
from autotest_lib.site_utils.lxc.container import Container

try:
    from chromite.lib import metrics
except ImportError:
    metrics = utils.metrics_mock


class ContainerFactory(object):
    """A factory class for creating LXC container objects.
    """

    def __init__(self, base_container, container_class=Container, snapshot=True,
                 force_cleanup=False):
        """Initializes a ContainerFactory.

        @param base_container: The base container from which other containers
                               are cloned.
        @param container_class: (optional) The Container class to instantiate.
                                By default, lxc.Container is instantiated.
        @param snapshot: (optional) If True, creates LXC snapshot clones instead
                         of full clones.  By default, snapshot clones are used.
        @param force_cleanup: (optional) If True, if a container is created with
                              a name and LXC directory matching an existing
                              container, the existing container is destroyed,
                              and the new container created in its place. By
                              default, existing containers are not destroyed and
                              a ContainerError is raised.
        """
        self._container_class = container_class
        self._base_container = base_container
        self._snapshot = snapshot
        self._force_cleanup = force_cleanup


    def create_container(self, cid, path):
        """Creates a new container.

        @param cid: A ContainerId for the new container.
        @param path: The LXC path for the new container.
        """
        # Legacy: use the string representation of the ContainerId as its name.
        name = str(cid)
        container = self._create_from_base(name, path)
        container.id = cid
        return container


    # create_from_base_duration is the original name of the metric.  Keep this
    # so we have history.
    @metrics.SecondsTimerDecorator(
            '%s/create_from_base_duration' % constants.STATS_KEY)
    def _create_from_base(self, name, container_path):
        """Creates a container from the base container.

        @param name: Name of the container.
        @param container_path: The LXC path of the new container.

        @return: A Container object for the created container.

        @raise ContainerError: If the container already exist.
        @raise error.CmdError: If lxc-clone call failed for any reason.
        """
        use_snapshot = constants.SUPPORT_SNAPSHOT_CLONE and self._snapshot

        try:
            return self._container_class.clone(src=self._base_container,
                                               new_name=name,
                                               new_path=container_path,
                                               snapshot=use_snapshot,
                                               cleanup=self._force_cleanup)
        except error.CmdError:
            logging.debug('Creating snapshot clone failed. Attempting without '
                           'snapshot...')
            if not use_snapshot:
                raise
            else:
                # Snapshot clone failed, retry clone without snapshot.
                container = self._container_class.clone(
                        src=self._base_container,
                        new_name=name,
                        new_path=container_path,
                        snapshot=False,
                        cleanup=self._force_cleanup)
                return container
