# Copied the test over from client/tests. The upstream test relies on make
# and perl. I wanted to avoid that. I also wanted to run each benchmark
# individually so that we can tune the runs to be as deterministic as
# possible (using taskset, nice, etc). I also wanted to be able to
# break up the test so that we can run individual tests.

import os
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class kernel_Lmbench(test.test):
    version = 1

    def _lat_ctx(self, processes):
        """
        Run lat_ctx with 0 kbyte messages (-s 0).

        To improve determinism, we use taskset to pin to a CPU and
        nice to prevent another process from being scheduled between
        lat_ctx processes.

        For further details on lat_ctx (output format, etc) see:
        http://lmbench.sourceforge.net/man/lat_ctx.8.html
        """
        cmd = '%s/bin/lat_ctx -s 0 %s' % (self.srcdir, processes)
        out = utils.system_output('taskset 0x1 nice -20 %s 2>&1' % cmd)
        return float(out.split()[-1])


    def initialize(self):
        self.job.require_gcc()


    def setup(self, tarball='lmbench3.tar.bz2'):
        """
        Install lmbench.

        Uncompresses the original lmbench tarball, applies patches to fix
        some build issues, configures lmbench and then modifies the config
        files to use appropriate directory and file locations.

        @param tarball: Lmbench tarball.
        @see: http://www.bitmover.com/lm/lmbench/lmbench3.tar.gz
                (original tarball, shipped as is in autotest).
        """
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)
        pwd = os.getcwd()
        os.chdir(self.srcdir)
        patches = ['0001-Fix-build-issues-with-lmbench.patch',
                   '0002-Changing-shebangs-on-lmbench-scripts.patch',
                   '0003-makefile.patch']
        for patch in patches:
            utils.system('patch -p1 < ../%s' % patch)
        # Set OS='' to avoid create a host-specific bin directory
        utils.make('OS=')
        os.chdir(pwd)


    def run_once(self):
        # For now just run lat_ctx but plan to add more tests
        result = self._lat_ctx(processes=8)
        self.write_perf_keyval({'lat_ctx_s0_p8': result})
