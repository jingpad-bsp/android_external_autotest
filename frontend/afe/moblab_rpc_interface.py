# Copyright (c) 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
This module includes all moblab-related RPCs. These RPCs can only be run
on moblab.
"""

# The boto module is only available/used in Moblab for validation of cloud
# storage access. The module is not available in the test lab environment,
# and the import error is handled.
try:
    import boto
except ImportError:
    boto = None

import ConfigParser
import logging
import os
import shutil
import socket
import re

import common

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import global_config
from autotest_lib.frontend.afe import rpc_utils
from autotest_lib.server.hosts import moblab_host

_CONFIG = global_config.global_config
MOBLAB_BOTO_LOCATION = '/home/moblab/.boto'

# Google Cloud Storage bucket url regex pattern. The pattern is used to extract
# the bucket name from the bucket URL. For example, "gs://image_bucket/google"
# should result in a bucket name "image_bucket".
GOOGLE_STORAGE_BUCKET_URL_PATTERN = re.compile(
        r'gs://(?P<bucket>[a-zA-Z][a-zA-Z0-9-_]*)/?.*')

# Contants used in Json RPC field names.
_IMAGE_STORAGE_SERVER = 'image_storage_server'
_GS_ACCESS_KEY_ID = 'gs_access_key_id'
_GS_SECRETE_ACCESS_KEY = 'gs_secret_access_key'
_RESULT_STORAGE_SERVER = 'results_storage_server'
_USE_EXISTING_BOTO_FILE = 'use_existing_boto_file'


@rpc_utils.moblab_only
def get_config_values():
    """Returns all config values parsed from global and shadow configs.

    Config values are grouped by sections, and each section is composed of
    a list of name value pairs.
    """
    sections =_CONFIG.get_sections()
    config_values = {}
    for section in sections:
        config_values[section] = _CONFIG.config.items(section)
    return rpc_utils.prepare_for_serialization(config_values)


def _write_config_file(config_file, config_values, overwrite=False):
    """Writes out a configuration file.

    @param config_file: The name of the configuration file.
    @param config_values: The ConfigParser object.
    @param ovewrite: Flag on if overwriting is allowed.
    """
    if not config_file:
        raise error.RPCException('Empty config file name.')
    if not overwrite and os.path.exists(config_file):
        raise error.RPCException('Config file already exists.')

    if config_values:
        with open(config_file, 'w') as config_file:
            config_values.write(config_file)


def _read_original_config():
    """Reads the orginal configuratino without shadow.

    @return: A configuration object, see global_config_class.
    """
    original_config = global_config.global_config_class()
    original_config.set_config_files(shadow_file='')
    return original_config


def _read_raw_config(config_file):
    """Reads the raw configuration from a configuration file.

    @param: config_file: The path of the configuration file.

    @return: A ConfigParser object.
    """
    shadow_config = ConfigParser.RawConfigParser()
    shadow_config.read(config_file)
    return shadow_config


def _get_shadow_config_from_partial_update(config_values):
    """Finds out the new shadow configuration based on a partial update.

    Since the input is only a partial config, we should not lose the config
    data inside the existing shadow config file. We also need to distinguish
    if the input config info overrides with a new value or reverts back to
    an original value.

    @param config_values: See get_moblab_settings().

    @return: The new shadow configuration as ConfigParser object.
    """
    original_config = _read_original_config()
    existing_shadow = _read_raw_config(_CONFIG.shadow_file)
    for section, config_value_list in config_values.iteritems():
        for key, value in config_value_list:
            if original_config.get_config_value(section, key,
                                                default='',
                                                allow_blank=True) != value:
                if not existing_shadow.has_section(section):
                    existing_shadow.add_section(section)
                existing_shadow.set(section, key, value)
            elif existing_shadow.has_option(section, key):
                existing_shadow.remove_option(section, key)
    return existing_shadow


def _update_partial_config(config_values):
    """Updates the shadow configuration file with a partial config udpate.

    @param config_values: See get_moblab_settings().
    """
    existing_config = _get_shadow_config_from_partial_update(config_values)
    _write_config_file(_CONFIG.shadow_file, existing_config, True)


@rpc_utils.moblab_only
def update_config_handler(config_values):
    """Update config values and override shadow config.

    @param config_values: See get_moblab_settings().
    """
    original_config = _read_original_config()
    new_shadow = ConfigParser.RawConfigParser()
    for section, config_value_list in config_values.iteritems():
        for key, value in config_value_list:
            if original_config.get_config_value(section, key,
                                                default='',
                                                allow_blank=True) != value:
                if not new_shadow.has_section(section):
                    new_shadow.add_section(section)
                new_shadow.set(section, key, value)

    if not _CONFIG.shadow_file or not os.path.exists(_CONFIG.shadow_file):
        raise error.RPCException('Shadow config file does not exist.')
    _write_config_file(_CONFIG.shadow_file, new_shadow, True)

    # TODO (sbasi) crbug.com/403916 - Remove the reboot command and
    # instead restart the services that rely on the config values.
    os.system('sudo reboot')


@rpc_utils.moblab_only
def reset_config_settings():
    """Reset moblab shadow config."""
    with open(_CONFIG.shadow_file, 'w') as config_file:
        pass
    os.system('sudo reboot')


@rpc_utils.moblab_only
def reboot_moblab():
    """Simply reboot the device."""
    os.system('sudo reboot')


@rpc_utils.moblab_only
def set_boto_key(boto_key):
    """Update the boto_key file.

    @param boto_key: File name of boto_key uploaded through handle_file_upload.
    """
    if not os.path.exists(boto_key):
        raise error.RPCException('Boto key: %s does not exist!' % boto_key)
    shutil.copyfile(boto_key, moblab_host.MOBLAB_BOTO_LOCATION)


@rpc_utils.moblab_only
def set_launch_control_key(launch_control_key):
    """Update the launch_control_key file.

    @param launch_control_key: File name of launch_control_key uploaded through
            handle_file_upload.
    """
    if not os.path.exists(launch_control_key):
        raise error.RPCException('Launch Control key: %s does not exist!' %
                                 launch_control_key)
    shutil.copyfile(launch_control_key,
                    moblab_host.MOBLAB_LAUNCH_CONTROL_KEY_LOCATION)
    # Restart the devserver service.
    os.system('sudo restart moblab-devserver-init')


###########Moblab Config Wizard RPCs #######################
def _get_public_ip_address(socket_handle):
    """Gets the public IP address.

    Connects to Google DNS server using a socket and gets the preferred IP
    address from the connection.

    @param: socket_handle: a unix socket.

    @return: public ip address as string.
    """
    try:
        socket_handle.settimeout(1)
        socket_handle.connect(('8.8.8.8', 53))
        socket_name = socket_handle.getsockname()
        if socket_name is not None:
            logging.info('Got socket name from UDP socket.')
            return socket_name[0]
        logging.warn('Created UDP socket but with no socket_name.')
    except socket.error:
        logging.warn('Could not get socket name from UDP socket.')
    return None


def _get_network_info():
    """Gets the network information.

    TCP socket is used to test the connectivity. If there is no connectivity, try to
    get the public IP with UDP socket.

    @return: a tuple as (public_ip_address, connected_to_internet).
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    ip = _get_public_ip_address(s)
    if ip is not None:
        logging.info('Established TCP connection with well known server.')
        return (ip, True)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return (_get_public_ip_address(s), False)


@rpc_utils.moblab_only
def get_network_info():
    """Returns the server ip addresses, and if the server connectivity.

    The server ip addresses as an array of strings, and the connectivity as a
    flag.
    """
    network_info = {}
    info = _get_network_info()
    if info[0] is not None:
        network_info['server_ips'] = [info[0]]
    network_info['is_connected'] = info[1]

    return rpc_utils.prepare_for_serialization(network_info)


# Gets the boto configuration.
def _get_boto_config():
    """Reads the boto configuration from the boto file.

    @return: Boto configuration as ConfigParser object.
    """
    boto_config = ConfigParser.ConfigParser()
    boto_config.read(MOBLAB_BOTO_LOCATION)
    return boto_config


@rpc_utils.moblab_only
def get_cloud_storage_info():
    """RPC handler to get the cloud storage access information.
    """
    cloud_storage_info = {}
    value =_CONFIG.get_config_value('CROS', _IMAGE_STORAGE_SERVER)
    if value is not None:
        cloud_storage_info[_IMAGE_STORAGE_SERVER] = value
    value = _CONFIG.get_config_value('CROS', _RESULT_STORAGE_SERVER,
            default=None)
    if value is not None:
        cloud_storage_info[_RESULT_STORAGE_SERVER] = value

    boto_config = _get_boto_config()
    sections = boto_config.sections()

    if sections:
        cloud_storage_info[_USE_EXISTING_BOTO_FILE] = True
    else:
        cloud_storage_info[_USE_EXISTING_BOTO_FILE] = False
    if 'Credentials' in sections:
        options = boto_config.options('Credentials')
        if _GS_ACCESS_KEY_ID in options:
            value = boto_config.get('Credentials', _GS_ACCESS_KEY_ID)
            cloud_storage_info[_GS_ACCESS_KEY_ID] = value
        if _GS_SECRETE_ACCESS_KEY in options:
            value = boto_config.get('Credentials', _GS_SECRETE_ACCESS_KEY)
            cloud_storage_info[_GS_SECRETE_ACCESS_KEY] = value

    return rpc_utils.prepare_for_serialization(cloud_storage_info)


def _get_bucket_name_from_url(bucket_url):
    """Gets the bucket name from a bucket url.

    @param: bucket_url: the bucket url string.
    """
    if bucket_url:
        match = GOOGLE_STORAGE_BUCKET_URL_PATTERN.match(bucket_url)
        if match:
            return match.group('bucket')
    return None


def _is_valid_boto_key(key_id, key_secret):
    """Checks if the boto key is valid.

    @param: key_id: The boto key id string.
    @param: key_secret: The boto key string.

    @return: A tuple as (valid_boolean, details_string).
    """
    if not key_id or not key_secret:
        return (False, "Empty key id or secret.")
    conn = boto.connect_gs(key_id, key_secret)
    try:
        buckets = conn.get_all_buckets()
        return (True, None)
    except boto.exception.GSResponseError:
        details = "The boto access key is not valid"
        return (False, details)
    finally:
        conn.close()


def _is_valid_bucket(key_id, key_secret, bucket_name):
    """Checks if a bucket is valid and accessible.

    @param: key_id: The boto key id string.
    @param: key_secret: The boto key string.
    @param: bucket name string.

    @return: A tuple as (valid_boolean, details_string).
    """
    if not key_id or not key_secret or not bucket_name:
        return (False, "Server error: invalid argument")
    conn = boto.connect_gs(key_id, key_secret)
    bucket = conn.lookup(bucket_name)
    conn.close()
    if bucket:
        return (True, None)
    return (False, "Bucket %s does not exist." % bucket_name)


def _is_valid_bucket_url(key_id, key_secret, bucket_url):
    """Validates the bucket url is accessible.

    @param: key_id: The boto key id string.
    @param: key_secret: The boto key string.
    @param: bucket url string.

    @return: A tuple as (valid_boolean, details_string).
    """
    bucket_name = _get_bucket_name_from_url(bucket_url)
    if bucket_name:
        return _is_valid_bucket(key_id, key_secret, bucket_name)
    return (False, "Bucket url %s is not valid" % bucket_url)


def _validate_cloud_storage_info(cloud_storage_info):
    """Checks if the cloud storage information is valid.

    @param: cloud_storage_info: The JSON RPC object for cloud storage info.

    @return: A tuple as (valid_boolean, details_string).
    """
    valid = True
    details = None
    if not cloud_storage_info[_USE_EXISTING_BOTO_FILE]:
        key_id = cloud_storage_info[_GS_ACCESS_KEY_ID]
        key_secret = cloud_storage_info[_GS_SECRETE_ACCESS_KEY]
        valid, details = _is_valid_boto_key(key_id, key_secret)

        if valid:
            valid, details = _is_valid_bucket_url(
                key_id, key_secret, cloud_storage_info[_IMAGE_STORAGE_SERVER])

        # allows result bucket to be empty.
        if valid and cloud_storage_info[_RESULT_STORAGE_SERVER]:
            valid, details = _is_valid_bucket_url(
                key_id, key_secret, cloud_storage_info[_RESULT_STORAGE_SERVER])
    return (valid, details)


def _create_operation_status_response(is_ok, details):
    """Helper method to create a operation status reponse.

    @param: is_ok: Boolean for if the operation is ok.
    @param: details: A detailed string.

    @return: A serialized JSON RPC object.
    """
    status_response = {'status_ok': is_ok}
    if details:
        status_response['status_details'] = details
    return rpc_utils.prepare_for_serialization(status_response)


@rpc_utils.moblab_only
def validate_cloud_storage_info(cloud_storage_info):
    """RPC handler to check if the cloud storage info is valid.

    @param cloud_storage_info: The JSON RPC object for cloud storage info.
    """
    valid, details = _validate_cloud_storage_info(cloud_storage_info)
    return _create_operation_status_response(valid, details)


@rpc_utils.moblab_only
def submit_wizard_config_info(cloud_storage_info):
    """RPC handler to submit the cloud storage info.

    @param cloud_storage_info: The JSON RPC object for cloud storage info.
    """
    valid, details = _validate_cloud_storage_info(cloud_storage_info)
    if not valid:
        return _create_operation_status_response(valid, details)
    config_update = {}
    config_update['CROS'] = [
        (_IMAGE_STORAGE_SERVER, cloud_storage_info[_IMAGE_STORAGE_SERVER]),
        (_RESULT_STORAGE_SERVER, cloud_storage_info[_RESULT_STORAGE_SERVER])
    ]
    _update_partial_config(config_update)

    if not cloud_storage_info[_USE_EXISTING_BOTO_FILE]:
        boto_config = ConfigParser.RawConfigParser()
        boto_config.add_section('Credentials')
        boto_config.set('Credentials', _GS_ACCESS_KEY_ID,
                        cloud_storage_info[_GS_ACCESS_KEY_ID])
        boto_config.set('Credentials', _GS_SECRETE_ACCESS_KEY,
                        cloud_storage_info[_GS_SECRETE_ACCESS_KEY])
        _write_config_file(MOBLAB_BOTO_LOCATION, boto_config, True)

    _CONFIG.parse_config_file()
    services = ['moblab-devserver-init', 'moblab-apache-init',
    'moblab-devserver-cleanup-init', ' moblab-gsoffloader_s-init',
    'moblab-base-container-init', 'moblab-scheduler-init', 'moblab-gsoffloader-init']
    cmd = ';/sbin/restart '.join(services)
    os.system(cmd)

    return _create_operation_status_response(True, None)


@rpc_utils.moblab_only
def get_version_info():
    """ RPC handler to get informaiton about the version of the moblab.
    @return: A serialized JSON RPC object.
    """
    lines = open('/etc/lsb-release').readlines()
    lines.remove('')
    version_response = {x.split('=')[0]: x.split('=')[1] for x in lines}
    return rpc_utils.prepare_for_serialization(version_response)

