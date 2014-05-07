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

import json, logging, re, utils
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


class fio_graph_generator():
    """
    Generate graph from fio log that created when specified these options.
    - write_bw_log
    - write_iops_log
    - write_lat_log

    The following limitations apply
    - Log file name must be in format jobname_testpass
    - Graph is generate using Google graph api -> Internet require to view.
    """

    html_head = """
<html>
  <head>
    <script type="text/javascript" src="https://www.google.com/jsapi"></script>
    <script type="text/javascript">
      google.load("visualization", "1", {packages:["corechart"]});
      google.setOnLoadCallback(drawChart);
      function drawChart() {
"""

    html_tail = """
        var chart_div = document.getElementById('chart_div');
        var chart = new google.visualization.ScatterChart(chart_div);
        chart.draw(data, options);
      }
    </script>
  </head>
  <body>
    <div id="chart_div" style="width: 100%; height: 100%;"></div>
  </body>
</html>
"""

    h_title = { True: 'Percentile', False: 'Time (s)' }
    v_title = { 'bw'  : 'Bandwidth (KB/s)',
                'iops': 'IOPs',
                'lat' : 'Total latency (us)',
                'clat': 'Completion latency (us)',
                'slat': 'Submission latency (us)' }
    graph_title = { 'bw'  : 'bandwidth',
                    'iops': 'IOPs',
                    'lat' : 'total latency',
                    'clat': 'completion latency',
                    'slat': 'submission latency' }

    test_name = ''
    test_type = ''
    pass_list = ''

    @classmethod
    def _parse_log_file(self, file_name, pass_index, pass_count, percentile):
        """
        Generate row for google.visualization.DataTable from one log file.
        Log file is the one that generated using write_{bw,lat,iops}_log
        option in the FIO job file.

        The fio log file format is  timestamp, value, direction, blocksize
        The output format for each row is { c: list of { v: value} }

        @param file_name:  log file name to read data from
        @param pass_index: index of current run pass
        @param pass_count: number of all test run passes
        @param percentile: flag to use percentile as key instead of timestamp

        @return: list of data rows in google.visualization.DataTable format
        """
        # Read data from log
        with open(file_name, 'r') as f:
            data = []

            for line in f.readlines():
                if not line:
                    break
                t, v, _, _ = [int(x) for x in line.split(', ')]
                data.append([t / 1000.0, v])

        # Sort & calculate percentile
        if percentile:
            data.sort(key=lambda x:x[1])
            l = len(data)
            for i in range(l):
                data[i][0] = 100 * (i + 0.5) / l

        # Generate the data row
        all_row = []
        row = [None] * (pass_count + 1)
        for d in data:
            row[0] = {'v' : '%.3f' % d[0]}
            row[pass_index + 1] = {'v': d[1] }
            all_row.append({'c': row[:]})

        return all_row

    @classmethod
    def _gen_data_col(self, pass_list, percentile):
        """
        Generate col for google.visualization.DataTable

        The output format is list of dict of label and type. In this case,
        type is always number.

        @param pass_list:  list of test run passes
        @param percentile: flag to use percentile as key instead of timestamp

        @return: list of column in google.visualization.DataTable format
        """
        if percentile:
            col_name_list = ['percentile'] + pass_list
        else:
            col_name_list = ['time'] + pass_list

        return [{'label': name, 'type': 'number'} for name in col_name_list]

    @classmethod
    def _gen_data_row(self, test_name, test_type, pass_list, percentile):
        """
        Generate row for google.visualization.DataTable by generate all log
        file name and call _parse_log_file for each file

        @param test_name: name of current workload. i.e. randwrite
        @param test_type: type of value collected for current test. i.e. IOPs
        @param pass_list: list of run passes for current test
        @param percentile: flag to use percentile as key instead of timestamp

        @return: list of data rows in google.visualization.DataTable format
        """
        all_row = []
        pass_count = len(pass_list)
        for pass_index, pass_str in enumerate(pass_list):
            log_file_name = str('%s_%s_%s.log' %
                                (test_name, pass_str, test_type))
            all_row.extend(self._parse_log_file(log_file_name, pass_index,
                                                pass_count, percentile))
        return all_row

    @classmethod
    def _write_data(self, f, test_name, test_type, pass_list, percentile):
        """
        Write google.visualization.DataTable object to output file.
        https://developers.google.com/chart/interactive/docs/reference

        @param test_name: name of current workload. i.e. randwrite
        @param test_type: type of value collected for current test. i.e. IOPs
        @param pass_list: list of run passes for current test
        @param percentile: flag to use percentile as key instead of timestamp
        """
        col = self._gen_data_col(pass_list, percentile)
        row = self._gen_data_row(test_name, test_type, pass_list, percentile)
        data_dict = { 'cols' : col, 'rows' : row}

        f.write('var data = new google.visualization.DataTable(')
        json.dump(data_dict, f)
        f.write(');\n')

    @classmethod
    def _write_option(self, f, test_name, test_type, percentile):
        """
        Write option to render scatter graph to output file.
        https://google-developers.appspot.com/chart/interactive/docs/gallery/scatterchart

        @param test_name: name of current workload. i.e. randwrite
        @param test_type: type of value collected for current test. i.e. IOPs
        @param percentile: flag to use percentile as key instead of timestamp
        """
        option = {'pointSize': 1 }
        if percentile:
            option['title'] = ('Percentile graph of %s for %s workload' %
                               (self.graph_title[test_type], test_name))
        else:
            option['title'] = ('Graph of %s for %s workload over time' %
                               (self.graph_title[test_type], test_name))

        option['hAxis'] = { 'title': self.h_title[percentile]}
        option['vAxis'] = { 'title': self.v_title[test_type]}

        f.write('var options = ')
        json.dump(option, f)
        f.write(';\n')

    @classmethod
    def _write_graph(self, test_name, test_type, pass_list, percentile=False):
        """
        Generate graph for test name / test type

        @param test_name: name of current workload. i.e. randwrite
        @param test_type: type of value collected for current test. i.e. IOPs
        @param pass_list: list of run passes for current test
        @param percentile: flag to use percentile as key instead of timestamp
        """
        logging.info('fio_graph_generator._write_graph %s %s %s',
                     test_name, test_type, str(pass_list))


        if percentile:
            out_file_name = '%s_%s_percentile.html' % (test_name, test_type)
        else:
            out_file_name = '%s_%s.html' % (test_name, test_type)

        with open(out_file_name, 'w') as f:
            f.write(self.html_head)
            self._write_data(f, test_name, test_type, pass_list, percentile)
            self._write_option(f, test_name, test_type, percentile)
            f.write(self.html_tail)

    def __init__(self, test_name, test_type, pass_list):
        """
        @param test_name: name of current workload. i.e. randwrite
        @param test_type: type of value collected for current test. i.e. IOPs
        @param pass_list: list of run passes for current test
        """
        self.test_name = test_name
        self.test_type = test_type
        self.pass_list = pass_list

    def run(self):
        """
        Run the graph generator.
        """
        self._write_graph(self.test_name, self.test_type, self.pass_list, False)
        self._write_graph(self.test_name, self.test_type, self.pass_list, True)


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


def fio_generate_graph():
    """
    Scan for fio log file in output directory and send data to generate each
    graph to fio_graph_generator class.
    """
    log_types = ['bw', 'iops', 'lat', 'clat', 'slat']

    # move fio log to result dir
    for log_type in log_types:
        logging.info('log_type %s', log_type)
        logs = utils.system_output('ls *_%s.log' % log_type, ignore_status=True)
        if not logs:
            continue

        # log file name should be in logname_pass_type.log
        # Example randread_p1_iops.log
        log_dict = dict()

        pattern = r"""(?P<jobname>.*)_                    # jobname
                      ((?P<runpass>p\d+)_)                # pass
                      (?P<type>bw|iops|lat|clat|slat).log # type
                   """
        matcher = re.compile(pattern, re.X)

        pass_list = []
        current_job = ''

        for log in logs.split():
            match = matcher.match(log)
            if not match:
                logging.warn('Unknown log file %s', log)
                continue

            jobname = match.group('jobname')
            runpass = match.group('runpass')

            # All files for particular job name are group together for create
            # graph that can compare performance between result from each pass.
            if jobname != current_job:
                if pass_list:
                    fio_graph_generator(current_job, log_type, pass_list).run()
                current_job = jobname
                pass_list = []

            pass_list.append(runpass)

        if pass_list:
            fio_graph_generator(current_job, log_type, pass_list).run()


        cmd = 'mv *_%s.log results' % log_type
        utils.run(cmd, ignore_status=True)
        utils.run('mv *.html results', ignore_status=True)


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

    fio_generate_graph()

    return fio_parser(fio.stdout)

