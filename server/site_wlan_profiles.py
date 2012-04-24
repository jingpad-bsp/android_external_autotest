#!/usr/bin/python

# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""ChromeOS connection manager Autotest tests covering service profiles.

This file provides functionality as described in crosbug.com/25795.
Specifically providing support for:

  * The Profiles property of the Manager.
  * The Entries property of the Profile.
  * The DeleteEntry method of the Profile.
  * The GetEntryByName method of the Profile.
"""

import logging
import optparse
import re
import sys

import dbus
import site_wlan_dbus_setup


def GetObject(kind, path):
  """Returns a DBus interface for the specified object.

  Args:
    kind: String containing the type of object such as "Profile" or "Service".
    path: String containing the DBus path to the object.

  Returns:
    The DBus interface to the object.
  """
  return dbus.Interface(
      site_wlan_dbus_setup.bus.get_object(site_wlan_dbus_setup.FLIMFLAM, path),
      site_wlan_dbus_setup.FLIMFLAM + "." + kind)


class DbusInterface(object):
  """Top-level wrapper class for objects found on the DBus."""

  def __init__(self, interface):
    """Constructor DBusInterface object with an interface.

    Args:
      interface: A dbus.Interface object used to access the DBus on behalf of
                 the object.
    """
    self.dbus_interface = interface

  def GetProperty(self, kind):
    """Returns the value of the specified property of the DBus object.

    Args:
      kind: A string, like "Profiles".  The property we're getting.
    Returns:
      The property of the given kind (see the DBus object's API documentation
      to get a description of the return value for this call).
    """
    return self.dbus_interface.GetProperties().get(kind)

  @property
  def name(self):
    return "<Base Class>"


class Manager(DbusInterface):
  """Wrapper for DBus 'Manager'."""

  def __init__(self):
    """Initializes using global 'manager' defined in site_wlan_dbus_setup.py.

    This file needs to use site_wlan_dbus_setup.py, a file which declares a
    global: manager.  This class wraps access to this variable so that it's
    only used here, in __init__.  All other access to 'manager' is done
    through this class.
    """
    DbusInterface.__init__(self, site_wlan_dbus_setup.manager)

  def GetProfile(self, desired=None):
    """Gets a specific Profile from the profile list.

    Args:
      desired: String containing the name of the desired profile.  If None, use
          the default profile.

    Returns:
      A 'Profile' object if the profile is found; 'None', otherwise.
    """
    if desired:
      desired_path = "/profile/%s" % desired
      profiles = self.GetProperty("Profiles")
      if desired_path in profiles:
        return Profile(desired_path)
    else:
      active_path = self.GetProperty("ActiveProfile")
      if active_path:
        return Profile(active_path)
    return None

  @property
  def name(self):
    return "Connection-Manager"


class Profile(DbusInterface):
  """Wrapper for a Connection Manager Profile."""

  class EntryIterator(object):
    """Iterates over this Profile's Entries.

    NOTE: This iterator does not take kindly to the entry list changing after
    the iterator is created.
    """
    def __init__(self, profile):
      # The Profile's "Entries" property is an array of paths to entries.
      self.__profile = profile
      self.__paths = self.__profile.GetProperty("Entries")
      self.__path_count = len(self.__paths)
      self.__index = 0

    def __iter__(self):
      return self

    def next(self):
      """Returns a tuple of the path to the next entry and the entry."""
      if self.__index >= self.__path_count:
        raise StopIteration
      path = self.__paths[self.__index]
      self.__index += 1
      entry = self.__profile.dbus_interface.GetEntry(path)
      return path, entry

  def __init__(self, profile_name):
    """Constructor.

    Args:
      profile_name: A string, possibly returned by Manager.GetProperty().
    """
    DbusInterface.__init__(self, GetObject("Profile", profile_name))

  def IterEntries(self):
    return self.EntryIterator(self)

  def GetEntryByName(self, desired):
    """Returns an entry whose Name property matches 'desired'.

    Args:
      desired: String containing the name of the desired entry.

    Returns:
      A tuple consisting of the RPC identifier for the entry and the
      dictionary that is the found entry (or 'None' if not found).
    """
    match = re.compile(desired + "$")

    for path, entry in self.IterEntries():
      name = entry["Name"]
      logging.debug("  Does '%s' match '%s'", name, desired)
      if name is not None and match.match(name):
        logging.debug("    YES, path=%s", name)
        return path, entry

    logging.error("** '%s' not in ENTRIES", desired)
    return None

  @property
  def name(self):
    return self.dbus_interface.GetProperties().get("Name")

  def DeleteEntry(self, desired_path):
    logging.debug("Deleting entry '%s' for profile '%s'", desired_path,
                  self.name)
    self.dbus_interface.DeleteEntry(desired_path)


class Service(DbusInterface):
  """Wrapper for the manager 'property'."""

  def __init__(self, service_name):
    """Constructor.

    Args:
      service_name: A string, possibly returned by Manager.GetProperty().
    """
    DbusInterface.__init__(self, GetObject("Service", service_name))

  @property
  def name(self):
    return self.dbus_interface.GetProperties().get("Name")


class ProfileTest(object):
  """Contains all the top-level testing methods for Profiles."""

  RETURN_FAILURE = -1
  RETURN_SUCCESS = 0

  def _GetProfileEntry(self, mgr, requests, ethernet_mac=None):
    """Parses "profile:xxx" and "entry:xxx" parameters from requests.

    Args:
      mgr: A DBus manager object.
      requests: A dictionary that contains variable:value pairs (both strings).
          One 'variable' can be 'profile', describing the profile to be used
          (defaults to the active profile).  Exactly one 'variable' is
          expected to be 'entry', describing the entry inside the profile.
      ethernet_mac: String containing only the 12 hex digits of the MAC address
          describing the primary Ethernet interface on the current box.
    Returns:
      'None' on error; otherwise, returns a tuple containing profile, the
      entry, and the entry's ident.
    """
    # Extract the specific Profile Entry (use active profile if none
    # specified).
    if not requests:
      return None

    logging.debug("REQUESTS: %s", requests)
    if "profile" in requests:
      profile_name = requests.pop("profile")
      profile = mgr.GetProfile(desired=profile_name)
    else:
      profile_name = "<ACTIVE PROFILE>"
      profile = mgr.GetProfile()

    if not profile:
      logging.error("Couldn't find profile '%s'.", profile_name)
      return None

    if not requests["entry"]:
      logging.error("You need to specify an entry.")
      return None

    # Since ethernet entry names include the MAC address, we'll extend the
    # name if 'desired' is just 'ethernet'.
    logging.debug("request[entry]=%s, ethernet_mac=%s", requests["entry"],
                 ethernet_mac)
    if (requests["entry"] == "ethernet") and (ethernet_mac is not None):
      entry_name = "ethernet_%s" % ethernet_mac
    else:
      entry_name = requests["entry"]

    result = profile.GetEntryByName(entry_name)
    if not result or len(result) != 2:
      return None
    ident, entry = result
    return profile, entry, ident

  def ClientCheckProfileProperties(self, mgr, options):
    """Checks that one or more profile entry properties equal what they should.

    Args:
      mgr: A DBus manager object.
      options: An object returned from optparse.OptionParser.parse_args().
          This is expected to include a value, options.param, that contains an
          array of strings, each of which take the form 'variable:value'.
          One 'variable' can be 'profile', describing the profile to be used
          (defaults to the active profile).  Exactly one 'variable' is
          expected to be 'entry', describing the entry inside the profile.
          The remaining 'variable' values are Entry IDs that are to be checked.

          For example:
            {'ethmac': '525400123456',
             'command': 'ClientCheckProfileProperties',
             'param': ['profile:test', 'entry:Ethernet', 'Favorite:1']}

    Returns:
      A value to be passed to sys.exit(): 0 for success, non-zero otherwise.
    """
    if not options.param:
      logging.error("You need at least one parameter.")
      return ProfileTest.RETURN_FAILURE

    # Convert the a:b format of the options into a dictionary.
    try:
      requests = dict(param.split(":", 2) for param in options.param)
    except ValueError as e:
      logging.error(
          "All parameters in '%s' must be of the form 'param:value' (%s).",
          options.param, e)
      return ProfileTest.RETURN_FAILURE

    ethernet_mac = options.ethmac
    result = self._GetProfileEntry(mgr, requests, ethernet_mac=ethernet_mac)

    if not result:
      return ProfileTest.RETURN_FAILURE

    profile, entry, entry_name = result

    # Look for the specified parameters in the entry.

    if "entry" in requests:
      del requests["entry"]  # Don't want to search entry for 'entry'.
    for param in requests:
      if param not in entry:
        logging.error("Entry %s[%s] does not exist in profile %s",
                      entry_name, param, profile.name)
        return ProfileTest.RETURN_FAILURE
      elif str(entry[param]) != requests[param]:
        logging.error("Entry %s[%s]==%s but should be %s.", entry_name, param,
                      entry[param], requests[param])
        return ProfileTest.RETURN_FAILURE
      else:
        logging.debug("Entry %s[%s]==%s", entry_name, param, entry[param])
    logging.debug("Everything matched for profile '%s', entry '%s'",
                 profile.name, entry["Name"])
    return ProfileTest.RETURN_SUCCESS

  def ClientProfileDeleteEntry(self, mgr, options):
    """Finds an entry via that entry's 'Name' property and deletes it.

    Args:
      mgr: A DBus manager object.
      options: An object returned from optparse.OptionParser.parse_args().
          This is expected to include a value, options.param, that contains an
          array of strings, each of which take the form 'variable:value'.
          One 'variable' can be 'profile', describing the profile to be used
          (defaults to the active profile).  Exactly one 'variable' is
          expected to be 'entry', describing the name of the entry inside the
          profile.  Any remaining variables are ignored.
    Returns:
      A value to be passed to sys.exit(): 0 for success, non-zero otherwise.
    """
    if not options.param:
      logging.error("You need at check least one parameter.")
      return ProfileTest.RETURN_FAILURE

    # Convert the a:b format of the options into a dictionary.
    try:
      requests = dict(param.split(":", 2) for param in options.param)
    except ValueError as e:
      logging.error(
          "All parameters in '%s' must be of the form 'param:value' (%s).",
          options.param, e)
      return ProfileTest.RETURN_FAILURE

    ethernet_mac = options.ethmac
    result = self._GetProfileEntry(mgr, requests, ethernet_mac=ethernet_mac)

    if not result:
      return ProfileTest.RETURN_FAILURE

    profile, unused_entry, path = result

    profile.DeleteEntry(path)

    return ProfileTest.RETURN_SUCCESS

  def Execute(self, argv):
    """Main entry point for the Profile-based tests.

    Args:
      argv: sys.argv

    Returns:
      A value to be passed to sys.exit(): 0 for success, non-zero otherwise.
    """
    mgr = Manager()
    parser = optparse.OptionParser("Usage: %prog [options...] [SSID=state...]")
    parser.add_option("--command", dest="command",
                      help="command to run, such as "
                      "'ClientCheckProfileProperties' or "
                      "'ClientProfileDeleteEntry'.")
    parser.add_option("--ethmac", dest="ethmac",
                      help="MAC address for the Ethernet connection (no "
                      "punctuation")
    parser.add_option("--param", dest="param", action="append",
                      help="A parameter to extract and a value against "
                      "which to check it")

    options, unused_args = parser.parse_args(argv[1:])

    result = ProfileTest.RETURN_FAILURE
    if not options.command:
      logging.error("You need, at least, a 'command' parameter.")
      return ProfileTest.RETURN_FAILURE

    func = getattr(self, options.command, None)
    if not func:
      logging.error("Command '%s' unknown; abort test", options["command"])
      return ProfileTest.RETURN_FAILURE
    else:
      result = func(mgr, options)
    return result


def main(argv):
  test = ProfileTest()
  result = test.Execute(argv)


if __name__ == "__main__":
  main(sys.argv)
