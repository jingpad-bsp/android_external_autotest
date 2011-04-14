# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import logging
import sys
import common
import constants
import login
import ownership

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error


class OwnershipTest(test.test):
    """Base class for tests that test device ownership and policies.

    If your subclass overrides the initialize() or cleanup() methods, it
    should make sure to invoke this class' version of those methods as well.
    The standard super(...) function cannot be used for this, since the base
    test class is not a 'new style' Python class.
    """
    version = 1

    def initialize(self):
        ownership.clear_ownership()
        login.refresh_login_screen()
        super(OwnershipTest, self).initialize()


    def connect_to_session_manager(self):
        """Create and return a DBus connection to session_manager.

        Connects to the session manager over the DBus system bus.  Returns
        appropriately configured DBus interface object.
        """
        return ownership.connect_to_session_manager()


    def generate_policy(self, key, pubkey, policy, old_key=None):
        """Generate and serialize a populated device policy protobuffer.

        Creates a protobuf containing the device policy |policy|, signed with
        |key|.  Also includes the public key |pubkey|, signed with |old_key|
        if provided.  If not, |pubkey| is signed with |key|.  The protobuf
        is serialized to a string and returned.
        """
        # Pull in protobuf definitions.
        sys.path.append(self.srcdir)
        from device_management_backend_pb2 import PolicyFetchResponse

        if old_key == None:
            old_key = key
        policy_proto = PolicyFetchResponse()
        policy_proto.policy_data = policy
        policy_proto.policy_data_signature = ownership.sign(key, policy)
        policy_proto.new_public_key = pubkey
        policy_proto.new_public_key_signature = ownership.sign(old_key, pubkey)
        return policy_proto.SerializeToString()


    def push_policy(self, policy_string, sm):
        """Push a device policy to the session manager over DBus.

        The serialized device policy |policy_string| is sent to the session
        manager with the StorePolicy DBus call.  Success of the store is
        validated by fetching the policy again and comparing.
        """
        sm.StorePolicy(dbus.ByteArray(policy_string), byte_arrays=True)
        login.wait_for_ownership()

        retrieved_policy = sm.RetrievePolicy(byte_arrays=True)
        if retrieved_policy != policy_string:
            raise error.TestFail('Policy should not be %s' % retrieved_policy)


    def cleanup(self):
        login.nuke_login_manager()
        super(OwnershipTest, self).cleanup()
