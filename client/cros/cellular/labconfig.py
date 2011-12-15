# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import optparse, pickle, re, subprocess

import cellular, labconfig_data

class LabConfigError(Exception):
  pass


def get_interface_ip(interface='eth0'):
    """Returns the IP address for an interface."""

    # We'd like to use
    #  utils.system_output('ifconfig eth0 2>&1', retain_output=True)
    # but that gives us a dependency on the rest of autotest, which
    # means that running the unit test requires pythonpath manipulation
    ifconfig = subprocess.Popen(['/sbin/ifconfig', interface],
                                stdout=subprocess.PIPE).communicate()[0]

    match = re.search(r'inet addr:([0-9.]+)', ifconfig)
    if not match:
        raise LabConfigError('Could not parse interface address from ' +
                             ifconfig)
    return match.group(1)


class Configuration(object):
    """Configuration for a cellular test.

    This includes things like the address of the cell emulator device
    and details of the RF switching between the emulated basestation
    and the DUT."""

    def __init__(self, args):
        parser = optparse.OptionParser()

        # Record our args so we can serialize ourself.
        self.args = args

        parser.add_option('--cell', dest='cell', default=None,
                          help='Cellular test cell to use')
        parser.add_option(
            '--technology', dest='technology', default='all',
            help='Radio access technologies to use (e.g. "WCDMA")')

        (self.options, _) = parser.parse_args(args)
        self.cell = self._get_cell(self.options.cell)

    def _get_cell(self, name):
        """Extracts the named cell from labconfig_data.CELLS."""
        if not name:
            raise LabConfigError(
                'Could not find --cell argument.  ' +
                'To specify a cell, pass --args=--cell=foo to run_remote_tests')

        if name not in labconfig_data.CELLS:
            raise LabConfigError(
                'Could not find cell %s, valid cells are %s' % (
                    name, labconfig_data.CELLS.keys()))

        return labconfig_data.CELLS[name]

    def _get_dut(self, machine=None):
        """Returns the DUT record for machine from cell["duts"].

        Right now, we use the interface of eth0 to figure out which
        machine we're running on.  The important thing is that this
        matches the IP address in the cell duts configuration.  We'll
        have to come up with a better way if this proves brittle."""

        if not machine:
            machine = get_interface_ip('eth0')

        for dut in self.cell["duts"]:
            if machine == dut["address"] or machine == dut["name"]:
                return dut
        return None

    def get_technologies(self, machine=None):
        """Gets technologies to use for machine; defaults to all available."""
        technologies_list = self.options.technology.split(',')

        if 'all' in technologies_list:
            m = self._get_dut(machine)
            technologies_list = m["technologies"]

        enums = [getattr(cellular.Technology, t, None)
                 for t in technologies_list]

        if None in enums:
            raise LabConfigError(
                'Could not understand a technology in %s' % technologies_list)

        return enums

    def get_pickle(self):
        return pickle.dumps(self)
