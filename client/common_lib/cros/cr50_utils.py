# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import re

from autotest_lib.client.common_lib import error


RO = 'ro'
RW = 'rw'
CR50_FILE = '/opt/google/cr50/firmware/cr50.bin.prod'
CR50_STATE = '/var/cache/cr50*'
GET_CR50_VERSION = 'cat /var/cache/cr50-version'
GET_CR50_MESSAGES ='grep "cr50-.*\[" /var/log/messages'
UPDATE_FAILURE = 'unexpected cr50-update exit code'
DUMMY_VER = '-1.-1.-1'
# This dictionary is used to search the usb_updater output for the version
# strings. There are two usb_updater commands that will return versions:
# 'fwver' and 'binver'.
#
# 'fwver'   is used to get the running RO and RW versions from cr50
# 'binver'  gets the version strings for each RO and RW region in the given
#           file
#
# The value in the dictionary is the regular expression that can be used to
# find the version strings for each region.
VERSION_RE = {
    "--fwver" : '\nRO (?P<ro>\S+).*\nRW (?P<rw>\S+)',
    "--binver" : 'RO_A:(?P<ro_a>\S+).*RW_A:(?P<rw_a>\S+).*' \
           'RO_B:(?P<ro_b>\S+).*RW_B:(?P<rw_b>\S+)',
}


def AssertVersionsAreEqual(name_a, ver_a, name_b, ver_b):
    """Raise an error ver_a isn't the same as ver_b

    Args:
        name_a: the name of section a
        ver_a: the version string for section a
        name_b: the name of section b
        ver_b: the version string for section b

    Raises:
        AssertionError if ver_a is not equal to ver_b
    """
    assert ver_a == ver_b, ("Versions do not match: %s %s %s %s" %
                            (name_a, ver_a, name_b, ver_b))


def GetNewestVersion(ver_a, ver_b):
    """Compare the versions. Return the newest one. If they are the same return
    None."""
    a = [int(x) for x in ver_a.split('.')]
    b = [int(x) for x in ver_b.split('.')]

    if a > b:
        return ver_a
    if b > a:
        return ver_b
    return None


def GetVersion(versions, name):
    """Return the version string from the dictionary.

    Get the version for each key in the versions dictionary that contains the
    substring name. Make sure all of the versions match and return the version
    string. Raise an error if the versions don't match.

    Args:
        version: dictionary with the partition names as keys and the
                 partition version strings as values.
        name: the string used to find the relevant items in versions.
    Returns:
        the version from versions or "-1.-1.-1" if an invalid RO was detected.
    """
    ver = None
    key = None
    for k, v in versions.iteritems():
        if name in k:
            if v == DUMMY_VER:
                logging.info("Detected invalid %s %s", name, v)
                return v
            elif ver:
                AssertVersionsAreEqual(key, ver, k, v)
            else:
                ver = v
                key = k
    return ver


def FindVersion(output, arg):
    """Find the ro and rw versions.

    @param output: The string to search
    @param arg: string representing the usb_updater option, either
                '--binver' or '--fwver'
    @param compare: raise an error if the ro or rw versions don't match
    """
    versions = re.search(VERSION_RE[arg], output)
    versions = versions.groupdict()
    ro = GetVersion(versions, RO)
    rw = GetVersion(versions, RW)
    return ro, rw


def GetSavedVersion(client):
    """Return the saved version from /var/cache/cr50-version"""
    result = client.run(GET_CR50_VERSION).stdout.strip()
    return FindVersion(result, "--fwver")


def GetVersionFromUpdater(client, args):
    """Return the version from usb_updater"""
    result = client.run("usb_updater %s" % ' '.join(args)).stdout.strip()
    return FindVersion(result, args[0])


def GetFwVersion(client):
    """Get the running version using 'usb_updater --fwver'"""
    return GetVersionFromUpdater(client, ["--fwver"])


def GetBinVersion(client, image=CR50_FILE):
    """Get the image version using 'usb_updater --binver image'"""
    # TODO(mruthven) b/37958867: change to ["--binver", image] when usb_updater
    # is fixed
    return GetVersionFromUpdater(client, ["--binver", image, image])


def GetVersionString(ver):
    return 'RO %s RW %s' % (ver[0], ver[1])


def GetRunningVersion(client):
    """Get the running Cr50 version.

    The version from usb_updater and /var/cache/cr50-version should be the
    same. Get both versions and make sure they match.

    Returns:
        running_ver: a tuple with the ro and rw version strings
    Raises:
        TestFail
        - If the version in /var/cache/cr50-version is not the same as the
          version from 'usb_updater --fwver'
    """
    running_ver = GetFwVersion(client)
    saved_ver = GetSavedVersion(client)

    AssertVersionsAreEqual("Running", GetVersionString(running_ver),
                           "Saved", GetVersionString(saved_ver))
    return running_ver


def CheckForFailures(client, last_message):
    """Check for any unexpected cr50-update exit codes.

    This only checks the cr50 update messages that have happened since
    last_message. If a unexpected exit code is detected it will raise an error>

    Args:
        last_message: the last cr50 message from the last update run

    Returns:
        the last cr50 message in /var/log/messages

    Raises:
        TestFail
            - If there is a unexpected cr50-update exit code after last_message
              in /var/log/messages
    """
    messages = client.run(GET_CR50_MESSAGES).stdout.strip()
    if last_message:
        messages = messages.rsplit(last_message, 1)[-1]
        if UPDATE_FAILURE in messages:
            logging.debug(messages)
            raise error.TestFail("Detected unexpected exit code during update")
    return messages.rsplit('\n', 1)[-1]


def VerifyUpdate(client, ver='', last_message=''):
    """Verify that the saved update state is correct and there were no
    unexpected cr50-update exit codes since the last update.

    Returns:
        new_ver: a tuple containing the running ro and rw versions
        last_message: The last cr50 update message in /var/log/messages
    """
    # Check that there were no unexpected reboots from cr50-result
    last_message = CheckForFailures(client, last_message)
    logging.debug("last cr50 message %s", last_message)

    new_ver = GetRunningVersion(client)
    if ver != '':
        if DUMMY_VER != ver[0]:
            AssertVersionsAreEqual("Old RO", ver[0], "Updated RO", new_ver[0])
        AssertVersionsAreEqual("Old RW", ver[1], "Updated RW", new_ver[1])
    return new_ver, last_message


def ClearUpdateStateAndReboot(client):
    """Removes the cr50 status files in /var/cache and reboots the AP"""
    client.run("rm %s" % CR50_STATE)
    client.reboot()


def InstallImage(client, src, dest=CR50_FILE):
    """Copy the image at src to dest on the dut
    Args:
        src: the image location of the server
        dest: the desired location on the dut
    Returns:
        The filename where the image was copied to on the dut, a tuple
        containing the RO and RW version of the file
    """
    # Send the file to the DUT
    client.send_file(src, dest)

    ver = GetBinVersion(client, dest)
    client.run("sync")
    return dest, ver
