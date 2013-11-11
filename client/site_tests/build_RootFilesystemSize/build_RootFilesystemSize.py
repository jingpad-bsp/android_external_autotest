import commands
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

class build_RootFilesystemSize(test.test):
    """Test that we have a minimal amount of free space on rootfs."""
    version = 1


    def run_once(self):
        """Run the free space on rootfs test."""

        # Report the production size.
        f = open('/root/bytes-rootfs-prod', 'r')
        self.write_perf_keyval({'bytes_rootfs_prod': float(f.read())})
        f.close()

        # Report the current (test) size.
        (status, output) = commands.getstatusoutput(
            'df -B1 / | tail -1')
        if status != 0:
            raise error.TestFail('Could not get size of rootfs')

        # Expected output format:
        #                Total      Used Available
        # rootfs    1056858112 768479232 288378880 73% /
        output_columns = output.split()
        used = output_columns[2]
        free = output_columns[3]

        self.write_perf_keyval({'bytes_rootfs_test': float(used)})

        # Fail if we are running out of free space on rootfs.
        required_free_space = 40 * 1024 * 1024

        if int(free) < required_free_space:
            raise error.TestFail('%s bytes free is less than the %s required.' %
                                 (free, required_free_space))
