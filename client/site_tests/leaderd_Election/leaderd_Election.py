# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import random
import uuid

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros.tendo import n_faced_peerd_helper
from autotest_lib.client.common_lib.cros.tendo import webserver_config
from autotest_lib.client.cros.tendo import leaderd_helper


NUM_INSTANCES = 5
HANDLER_PORT_BASE = 8080
POLLING_PERIOD_SECONDS = 0.8

class leaderd_Election(test.test):
    """Test that a group of leaderd instances elects a leader."""
    version = 1


    def run_once(self):
        self._objects_to_close = []
        # Start up N fake instances of peerd
        self._n_faced_peerd = n_faced_peerd_helper.NFacedPeerdHelper(
                NUM_INSTANCES)
        self._objects_to_close.append(self._n_faced_peerd)
        self._n_faced_peerd.start()

        # Set up N protocol handlers on different ports
        protocol_handlers = webserver_config.get_n_protocol_handlers(
                NUM_INSTANCES,
                HANDLER_PORT_BASE)
        webserver = webserver_config.WebserverConfig(
                extra_protocol_handlers=protocol_handlers)
        self._objects_to_close.append(webserver)
        webserver.restart_with_config()

        # Start N instances of leaderd and join a group on each.
        group_uuid = uuid.uuid4()
        leaderd = leaderd_helper.LeaderdHelper()
        group_paths = dict()  # Maps from instance number to group path.
        for i in range(NUM_INSTANCES):
            leaderd_instance = leaderd.start_instance(
                    leaderd_helper.get_nth_service_name(i),
                    n_faced_peerd_helper.get_nth_service_name(i),
                    protocol_handlers[i].name)
            self._objects_to_close.append(leaderd_instance)
            group_paths[i] = leaderd.join_group(group_uuid, instance_number=i)

        # Confirm that all instances of leaderd know about all other instances.
        expected_peer_ids = sorted([self._n_faced_peerd.get_face_identifier(n)
                                    for n in range(NUM_INSTANCES)])
        everyone_sees_each_other = leaderd.confirm_instances_see_each_other(
                group_paths, expected_peer_ids)
        if not everyone_sees_each_other:
            raise error.TestFail('Timed out waiting for all leaderd instances '
                                 'to detect all other instances.')

        # Increase the score of a leader instance.
        leader_instance = int(random.random() * NUM_INSTANCES)
        logging.info('Leader instance for this run is %d', leader_instance)
        leaderd.set_score(group_paths[leader_instance], 100,
                          instance_number=leader_instance)
        expected_leader_id = self._n_faced_peerd.get_face_identifier(
                leader_instance)

        # Confirm that everyone agrees our chosen instance is the leader.
        everyone_agrees_on_leader = leaderd.confirm_instances_follow_leader(
                group_paths, expected_leader_id)
        if not everyone_agrees_on_leader:
            raise error.TestFail(
                    'Expected instance of leaderd did not become leader.')


    def cleanup(self):
        for object_to_close in self._objects_to_close:
            if object_to_close is not None:
                object_to_close.close()
