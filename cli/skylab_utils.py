# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Constants and util methods to interact with skylab inventory repo."""

import logging

from autotest_lib.client.common_lib import revision_control
from skylab_inventory import text_manager

# The git url of the internal skylab_inventory
INTERNAL_INVENTORY_REPO_URL = ('https://chrome-internal.googlesource.com/'
                               'chromeos/infra_internal/skylab_inventory.git')


def construct_commit_message(subject, bug=None, test=None):
    """Construct commit message for skylab inventory repo commit.

    @param subject: Commit message subject.
    @param bug: Bug number of the commit.
    @param test: Tests of the commit.

    @return: A commit message string.
    """
    return '\n'.join([subject, '', 'BUG=%s' % bug, 'TEST=%s' % test])


class InventoryRepo(object):
    """Class to present a inventory repository."""

    def __init__(self, inventory_repo_dir):
        self.inventory_repo_dir = inventory_repo_dir
        self.git_repo = None

    def initialize(self):
        """Initialize inventory repo at the given dir."""
        git_repo = revision_control.GitRepo(
                self.inventory_repo_dir,
                giturl=INTERNAL_INVENTORY_REPO_URL,
                abs_work_tree=self.inventory_repo_dir)

        if git_repo.is_repo_initialized():
            logging.info('Inventory repo was already initialized, start '
                         'pulling.')
            git_repo.pull()
        else:
            logging.info('No inventory repo was found, start cloning.')
            git_repo.clone()

        return git_repo


    def get_data_dir(self):
        """Get path to the data dir."""
        return text_manager.get_data_dir(self.inventory_repo_dir)
