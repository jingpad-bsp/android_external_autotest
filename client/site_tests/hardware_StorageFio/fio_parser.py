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

        fields = ['usec_%s_' +  '%s_min_%s_lat' % (io, typ),
                  'usec_%s_' +  '%s_max_%s_lat' % (io, typ),
                  'usec_%s_' + '%s_mean_%s_lat' % (io, typ),
                  'usec_%s_' + '%s_stdv_%s_lat' % (io, typ)]
        for field, idx in zip(fields, idxs):
            self._fio_table.append((field, idx, self._parse_gen))


    def _append_percentiles(self, idxs, io):
        """
        Appends repetitive percentile fields to self._fio_table.

        @param idxs: range of field indexes to use for the map.
        @param io: I/O type: rd or wr

        """

        for i in idxs:
            field = 'usec_%s_' + '%s_latency_' % io + '%.2f_percent'
            self._fio_table.append((field, i, self._parse_percentile))


    def _build_fio_2_0_table(self):
        """
        Creates map from field name to fio output index and parse function.

        """

        # General fio Job Info:
        self._fio_table.extend([
                ('%s_fio_version'                 ,   1,    self._parse_gen),
                ('%s_groupid'                     ,   3,    self._parse_gen),
                ('%s_error'                       ,   4,    self._parse_gen)])

        # Results of READ Status:
        self._fio_table.extend([
                ('KB_%s_rd_tot_io'                ,   5,    self._parse_gen),
                ('KB_sec_%s_rd_bw'                ,   6,    self._parse_gen),
                ('iops_%s_rd'                     ,   7,    self._parse_gen),
                ('msec_%s_rd_runtime'             ,   8,    self._parse_gen)])
        self._append_stats(range( 9, 13), 'rd', 'submitted')
        self._append_stats(range(13, 17), 'rd', 'completed')
        self._append_percentiles(range(17, 37), 'rd')
        self._append_stats(range(37, 41), 'rd',  'total')
        self._fio_table.extend([
                ('KB_sec_%s_rd_min_bw'            ,  41,    self._parse_gen),
                ('KB_sec_%s_rd_max_bw'            ,  42,    self._parse_gen),
                ('KB_sec_%s_rd_aggr_percent_bw'      ,  43,    self._parse_gen),
                ('KB_sec_%s_rd_mean_bw'           ,  44,    self._parse_gen),
                ('KB_sec_%s_rd_stdev_bw'          ,  45,    self._parse_gen)])

        # Results of WRITE Status:
        self._fio_table.extend([
                ('KB_%s_wr_tot_io'                ,  46,    self._parse_gen),
                ('KB_sec_%s_wr_bw'                ,  47,    self._parse_gen),
                ('iops_%s_wr'                     ,  48,    self._parse_gen),
                ('msec_%s_wr_runtime'             ,  49,    self._parse_gen)])
        self._append_stats(range(50, 54), 'wr', 'submitted')
        self._append_stats(range(54, 58), 'wr', 'completed')
        self._append_percentiles(range(58, 78), 'wr')
        self._append_stats(range(78, 82), 'wr',  'total')
        self._fio_table.extend([
                ('KB_sec_%s_wr_min_bw'            ,  82,    self._parse_gen),
                ('KB_sec_%s_wr_max_bw'            ,  83,    self._parse_gen),
                ('KB_sec_%s_wr_aggr_percent_bw'   ,  84,    self._parse_gen),
                ('KB_sec_%s_wr_mean_bw'           ,  85,    self._parse_gen),
                ('KB_sec_%s_wr_stdv_bw'           ,  86,    self._parse_gen)])

        # Other Results:
        self._fio_table.extend([
                ('percent_%s_cpu_usg_usr'          ,  87,    self._parse_gen),
                ('percent_%s_cpu_usg_sys'          ,  88,    self._parse_gen),
                ('percent_%s_cpu_usg_context_sw'   ,  89,    self._parse_gen),
                ('%s_mjr_faults'                   ,  90,    self._parse_gen),
                ('%s_mnr_faults'                   ,  91,    self._parse_gen),
                ('%s_io_depth_le_1'                ,  92,    self._parse_gen),
                ('%s_io_depth_2'                   ,  93,    self._parse_gen),
                ('%s_io_depth_4'                   ,  94,    self._parse_gen),
                ('%s_io_depth_8'                   ,  95,    self._parse_gen),
                ('%s_io_depth_16'                  ,  96,    self._parse_gen),
                ('%s_io_depth_32'                  ,  97,    self._parse_gen),
                ('%s_io_depth_ge_64'               ,  98,    self._parse_gen),
                ('percent_%s_io_lats_le_2_usec'    ,  99,    self._parse_gen),
                ('percent_%s_io_lats_4_usec'       , 100,    self._parse_gen),
                ('percent_%s_io_lats_10_usec'      , 101,    self._parse_gen),
                ('percent_%s_io_lats_20_usec'      , 102,    self._parse_gen),
                ('percent_%s_io_lats_50_usec'      , 103,    self._parse_gen),
                ('percent_%s_io_lats_100_usec'     , 104,    self._parse_gen),
                ('percent_%s_io_lats_250_usec'     , 105,    self._parse_gen),
                ('percent_%s_io_lats_500_usec'     , 106,    self._parse_gen),
                ('percent_%s_io_lats_750_usec'     , 107,    self._parse_gen),
                ('percent_%s_io_lats_1000_usec'    , 108,    self._parse_gen),
                ('percent_%s_io_lats_le_2_msec'    , 109,    self._parse_gen),
                ('percent_%s_io_lats_4_msec'       , 110,    self._parse_gen),
                ('percent_%s_io_lats_10_msec'      , 111,    self._parse_gen),
                ('percent_%s_io_lats_20_msec'      , 112,    self._parse_gen),
                ('percent_%s_io_lats_50_msec'      , 113,    self._parse_gen),
                ('percent_%s_io_lats_100_msec'     , 114,    self._parse_gen),
                ('percent_%s_io_lats_250_msec'     , 115,    self._parse_gen),
                ('percent_%s_io_lats_500_msec'     , 116,    self._parse_gen),
                ('percent_%s_io_lats_750_msec'     , 117,    self._parse_gen),
                ('percent_%s_io_lats_1000_msec'    , 118,    self._parse_gen),
                ('percent_%s_io_lats_2000_msec'    , 119,    self._parse_gen),
                ('percent_%s_io_lats_gt_2000_msec' , 120,    self._parse_gen),
                ('%s_disk_name'                    , 121,    self._parse_gen),
                ('%s_rd_ios'                       , 122,    self._parse_gen),
                ('%s_wr_ios'                       , 123,    self._parse_gen),
                ('%s_rd_merges'                    , 124,    self._parse_gen),
                ('%s_wr_merges'                    , 125,    self._parse_gen),
                ('%s_rd_ticks'                     , 126,    self._parse_gen),
                ('%s_wr_ticks'                     , 127,    self._parse_gen),
                ('%s_time_in_queue'                , 128,    self._parse_gen),
                ('percent_%s_dsk_util'             , 129,    self._parse_gen)])


    def __init__(self, version, data):
        """
        Fills the dictionary object with the fio output upon instantiation.

        @param data: List of values from fio output.

        @raises fio_parser_exception.

        """

        UserDict.__init__(self)

        # Check that data parameter.
        if len(data) == 0:
            raise fio_parser_exception('No fio output supplied.')

        # Create table that relates field name to fio output index and
        # parsing function to be used for the field.
        self._fio_table = []
        version_2x = ['2.0.8', '2.1']

        if version in version_2x:
            self._build_fio_2_0_table()
        else:
            raise fio_parser_exception('fio-%s output unsupported.'
               'Supported versions are %s' % (version, version_2x))

        # Fill dictionary object.
        self._job_name = data[2]
        for field, idx, parser in self._fio_table:
            parser(self._job_name, field, data[idx])
