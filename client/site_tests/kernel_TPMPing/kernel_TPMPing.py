# Copyright (c) 2010,2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import re
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

def get_major_minor(ver_string):
  """
  Obtain major and minor version numbers from a version string.

  @param ver_string: version string of form "MAJOR.MINOR[.OTHER_NUMBERS]"
  @return: list containing major and minor version numbers

  """
  return map(int, ver_string.split('.')[:2])

class kernel_TPMPing(test.test):
  """See control file for doc"""
  version = 2

  def run_once(self):
    """Run the test."""

    # Check basic connectivity: TPM can report its version info.
    tpm_version = utils.system_output("tpm_version")
    match = re.search('TPM ([0-9\.]+) Version Info', tpm_version)
    if not match:
      raise error.TestFail("Invalid tpm_version output:\n%s\n" % tpm_version)
    else:
      logging.info(tpm_version)

    # Obtain TPM spec and kernel versions.
    logging.info("TPM spec version: %s", match.group(1))
    spec_version = get_major_minor(match.group(1))

    version = utils.system_output('/bin/uname -r').strip()
    logging.info("Kernel version: %s", version)
    kernel_version = get_major_minor(version)

    # The 'gentle shutdown' test is not compatible with kernel version < 3.8
    # and TPM 2.0 chips.
    if kernel_version >= [3, 8] and spec_version != [2, 0]:
      # If the "[gentle shutdown]" string followed by 'Linux Version'
      # is missing from /var/log/messages,
      # we forgot to carry over an important patch.
      result = utils.system_output('awk \'/Linux version [0-9]+\./ '
                                   '{gentle=0;} /\[gentle shutdown\]/ '
                                   '{gentle=1;} END {print gentle}\' '
                                   '$(ls -t /var/log/messages* | tac)',
                                    ignore_status=True)

      # We only care about the most recent instance of the TPM driver message.
      if result == '0':
        raise error.TestFail('no \'gentle shutdown\' TPM driver init message')
    else:
      logging.info('Bypassing the gentle shutdown test')
