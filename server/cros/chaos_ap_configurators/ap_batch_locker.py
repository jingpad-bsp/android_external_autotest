# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import random

from time import sleep

import common
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils
from autotest_lib.server.cros.chaos_ap_configurators import \
    ap_configurator_factory
from autotest_lib.server.cros.chaos_ap_configurators import ap_cartridge


# Max number of retry attempts to lock an ap.
MAX_RETRIES = 3


class ApLocker(object):
    """Object to keep track of AP lock state.

    @attribute configurator: an APConfigurator object.
    @attribute to_be_locked: a boolean, True iff ap has not been locked.
    @attribute retries: an integer, max number of retry attempts to lock ap.
    """


    def __init__(self, configurator, retries):
        """Initialize.

        @param configurator: an APConfigurator object.
        @param retries: an integer, max number of retry attempts to lock ap.
        """
        self.configurator = configurator
        self.to_be_locked = True
        self.retries = retries


    def __repr__(self):
        """@return class name, ap host name, lock status and retries."""
        return 'class: %s, host name: %s, to_be_locked = %s, retries = %d' % (
                self.__class__.__name__,
                self.configurator.host_name,
                self.to_be_locked,
                self.retries)


def construct_ap_lockers(ap_spec, retries):
    """Convert APConfigurator objects to ApLocker objects for locking.

    @param ap_spec: a dict of strings, AP attributes.
    @param retries: an integer, max number of retry attempts to lock ap.
    @return a list of ApLocker objects.
    """
    ap_lockers_list = []
    factory = ap_configurator_factory.APConfiguratorFactory()
    for ap in factory.get_ap_configurators(ap_spec):
        ap_lockers_list.append(ApLocker(ap, retries))

    if not len(ap_lockers_list):
        raise error.TestError('Found no matching APs to test against.')

    logging.debug('Found %d APs', len(ap_lockers_list))
    return ap_lockers_list


class ApBatchLocker(object):
    """Object to lock/unlock an APConfigurator.

    @attribute SECONDS_TO_SLEEP: an integer, number of seconds to sleep between
                                 retries.
    @attribute ap_spec: a dict of strings, AP attributes.
    @attribute retries: an integer, max number of retry attempts to lock ap.
                        Defaults to MAX_RETRIES.
    @attribute aps_to_lock: a list of ApLocker objects.
    @attribute manager: a HostLockManager object, used to lock/unlock APs.
    """


    MIN_SECONDS_TO_SLEEP = 30
    MAX_SECONDS_TO_SLEEP = 120


    def __init__(self, lock_manager, ap_spec, retries=MAX_RETRIES):
        """Initialize.

        @param ap_spec: a dict of strings, AP attributes.
        @param retries: an integer, max number of retry attempts to lock ap.
                        Defaults to MAX_RETRIES.
        """
        self.aps_to_lock = construct_ap_lockers(ap_spec, retries)
        self.manager = lock_manager
        self._locked_aps = []


    def has_more_aps(self):
        """@return True iff there is at least one AP to be locked."""
        return len(self.aps_to_lock) > 0


    def lock_ap_in_afe(self, ap_locker):
        """Locks an AP host in AFE.

        @param ap_locker: an ApLocker object, AP to be locked.
        @return a boolean, True iff ap_locker is locked.
        """
        if not utils.host_is_in_lab_zone(ap_locker.configurator.host_name):
            ap_locker.to_be_locked = False
            return True

        if self.manager.lock([ap_locker.configurator.host_name]):
            self._locked_aps.append(ap_locker.configurator.host_name)
            logging.info('locked %s', ap_locker.configurator.host_name)
            ap_locker.to_be_locked = False
            return True
        else:
            ap_locker.retries -= 1
            logging.info('%d retries left for %s',
                         ap_locker.retries,
                         ap_locker.configurator.host_name)
            if ap_locker.retries == 0:
                logging.info('No more retries left. Remove %s from list',
                             ap_locker.configurator.host_name)
                ap_locker.to_be_locked = False

        return False


    def get_ap_batch(self, batch_size=ap_cartridge.THREAD_MAX):
        """Allocates a batch of locked APs.

        @param batch_size: an integer, max. number of aps to lock in one batch.
                           Defaults to THREAD_MAX in ap_cartridge.py
        @return a list of APConfigurator objects, locked on AFE.
        """
        # We need this while loop to continuously loop over the for loop.
        # To exit the while loop, we either:
        #  - locked batch_size number of aps and return them
        #  - exhausted all retries on all aps in aps_to_lock
        while len(self.aps_to_lock):
            ap_batch = []

            for ap_locker in self.aps_to_lock:
                logging.info('checking %s', ap_locker.configurator.host_name)
                if self.lock_ap_in_afe(ap_locker):
                    ap_batch.append(ap_locker.configurator)
                    if len(ap_batch) == batch_size:
                        break

            # Remove locked APs from list of APs to process.
            aps_to_rm = [ap for ap in self.aps_to_lock if not ap.to_be_locked]
            self.aps_to_lock = list(set(self.aps_to_lock) - set(aps_to_rm))
            for ap in aps_to_rm:
                logging.info('Removed %s from self.aps_to_lock',
                             ap.configurator.host_name)
            logging.info('Remaining aps to lock = %s',
                         [ap.configurator.host_name for ap in self.aps_to_lock])

            # Return available APs and retry remaining ones later.
            if ap_batch:
                return ap_batch

            # Sleep before next retry.
            if self.aps_to_lock:
                seconds_to_sleep = random.randint(self.MIN_SECONDS_TO_SLEEP,
                                                  self.MAX_SECONDS_TO_SLEEP)
                logging.info('Sleep %d sec before retry', seconds_to_sleep)
                sleep(seconds_to_sleep)

        return []


    def unlock_one_ap(self, host):
        """Unlock one AP after we're done.

        @param host: a string, host name.
        """
        if not host in self._locked_aps:
            logging.error('Tried to unlock a host we have not locked?')
            return

        self.manager.unlock(hosts=[host])
        self._locked_aps.remove(host)


    def unlock_aps(self):
        """Unlock APs after we're done."""
        for host in self._locked_aps:
            self.unlock_one_ap(host)
