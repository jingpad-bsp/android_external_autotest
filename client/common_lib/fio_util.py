# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Library to run fio scripts.

fio_runner launch fio and collect results.
The output dictionary can be add to autotest keyval:
        results = {}
        results.update(fio_util.fio_runner(job_file, env_vars))
        self.write_perf_keyval(results)

Decoding class can be invoked independently.

"""

import logging, utils
from UserDict import UserDict

class fio_parser_exception(Exception):
    """
    Exception class for fio_job_output.

    """

    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)


def fio_version(version_line):
    """
    Strip 'fio-' prefix from self-reported version

    @param version_line: first line of fio output should be version.

    @raises fio_parser_exception when prefix isn't "fio-" as expected.

    """

    if version_line[0:4] == "fio-":
        return version_line[4:]
    raise fio_parser_exception('fio version not found:  %s' % version_line)


class fio_job_output(UserDict):
    """
    Dictionary class to hold the fio output.

    This class accepts fio output as a list of values.

    """

    def _parse_gen(self, job, field, val):
        """
        Parses a regular field and adds it to the dictionary.

        @param job: fio job name.
        @param field: fio output field name.
        @param val: fio output field value.

        """

        self[field % job] = val


    def _parse_percentile(self, job, field, val):
        """
        Parses a percentile field and adds it to the dictionary.

        @param job: fio job name.
        @param field: fio output field name.
        @param val: fio output field value.

        """

        prc = float(val.split('=')[0].strip('%'))
        self[field % (job, prc)] = val.split('=')[1]


    def _append_stats(self, idxs, io, typ):
        """
        Appends repetitive statistics fields to self._fio_table.

        @param idxs: range of field indexes to use for the map.
        @param io: I/O type: rd or wr
        @param typ: latency type: submission or completion.

        """

        fields = ['_%s_' + '%s_min_%s_lat_usec' % (io, typ),
                  '_%s_' + '%s_max_%s_lat_usec' % (io, typ),
                  '_%s_' + '%s_mean_%s_lat_usec' % (io, typ),
                  '_%s_' + '%s_stdv_%s_lat_usec' % (io, typ)]
        for field, idx in zip(fields, idxs):
            self._fio_table.append((field, idx, self._parse_gen))


    def _append_percentiles(self, idxs, io):
        """
        Appends repetitive percentile fields to self._fio_table.

        @param idxs: range of field indexes to use for the map.
        @param io: I/O type: rd or wr

        """

        for i in idxs:
            field = '_%s_' + '%s_lat_' % io + '%.2f_percent_usec'
            self._fio_table.append((field, i, self._parse_percentile))


    def _build_fio_terse_4_table(self):
        """
        Creates map from field name to fio output index and parse function.

        """

        # General fio Job Info:
        self._fio_table.extend([
                ('_%s_fio_version'                  , 1, self._parse_gen),
                ('_%s_groupid'                      , 3, self._parse_gen),
                ('_%s_error'                        , 4, self._parse_gen)])

        # Results of READ Status:
        self._fio_table.extend([
                ('_%s_rd_total_io_KB'               , 5, self._parse_gen),
                ('_%s_rd_bw_KB_sec'                 , 6, self._parse_gen),
                ('_%s_rd_IOPS'                      , 7, self._parse_gen),
                ('_%s_rd_runtime_msec'              , 8, self._parse_gen)])
        self._append_stats(range(9, 13), 'rd', 'submitted')
        self._append_stats(range(13, 17), 'rd', 'completed')
        self._append_percentiles(range(17, 37), 'rd')
        self._append_stats(range(37, 41), 'rd', 'total')
        self._fio_table.extend([
                ('_%s_rd_min_bw_KB_sec'             , 41, self._parse_gen),
                ('_%s_rd_max_bw_KB_sec'             , 42, self._parse_gen),
                ('_%s_rd_percent'                   , 43, self._parse_gen),
                ('_%s_rd_mean_bw_KB_sec'            , 44, self._parse_gen),
                ('_%s_rd_stdev_bw_KB_sec'           , 45, self._parse_gen)])

        # Results of WRITE Status:
        self._fio_table.extend([
                ('_%s_wr_total_io_KB'               , 46, self._parse_gen),
                ('_%s_wr_bw_KB_sec'                 , 47, self._parse_gen),
                ('_%s_wr_IOPS'                      , 48, self._parse_gen),
                ('_%s_wr_runtime_msec'              , 49, self._parse_gen)])
        self._append_stats(range(50, 54), 'wr', 'submitted')
        self._append_stats(range(54, 58), 'wr', 'completed')
        self._append_percentiles(range(58, 78), 'wr')
        self._append_stats(range(78, 82), 'wr', 'total')
        self._fio_table.extend([
                ('_%s_wr_min_bw_KB_sec'             , 82, self._parse_gen),
                ('_%s_wr_max_bw_KB_sec'             , 83, self._parse_gen),
                ('_%s_wr_percent'                   , 84, self._parse_gen),
                ('_%s_wr_mean_bw_KB_sec'            , 85, self._parse_gen),
                ('_%s_wr_stdv_bw_KB_sec'            , 86, self._parse_gen)])

        # Results of TRIM Status:
        self._fio_table.extend([
                ('_%s_tr_total_io_KB'               , 87, self._parse_gen),
                ('_%s_tr_bw_KB_sec'                 , 88, self._parse_gen),
                ('_%s_tr_IOPS'                      , 89, self._parse_gen),
                ('_%s_tr_runtime_msec'              , 90, self._parse_gen)])
        self._append_stats(range(91, 95), 'tr', 'submitted')
        self._append_stats(range(95, 99), 'tr', 'completed')
        self._append_percentiles(range(99, 119), 'tr')
        self._append_stats(range(119, 123), 'tr', 'total')
        self._fio_table.extend([
                ('_%s_tr_min_bw_KB_sec'             , 123, self._parse_gen),
                ('_%s_tr_max_bw_KB_sec'             , 124, self._parse_gen),
                ('_%s_tr_percent'                   , 125, self._parse_gen),
                ('_%s_tr_mean_bw_KB_sec'            , 126, self._parse_gen),
                ('_%s_tr_stdv_bw_KB_sec'            , 127, self._parse_gen)])

        # Other Results:
        self._fio_table.extend([
                ('_%s_cpu_usg_usr_percent'          , 128, self._parse_gen),
                ('_%s_cpu_usg_sys_percent'          , 129, self._parse_gen),
                ('_%s_cpu_context_count'            , 130, self._parse_gen),
                ('_%s_major_page_faults'            , 131, self._parse_gen),
                ('_%s_minor_page_faults'            , 132, self._parse_gen),
                ('_%s_io_depth_le_1_percent'        , 133, self._parse_gen),
                ('_%s_io_depth_2_percent'           , 134, self._parse_gen),
                ('_%s_io_depth_4_percent'           , 135, self._parse_gen),
                ('_%s_io_depth_8_percent'           , 136, self._parse_gen),
                ('_%s_io_depth_16_percent'          , 137, self._parse_gen),
                ('_%s_io_depth_32_percent'          , 138, self._parse_gen),
                ('_%s_io_depth_ge_64_percent'       , 139, self._parse_gen),
                ('_%s_io_lats_le_2_usec_percent'    , 140, self._parse_gen),
                ('_%s_io_lats_4_usec_percent'       , 141, self._parse_gen),
                ('_%s_io_lats_10_usec_percent'      , 142, self._parse_gen),
                ('_%s_io_lats_20_usec_percent'      , 143, self._parse_gen),
                ('_%s_io_lats_50_usec_percent'      , 144, self._parse_gen),
                ('_%s_io_lats_100_usec_percent'     , 145, self._parse_gen),
                ('_%s_io_lats_250_usec_percent'     , 146, self._parse_gen),
                ('_%s_io_lats_500_usec_percent'     , 147, self._parse_gen),
                ('_%s_io_lats_750_usec_percent'     , 148, self._parse_gen),
                ('_%s_io_lats_1000_usec_percent'    , 149, self._parse_gen),
                ('_%s_io_lats_le_2_msec_percent'    , 150, self._parse_gen),
                ('_%s_io_lats_4_msec_percent'       , 151, self._parse_gen),
                ('_%s_io_lats_10_msec_percent'      , 152, self._parse_gen),
                ('_%s_io_lats_20_msec_percent'      , 153, self._parse_gen),
                ('_%s_io_lats_50_msec_percent'      , 154, self._parse_gen),
                ('_%s_io_lats_100_msec_percent'     , 155, self._parse_gen),
                ('_%s_io_lats_250_msec_percent'     , 156, self._parse_gen),
                ('_%s_io_lats_500_msec_percent'     , 157, self._parse_gen),
                ('_%s_io_lats_750_msec_percent'     , 158, self._parse_gen),
                ('_%s_io_lats_1000_msec_percent'    , 159, self._parse_gen),
                ('_%s_io_lats_2000_msec_percent'    , 160, self._parse_gen),
                ('_%s_io_lats_gt_2000_msec_percent' , 161, self._parse_gen),

                # Disk Utilization: only boot disk is tested
                ('_%s_disk_name'                    , 162, self._parse_gen),
                ('_%s_rd_ios'                       , 163, self._parse_gen),
                ('_%s_wr_ios'                       , 164, self._parse_gen),
                ('_%s_rd_merges'                    , 165, self._parse_gen),
                ('_%s_wr_merges'                    , 166, self._parse_gen),
                ('_%s_rd_ticks'                     , 167, self._parse_gen),
                ('_%s_wr_ticks'                     , 168, self._parse_gen),
                ('_%s_time_in_queue'                , 169, self._parse_gen),
                ('_%s_disk_util_percent'            , 170, self._parse_gen)])


    def __init__(self, data):
        """
        Fills the dictionary object with the fio output upon instantiation.

        @param data: fio HOWTO documents list of values from fio output.

        @raises fio_parser_exception.

        """

        UserDict.__init__(self)

        # Check that data parameter.
        if len(data) == 0:
            raise fio_parser_exception('No fio output supplied.')

        # Create table that relates field name to fio output index and
        # parsing function to be used for the field.
        self._fio_table = []
        terse_version = int(data[0])
        fio_terse_parser = { 4 : self._build_fio_terse_4_table }

        if terse_version in fio_terse_parser:
            fio_terse_parser[terse_version]()
        else:
            raise fio_parser_exception('fio terse version %s unsupported.'
               'fio_parser supports terse version %s' %
               (terse_version, fio_terse_parser.keys()))

        # Fill dictionary object.
        self._job_name = data[2]
        for field, idx, parser in self._fio_table:
            # Field 162-170 only reported when we test on block device.
            if len(data) <= idx:
                break
            parser(self._job_name, field, data[idx])


def fio_parser(lines):
    """Parse the terse fio output

    This collects all metrics given by fio and labels them according to unit
    of measurement and test case name.

    @param lines: text output of terse fio output.

    """
    # fio version 2.0.8+ outputs all needed information with --minimal
    # Using that instead of the human-readable version, since it's easier
    # to parse.
    # Following is a partial example of the semicolon-delimited output.
    # 3;fio-2.1;quick_write;0;0;0;0;0;0;0;0;0.000000;0.000000;0;0;0.000000;
    # 0.000000;1.000000%=0;5.000000%=0;10.000000%=0;20.000000%=0;
    # ...
    # Refer to the HOWTO file of the fio package for more information.

    results = {}

    # Extract the values from the test.
    for line in lines.splitlines():
        # Put the values from the output into an array.
        values = line.split(';')
        # This check makes sure that we are parsing the actual values
        # instead of the job description or possible blank lines.
        if len(values) <= 128:
            continue
        results.update(fio_job_output(values))

    return results


def fio_runner(job, env_vars):
    """
    Runs fio.

    @param job: fio config file to use
    @param env_vars: environment variable fio will substituete in the fio
        config file.

    @return fio results.

    """

    # running fio with ionice -c 3 so it doesn't lock out other
    # processes from the disk while it is running.
    # If you want to run the fio test for performance purposes,
    # take out the ionice and disable hung process detection:
    # "echo 0 > /proc/sys/kernel/hung_task_timeout_secs"
    # -c 3 = Idle
    # Tried lowest priority for "best effort" but still failed
    ionice = 'ionice -c 3'

    # Using the --minimal flag for easier results parsing
    # Newest fio doesn't omit any information in --minimal
    # Need to set terse-version to 4 for trim related output
    options = ['--minimal', '--terse-version=4']
    fio_cmd_line = ' '.join([env_vars, ionice, 'fio',
                             ' '.join(options),
                             '"' + job + '"'])
    fio = utils.run(fio_cmd_line)

    logging.debug(fio.stdout)
    return fio_parser(fio.stdout)

