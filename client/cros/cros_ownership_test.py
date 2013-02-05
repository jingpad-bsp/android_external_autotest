# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus, sys

import common, cros_ui, login, ownership
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error


class OwnershipTest(test.test):
    """Base class for tests that test device ownership and policies.

    If your subclass overrides the initialize() or cleanup() methods, it
    should make sure to invoke this class' version of those methods as well.
    The standard super(...) function cannot be used for this, since the base
    test class is not a 'new style' Python class.
    """
    version = 1

    _testuser = 'ownership_test@chromium.org'
    _testpass = 'testme'

    def initialize(self):
        # Start with a clean slate wrt ownership
        cros_ui.stop()
        ownership.clear_ownership()
        cros_ui.start()
        super(OwnershipTest, self).initialize()


    def connect_to_session_manager(self):
        """Create and return a DBus connection to session_manager.

        Connects to the session manager over the DBus system bus.  Returns
        appropriately configured DBus interface object.
        """
        return ownership.connect_to_session_manager()


    def compare_policy_response(self, policy_response,
                                owner=None, guests=None, new_users=None,
                                roaming=None, whitelist=None, proxies=None):
        """Check the contents of |policy_response| against given args.

        Deserializes |policy_response| into a PolicyFetchResponse protobuf,
        with an embedded (serialized) PolicyData protobuf that embeds a
        (serialized) ChromeDeviceSettingsProto, and checks to see if this
        protobuf turducken contains the information passed in.

        @param policy_response: string serialization of a PolicyData protobuf.
        @param owner: string representing the owner's name/account.
        @param guests: boolean indicating whether guests should be allowed.
        @param new_users: boolean indicating if user pods are on login screen.
        @param roaming: boolean indicating whether data roaming is enabled.
        @param whitelist: list of accounts that are allowed to log in.
        @param proxies: dictionary - { 'proxy_mode': <string> }

        @return True if |policy_response| has all the provided data, else False.
        """
        # Pull in protobuf definitions.
        sys.path.append(self.srcdir)
        from device_management_backend_pb2 import PolicyFetchResponse
        from device_management_backend_pb2 import PolicyData
        from chrome_device_policy_pb2 import ChromeDeviceSettingsProto
        from chrome_device_policy_pb2 import AllowNewUsersProto
        from chrome_device_policy_pb2 import GuestModeEnabledProto
        from chrome_device_policy_pb2 import ShowUserNamesOnSigninProto
        from chrome_device_policy_pb2 import DataRoamingEnabledProto
        from chrome_device_policy_pb2 import DeviceProxySettingsProto

        response_proto = PolicyFetchResponse()
        response_proto.ParseFromString(policy_response)
        ownership.assert_has_policy_data(response_proto)

        data_proto = PolicyData()
        data_proto.ParseFromString(response_proto.policy_data)
        ownership.assert_has_device_settings(data_proto)
        if owner != None: ownership.assert_username(data_proto, owner)

        settings = ChromeDeviceSettingsProto()
        settings.ParseFromString(data_proto.policy_value)
        if guests != None: ownership.assert_guest_setting(settings, guests)
        if new_users != None: ownership.assert_show_users(settings, new_users)
        if roaming != None: ownership.assert_roaming(settings, roaming)
        if whitelist:
            ownership.assert_new_users(settings, False)
            ownership.assert_users_on_whitelist(settings, whitelist)
        if proxies != None: ownership.assert_proxy_settings(settings, proxies)


    def build_policy_data(self, owner=None, guests=None, new_users=None,
                          roaming=None, whitelist=None, proxies=None):
        """Generate and serialize a populated device policy protobuffer.

        Creates a PolicyData protobuf, with an embedded
        ChromeDeviceSettingsProto, containing the information passed in.

        @param owner: string representing the owner's name/account.
        @param guests: boolean indicating whether guests should be allowed.
        @param new_users: boolean indicating if user pods are on login screen.
        @param roaming: boolean indicating whether data roaming is enabled.
        @param whitelist: list of accounts that are allowed to log in.
        @param proxies: dictionary - { 'proxy_mode': <string> }

        @return serialization of the PolicyData proto that we build.
        """
        # Pull in protobuf definitions.
        sys.path.append(self.srcdir)
        from device_management_backend_pb2 import PolicyData
        from chrome_device_policy_pb2 import ChromeDeviceSettingsProto
        from chrome_device_policy_pb2 import AllowNewUsersProto
        from chrome_device_policy_pb2 import GuestModeEnabledProto
        from chrome_device_policy_pb2 import ShowUserNamesOnSigninProto
        from chrome_device_policy_pb2 import DataRoamingEnabledProto
        from chrome_device_policy_pb2 import DeviceProxySettingsProto

        data_proto = PolicyData()
        data_proto.policy_type = ownership.POLICY_TYPE
        if owner != None: data_proto.username = owner

        settings = ChromeDeviceSettingsProto()
        if guests != None:
            settings.guest_mode_enabled.guest_mode_enabled = guests
        if new_users != None:
            settings.show_user_names.show_user_names = new_users
        if roaming != None:
            settings.data_roaming_enabled.data_roaming_enabled = roaming
        if whitelist:
            settings.allow_new_users.allow_new_users = False
            for user in whitelist:
                settings.user_whitelist.user_whitelist.append(user)
        if proxies != None:
            settings.device_proxy_settings.proxy_mode = proxies['proxy_mode']

        data_proto.policy_value = settings.SerializeToString()
        return data_proto.SerializeToString()


    def generate_policy(self, key, pubkey, policy, old_key=None):
        """Generate and serialize a populated, signed device policy protobuffer.

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


    def get_policy(self, sm):
        return sm.RetrievePolicy(byte_arrays=True)


    def cleanup(self):
        login.wait_for_browser()  # Ensure login manager is there before nuking.
        cros_ui.nuke()
        super(OwnershipTest, self).cleanup()
