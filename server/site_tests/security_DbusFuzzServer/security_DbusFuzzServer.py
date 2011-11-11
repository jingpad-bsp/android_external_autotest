# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, os.path, re, shutil, time
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.server import autotest, test

class security_DbusFuzzServer(test.test):
    version = 1
    FUZZER_BIN = 'dbusfuzz.py'
    FUZZPLAN = 'fuzzplan.yaml'
    CLIENT_INSTALL_PATH_TMPL = '/tmp/DbusFuzzServer.XXXXXX'
    _client_install_path = None


    def client_install_path(self):
        """Get the directory where dbusfuzz/the fuzzplan can be installed."""
        if self._client_install_path:
            return self._client_install_path
        # Otherwise, this needs to be setup still.
        self._client_install_path = self.client.run('mktemp -d "%s"' %
            self.CLIENT_INSTALL_PATH_TMPL).stdout.rstrip()
        return self._client_install_path


    def invalidate_install_path(self):
        """Invalidate the memo-ized location of the fuzzer installed
           on the client. (This will cause a new location to have to be
           created next time it's requested.)
        """
        self._client_install_path = None


    def client_fuzzer_path(self):
        """Get the path to dbusfuzz on the remote machine."""
        return os.path.join(self.client_install_path(), self.FUZZER_BIN)


    def client_fuzzplan_path(self):
        """Get the path to the fuzzplan on the remote machine."""
        return os.path.join(self.client_install_path(), self.FUZZPLAN)


    def install_fuzzer(self):
        self.client.send_file(os.path.join(self.bindir, self.FUZZER_BIN),
                              self.client_fuzzer_path(), delete_dest=True)
        self.client.send_file(os.path.join(self.bindir, self.FUZZPLAN),
                              self.client_fuzzplan_path(), delete_dest=True)
        return True


    def run_fuzzer(self, start_at=0, stop_at=None, pretend=False):
        args = ['python', self.client_fuzzer_path()]

        if start_at:
            args.append('--start_at=%s' % start_at)
        if stop_at != None:
            args.append('--stop_at=%s' % stop_at)
        if pretend:
            args.append('--pretend')

        args.append(self.client_fuzzplan_path())

        status = self.client.run(' '.join(args)).stdout
        # TODO(jimhebert) Import dbusfuzz and get these symbolically.
        # And, actually, we should probably stop comparing them on
        # this side of the function because the caller is having to
        # guess if we were 'DONE' or not. Just return these.
        matches = re.match('(\w+)[:](\d+)', status)
        if matches:
            return (matches.group(1) != 'FAIL', int(matches.group(2)))
        else: # Catastrophic failure, fuzzer died or something.
            # Assume we didn't run any of them since we have no evidence.
            # Signal that the machine should be bounced and this chunk of tests
            # attempted again.
            return (False, start_at - 1)


    def bounce_client(self):
        """Handles all the details of forcing the machine
           back to a clean state. Specifically, any accumulation
           of state from having sent various fuzzed values into
           various daemons is all wiped out. This minimizes
           hard-to-reproduce bugs -- a given test case then
           has O(frag_len) tests worth of accumulated state.
        """
        # TODO(jimhebert) In the future we will want to be more
        # hands-on with bouncing things, which will require the
        # development of 'Bouncer' classes which know how to perform a
        # clean recovery in your particular environment.
        # E.g. a KVMBouncer class would replace the current qemu-loop.sh,
        # a ServoBouncer class would know how to physically power-up
        # servo-wired Chromebook hardware, etc. Part of the control
        # file / run_remote_tests command line arguments would include
        # a flag indicating which Bounce strategy to employ.
        #
        # In the current implementation, bounce_client assumes that
        # halting the client system is sufficient to trigger your
        # local autotest-farm-management logic to spring into action
        # and revive the 'dead' machine.

        boot_id = self.client.get_boot_id()
        self.client.run('(sleep 2;sudo halt) &')
        logging.debug('Calling wait_down()')
        self.client.wait_down(old_boot_id=boot_id)
        logging.debug('Done.')
        logging.debug('Calling wait_up()')
        self.client.wait_up()
        logging.debug('Done.')
        # Have to re-install this every time because we lose it as part
        # of the roll-back to clean state.
        self.invalidate_install_path()
        self.install_fuzzer()
        # FIXME this just waits until, what, sshd is up? Ought to wait until
        # something like, UI is completely started?
        return True


    # TODO take first-test/last-test params here and enable parallelism
    # at the autotest layer?
    def run_once(self, host=None, frag_len=100):
        """Run dbusfuzzer on the specified remote host. Fragment
           the run into chunks of frag_len, each invoked seperately
           over the (ssh) connection.

           E.g. with a frag_len of 10, the first ssh into the remote host
           will run fuzzer test cases 0-9, then return.  Adjusting frag_len
           allows you to trade off between the overhead of each ssh and
           issues like detecting hangs/using reasonable timeouts.
         """
        self.client = host

        first_test = 0
        last_test = frag_len - 1
        done = False
        # It is possible that the attempt to run this frag_len chunk
        # of tests will catastrophically fail. In that situation we
        # want to retry once but not make the mistake of infinite
        # retries which make zero forward progress through our
        # test cases. So, 'in_full_retry' tracks whether we are already
        # on our 2nd-chance trying to restart a given chunk of tests.
        in_full_retry = False
        crashers = [] # An array of test numbers which led to crashes.
        while not done:
            self.bounce_client()
            (passed, stopped_at) = self.run_fuzzer(start_at=first_test,
                                                   stop_at=last_test)
            if passed and stopped_at < last_test:
                # This iteration stopped early, without any failures, which
                # means we're out of tests.
                done = True
                continue
            if not passed:
                # We stopped short due to a failure. Record the failure and
                # resume at the next test.
                logging.info("Crash detected with test case ", stopped_at)
                crashers.append(stopped_at)
                if stopped_at < first_test:
                    # Catastrophic failure. Need to try the whole
                    # chunk again.  in_full_retry lets us detect if
                    # we're infinite-looping on such a retry:
                    if not in_full_retry:
                        in_full_retry = True
                        # Avoid incrementing test#.
                        continue
                    # Don't do a full retry while already in
                    # one. Infinite loop. Give up.
                    logging.error("Abort: infinite retry on tests %d-%d." %
                                  (first_test, last_test))
                    raise error.TestError('Catastrophic failure.')

            # If we get here, maybe we passed, maybe we failed, but
            # either way we know we made progress, and we know where
            # to pick up on the next iteration.
            first_test = stopped_at + 1
            last_test = first_test + frag_len - 1
            in_full_retry = False

        if crashers:
            raise error.TestFail('Crashes detected.')
