# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime, logging, subprocess, time
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, smogcheck_tpm, smogcheck_ttci


# TODO(tgao): refactor runInSubprocess() and enableI2C() into a separate library
#             to minimize code duplication, e.g. same repeat in
#             ../hardware_TPMttci/hardware_TPMttci.py
def runInSubprocess(args, rc_list=None):
    """Run a command in subprocess and return stdout.

    Args:
      args: a list of string, command to run.
      rc_list: a list of int, acceptable return code values.

    Returns:
      out: a string, stdout of the command executed.
      err: a string, stderr of the command executed, or None.

    Raises:
      RuntimeError: if subprocess return code is non-zero and not in rc_list.
    """
    if rc_list is None:
        rc_list = []

    # Sleep for 1 second so we don't overwhelm I2C bus with too many commands
    time.sleep(1)
    logging.debug('runInSubprocess args = %r; rc_list = %r', args, rc_list)
    proc = subprocess.Popen(args,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    out, err = proc.communicate()
    logging.error('runInSubprocess %s: out=%r, err=%r', args[0], out, err)
    if proc.returncode and proc.returncode not in rc_list:
        raise RuntimeError('runInSubprocess %s failed with returncode %d: %s' %
                           (args[0], proc.returncode, out))
    return str(out), str(err)


def enableI2C():
    """Enable i2c-dev so i2c-tools can be used.

    Dependency: 'i2cdetect' is a command from 'i2c-tools' package, which comes
                with Chrom* OS image and is available from inside chroot.

    Raises:
      TestFail: if i2c-dev can't be enabled.
    """
    args = ['i2cdetect', '-l']
    out, _ = runInSubprocess(args)
    if not out:
        logging.info('i2c-dev disabled. Enabling it with modprobe')
        out, _ = runInSubprocess(['modprobe', 'i2c-dev'])
        if out:
            raise error.TestFail('Error enable i2c-dev: %s' % out)
        out, _ = runInSubprocess(args)
    logging.info('i2c-dev ready to go:\n%s', out)


class hardware_TPMtspi(test.test):
    version = 1

    def setup(self):
        enableI2C()

    def _prepareTpmController(self):
        """Prepare a TpmController instance for use.

        Returns:
          an operational TpmControler instance, ready to use.
        """
        try:
            return smogcheck_tpm.TpmController()
        except smogcheck_tpm.SmogcheckError, e:
            raise error.TestFail('Error creating a TpmController: %s', e)

    def run_once(self):
        self.tpm_obj = self._prepareTpmController()

        start_time = datetime.datetime.now()
        try:
            self.tpm_obj.setupContext()
            self.tpm_obj.getTpmVersion()
            self.tpm_obj.runTpmSelfTest()

            # TODO(tgao): uncomment to enable.
            #self.tpm_obj.takeTpmOwnership()

            # TODO(tgao): uncomment to enable.
            #self.tpm_obj.clearTpm()

            # TODO(tgao): uncomment to enable.
            #self.tpm_obj.setTpmActive('status')

            # TODO(tgao): uncomment to enable.
            #self.tpm_obj.setTpmActive('deactivate')

            # TODO(tgao): uncomment to enable.
            #self.tpm_obj.setTpmActive('activate')

            # TODO(tgao): uncomment to enable.
            #self.tpm_obj.setTpmActive('temp')

            # TODO(tgao): uncomment to enable.
            #self.tpm_obj.setTpmClearable('status')

            # TODO(tgao): uncomment to enable.
            #self.tpm_obj.setTpmClearable('owner')

            # TODO(tgao): uncomment to enable.
            #self.tpm_obj.setTpmClearable('force')

        except smogcheck_tpm.SmogcheckError, e:
            raise error.TestFail('Error: %r' % e)
        finally:
            # Close TPM context
            if self.tpm_obj.closeContext():
                raise error.TestFail('Error closing tspi context')

        end_time = datetime.datetime.now()
        smogcheck_ttci.computeTimeElapsed(end_time, start_time)
