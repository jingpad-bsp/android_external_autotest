# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from time import sleep

from autotest_lib.server.cros.chaos_ap_configurators import ap_cartridge
from autotest_lib.server.cros.chaos_ap_configurators import \
    ap_configurator_factory
from autotest_lib.server.cros.dynamic_suite import host_lock_manager


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


    SECONDS_TO_SLEEP = 30


    def __init__(self, ap_spec, retries=MAX_RETRIES):
        """Initialize.

        @param ap_spec: a dict of strings, AP attributes.
        @param retries: an integer, max number of retry attempts to lock ap.
                        Defaults to MAX_RETRIES.
        """
        self.aps_to_lock = construct_ap_lockers(ap_spec, retries)
        self.manager = host_lock_manager.HostLockManager()


    def has_more_aps(self):
        """@return True iff there is at least one AP to be locked."""
        return len(self.aps_to_lock) > 0


    def lock_ap_in_afe(self, ap_locker):
        """Locks an AP host in AFE.

        @param ap_locker: an ApLocker object, AP to be locked.
        @return a boolean, True iff ap_locker is locked.
        """
        try:
            self.manager.add([ap_locker.configurator.host_name])
            self.manager.lock()
            logging.info('locked %s and removed it from list',
                         ap_locker.configurator.host_name)
            self.aps_to_lock.remove(ap_locker)
            ap_locker.to_be_locked = False
            return True
        # Catching a wide exception b/c frontend.AFE.run() throws Exception
        except Exception as e:
            ap_locker.retries -= 1
            logging.info('%d retries left for %s',
                         ap_locker.retries,
                         ap_locker.configurator.host_name)
            if ap_locker.retries == 0:
                logging.info('No more retries left. Remove %s from list',
                             ap_locker.configurator.host_name)
                self.aps_to_lock.remove(ap_locker)
            # FIXME(tgao): check error msg and remove unlockable aps sooner?
            #              e.g., an AP not registered w/ AFE.
        return False


    # TODO(tgao): have the batch locker running in its own thread just adding
    # to the batch list and then the test can pop them off as it uses them.
    def get_ap_batch(self, batch_size=ap_cartridge.THREAD_MAX):
        """Allocates a batch of locked APs.

        @param batch_size: an integer, max. number of aps to lock in one batch.
                           Defaults to THREAD_MAX in ap_cartridge.py
        @return a list of APConfigurator objects, locked on AFE.
        """
        ap_batch = []
        # We need this while loop to continuously loop over the for loop.
        # To exit the while loop, we either:
        #  - locked batch_size number of aps and return them
        #  - exhausted all retries on all aps in aps_to_lock
        while len(self.aps_to_lock) > 0:
            for ap_locker in self.aps_to_lock:
                logging.debug('checking %s', ap_locker.configurator.host_name)
                if ap_locker.to_be_locked:
                    if self.lock_ap_in_afe(ap_locker):
                        ap_batch.append(ap_locker.configurator)
                        if len(ap_batch) == batch_size:
                            return ap_batch
                    # Unable to lock ap, sleep before moving on to next ap.
                    else:
                      logging.info('Sleep %d sec before retry',
                                   self.SECONDS_TO_SLEEP)
                      sleep(self.SECONDS_TO_SLEEP)
        if ap_batch:
            logging.info('partial batch with %d ap', len(ap_batch))
        return ap_batch


class ApBatchLockerManager(object):
    """Context manager to make sure that 'ApBatchLocker' shuts down properly.

    @attribute ap_spec: a dict of strings, AP attributes.
    @attributes _batch_locker: a ApBatchLocker object.
    @attributes _hosts_locked_by: a HostLockedBy object.
    """


    def __init__(self, ap_spec):
        """Initialize.

        @param ap_spec: a dict of strings, attributes of desired APs.
                See docstring of get_ap_configurators() in
                ap_configurator_factory.py.
        @param capturer: a PacketCaptureManager object, packet tracer.
        """
        self.ap_spec = ap_spec
        self._batch_locker = None
        self._hosts_locked_by = None


    # TODO(milleral): This code needs to be cleaned up once the host locking
    # code is made more usable (see crosbug.com/36072).

    def __enter__(self):
        self._batch_locker = ApBatchLocker(self.ap_spec)
        self._hosts_locked_by = host_lock_manager.HostsLockedBy(
            self._batch_locker.manager)
        self._hosts_locked_by.__enter__()
        return self._batch_locker


    def __exit__(self, exit_type, exit_value, exit_traceback):
        if self._hosts_locked_by:
            self._hosts_locked_by.__exit__(exit_type, exit_value,
                                           exit_traceback)
