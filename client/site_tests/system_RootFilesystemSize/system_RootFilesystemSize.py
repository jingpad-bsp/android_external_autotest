import commands, math, re
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

class system_RootFilesystemSize(test.test):
    version = 1


    def run_once(self):
        # Report the production size
        f = open('/root/bytes-rootfs-prod', 'r')
        self.write_perf_keyval({'bytes_rootfs_prod': float(f.read())})
        f.close()

        # Report the current (test) size
        (status, output) = commands.getstatusoutput(
            'df -B1 / | tail -1 | awk \'{ print $3 }\'')
        if status != 0:
            raise error.TestFail('Could not get size of rootfs')

        self.write_perf_keyval({'bytes_rootfs_test': float(output)})
