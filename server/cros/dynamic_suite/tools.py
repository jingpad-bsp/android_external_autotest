# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import random
import re

from autotest_lib.client.common_lib import global_config


_CONFIG = global_config.global_config


def image_url_pattern():
    """Returns image_url_pattern from global_config."""
    return _CONFIG.get_config_value('CROS', 'image_url_pattern', type=str)


def firmware_url_pattern():
    """Returns firmware_url_pattern from global_config."""
    return _CONFIG.get_config_value('CROS', 'firmware_url_pattern', type=str)


def sharding_factor():
    """Returns sharding_factor from global_config."""
    return _CONFIG.get_config_value('CROS', 'sharding_factor', type=int)


def infrastructure_user():
    """Returns infrastructure_user from global_config."""
    return _CONFIG.get_config_value('CROS', 'infrastructure_user', type=str)


def package_url_pattern():
    """Returns package_url_pattern from global_config."""
    return _CONFIG.get_config_value('CROS', 'package_url_pattern', type=str)


def try_job_timeout_mins():
    """Returns try_job_timeout_mins from global_config."""
    return _CONFIG.get_config_value('SCHEDULER', 'try_job_timeout_mins',
                                    type=int, default=4*60)


def get_package_url(devserver_url, build):
    """Returns the package url from the |devserver_url| and |build|.

    @param devserver_url: a string specifying the host to contact e.g.
        http://my_host:9090.
    @param build: the build/image string to use e.g. mario-release/R19-123.0.1.
    @return the url where you can find the packages for the build.
    """
    return package_url_pattern() % (devserver_url, build)


def get_devserver_build_from_package_url(package_url):
    """The inverse method of get_package_url.

    @param package_url: a string specifying the package url.

    @return tuple containing the devserver_url, build.
    """
    pattern = package_url_pattern()
    re_pattern = pattern.replace('%s', '(\S+)')

    devserver_build_tuple = re.search(re_pattern, package_url).groups()

    # TODO(beeps): This is a temporary hack around the fact that all
    # job_repo_urls in the database currently contain 'archive'. Remove
    # when all hosts have been reimaged at least once. Ref: crbug.com/214373.
    return (devserver_build_tuple[0],
            devserver_build_tuple[1].replace('archive/', ''))


def get_random_best_host(afe, host_list, require_usable_hosts=True):
    """
    Randomly choose the 'best' host from host_list, using fresh status.

    Hit the AFE to get latest status for the listed hosts.  Then apply
    the following heuristic to pick the 'best' set:

    Remove unusable hosts (not tools.is_usable()), then
    'Ready' > 'Running, Cleaning, Verifying, etc'

    If any 'Ready' hosts exist, return a random choice.  If not, randomly
    choose from the next tier.  If there are none of those either, None.

    @param afe: autotest front end that holds the hosts being managed.
    @param host_list: an iterable of Host objects, per server/frontend.py
    @param require_usable_hosts: only return hosts currently in a usable
                                 state.
    @return a Host object, or None if no appropriate host is found.
    """
    if not host_list:
        return None
    hostnames = [host.hostname for host in host_list]
    updated_hosts = afe.get_hosts(hostnames=hostnames)
    usable_hosts = [host for host in updated_hosts if is_usable(host)]
    ready_hosts = [host for host in usable_hosts if host.status == 'Ready']
    unusable_hosts = [h for h in updated_hosts if not is_usable(h)]
    if ready_hosts:
        return random.choice(ready_hosts)
    if usable_hosts:
        return random.choice(usable_hosts)
    if not require_usable_hosts and unusable_hosts:
        return random.choice(unusable_hosts)
    return None


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


def is_usable(host):
    """
    Given a host, determine if the host is usable right now.

    @param host: Host instance (as in server/frontend.py)
    @return True if host is alive and not incorrectly locked.  Else, False.
    """
    return alive(host) and not incorrectly_locked(host)


def alive(host):
    """
    Given a host, determine if the host is alive.

    @param host: Host instance (as in server/frontend.py)
    @return True if host is not under, or in need of, repair.  Else, False.
    """
    return host.status not in ['Repair Failed', 'Repairing']


def incorrectly_locked(host):
    """
    Given a host, determine if the host is locked by some user.

    If the host is unlocked, or locked by the test infrastructure,
    this will return False.  There is only one system user defined as part
    of the test infrastructure and is listed in global_config.ini under the
    [CROS] section in the 'infrastructure_user' field.

    @param host: Host instance (as in server/frontend.py)
    @return False if the host is not locked, or locked by the infra.
            True if the host is locked by the infra user.
    """
    return (host.locked and host.locked_by != infrastructure_user())
