# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, re
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class kernel_ConfigVerify(test.test):
    version = 1
    IS_BUILTIN = [
        # Sanity checks; should be present in builds as builtins.
        'INET',
        'MMU',
        'MODULES',
        'PRINTK',
        'SECURITY',
        # Security; adds stack buffer overflow protections.
        'CC_STACKPROTECTOR',
        # Security; enables the SECCOMP application API.
        'SECCOMP',
        # Security; blocks direct physical memory access.
        'STRICT_DEVMEM',
        # Security; provides some protections against SYN flooding.
        'SYN_COOKIES',
        # Security; make sure both PID_NS and NET_NS are enabled
        # for the SUID sandbox.
        'PID_NS',
        'NET_NS',
        # Security; perform additional validation of credentials.
        'DEBUG_CREDENTIALS',
    ]
    IS_MODULE = [
        # Sanity checks; should be present in builds as modules.
        'BLK_DEV_SR',
        'BT',
        'TUN',
    ]
    IS_ENABLED = [
        # Either module or enabled, depending on platform.
        'VIDEO_V4L2',
    ]
    IS_MISSING = [
        # Sanity checks.
        'M386',                 # Never going to optimize to this CPU.
        'CHARLIE_THE_UNICORN',  # Config not in real kernel config var list.
        # Dangerous; allows direct physical memory writing.
        'ACPI_CUSTOM_METHOD',
        # Dangerous; disables brk ASLR.
        'COMPAT_BRK',
        # Dangerous; disables VDSO ASLR.
        'COMPAT_VDSO',
        # Dangerous; allows direct kernel memory writing.
        'DEVKMEM',
        # Dangerous; allows replacement of running kernel.
        'KEXEC',
        # Dangerous; allows replacement of running kernel.
        'HIBERNATION',
    ]
    IS_EXCLUSIVE = [
        # Security; no surprise binary formats.
        {
            'regex': 'BINFMT_',
            'builtin': [
                'BINFMT_ELF',
            ],
            'module': [
            ],
            'missing': [
                # Sanity checks; one disabled, one does not exist.
                'BINFMT_MISC',
                'BINFMT_IMPOSSIBLE',
            ],
        },
        # Security; no surprise filesystem formats.
        {
            'regex': '.*_FS$',
            'builtin': [
                'DEBUG_FS',
                'ECRYPT_FS',
                'EXT4_FS',
                'EXT4_USE_FOR_EXT23',
                'PROC_FS',
                'SCSI_PROC_FS',
            ],
            'module': [
                'FAT_FS',
                'FUSE_FS',
                'HFSPLUS_FS',
                'ISO9660_FS',
                'UDF_FS',
                'VFAT_FS',
            ],
            'missing': [
                # Sanity checks; one disabled, one does not exist.
                'EXT2_FS',
                'EXT3_FS',
                'XFS_FS',
                'IMPOSSIBLE_FS',
            ],
        },
        # Security; no surprise partition formats.
        {
            'regex': '.*_PARTITION$',
            'builtin': [
                'EFI_PARTITION',
                'MSDOS_PARTITION',
            ],
            'module': [
            ],
            'missing': [
                # Sanity checks; one disabled, one does not exist.
                'LDM_PARTITION',
                'IMPOSSIBLE_PARTITION',
            ],
        },
    ]

    def _passed(self, msg):
        logging.info('ok: %s' % (msg))

    def _failed(self, msg):
        logging.error('FAIL: %s' % (msg))
        self._failures.append(msg)

    def _fatal(self, msg):
        logging.error('FATAL: %s' % (msg))
        raise error.TestError(msg)

    def _config_required(self, name, wanted):
        value = self._config.get(name, None)
        if value in wanted:
            self._passed('"%s" was "%s" in kernel config' % (name, value))
        else:
            self._failed('"%s" was "%s" (wanted one of "%s") in kernel config' %
                         (name, value, '|'.join(wanted)))

    def has_value(self, name, value):
        self._config_required('CONFIG_%s' % (name), value)

    def has_builtin(self, name):
        self.has_value(name, ['y'])

    def has_module(self, name):
        self.has_value(name, ['m'])

    def is_enabled(self, name):
        self.has_value(name, ['y', 'm'])

    def is_missing(self, name):
        self.has_value(name, [None])

    # Checks every config line for the exclusive regex and validate existence
    # of expected entries.
    def is_exclusive(self, exclusive):
        expected = set()
        for name in exclusive['missing']:
            self.is_missing(name)
        for name in exclusive['builtin']:
            self.has_builtin(name)
            expected.add('CONFIG_%s' % (name))
        for name in exclusive['module']:
            self.has_module(name)
            expected.add('CONFIG_%s' % (name))

        # Now make sure nothing else with the specified regex exists.
        regex = r'CONFIG_%s' % (exclusive['regex'])
        for name in self._config:
            if not re.match(regex, name):
                continue
            if not name in expected:
                self._failed('"%s" found for "%s" when only "%s" allowed' %
                             (name, regex, "|".join(expected)))

    def load_configs(self, filename):
        # Make sure the given file actually exists.
        if not os.path.exists(filename):
            self._fatal('%s is missing' % (filename))

        # Import kernel config variables into a dictionary for each searching.
        config = dict()
        for item in open(filename).readlines():
            item = item.strip()
            if not '=' in item:
                continue
            key, value = item.split('=', 1)
            config[key] = value

        # Make sure we actually loaded something sensible.
        if len(config) == 0:
            self._fatal('%s has no CONFIG variables' % (filename))

        return config

    def run_once(self):
        # Empty failure list means test passes.
        self._failures = []

        # Cache the architecture to avoid redundant execs to "uname".
        self._arch = utils.get_arch()

        # Locate and load the list of kernel config variables.
        self._config = self.load_configs('/boot/config-%s' %
                                         utils.system_output('uname -r'))

        # Run the static checks.
        map(self.has_builtin, self.IS_BUILTIN)
        map(self.has_module, self.IS_MODULE)
        map(self.is_enabled, self.IS_ENABLED)
        map(self.is_missing, self.IS_MISSING)
        map(self.is_exclusive, self.IS_EXCLUSIVE)

        # Run the dynamic checks.

        # Security; NULL-address hole should be as large as possible.
        # Upstream kernel recommends 64k, which should be large enough to
        # catch nearly all dereferenced structures.
        wanted = '65536'
        if self._arch.startswith('arm'):
            # ... except on ARM where it shouldn't be larger than 32k due
            # to historical ELF load location.
            wanted = '32768'
        self.has_value('DEFAULT_MMAP_MIN_ADDR', [wanted])

        # Security; make sure NX page table bits are usable.
        if not self._arch.startswith('arm'):
            if self._arch == "i386":
                self.has_builtin('X86_PAE')
            else:
                self.has_builtin('X86_64')

        # Security; marks data segments as RO/NX.
        if self._arch.startswith('arm'):
            # TODO(kees): ARM kernel needs the module RO/NX logic added.
            self.is_missing('DEBUG_RODATA')
            self.is_missing('DEBUG_SET_MODULE_RONX')
        else:
            self.has_builtin('DEBUG_RODATA')
            self.has_builtin('DEBUG_SET_MODULE_RONX')

        # Kernel: make sure port 0xED is the one used for I/O delay
        if not self._arch.startswith('arm'):
            self.has_builtin('IO_DELAY_0XED')
            needed = self._config.get('CONFIG_IO_DELAY_TYPE_0XED', None)
            self.has_value('DEFAULT_IO_DELAY_TYPE', [needed])

        # Raise a failure if anything unexpected was seen.
        if len(self._failures):
            raise error.TestFail((", ".join(self._failures)))
