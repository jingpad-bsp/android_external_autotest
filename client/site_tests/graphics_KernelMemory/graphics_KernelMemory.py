# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging, time
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error


class graphics_KernelMemory(test.test):
    """
    Reads from sysfs to determine kernel gem objects and memory info.
    """
    version = 1

    # These are sysfs fields that will be read by this test.  For different
    # architectures, the sysfs field paths are different.  The "paths" are given
    # as lists of strings because the actual path may vary depending on the
    # system.  This test will read from the first sysfs path in the list that is
    # present.
    # e.g. ".../memory" vs ".../gpu_memory" -- if the system has either one of
    # these, the test will read from that path.

    exynos_fields = {
        'gem_objects' : ['/sys/kernel/debug/dri/0/exynos_gem_objects'],
        'memory'      : ['/sys/class/misc/mali0/device/memory',
                         '/sys/class/misc/mali0/device/gpu_memory'],
    }
    tegra_fields = {
        'memory': ['/sys/kernel/debug/memblock/memory'],
    }
    x86_fields = {
        'gem_objects' : ['/sys/kernel/debug/dri/0/i915_gem_objects'],
        'memory'      : ['/sys/kernel/debug/dri/0/i915_gem_gtt'],
    }
    arch_fields = {
        'exynos5' : exynos_fields,
        'tegra'   : tegra_fields,
        'i386'    : x86_fields,
        'x86_64'  : x86_fields,
    }


    def run_once(self):
        num_errors = 0
        keyvals = {}

        # Get architecture type and list of sysfs fields to read.
        arch = utils.get_cpu_soc_family()

        if not arch in self.arch_fields:
            raise error.TestFail('Architecture "%s" not yet supported.' % arch)
        test_fields = self.arch_fields[arch]

        # TODO(ihf): We want to give this test something well-defined to
        # measure. For now that will be the CrOS login-screen memory use.
        # We could also log into the machine using telemetry, but that is
        # still flaky. So for now we, lame as we are, just sleep a bit.
        time.sleep(10.0)

        for field_name in test_fields:
            possible_field_paths = test_fields[field_name]
            field_value = None
            for path in possible_field_paths:
                if utils.system('ls %s' % path):
                    continue
                field_value = utils.system_output('cat %s' % path)
                break

            if not field_value:
                logging.error('Unable to find any sysfs paths for field "%s"',
                              field_name)
                num_errors += 1
                continue

            parsed_results = self._parse_sysfs(field_value)

            for key in parsed_results:
                keyvals['%s_%s' % (field_name, key)] = parsed_results[key]
                self.output_perf_value(description='%s_%s' % (field_name, key),
                               value=parsed_results[key], units='bytes',
                               higher_is_better=False)

            if 'bytes' in parsed_results and parsed_results['bytes'] == 0:
                logging.error('%s reported 0 bytes', field_name)
                num_errors += 1

        self.write_perf_keyval(keyvals)

        if num_errors > 0:
            raise error.TestFail('Test failed with %d errors' % num_errors)


    def _parse_sysfs(self, output):
        """
        Parses output of graphics memory sysfs to determine the number of
        buffer objects and bytes.

        Arguments:
            output      Unprocessed sysfs output
        Return value:
            Dictionary containing integer values of number bytes and objects.
            They may have the keys 'bytes' and 'objects', respectively.  However
            the result may not contain both of these values.
        """
        results = {}
        labels = ['bytes', 'objects']

        for line in output.split('\n'):
            # Strip any commas to make parsing easier.
            line_words = line.replace(',', '').split()

            prev_word = None
            for word in line_words:
                # When a label has been found, the previous word should be the
                # value.  e.g. "3200 bytes"
                if word in labels and word not in results and prev_word:
                    logging.info(prev_word)
                    results[word] = int(prev_word)

                prev_word = word

            # Once all values has been parsed, return.
            if len(results) == len(labels):
                return results

        return results
