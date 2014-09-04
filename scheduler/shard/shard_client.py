#!/usr/bin/python
#pylint: disable-msg=C0111

# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import datetime
import logging
import os
import signal
import time

import common
from autotest_lib.frontend import setup_django_environment
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import global_config
from autotest_lib.client.common_lib import logging_manager
from autotest_lib.frontend.afe import models, rpc_utils
from autotest_lib.scheduler import email_manager
from autotest_lib.server import frontend
from autotest_lib.shard import shard_logging_config



"""
Autotest shard client

The shard client can be run as standalone service. It periodically polls the
master in a heartbeat, retrieves new jobs and hosts and inserts them into the
local database.

A shard is set up (by a human) and pointed to the global AFE (cautotest).
On the shard, this script periodically makes so called heartbeat requests to the
global AFE, which will then complete the following actions:

1. Find the previously created (with atest) record for the shard. Shards are
   identified by their hostnames, specified in the shadow_config.
2. Take the records that were sent in the heartbeat and insert them into the
   global database.
   - This is to set the status of jobs to completed in the master database after
     they were run by a slave. This is necessary so one can just look at the
     master's afe to see the statuses of all jobs. Otherwise one would have to
     check the tko tables or the individual slave AFEs.
3. Find labels that have been assigned to this shard.
4. Assign hosts
   - All hosts that have the specified label and aren't leased will be assigned
5. Assign jobs, that:
   - depend on the specified label
   - haven't been assigned before
   - aren't started yet
   - aren't completed yet
6. Serialize the chosen jobs and hosts:
   - Find objects that the Host/Job objects depend on: Labels, AclGroups, Users,
     and many more. Details about this can be found around
     model_logic.serialize()
7. Send these objects to the slave.


On the client side, this will happen:
1. Deserialize the objects sent from the master and persist them to the local
   database.
2. monitor_db on the shard will pick up these jobs and schedule them on the
   available hosts (which were retrieved from a heartbeat).
3. Once a job is finished, it's shard_id is set to NULL
4. The shard_client will pick up all jobs where shard_id=NULL and will
   send them to the master in the request of the next heartbeat.
   - The master will persist them as described earlier.
   - the shard_id will be set back to the shard's id, so the record won't be
     uploaded again.
"""


HEARTBEAT_AFE_ENDPOINT = 'shard_heartbeat'


class ShardClient(object):
    """Performs client side tasks of sharding, i.e. the heartbeat.

    This class contains the to do periodic heartbeats to a global AFE,
    to retrieve new jobs from it and to report completed jobs back.
    """

    def __init__(self, global_afe_hostname, shard_hostname, tick_pause_sec):
        self.afe = frontend.AFE(server=global_afe_hostname)
        self.hostname = shard_hostname
        self.tick_pause_sec = tick_pause_sec
        self._shutdown = False


    def process_heartbeat_response(self, heartbeat_response):
        """Save objects returned by a heartbeat to the local database.

        This deseralizes hosts and jobs including their dependencies and saves
        them to the local database.

        @param heartbeat_response: A dictionary with keys 'hosts' and 'jobs',
                                   as returned by the `shard_heartbeat` rpc
                                   call.
        """
        hosts_serialized = heartbeat_response['hosts']
        jobs_serialized = heartbeat_response['jobs']

        # Persisting is automatically done inside deserialize
        for host in hosts_serialized:
            models.Host.deserialize(host)
        for job in jobs_serialized:
            models.Job.deserialize(job)


    def do_heartbeat(self):
        """Perform a heartbeat: Retreive new jobs.

        This function executes a `shard_heartbeat` RPC. It retrieves the
        response of this call and processes the response by storing the returned
        objects in the local database.
        """
        logging.info("Performing heartbeat.")
        response = self.afe.run(HEARTBEAT_AFE_ENDPOINT,
                                shard_hostname=self.hostname)
        self.process_heartbeat_response(response)
        logging.info("Heartbeat completed.")


    def tick(self):
        """Performs all tasks the shard clients needs to do periodically."""
        self.do_heartbeat()


    def loop(self):
        """Calls tick() until shutdown() is called."""
        while not self._shutdown:
            self.tick()
            time.sleep(self.tick_pause_sec)


    def shutdown(self):
        """Stops the shard client after the current tick."""
        logging.info("Shutdown request received.")
        self._shutdown = True


def handle_signal(signum, frame):
    """Sigint handler so we don't crash mid-tick."""
    global handle_signal
    _heartbeat_client.shutdown()


def _ensure_running_on_shard():
    """Raises an exception if run from elsewhere than a shard.

    @raises error.HeartbeatOnlyAllowedInShardModeException if run from
            elsewhere than from a shard.
    """
    is_shard = global_config.global_config.get_config_value(
            'SHARD', 'is_slave_shard', type=bool)

    if not is_shard:
        raise error.HeartbeatOnlyAllowedInShardModeException(
            'To run the shard client, is_slave_shard must be set to True')


def _get_global_afe_hostname():
    """Read the hostname of the global AFE from the global configuration."""
    return global_config.global_config.get_config_value(
            'SHARD', 'global_afe_hostname')


def _get_my_shard_hostname():
    """Read the hostname the local shard from the global configuration."""
    return global_config.global_config.get_config_value(
        'SHARD', 'shard_hostname')


def _get_tick_pause_sec():
    """Read pause to make between two ticks from the global configuration."""
    return global_config.global_config.get_config_value(
        'SHARD', 'heartbeat_pause_sec', type=float)


def get_shard_client():
    """Instantiate a shard client instance.

    Configuration values will be read from the global configuration.

    @returns A shard client instance.
    """
    _ensure_running_on_shard()

    global_afe_hostname = _get_global_afe_hostname()
    shard_hostname = _get_my_shard_hostname()
    tick_pause_sec = _get_tick_pause_sec()
    return ShardClient(global_afe_hostname, shard_hostname, tick_pause_sec)


def main():
    try:
        main_without_exception_handling()
    except Exception as e:
        message = 'Uncaught exception; terminating shard_client.'
        email_manager.manager.log_stacktrace(message)
        logging.exception(message)
        raise
    finally:
        email_manager.manager.send_queued_emails()


def main_without_exception_handling():
    parser = argparse.ArgumentParser(description='Shard client.')
    options = parser.parse_args()

    logging_manager.configure_logging(
        shard_logging_config.ShardLoggingConfig())

    logging.info("Setting signal handler.")
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    logging.info("Starting shard client.")
    global _heartbeat_client
    _heartbeat_client = get_shard_client()
    _heartbeat_client.loop()


if __name__ == '__main__':
    main()
