# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


from autotest_lib.client.common_lib import global_config
from autotest_lib.client.common_lib.cros import dev_server


_CONFIG = global_config.global_config


def image_url_pattern():
    return _CONFIG.get_config_value('CROS', 'image_url_pattern', type=str)


def sharding_factor():
    return _CONFIG.get_config_value('CROS', 'sharding_factor', type=int)


def infrastructure_user_list():
    return _CONFIG.get_config_value('CROS', 'infrastructure_users', type=list,
                                    default=[])


def package_url_pattern():
    return _CONFIG.get_config_value('CROS', 'package_url_pattern', type=str)


def get_package_url(devserver_url, build):
    """Returns the package url from the |devserver_url| and |build|.

    @param devserver_url: a string specifying the host to contact e.g.
        http://my_host:9090.
    @param build: the build/image string to use e.g. mario-release/R19-123.0.1.
    @return the url where you can find the packages for the build.
    """
    return package_url_pattern() % (devserver_url, build)


def inject_vars(vars, control_file_in):
    """
    Inject the contents of |vars| into |control_file_in|.

    @param vars: a dict to shoehorn into the provided control file string.
    @param control_file_in: the contents of a control file to munge.
    @return the modified control file string.
    """
    control_file = ''
    for key, value in vars.iteritems():
        # None gets injected as 'None' without this check; same for digits.
        if isinstance(value, str):
            control_file += "%s='%s'\n" % (key, value)
        else:
            control_file += "%s=%r\n" % (key, value)
    return control_file + control_file_in
