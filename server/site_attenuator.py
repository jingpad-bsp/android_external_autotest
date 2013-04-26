# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# TODO(tgao): use XMLHTTP instead of repeated SSH commands. See
#             https://gerrit.chromium.org/gerrit/37180 and the code for
#             remote_pyauto in client/cros for examples

import os


# Port of variable attenuator.
VA_PORT = 'va_port'
# Fixed attenuation in dB.
FIXED_ATTEN = 'fixed_atten'
# Total attenuation in dB.
TOTAL_ATTEN = 'total_atten'


class ScriptNotFound(Exception):
    """Raised when attenuator scripts cannot be found."""

    def __init__(self, script_name):
        """Initialize.

        @param script_name: a string.
        """
        super(ScriptNotFound, self).__init__(
            'Script %s not found in search path' % script_name)


class Attenuator(object):
    """Attenuator support for WiFiTest class.

    This class implements wifi test methods that communicate with a variable
    attenuator over SSH in control network.
    """

    def __init__(self, host):
        """Initialize.

        @param host: an Autotest host object, representing the attenuator.
        """
        self.host = host
        self.installed_scripts = {}


    def init_va(self, params):
        """Initializes attenuator port.

        @param params: a Python dictionary.
        """
        port_num = params.get(VA_PORT, 0)

        # Install Python scripts on attenuator
        # TODO(tgao): bundle these scripts as part of a test image?
        init_script = self._copy_script('attenuator_init.py',
                                        'attenuator_util.py',
                                        'constants.py')
        self.host.run('python "%s" -p %s 2>&1' % (init_script, port_num))


    def get_attenuation(self, params):
        """Reads current attenuation level in dB.

        @param params: a Python dictionary.
        """
        port_num = params.get(VA_PORT, 0)
        attenuator_script = self._copy_script('attenuator_config.py',
                                              'attenuator_util.py',
                                              'constants.py')
        self.host.run('python "%s" -p %d 2>&1' % (attenuator_script, port_num))

    def set_attenuation(self, params):
        """Sets desired attenuation level in dB.

        @param params: a Python dictionary.
        @returns total_atten: an integer, total attenuation in dB.
        """
        port_num = params.get(VA_PORT, 0)
        fixed_atten = params.get(FIXED_ATTEN, None)
        total_atten = params.get(TOTAL_ATTEN, None)

        attenuator_script = self._copy_script('attenuator_config.py',
                                              'attenuator_util.py',
                                              'constants.py')
        self.host.run('python "%s" -p %d -f %d -t %d 2>&1' %
                      (attenuator_script, port_num, fixed_atten, total_atten))
        return total_atten


    # TODO(tgao): refactor & merge this w/ site_linux.router.install_script()
    def _copy_script(self, script_name, *support_scripts):
        """Copies script to DUT.

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
