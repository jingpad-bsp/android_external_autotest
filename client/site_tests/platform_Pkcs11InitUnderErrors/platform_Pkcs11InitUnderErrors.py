# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, shutil

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import pkcs11

class Pkcs11InitFailure(error.TestError):
    pass


class platform_Pkcs11InitUnderErrors(test.test):
    version = 1

    def __delete_if_exists(self, path):
        if os.path.exists(path):
            os.remove(path)


    def __try_manual_init(self, test_desc):
        """Manually request PKCS#11 initialization. And wait for it to finish.

        Will raise TestFail exception with |desc| on failure.

        Args:
          test_desc: string description of test being run.
        """
        try:
            pkcs11.ensure_initial_state()
            pkcs11.init_pkcs11()
            if not pkcs11.verify_pkcs11_initialized():
                raise error.TestFail('Initialized token failed checks!')
        except Exception, e:
            logging.error('PKCS#11 initialization failed for test - "%s"',
                          test_desc)
            logging.error('Failure reason: %s', e)
            raise error.TestFail('PKCS#11 initialization failed for: %s' %
                                 test_desc)

    def __test_erase_everything(self):
        shutil.rmtree(pkcs11.USER_TOKEN_DIR, ignore_errors=True)
        shutil.rmtree(pkcs11.PKCS11_DIR, ignore_errors=True)
        self.__try_manual_init(test_desc='Erase both token and PKCS#11 files')


    def __test_erase_token(self):
        shutil.rmtree(pkcs11.USER_TOKEN_DIR, ignore_errors=True)
        self.__try_manual_init(test_desc='Erase user token in %s' %
                               pkcs11.USER_TOKEN_DIR)


    def __test_erase_pkcs11dir(self):
        shutil.rmtree(pkcs11.PKCS11_DIR, ignore_errors=True)
        self.__try_manual_init(test_desc='Erase PKCS#11 files in %s' %
                               pkcs11.PKCS11_DIR)


    def __test_broken_symlinks(self):
        symlinks_list = ['tpm/chronos', 'tpm/ipsec', 'tpm/root']
        for link in symlinks_list:
            self.__delete_if_exists(os.path.join(pkcs11.PKCS11_DIR, link))
        self.__try_manual_init(test_desc='Broken symlinks in %s' %
                               pkcs11.PKCS11_DIR)


    def __test_missing_token_files(self):
        token_file_list = ['NVTOK.DAT', 'TOK_OBJ/OBJ.IDX', 'TOK_OBJ/30000000']
        for f in token_file_list:
            self.__delete_if_exists(os.path.join(pkcs11.USER_TOKEN_DIR, f))
        self.__try_manual_init(test_desc='Missing token files in %s' %
                               pkcs11.USER_TOKEN_DIR)


    def __test_corrupt_token(self):
        # Overwrite some user token files with NULL bytes.
        token_file_list = ['TOK_OBJ/OBJ.IDX', 'TOK_OBJ/00000000',
                           'TOK_OBJ/70000000']
        for f in token_file_list:
            utils.system(
                'dd if=/dev/zero of=%s bs=1 count=1000 >/dev/null 2>&1' %
                os.path.join(pkcs11.USER_TOKEN_DIR, f))
        self.__try_manual_init(test_desc='Corrupt token files in %s' %
                               pkcs11.USER_TOKEN_DIR)


    def run_once(self):
        if pkcs11.is_chaps_enabled():
            return
        self.__test_erase_everything()
        self.__test_erase_token()
        self.__test_erase_pkcs11dir()
        self.__test_broken_symlinks()
        self.__test_missing_token_files()
        self.__test_corrupt_token()
