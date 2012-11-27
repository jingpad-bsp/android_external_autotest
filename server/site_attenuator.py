# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# TODO(tgao): use XMLHTTP instead of repeated SSH commands. See
#             https://gerrit.chromium.org/gerrit/37180 and the code for
#             remote_pyauto in client/cros for examples

import logging
import os
from autotest_lib.client.common_lib import error


# Port of variable attenuator.
VA_PORT = 'va_port'
# Fixed path loss in dB.
FIXED_DB = 'fixed_db'
# Total path loss in dB.
TOTAL_DB = 'total_db'


class ScriptNotFound(Exception):
    """
    Raised when attenuator scripts cannot be found.
    """

    def __init__(self, script_name):
        """
        @param script_name: a string.
        """
        super(ScriptNotFound, self).__init__(
            'Script %s not found in search path' % script_name)


class Attenuator(object):
    """
    Attenuator support for WiFiTest class.

    This class implements wifi test methods that communicate with a variable
    attenuator over SSH in control network.
    """

    def __init__(self, host):
        """
        @param host: an Autotest host object, representing the attenuator.
        """
        self.host = host
        self.installed_scripts = {}


    # TODO(tgao): needed? e.g. reset GPIO pins
    def cleanup(self):
        pass


    def _get_intval(self, key, params):
        """
        Reads integer value of key from params.

        @param key: a string.
        @param params: a Python dictionary.
        @raises TestFail: if params does not contain key.
        """
        if key not in params:
            raise error.TestFail("Unable to find %r in %r" % (key, params))
        return int(params[key], 10)


    def init_va(self, params):
        """
        Initializes attenuator port.

        @param params: a Python dictionary.
        """
        port_num = self._get_intval(VA_PORT, params)

        # Install Python scripts on attenuator
        # TODO(tgao): bundle these scripts as part of a test image?
        init_script = self._copy_script('attenuator_init.py',
                                        'attenuator_util.py',
                                        'constants.py')
        result = self.host.run('python "%s" -p %d' %
                               (init_script, port_num))


    def get_attenuation(self, params):
        """
        Reads current attenuation level in dB.

        @param params: a Python dictionary.
        """
        port_num = self._get_intval(VA_PORT, params)
        attenuator_script = self._copy_script('attenuator_config.py',
                                              'attenuator_util.py',
                                              'constants.py')
        result = self.host.run('python "%s" -p %d' %
                               (attenuator_script, port_num))

    def set_attenuation(self, params):
        """
        Sets desired attenuation level in dB.

        @param params: a Python dictionary.
        """
        port_num = self._get_intval(VA_PORT, params)
        fixed_db = self._get_intval(FIXED_DB, params)
        total_db = self._get_intval(TOTAL_DB, params)

        attenuator_script = self._copy_script('attenuator_config.py',
                                              'attenuator_util.py',
                                              'constants.py')
        result = self.host.run(
            'python "%s" -p %d -f %d -t %d' %
            (attenuator_script, port_num, fixed_db, total_db))


    # TODO(tgao): refactor & merge this w/ site_linux.router.install_script()
    def _copy_script(self, script_name, *support_scripts):
        """
        Copies script to DUT.

        @param script_name: a string.
        @param support_scripts: a list of strings.
        """
        if script_name in self.installed_scripts:
            return self.installed_scripts[script_name]
        script_dir = self.host.get_tmp_dir()
        script_file = os.path.join(script_dir, script_name)
        for copy_file in [script_name] + list(support_scripts):
            # Look either relative to the current location of this file or
            # relative to ../client/common_lib/cros/site_attenuator/
            # for the script.
            script_relative_paths = [['.'],
                                     ['..', 'client', 'common_lib', 'cros',
                                      'site_attenuator']]
            for rel_path in script_relative_paths:
                src_file = os.path.join(
                    os.path.dirname(os.path.realpath(__file__)),
                    *(rel_path + [copy_file]))
                if os.path.exists(src_file):
                    break
            else:
                raise ScriptNotFound(copy_file)

            dest_file = os.path.join(script_dir,
                                     os.path.basename(src_file))
            self.host.send_file(src_file, dest_file, delete_dest=True)
        self.installed_scripts[script_name] = script_file
        return script_file
