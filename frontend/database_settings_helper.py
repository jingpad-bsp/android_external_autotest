#pylint: disable-msg=C0111

# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Helpers to load database settings.

Two databases are used with django (a default and one for tko tables,
which always must be the global database).

In case an instance is not running on a shard, those two databases will be the
same. To avoid configuration overhead, only one database should be needed in
the configuration file.

If this instance is running on a shard though, it should be ensured a second
database is explicitly configured. If this is not the case, this should fail
loudly.

The complexity to do this, is combined in this file.
"""


# Don't import anything that needs django here: Django may not be configured
# on the builders, and this is also used by tko/db.py so failures like this
# may occur: http://crbug.com/421565
import common
from autotest_lib.client.common_lib import global_config

c = global_config.global_config
SHARD_HOSTNAME = c.get_config_value('SHARD', 'shard_hostname', default=None)
_section = 'AUTOTEST_WEB'


def _get_config(config_key, prefix='',
                default=global_config.global_config._NO_DEFAULT_SPECIFIED,
                type=str):
    """Retrieves a global config value for the specified key.

    @param config_key: The string key associated with the desired config value.
    @param prefix: If existing, the value with the key prefix + config_key
                   will be returned. If it doesn't exist, the normal key
                   is used for the lookup.
    @param default: The default value to return if the value couldn't be looked
                    up; neither for prefix + config_key nor config_key.
    @param type: Expected type of the return value.

    @return: The config value, as returned by
             global_config.global_config.get_config_value().
    """

    # When running on a shard, fail loudly if the global_db_ prefixed settings
    # aren't present.
    if SHARD_HOSTNAME:
        return c.get_config_value(_section, prefix + config_key,
                                  default=default, type=type)

    return c.get_config_value_with_fallback(_section, prefix + config_key,
                                            config_key, default=default,
                                            type=type)


def get_database_config(config_prefix=''):
    """Create a configuration dictionary that can be passed to Django.

    @param config_prefix: If specified, this function will try to prefix lookup
                          keys from global_config with this. If those values
                          don't exist, the normal key without the prefix will
                          be used.

    @return A dictionary that can be used in the Django DATABASES setting.
    """
    config = {
        'ENGINE': 'autotest_lib.frontend.db.backends.afe',
        'PORT': '',
        'HOST': _get_config("host", config_prefix),
        'NAME': _get_config("database", config_prefix),
        'USER': _get_config("user", config_prefix),
        'PASSWORD': _get_config("password", config_prefix, default=''),
        'READONLY_HOST': _get_config(
                "readonly_host", config_prefix,
                default=_get_config("host", config_prefix)),
        'READONLY_USER': _get_config(
                "readonly_user", config_prefix,
                default=_get_config("user", config_prefix)),
    }
    if config['READONLY_USER'] != config['USER']:
        config['READONLY_PASSWORD'] = _get_config(
                'readonly_password', config_prefix, default='')
    else:
        config['READONLY_PASSWORD'] = config['PASSWORD']
    return config
