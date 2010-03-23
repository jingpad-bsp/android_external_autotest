# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class firmware_VbootCrypto(test.test):
    """
    Tests for correctness of verified boot reference crypto implementation.
    """
    version = 1
    preserve_srcdir = True

    def setup(self):
        os.chdir(self.srcdir)
        utils.system('make clean all')


    # Parses the [result] and output the key-value pairs.
    def __output_result_keyvals(self, results):
        for keyval in results.splitlines():
            if keyval.strip().startswith('#'):
                continue
            key, val = keyval.split(':')
            self.keyvals[key.strip()] = float(val)


    def __generate_test_cases(self):
        gen_test_case_cmd = os.path.join(self.srcdir, "tests",
                                         "gen_test_cases.sh")
        return_code = utils.system(gen_test_case_cmd, ignore_status = True)
        if return_code == 255:
            return False
        if return_code == 1:
            raise error.TestError("Couldn't generate test cases")
        return True


    def __sha_test(self):
        sha_test_cmd = os.path.join(self.srcdir, "tests", "sha_tests")
        return_code = utils.system(sha_test_cmd, ignore_status=True)
        if return_code == 255:
            return False
        if return_code == 1:
            raise error.TestError("SHA Test Error")
        return True


    def __rsa_test(self):
        os.chdir(self.srcdir)
        rsa_test_cmd = os.path.join(self.srcdir, "tests",
                                    "run_rsa_tests.sh")
        return_code = utils.system(rsa_test_cmd, ignore_status=True)
        if return_code == 255:
            return False
        if return_code == 1:
            raise error.TestError("RSA Test Error")
        return True


    def __image_verification_test(self):
        image_verification_cmd = "cd %s && ./run_image_verification_tests.sh" \
                                 % os.path.join(self.srcdir, "tests")
        return_code = utils.system(image_verification_cmd,
                                   ignore_status=True)
        if return_code == 255:
            return False
        if return_code == 1:
            raise error.TestError("Image Verification Test Error")
        return True


    def __sha_benchmark(self):
        sha_benchmark_cmd = os.path.join(self.srcdir, "tests",
                                         "sha_benchmark")
        self.results = utils.system_output(sha_benchmark_cmd,
                                           retain_output=True)
        self.__output_result_keyvals(self.results)


    def __rsa_benchmark(self):
        rsa_benchmark_cmd = "cd %s && ./rsa_verify_benchmark" % \
                            os.path.join(self.srcdir, "tests")
        self.results = utils.system_output(rsa_benchmark_cmd,
                                           retain_output=True)
        self.__output_result_keyvals(self.results)


    def __verify_image_benchmark(self):
        firmware_benchmark_cmd = "cd %s && ./firmware_verify_benchmark" % \
                                 os.path.join(self.srcdir, "tests");
        kernel_benchmark_cmd = "cd %s && ./kernel_verify_benchmark" % \
                                 os.path.join(self.srcdir, "tests");
        self.results = utils.system_output(firmware_benchmark_cmd,
                                           retain_output=True)
        self.__output_result_keyvals(self.results)
        self.results = utils.system_output(kernel_benchmark_cmd,
                                           retain_output=True)
        self.__output_result_keyvals(self.results)


    def run_once(self):
        self.keyvals = {}
        self.__generate_test_cases()
        success = self.__sha_test()
        if not success:
            raise error.TestFail("SHA Test Failed")
        success = self.__rsa_test()
        if not success:
            raise error.TestFail("RSA Test Failed")
        success = self.__image_verification_test()
        if not success:
            raise error.TestFail("Image Verification Test Failed")
        self.__sha_benchmark()
        self.__rsa_benchmark()
        self.__verify_image_benchmark()
        self.write_perf_keyval(self.keyvals)
