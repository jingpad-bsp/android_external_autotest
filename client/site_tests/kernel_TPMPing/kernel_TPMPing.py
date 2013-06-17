# Copyright (c) 2010,2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class kernel_TPMPing(test.test):
  """See control file for doc"""
  version = 2

  def run_once(self):
    tpm_version = utils.system_output("tpm_version")
    if tpm_version.find("Version Info") == -1:
      raise error.TestFail("Invalid tpm_version output:\n%s\n" % tpm_version)
    else:
      logging.info(tpm_version)

    # If the "gentle shutdown" string is missing from the log, we
    # forgot to carry over an important patch.
    tpm_device_re = "tpm_tis: 1.2 TPM (device"
    tpm_gentle_re = "\\[gentle shutdown\\]"
    log_file_glob = "$(echo /var/log/messages* | tac -s ' ')"
    # We only care about the most recent instance of the TPM driver message.
    if utils.system("grep '%s' %s | tail -1 | grep '%s'" %
                    (tpm_device_re, log_file_glob, tpm_gentle_re),
                    ignore_status=True) != 0:
      raise error.TestFail("no 'gentle shutdown' TPM driver init message")
