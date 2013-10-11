# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

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

        fields = ['%s-' +  '%s_min_%s_lat-usec' % (io, typ),
                  '%s-' +  '%s_max_%s_lat-usec' % (io, typ),
                  '%s-' + '%s_mean_%s_lat-usec' % (io, typ),
                  '%s-' + '%s_stdv_%s_lat-usec' % (io, typ)]
        for field, idx in zip(fields, idxs):
            self._fio_table.append((field, idx, self._parse_gen))


    def _append_percentiles(self, idxs, io):
        """
        Appends repetitive percentile fields to self._fio_table.

        @param idxs: range of field indexes to use for the map.
        @param io: I/O type: rd or wr

        """

        for i in idxs:
            field = '%s-' + '%s_lat_' % io + '%.2f_percent-usec'
            self._fio_table.append((field, i, self._parse_percentile))


    def _build_fio_2_0_table(self):
        """
        Creates map from field name to fio output index and parse function.

        """

        # General fio Job Info:
        self._fio_table.extend([
                ('%s-fio_version'                  ,   1,    self._parse_gen),
                ('%s-groupid'                      ,   3,    self._parse_gen),
                ('%s-error'                        ,   4,    self._parse_gen)])

        # Results of READ Status:
        self._fio_table.extend([
                ('%s-rd_total_io-KB'               ,   5,    self._parse_gen),
                ('%s-rd_bw-KB_sec'                 ,   6,    self._parse_gen),
                ('%s-rd-IOPS'                      ,   7,    self._parse_gen),
                ('%s-rd_runtime-msec'              ,   8,    self._parse_gen)])
        self._append_stats(range( 9, 13), 'rd', 'submitted')
        self._append_stats(range(13, 17), 'rd', 'completed')
        self._append_percentiles(range(17, 37), 'rd')
        self._append_stats(range(37, 41), 'rd',  'total')
        self._fio_table.extend([
                ('%s-rd_min_bw-KB_sec'             ,  41,    self._parse_gen),
                ('%s-rd_max_bw-KB_sec'             ,  42,    self._parse_gen),
                ('%s-rd-percent'                   ,  43,    self._parse_gen),
                ('%s-rd_mean_bw-KB_sec'            ,  44,    self._parse_gen),
                ('%s-rd_stdev_bw-KB_sec'           ,  45,    self._parse_gen)])

        # Results of WRITE Status:
        self._fio_table.extend([
                ('%s-wr_total_io-KB'               ,  46,    self._parse_gen),
                ('%s-wr_bw-KB_sec'                 ,  47,    self._parse_gen),
                ('%s-wr-IOPS'                      ,  48,    self._parse_gen),
                ('%s-wr_runtime-msec'              ,  49,    self._parse_gen)])
        self._append_stats(range(50, 54), 'wr', 'submitted')
        self._append_stats(range(54, 58), 'wr', 'completed')
        self._append_percentiles(range(58, 78), 'wr')
        self._append_stats(range(78, 82), 'wr',  'total')
        self._fio_table.extend([
                ('%s-wr_min_bw-KB_sec'             ,  82,    self._parse_gen),
                ('%s-wr_max_bw-KB_sec'             ,  83,    self._parse_gen),
                ('%s-wr-percent'                   ,  84,    self._parse_gen),
                ('%s-wr_mean_bw-KB_sec'            ,  85,    self._parse_gen),
                ('%s-wr_stdv_bw-KB_sec'            ,  86,    self._parse_gen)])

        # Other Results:
        self._fio_table.extend([
                ('%s-cpu_usg_usr-percent'          ,  87,    self._parse_gen),
                ('%s-cpu_usg_sys-percent'          ,  88,    self._parse_gen),
                ('%s-cpu_context_sw-percent'       ,  89,    self._parse_gen),
                ('%s-major_page_faults'            ,  90,    self._parse_gen),
                ('%s-minor_page_faults'            ,  91,    self._parse_gen),
                ('%s-io_depth_le_1-percent'        ,  92,    self._parse_gen),
                ('%s-io_depth_2-percent'           ,  93,    self._parse_gen),
                ('%s-io_depth_4-percent'           ,  94,    self._parse_gen),
                ('%s-io_depth_8-percent'           ,  95,    self._parse_gen),
                ('%s-io_depth_16-percent'          ,  96,    self._parse_gen),
                ('%s-io_depth_32-percent'          ,  97,    self._parse_gen),
                ('%s-io_depth_ge_64-percent'       ,  98,    self._parse_gen),
                ('%s-io_lats_le_2_usec-percent'    ,  99,    self._parse_gen),
                ('%s-io_lats_4_usec-percent'       , 100,    self._parse_gen),
                ('%s-io_lats_10_usec-percent'      , 101,    self._parse_gen),
                ('%s-io_lats_20_usec-percent'      , 102,    self._parse_gen),
                ('%s-io_lats_50_usec-percent'      , 103,    self._parse_gen),
                ('%s-io_lats_100_usec-percent'     , 104,    self._parse_gen),
                ('%s-io_lats_250_usec-percent'     , 105,    self._parse_gen),
                ('%s-io_lats_500_usec-percent'     , 106,    self._parse_gen),
                ('%s-io_lats_750_usec-percent'     , 107,    self._parse_gen),
                ('%s-io_lats_1000_usec-percent'    , 108,    self._parse_gen),
                ('%s-io_lats_le_2_msec-percent'    , 109,    self._parse_gen),
                ('%s-io_lats_4_msec-percent'       , 110,    self._parse_gen),
                ('%s-io_lats_10_msec-percent'      , 111,    self._parse_gen),
                ('%s-io_lats_20_msec-percent'      , 112,    self._parse_gen),
                ('%s-io_lats_50_msec-percent'      , 113,    self._parse_gen),
                ('%s-io_lats_100_msec-percent'     , 114,    self._parse_gen),
                ('%s-io_lats_250_msec-percent'     , 115,    self._parse_gen),
                ('%s-io_lats_500_msec-percent'     , 116,    self._parse_gen),
                ('%s-io_lats_750_msec-percent'     , 117,    self._parse_gen),
                ('%s-io_lats_1000_msec-percent'    , 118,    self._parse_gen),
                ('%s-io_lats_2000_msec-percent'    , 119,    self._parse_gen),
                ('%s-io_lats_gt_2000_msec-percent' , 120,    self._parse_gen),

                # Disk Utilization: only boot disk is tested
                ('%s-disk_name'                    , 121,    self._parse_gen),
                ('%s-rd_ios'                       , 122,    self._parse_gen),
                ('%s-wr_ios'                       , 123,    self._parse_gen),
                ('%s-rd_merges'                    , 124,    self._parse_gen),
                ('%s-wr_merges'                    , 125,    self._parse_gen),
                ('%s-rd_ticks'                     , 126,    self._parse_gen),
                ('%s-wr_ticks'                     , 127,    self._parse_gen),
                ('%s-time_in_queue'                , 128,    self._parse_gen),
                ('%s-disk_util-percent'            , 129,    self._parse_gen)])


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
        version = fio_version(data[1])
        version_2x = ['2.0', '2.1']

        if version[0:3] in version_2x:
            self._build_fio_2_0_table()
        else:
            raise fio_parser_exception('fio-%s output unsupported.'
               'fio_parser supports version(s) %s' % (version, version_2x))

        # Fill dictionary object.
        self._job_name = data[2]
        for field, idx, parser in self._fio_table:
            parser(self._job_name, field, data[idx])
