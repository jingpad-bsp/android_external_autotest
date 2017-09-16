# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is a FAFT test to check if TCPCs are up-to-date.

This test figures out which TCPCs exist on a DUT and matches
these up with corresponding firmware blobs in the system
image shellball.  If mismatches are detected, the test fails.

The test can optionally be invoked with --args bios=... to
specify an alternate reference firmware image.
"""

import logging
import os

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils
from autotest_lib.server.cros.faft.firmware_test import FirmwareTest


class generic_chip(object):
  """A chip we don't actually support."""

  chip_name = 'unknown'
  fw_name = None

  def __init__(self):
    self.fw_ver = None

  def set_fw_ver_from_string(self, version):
    """Set version property from string."""
    self.fw_ver = int(version, 0)


class ps8751(generic_chip):
  """The PS8751 TCPC chip."""

  chip_name = 'ps8751'
  fw_name = 'ps8751_a3'
  cbfs_hash_name = fw_name + '.hash'

  def fw_ver_from_hash(self, blob):
    """Return the firmware version encoded in the firmware hash."""

    return blob[1]


class anx3429(generic_chip):
  """The ANX3429 TCPC chip."""

  chip_name = 'anx3429'
  fw_name = 'anx3429_ocm'
  cbfs_hash_name = fw_name + '.hash'

  def fw_ver_from_hash(self, blob):
    """Return the firmware version encoded in the firmware hash."""

    return blob[0]


#
# map of chip IDs to corresponding class
#

chip_id_map = {
    '0x8751': ps8751,
    '0x3429': anx3429,
}


class firmware_CompareChipFwToShellBall(FirmwareTest):
  """Compares the active DUT chip firmware with reference.

  FAFT test to verify that a DUT runs the expected chip
  firmware based on the system shellball or a specified
  reference image.
  """
  version = 1

  CBFSTOOL = 'cbfstool'
  BIOS = 'bios.bin'
  HEXDUMP = 'hexdump -v -e \'1/1 "0x%02x\\n"\''
  MAXPORTS = 100

  def initialize(self, host, cmdline_args):
    super(firmware_CompareChipFwToShellBall,
          self).initialize(host, cmdline_args)
    dict_args = utils.args_to_dict(cmdline_args)
    self.new_bios_path = dict_args['bios'] if 'bios' in dict_args else None
    self.cbfs_extract_dir = None
    self.dut_bios_path = None

  def cleanup(self):
    if self.cbfs_extract_dir:
      self.faft_client.system.remove_dir(self.cbfs_extract_dir)
    super(firmware_CompareChipFwToShellBall, self).cleanup()

  def dut_run_cmd_status(self, command):
    """Executes a command on DUT.

    Args:
      command: shell command to be executed on DUT.

    Returns:
      Exit status as boolean.
    """

    try:
      self.faft_client.system.run_shell_command(command)
    except Exception:
      return False
    return True

  def dut_get_chip(self, port):
    """Gets the chip info for a port.

    Args:
      port: TCPC port number on DUT

    Returns:
      A chip object if available, else None.
    """

    cmd = 'mosys -s product_id pd chip %d' % port
    chip_id = self.faft_client.system.run_shell_command_get_output(cmd)
    if not chip_id:
      # chip probably does not exist
      return None
    chip_id = chip_id[0]

    if chip_id not in chip_id_map:
      logging.info('chip type %s not recognized', chip_id)
      return generic_chip()
    chip = chip_id_map[chip_id]()

    cmd = 'mosys -s fw_version pd chip %d' % port
    fw_rev = self.faft_client.system.run_shell_command_get_output(cmd)
    if not fw_rev:
      # chip probably does not exist
      return None
    fw_rev = fw_rev[0]
    chip.set_fw_ver_from_string(fw_rev)
    return chip

  def dut_scan_chips(self):
    """Scans for TCPC chips on DUT.

    Returns:
      A tuple (S, L) consisting of a set S of chip types and a list L
      of chips indexed by port number found on on the DUT.

    Raises:
      TestFail: DUT has >= MAXPORTS pd ports.
    """

    chip_types = set()
    port2chip = []
    for port in xrange(self.MAXPORTS):
      chip = self.dut_get_chip(port)
      if not chip:
        return (chip_types, port2chip)
      port2chip.append(chip)
      chip_types.add(chip.__class__)
    logging.error('found at least %u TCPC ports '
                  '- please update test to handle more ports '
                  'if this is expected.', self.MAXPORTS)
    raise error.TestFail('MAXPORTS exceeded' % self.MAXPORTS)

  def dut_locate_bios_bin(self):
    """Finds bios.bin on DUT.

    Figures out where FAFT unpacked the shellball
    and return path to extracted bios.bin.

    Returns:
      Full path of bios.bin on DUT.
    """

    work_path = self.faft_client.updater.get_work_path()
    bios_relative_path = self.faft_client.updater.get_bios_relative_path()
    bios_bin = os.path.join(work_path, bios_relative_path)
    return bios_bin

  def dut_prep_cbfs(self, host):
    """Sets up cbfs on DUT.

    Finds bios.bin on the DUT and sets up a temp dir to operate on
    bios.bin.  If a bios.bin was specified, it is copied to the DUT
    and used instead of the native bios.bin.

    Args:
      host: A Handle for remote DUT operations.
    """

    self.cbfs_extract_dir = self.faft_client.system.create_temp_dir('extract-')
    if self.new_bios_path:
      self.dut_bios_path = os.path.join(self.cbfs_extract_dir, self.BIOS)
      host.send_file(self.new_bios_path, self.dut_bios_path)
    else:
      self.dut_bios_path = self.dut_locate_bios_bin()

    cmd = '%s %s print -r FW_MAIN_A' % (
        self.CBFSTOOL, self.dut_bios_path)
    out = self.faft_client.system.run_shell_command_get_output(cmd)
    if not out:
      raise error.TestError('%s failed.' % self.CBFSTOOL)

  def dut_cbfs_extract_chips(self, chip_types):
    """Extracts firmware hash blobs from cbfs.

    Iterates over requested chip types and looks for corresponding
    firmware hash blobs in cbfs.  These firmware hash blobs are
    extracted into cbfs_extract_dir.

    Args:
      chip_types:
        A set of chip types for which the hash blobs will be
        extracted.

    Returns:
      A dict mapping found chip names to chip instances.
    """

    cbfs_chip_info = {}
    for chip_type in chip_types:
      chip = chip_type()
      fw = chip.fw_name
      if not fw:
        continue
      cbfs_extract = '%s %s extract -r FW_MAIN_A -n %s%%s -f %s%%s' % (
          self.CBFSTOOL,
          self.dut_bios_path,
          fw,
          os.path.join(self.cbfs_extract_dir, fw))

      cmd = cbfs_extract % ('.hash', '.hash')
      if not self.dut_run_cmd_status(cmd):
        logging.warning('%s firmware hash not bundled in %s',
                        chip.chip_name, self.BIOS)
        continue

      cmd = '%s %s.hash' % (
          self.HEXDUMP,
          os.path.join(self.cbfs_extract_dir, fw))
      hashblob = self.faft_client.system.run_shell_command_get_output(cmd)
      if not hashblob:
        logging.warning('%s firmware hash not extracted from %s',
                        chip.chip_name, self.BIOS)
        continue

      bundled_fw_ver = chip.fw_ver_from_hash(hashblob)
      if not bundled_fw_ver:
        raise error.TestFail('could not decode %s firmware hash: %s' % (
            chip.chip_name, hashblob))

      chip.set_fw_ver_from_string(bundled_fw_ver)
      cbfs_chip_info[chip.chip_name] = chip
      logging.info('%s bundled firmware for %s is version %s',
                   self.BIOS, chip.chip_name, bundled_fw_ver)
    return cbfs_chip_info

  def check_chip_versions(self, port2chip, ref_chip_info):
    """Verifies DUT chips have expected firmware.

    Iterates over found DUT chips and verifies their firmware version
    matches the chips found in the reference ref_chip_info map.

    Args:
      port2chip: A list of chips to verify against ref_chip_info.
      ref_chip_info: A dict of reference chip chip instances indexed
          by chip name.
    """

    for p, pinfo in enumerate(port2chip):
      if not pinfo.fw_ver:
        # must be an unknown chip
        continue
      msg = 'DUT port %s is a %s running firmware 0x%02x' % (
          p, pinfo.chip_name, pinfo.fw_ver)
      if pinfo.chip_name not in ref_chip_info:
        logging.warning('%s but there is no reference version', msg)
        continue
      expected_fw_ver = ref_chip_info[pinfo.chip_name].fw_ver
      logging.info('%s%s', msg,
                   ('' if pinfo.fw_ver == expected_fw_ver else
                    ' (expected 0x%02x)' % expected_fw_ver))

      if pinfo.fw_ver != expected_fw_ver:
        msg = '%s firmware was not updated to 0x%02x' % (
            pinfo.chip_name, expected_fw_ver)
        raise error.TestFail(msg)

  def run_once(self, host):
    # Make sure the client library is on the device so that the proxy
    # code is there when we try to call it.

    (dut_chip_types, dut_chips) = self.dut_scan_chips()
    if not dut_chip_types:
      logging.info('mosys reported no chips on DUT, skipping test')
      return

    self.dut_prep_cbfs(host)
    ref_chip_info = self.dut_cbfs_extract_chips(dut_chip_types)
    self.check_chip_versions(dut_chips, ref_chip_info)
