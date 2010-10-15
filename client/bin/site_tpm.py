# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dircache, logging, os, utils, time
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

TPM_TSS_VERSION = "1.2"
TPM_OWNER_SECRET = "owner123"
TPM_SRK_SECRET = "srk123"

# These tests fail on the most important dogfood hardware (as of 10/10/10).

excluded_tests = [
        "Tspi_Context_GetRegisteredKeysByUUID01",
        "Tspi_Context_GetRegisteredKeysByUUID2_01",
        "Tspi_Context_LoadKeyByUUID03",
        "Tspi_Context_UnregisterKey03",
        "Tspi_NV_DefineSpace04",
        "Tspi_NV_DefineSpace11",
        "Tspi_NV_DefineSpace12",
        "Tspi_TPM_LoadMaintenancePubKey01",
        "Tspi_TPM_SetStatus01",
        "Tspi_Key_UnloadKey-trans01",
        "Tspi_Key_UnloadKey-trans02",
        "Tspi_NV_ReadValue-trans01",
        "Tspi_NV_ReadValue-trans02",
        "Tspi_NV_WriteValue-trans01",
        "Tspi_NV_WriteValue-trans02",
        "Tspi_TPM_CheckMaintenancePubKey-trans01",
        "Tspi_TPM_CheckMaintenancePubKey-trans02",
        "Tspi_TPM_CheckMaintenancePubKey-trans03",
        "Tspi_TPM_CreateMaintenanceArchive-trans01",
        "Tspi_TPM_CreateMaintenanceArchive-trans02",
        "Tspi_TPM_CreateMaintenanceArchive-trans03",
        "Tspi_TPM_Delegate_VerifyDelegation-trans03",
        "Tspi_TPM_GetAuditDigest-trans01",
        "Tspi_TPM_GetAuditDigest-trans02",
        "Tspi_TPM_GetAuditDigest-trans03",
        "Tspi_TPM_GetPubEndorsementKey-trans01",
        "Tspi_TPM_GetPubEndorsementKey-trans02",
        "Tspi_TPM_GetPubEndorsementKey-trans03",
        "Tspi_TPM_KillMaintenanceFeature-trans01",
        "Tspi_TPM_KillMaintenanceFeature-trans02",
        "Tspi_TPM_KillMaintenanceFeature-trans03",
        "Tspi_TPM_LoadMaintenancePubKey-trans01",
        "Tspi_TPM_LoadMaintenancePubKey-trans02",
        "Tspi_TPM_LoadMaintenancePubKey-trans03",
        "Tspi_TPM_OwnerGetSRKPubKey-trans01",
        "Tspi_TPM_OwnerGetSRKPubKey-trans02",
        "Tspi_TPM_SetOperatorAuth-trans01",
        "Tspi_TPM_SetOperatorAuth-trans02",
        "Tspi_TPM_SetOperatorAuth-trans03",
        "Tspi_TPM_SetStatus-trans01",
        "Tspi_TPM_SetStatus-trans02",
        "Tspi_TPM_SetStatus-trans03",
        "Tspi_ChangeAuthAsym01",
        "Tspi_ChangeAuthAsym02",
        "Tspi_ChangeAuthAsym03",
        "Tspi_GetAttribData17",
        "Tspi_SetAttribData01",
        "Tspi_Hash_TickStampBlob01",
        "Tspi_Context_GetCapability18",
        "Tspi_TPM_CollateIdentityRequest01",
        "Tspi_TPM_CollateIdentityRequest-trans01",
        "Tspi_TPM_CollateIdentityRequest-trans02",
        "Tspi_TPM_CollateIdentityRequest-trans03",
        # bad tests (incorrect exit code)
        "Tspi_NV_WriteValue-trans03",
        "Tspi_TPM_Delegate_VerifyDelegation-trans01",
        "Tspi_TPM_Delegate_VerifyDelegation-trans02",
]

def run_trousers_tests(bindir):
        # Special return codes from trousers tests.
        TEST_RETURN_SUCCESS = 0
        TEST_RETURN_NOT_IMPLEMENTED = 6
        TEST_RETURN_NOT_APPLICABLE = 126

        num_tests_considered = 0
        num_tests_passed = 0
        num_tests_failed = 0
        num_tests_not_implemented = 0
        num_tests_not_applicable = 0

        os.putenv('TESTSUITE_OWNER_SECRET', TPM_OWNER_SECRET)
        os.putenv('TESTSUITE_SRK_SECRET', TPM_SRK_SECRET)

        for test in dircache.listdir(bindir):
            if test in excluded_tests:
                    logging.info('Skipping test: %s' % test)
                    continue
            logging.info('Running test: %s' % test)
            num_tests_considered = num_tests_considered + 1
            return_code = utils.system('%s/%s -v %s' %
                                       (bindir, test, TPM_TSS_VERSION),
                                       timeout=180,  # In seconds
                                       ignore_status=True  # Want return code
                                       )
            logging.info('-- Return code: %d (%s)' % (return_code, test))
            if return_code == TEST_RETURN_SUCCESS:
                num_tests_passed = num_tests_passed + 1
            elif return_code == TEST_RETURN_NOT_IMPLEMENTED:
                num_tests_not_implemented = num_tests_not_implemented + 1
            elif return_code == TEST_RETURN_NOT_APPLICABLE:
                num_tests_not_applicable = num_tests_not_applicable + 1
            else:
                num_tests_failed = num_tests_failed + 1

        logging.info('Considered %d tests.' % num_tests_considered)
        logging.info('-- Passed: %d' % num_tests_passed)
        logging.info('-- Failed: %d' % num_tests_failed)
        logging.info('-- Not Implemented: %d' % num_tests_not_implemented)
        logging.info('-- Not Applicable: %d' % num_tests_not_applicable)

        if num_tests_failed != 0:
            raise error.TestError('Test failed (%d failures)' %
                                  num_tests_failed)
