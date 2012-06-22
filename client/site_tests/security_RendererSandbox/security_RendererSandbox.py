# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import os, subprocess, time, re
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui_test, login

class security_RendererSandbox(cros_ui_test.UITest):
    version = 1
    render_pid = -1


    def check_for_seccomp_sandbox(self):
        # the seccomp sandbox has exactly one child process that has no
        # other threads, this is the trusted helper process.
        seccomp = subprocess.Popen(['ps', 'h', '--format', 'pid',
                                    '--ppid', '%s' % self.render_pid],
                                   stdout=subprocess.PIPE)
        helper_processes = seccomp.communicate()[0].splitlines()
        if len(helper_processes) != 1:
            raise error.TestFail('Invalid number of Renderer child process')

        helper_pid = helper_processes[0].strip()
        threads = os.listdir('/proc/%s/task' % helper_pid)
        if len(threads) != 1:
            raise error.TestFail('Invalid number of helper process threads')

        exe = os.readlink('/proc/%s/exe' % helper_pid)
        pattern = re.compile('/chrome$')
        chrome = pattern.search(exe)
        if chrome == None:
            raise error.TestFail('Invalid child process executable')


    def check_for_suid_sandbox(self):
        # for setuid sandbox, make sure there is no content in the CWD
        # directory
        cwd_contents = os.listdir('/proc/%s/cwd' % self.render_pid)
        if len(cwd_contents) > 0:
          raise error.TestFail('Contents present in the CWD directory')


    def run_once(self, time_to_wait=20):

        # wait till the page is loaded and poll for the renderer pid
        # if renderer pid is found, it is stored in self.render_pid
        utils.poll_for_condition(
            self._get_renderer_pid,
            error.TestFail('Timed out waiting to obtain pid of renderer'),
            time_to_wait)

        # check if renderer is sandboxed
        # for now, x86 renderer must be running in a seccomp sandbox and
        # arm render must run in a setuid sandbox
        arch = utils.get_arch()
        if arch == 'i386':
            # Seccomp is currently disabled because of performance issues. See
            # crosbug.com/8397
            # self.check_for_seccomp_sandbox()
            self.check_for_suid_sandbox()
        else:
            self.check_for_suid_sandbox()


    # queries pgrep for the pid of the renderer. since this function is passed
    # as an argument to utils.poll_for_condition, the return values are set
    # to true/false depending on whether a pid has been found
    def _get_renderer_pid(self):
        pgrep = subprocess.Popen(['pgrep', '-f', '-l', 'type=renderer'],
                                 stdout=subprocess.PIPE)
        procs = pgrep.communicate()[0].splitlines()
        pids = []
        # we're adding '--ignored= --type=renderer' to the GPU process cmdline
        # to fix http://code.google.com/p/chromium/issues/detail?id=129884
        # this confuses 'pgrep' above, returning the pid of the GPU process,
        # which is not sandboxed, as the pid of a renderer, breaking the test
        for proc in procs:
            if '--ignored= --type=renderer' not in proc:
                pids.append(proc.split()[0])

        if pids:
            self.render_pid = pids[0]
            return True
        else:
            return False
