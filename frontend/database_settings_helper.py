#pylint: disable-msg=C0111

# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Helpers to load database settings.

Three databases are used with django (a default and one for tko tables,
which always must be the global database, plus a readonly connection to the
global database).

In order to save configuration overhead, settings that aren't set for the
desired database type, should be obtained from the setting with the next lower
priority. The order is:
readonly -> global -> local.
I.e. this means if `readonly_host` is not set, `global_db_host` will be used. If
that is also not set, `host` (the local one) will be used.

In case an instance is running on a shard, a global database must explicitly
be set. Instead of failing over from global to local, an exception will be
raised in that case.

The complexity to do this, is combined in this file.
"""


# Don't import anything that needs django here: Django may not be configured
# on the builders, and this is also used by tko/db.py so failures like this
# may occur: http://crbug.com/421565
import common
from autotest_lib.client.common_lib import global_config

config = global_config.global_config
SHARD_HOSTNAME = config.get_config_value('SHARD', 'shard_hostname',
                                         default=None)


def _get_config(config_key, **kwargs):
    """Retrieves a config value for the specified key.

    @param config_key: The string key associated with the desired config value.
    @param **kwargs: Additional arguments to be passed to
                     global_config.get_config_value.

    @return: The config value, as returned by
             global_config.global_config.get_config_value().
    """
    return config.get_config_value('AUTOTEST_WEB', config_key, **kwargs)


def _get_global_config(config_key, default=config._NO_DEFAULT_SPECIFIED, **kwargs):
    """Retrieves a global config value for the specified key.

    If the value can't be found, this will happen:
    - if no default value was specified, and this is run on a shard instance,
      a ConfigError will be raised.
    - if a default value is set or this is run on a non-shard instancee, the
      non-global value is returned

    @param config_key: The string key associated with the desired config value.
    @param default: The default value to return if the value couldn't be looked
                    up; neither with global_db_ nor no prefix.
    @param **kwargs: Additional arguments to be passed to
                     global_config.get_config_value.

    @return: The config value, as returned by
             global_config.global_config.get_config_value().
    """
    try:
        return _get_config('global_db_' + config_key, **kwargs)
    except global_config.ConfigError:
        if SHARD_HOSTNAME and default == config._NO_DEFAULT_SPECIFIED:
            # When running on a shard, fail loudly if the global_db_ prefixed
            # settings aren't present.
            raise
        return _get_config(config_key, default=default, **kwargs)


def _get_readonly_config(config_key, default=config._NO_DEFAULT_SPECIFIED,
                         **kwargs):
    """Retrieves a readonly config value for the specified key.

    If no value can be found, the value of non readonly but global value
    is returned instead.

    @param config_key: The string key associated with the desired config value.
    @param default: The default value to return if the value couldn't be looked
                    up; neither with readonly_, global_db_ nor no prefix.
    @param **kwargs: Additional arguments to be passed to
                     global_config.get_config_value.

    @return: The config value, as returned by
             global_config.global_config.get_config_value().
    """
    try:
        return _get_config('readonly_' + config_key, **kwargs)
    except global_config.ConfigError:
        return _get_global_config(config_key, default=default, **kwargs)


def _get_database_config(getter):
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
        'HOST': getter('host'),
        'NAME': getter('database'),
        'USER': getter('user'),
        'PASSWORD': getter('password', default=''),
        'READONLY_HOST': getter('readonly_host', default=getter('host')),
        'READONLY_USER': getter('readonly_user', default=getter('user')),
    }
    if config['READONLY_USER'] != config['USER']:
        config['READONLY_PASSWORD'] = getter('readonly_password', default='')
    else:
        config['READONLY_PASSWORD'] = config['PASSWORD']
    return config


def get_global_db_config():
    """Returns settings for the global database as required by django.

    @return: A dictionary that can be used in the Django DATABASES setting.
    """
    return _get_database_config(getter=_get_global_config)


def get_default_db_config():
    """Returns settings for the default/local database as required by django.

    @return: A dictionary that can be used in the Django DATABASES setting.
    """
    return _get_database_config(getter=_get_config)


def get_readonly_db_config():
    """Returns settings for the readonly database as required by django.

    @return: A dictionary that can be used in the Django DATABASES setting.
    """
    return _get_database_config(getter=_get_readonly_config)
