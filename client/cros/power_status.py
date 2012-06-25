# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import glob, logging, math, numpy, os, re, threading, time

import common
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error, enum

BatteryDataReportType = enum.Enum('CHARGE', 'ENERGY')

# battery data reported at 1e6 scale
BATTERY_DATA_SCALE = 1e6

class DevStat(object):
    """
    Device power status. This class implements generic status initialization
    and parsing routines.
    """

    def __init__(self, fields, path=None):
        self.fields = fields
        self.path = path


    def reset_fields(self):
        """
        Reset all class fields to None to mark their status as unknown.
        """
        for field in self.fields.iterkeys():
            setattr(self, field, None)


    def read_val(self,  file_name, field_type):
        try:
            path = os.path.join(self.path, file_name)
            f = open(path, 'r')
            out = f.readline()
            val = field_type(out)
            return val

        except:
            return field_type(0)


    def read_all_vals(self):
        for field, prop in self.fields.iteritems():
            if prop[0]:
                val = self.read_val(prop[0], prop[1])
                setattr(self, field, val)


class ThermalStatACPI(DevStat):
    """
    ACPI-based thermal status.

    Fields:
    (All temperatures are in millidegrees Celsius.)

    str   enabled:            Whether thermal zone is enabled
    int   temp:               Current temperature
    str   type:               Thermal zone type
    int   num_trip_points:    Number of thermal trip points that activate
                                cooling devices
    int   num_points_tripped: Temperature is above this many trip points
    str   trip_point_N_type:  Trip point #N's type
    int   trip_point_N_temp:  Trip point #N's temperature value
    int   cdevX_trip_point:   Trip point o cooling device #X (index)
    """

    MAX_TRIP_POINTS = 20

    thermal_fields = {
        'enabled':              ['enabled', str],
        'temp':                 ['temp', int],
        'type':                 ['type', str],
        'num_points_tripped':   ['', '']
        }
    def __init__(self, path=None):
        # Browse the thermal folder for trip point fields.
        self.num_trip_points = 0

        thermal_fields = glob.glob(path + '/*')
        for file in thermal_fields:
            field = file[len(path + '/'):]
            if field.find('trip_point') != -1:
                if field.find('temp'):
                    field_type = int
                else:
                    field_type = str
                self.thermal_fields[field] = [field, field_type]

                # Count the number of trip points.
                if field.find('_type') != -1:
                    self.num_trip_points += 1

        super(ThermalStatACPI, self).__init__(self.thermal_fields, path)
        self.update()

    def update(self):
        if not os.path.exists(self.path):
            return

        self.read_all_vals()
        self.num_points_tripped = 0

        for field in self.thermal_fields:
            if field.find('trip_point_') != -1 and field.find('_temp') != -1 \
                    and self.temp > self.read_val(field, int):
               self.num_points_tripped += 1
               logging.info('Temperature trip point #' + \
                            field[len('trip_point_'):field.rfind('_temp')] + \
                            ' tripped.')


class ThermalStatHwmon(DevStat):
    """
    hwmon-based thermal status.

    Fields:
    int   temperature:        Current temperature in degrees Celsius
    """

    thermal_fields = {
        'temp':                 ['temperature', int],
        }
    def __init__(self, path=None):
        super(ThermalStatHwmon, self).__init__(self.thermal_fields, path)
        self.update()

    def update(self):
        if not os.path.exists(self.path):
            return

        self.read_all_vals()

    def read_val(self,  file_name, field_type):
        try:
            path = os.path.join(self.path, file_name)
            f = open(path, 'r')
            out = f.readline()
            val = field_type(out)

            # Convert degrees Celcius to millidegrees Celcius.
            if file_name == 'temperature':
                val = val * 1000
            return val

        except:
            return field_type(0)

class BatteryStat(DevStat):
    """
    Battery status.

    Fields:

    float charge_full:        Last full capacity reached [Ah]
    float charge_full_design: Full capacity by design [Ah]
    float charge_now:         Remaining charge [Ah]
    float current_now:        Battery discharge rate [A]
    float energy:             Current battery charge [Wh]
    float energy_full:        Last full capacity reached [Wh]
    float energy_full_design: Full capacity by design [Wh]
    float energy_rate:        Battery discharge rate [W]
    float power_now:          Battery discharge rate [W]
    float remaining_time:     Remaining discharging time [h]
    float voltage_min_design: Minimum voltage by design [V]
    float voltage_now:        Voltage now [V]
    """

    battery_fields = {
        'charge_full':          ['charge_full', float],
        'charge_full_design':   ['charge_full_design', float],
        'charge_now':           ['charge_now', float],
        'current_now':          ['current_now', float],
        'voltage_min_design':   ['voltage_min_design', float],
        'voltage_now':          ['voltage_now', float],
        'energy':               ['energy_now', float],
        'energy_full':          ['energy_full', float],
        'energy_full_design':   ['energy_full_design', float],
        'power_now':            ['power_now', float],
        'energy_rate':          ['', ''],
        'remaining_time':       ['', '']
        }

    def __init__(self, path=None):
        super(BatteryStat, self).__init__(self.battery_fields, path)
        self.update()


    def update(self):
        self.read_all_vals()

        if self.charge_full == 0 and self.energy_full != 0:
            battery_type = BatteryDataReportType.ENERGY;
        else:
            battery_type = BatteryDataReportType.CHARGE;

        # Since charge data is present, calculate parameters based upon
        # reported charge data.
        if battery_type == BatteryDataReportType.CHARGE:
            self.charge_full = self.charge_full / BATTERY_DATA_SCALE
            self.charge_full_design = self.charge_full_design / \
                                      BATTERY_DATA_SCALE
            self.charge_now = self.charge_now / BATTERY_DATA_SCALE

            self.current_now = math.fabs(self.current_now) / \
                               BATTERY_DATA_SCALE

            self.energy =  self.voltage_now * \
                           self.charge_now / \
                           BATTERY_DATA_SCALE
            self.energy_full = self.voltage_now * \
                               self.charge_full / \
                               BATTERY_DATA_SCALE
            self.energy_full_design = self.voltage_now * \
                                      self.charge_full_design / \
                                      BATTERY_DATA_SCALE

        # Charge data not present, so calculate parameters based upon
        # reported energy data.
        elif battery_type == BatteryDataReportType.ENERGY:
            self.charge_full = self.energy_full / self.voltage_now
            self.charge_full_design = self.energy_full_design / \
                                      self.voltage_now
            self.charge_now = self.energy / self.voltage_now

            # TODO(shawnn): check if power_now can really be reported
            # as negative, in the same way current_now can
            self.current_now = math.fabs(self.power_now) / self.voltage_now

            self.energy = self.energy / BATTERY_DATA_SCALE
            self.energy_full = self.energy_full / BATTERY_DATA_SCALE
            self.energy_full_design = self.energy_full_design / \
                                      BATTERY_DATA_SCALE

        self.voltage_min_design = self.voltage_min_design / \
                                  BATTERY_DATA_SCALE
        self.voltage_now = self.voltage_now / \
                           BATTERY_DATA_SCALE

        if self.charge_full > (self.charge_full_design * 1.5):
            raise error.TestError('Unreasonable charge_full value')
        if self.charge_now > (self.charge_full_design * 1.5):
            raise error.TestError('Unreasonable charge_now value')

        self.energy_rate =  self.voltage_now * self.current_now

        self.remaining_time = 0
        if self.current_now:
            self.remaining_time =  self.energy / self.energy_rate


class LineStatDummy(object):
    """
    Dummy line stat for devices which don't provide power_supply related sysfs
    interface.
    """
    def __init__(self):
        self.online = True


    def update(self):
        pass

class LineStat(DevStat):
    """
    Power line status.

    Fields:

    bool online:              Line power online
    """

    linepower_fields = {
        'is_online':             ['online', int]
        }


    def __init__(self, path=None):
        super(LineStat, self).__init__(self.linepower_fields, path)
        self.update()


    def update(self):
        self.read_all_vals()
        self.online = self.is_online == 1


class SysStat(object):
    """
    System power status for a given host.

    Fields:

    battery:   A list of BatteryStat objects.
    linepower: A list of LineStat objects.
    """

    def __init__(self):
        power_supply_path = '/sys/class/power_supply/*'
        self.battery = None
        self.linepower = None
        self.thermal = None
        self.thermal_path = None
        self.battery_path = None
        self.linepower_path = None
        thermal_path_acpi = '/sys/class/thermal/thermal_zone*'
        thermal_path_hwmon = '/sys/class/hwmon/hwmon*/device'
        # Look for these types of thermal sysfs paths, in the listed order.
        thermal_stat_types = { thermal_path_acpi:     ThermalStatACPI,
                               thermal_path_hwmon:    ThermalStatHwmon }

        power_supplies = glob.glob(power_supply_path)
        for path in power_supplies:
            type_path = os.path.join(path,'type')
            if not os.path.exists(type_path):
                continue
            power_type = utils.read_one_line(type_path)
            if power_type == 'Battery':
                self.battery_path = path
            elif power_type == 'Mains':
                self.linepower_path = path

        if not self.battery_path or not self.linepower_path:
            logging.warn("System does not provide power sysfs interface")

        for thermal_path, thermal_type in thermal_stat_types.items():
            try:
                self.thermal_path = glob.glob(thermal_path)[0]
                self.thermal_type = thermal_type
                logging.debug('Using %s for thermal info.' % self.thermal_path)
                break
            except:
                logging.debug('Could not find thermal path %s, skipping.' %
                              thermal_path)
                continue

        self.min_temp = 999999999
        self.max_temp = -999999999
        self.temp_log = {}

    def refresh(self):
        """
        Initialize device power status objects.
        """
        if self.battery_path:
            self.battery = [ BatteryStat(self.battery_path) ]
        if self.linepower_path:
            self.linepower = [ LineStat(self.linepower_path) ]
        else:
            self.linepower = [ LineStatDummy() ]
        if self.thermal_path:
            self.thermal = [ self.thermal_type(self.thermal_path) ]

        try:
            if self.thermal[0].temp < self.min_temp:
                self.min_temp = self.thermal[0].temp
            if self.thermal[0].temp > self.max_temp:
                self.max_temp = self.thermal[0].temp
            logging.info('Temperature reading: ' + str(self.thermal[0].temp))
        except:
            logging.error('Could not read temperature, skipping.')


    def on_ac(self):
        return self.linepower[0].online


    def percent_current_charge(self):
        return self.battery[0].charge_now * 100 / \
               self.battery[0].charge_full_design


    def assert_battery_state(self, percent_initial_charge_min):
        """Check initial power configuration state is battery.

        Args:
          percent_initial_charge_min: float between 0 -> 1.00 of
            percentage of battery that must be remaining.
            None|0|False means check not performed.

        Raises:
          TestError: if one of battery assertions fails
        """
        if self.on_ac():
            raise error.TestError(
                'Running on AC power. Please remove AC power cable')

        percent_initial_charge = self.percent_current_charge()

        if percent_initial_charge_min and percent_initial_charge < \
                                          percent_initial_charge_min:
            raise error.TestError('Initial charge (%f) less than min (%f)'
                      % (percent_initial_charge, percent_initial_charge_min))


def get_status():
    """
    Return a new power status object (SysStat). A new power status snapshot
    for a given host can be obtained by either calling this routine again and
    constructing a new SysStat object, or by using the refresh method of the
    SysStat object.
    """
    status = SysStat()
    status.refresh()
    return status


class CPUFreqStats(object):
    """
    CPU Frequency statistics

    """

    def __init__(self):
        cpufreq_stats_path = '/sys/devices/system/cpu/cpu*/cpufreq/stats/' + \
                             'time_in_state'
        self._file_paths = glob.glob(cpufreq_stats_path)
        if not self._file_paths:
            logging.debug('time_in_state file not found')

        self._stats = self._read_stats()


    def refresh(self, incremental=True):
        """
        This method returns the percentage time spent in each of the CPU
        frequency levels.

        @incremental: If False, stats returned are from when the system
                      was booted up. Otherwise, stats are since the last time
                      stats were refreshed.
        """
        stats = self._read_stats()
        diff_stats = stats
        if incremental:
            diff_stats = self._do_diff(stats, self._stats)
        percent_stats = self._to_percent(diff_stats)
        self._stats = stats
        return percent_stats


    def _read_stats(self):
        stats = {}
        for path in self._file_paths:
            data = utils.read_file(path)
            for line in data.splitlines():
                list = line.split()
                freq = int(list[0])
                time = int(list[1])
                if freq in stats:
                    stats[freq] += time
                else:
                    stats[freq] = time
        return stats


    def _get_total_time(self, stats):
        total_time = 0
        for freq in stats:
            total_time += stats[freq]
        return total_time


    def _to_percent(self, stats):
        percent_stats = {}
        total_time = self._get_total_time(stats)
        for freq in stats:
            percent_stats[freq] = stats[freq] * 100.0 / total_time
        return percent_stats


    def _do_diff(self, stats_new, stats_old):
        diff_stats = {}
        for freq in stats_new:
            diff_stats[freq] = stats_new[freq] -  stats_old[freq]
        return diff_stats


class CPUIdleStats(object):
    """
    CPU Idle statistics
    """
    # TODO (snanda): Handle changes in number of c-states due to events such
    # as ac <-> battery transitions.
    # TODO (snanda): Handle non-S0 states. Time spent in suspend states is
    # currently not factored out.

    def __init__(self):
        self._num_cpus = utils.count_cpus()
        self._time = time.time()
        self._stats = self._read_stats()


    def refresh(self):
        """
        This method returns the percentage time spent in each of the CPU
        idle states. The stats returned are from whichever is the later of:
        a) time this class was instantiated, or
        b) time when refresh was last called
        """
        time_now = time.time()
        stats = self._read_stats()

        diff_stats = self._do_diff(stats, self._stats)
        diff_time = time_now - self._time

        percent_stats = self._to_percent(diff_stats, diff_time)

        self._time = time_now
        self._stats = stats
        return percent_stats


    def _read_stats(self):
        cpuidle_stats = {}
        cpuidle_path = '/sys/devices/system/cpu/cpu*/cpuidle'
        cpus = glob.glob(cpuidle_path)

        for cpu in cpus:
            state_path = os.path.join(cpu, 'state*')
            states = glob.glob(state_path)

            for state in states:
                latency = int(utils.read_one_line(os.path.join(state,
                                                               'latency')))

                if not latency:
                    # C0 state. Skip it since the stats aren't right for it.
                    continue

                name = utils.read_one_line(os.path.join(state, 'name'))
                time = int(utils.read_one_line(os.path.join(state, 'time')))
                if name in cpuidle_stats:
                    cpuidle_stats[name] += time
                else:
                    cpuidle_stats[name] = time

        return cpuidle_stats


    def _to_percent(self, stats, test_time):
        # convert time from sec to us.
        test_time *= 1000 * 1000
        # scale time by the number of CPUs in the system
        test_time *= self._num_cpus

        percent_stats = {}
        non_c0_time = 0
        for state in stats:
            percent_stats[state] = stats[state] * 100.0 / test_time
            non_c0_time += stats[state]

        c0_time = test_time - non_c0_time
        percent_stats['C0'] = c0_time * 100.0 / test_time

        return percent_stats


    def _do_diff(self, stats_new, stats_old):
        diff_stats = {}
        for state in stats_new:
            diff_stats[state] = stats_new[state] -  stats_old[state]
        return diff_stats


class USBSuspendStats(object):
    # TODO (snanda): handle hot (un)plugging of USB devices
    # TODO (snanda): handle duration counters wraparound

    def __init__(self):
        usb_stats_path = '/sys/bus/usb/devices/*/power'
        self._file_paths = glob.glob(usb_stats_path)
        if not self._file_paths:
            logging.debug('USB stats path not found')

        self._active, self._connected = self._read_stats()


    def refresh(self, incremental=True):
        """
        This method returns the percentage time spent in active state for
        all USB devices in the system.

        @incremental: If False, stats returned are from when the system
                      was booted up. Otherwise, stats are since the last time
                      stats were refreshed.
        """

        active, connected = self._read_stats()
        if incremental:
            percent_active = (active - self._active) * 100.0 / \
                             (connected - self._connected)
        else:
            percent_active = active * 100.0 / connected

        self._active = active
        self._connected = connected

        return percent_active


    def _read_stats(self):
        total_active = 0
        total_connected = 0

        for path in self._file_paths:
            active_duration_path = os.path.join(path, 'active_duration')
            connected_duration_path = os.path.join(path, 'connected_duration')

            if not os.path.exists(active_duration_path) or \
               not os.path.exists(connected_duration_path):
                logging.debug('duration paths do not exist for: %s', path)
                continue

            active = int(utils.read_file(active_duration_path))
            connected = int(utils.read_file(connected_duration_path))
            logging.debug('device %s active for %.2f%%',
                          path, active * 100.0 / connected)

            total_active += active
            total_connected += connected

        return total_active, total_connected


class PowerMeasurement(object):
    """Class to measure power.

    Public attributes:
        domain: String name of the power domain being measured.  Example is
          'system' for total system power

    Public methods:
        refresh: Performs any power/energy sampling and calculation and returns
            power as float in watts.  This method MUST be implemented in
            subclass.
    """

    def __init__(self, domain):
        """Constructor."""
        self.domain = domain


    def refresh(self):
        """Performs any power/energy sampling and calculation.

        MUST be implemented in subclass

        Returns:
            float, power in watts.
        """
        raise NotImplementedError("'refresh' method should be implemented in "
                                  "subclass.")


class SystemPower(PowerMeasurement):
    """Class to measure system power.

    TODO(tbroch): This class provides a subset of functionality in BatteryStat
    in hopes of minimizing power draw.  Investigate whether its really
    significant and if not, deprecate.

    Private Attributes:
      _voltage_file: path to retrieve voltage in uvolts
      _current_file: path to retrieve current in uamps
    """

    def __init__(self, battery_dir):
        """Constructor.

        Args:
            battery_dir: path to dir containing the files to probe and log.
                usually something like /sys/class/power_supply/BAT0/
        """
        super(SystemPower, self).__init__('system')
        # Files to log voltage and current from
        self._voltage_file = os.path.join(battery_dir, 'voltage_now')
        self._current_file = os.path.join(battery_dir, 'current_now')


    def refresh(self):
        """refresh method.

        See superclass PowerMeasurement for details.
        """

        voltage_str = utils.read_one_line(self._voltage_file)
        current_str = utils.read_one_line(self._current_file)

        # Values in sysfs are in microamps and microvolts
        # multiply and convert to Watts
        power = float(voltage_str) * float(current_str) / 10**12
        return power


class PowerLogger(threading.Thread):
    """A thread that logs power draw readings in watts.

    Example code snippet:
         mylogger = PowerLogger([PowerMeasurent1, PowerMeasurent2])
         mylogger.run()
         for testname in tests:
             start_time = time.time()
             #run the test method for testname
             mlogger.checkpoint(tetname, start_time)
         keyvals = mylogger.calc()

    Public attributes:
        seconds_period: float, probing interval in seconds.
        readings: list of lists of floats of power measurements in watts.
        times: list of floats of time (since Epoch) of when power measurements
            occurred.  len(time) == len(readings).
        done: flag to stop the logger.
        domains: list of power domain strings being measured

    Public methods:
        run: launches the thread to gather power measuremnts
        calc: calculates
        save_results:

    Private attributes:
       _power_measurements: list of PowerMeasurement objects to be sampled.
       _checkpoint_data: list of tuples.  Tuple contains:
           tname: String of testname associated with this time interval
           tstart: Float of time when subtest started
           tend: Float of time when subtest ended
       _results: list of results tuples.  Tuple contains:
           prefix: String of subtest
           mean: Flost of mean power in watts
           std: Float of standard deviation of power measurements
           tstart: Float of time when subtest started
           tend: Float of time when subtest ended
    """
    def __init__(self, power_measurements, seconds_period=1.0):
        """Initialize a logger.

        Args:
            power_measurements: list of PowerMeasurement objects to be sampled.
            seconds_period: float, probing interval in seconds.  Default 1.0
        """
        threading.Thread.__init__(self)

        self.seconds_period = seconds_period

        self.readings = []
        self.times = []
        self._checkpoint_data = []

        self.domains = []
        self._power_measurements = power_measurements
        for meas in self._power_measurements:
            self.domains.append(meas.domain)

        self.done = False


    def run(self):
        """Threads run method."""
        while(not self.done):
            self.times.append(time.time())
            readings = []
            for meas in self._power_measurements:
                readings.append(meas.refresh())
            self.readings.append(readings)
            time.sleep(self.seconds_period)


    def checkpoint(self, tname, tstart, tend=None):
        """Check point the times in seconds associated with test tname.

        Args:
           tname: String of testname associated with this time interval
           tstart: Float in seconds of when tname test started.  Should be based
                off time.time()
           tend: Float in seconds of when tname test ended.  Should be based
                off time.time().  If None, then value computed in the method.
        """
        if not tend:
            tend = time.time()
        self._checkpoint_data.append((tname, tstart, tend))
        logging.info('Finished test "%s" between timestamps [%s, %s]',
                     tname, tstart, tend)


    def calc(self):
        """Calculate average power consumption during each of the sub-tests.

        Method performs the following steps:
            1. Signals the thread to stop running.
            2. Calculates mean, max, min, count on the samples for each of the
               measurements.
            3. Stores results to be written later.
            4. Creates keyvals for autotest publishing.

        Returns:
            dict of keyvals suitable for autotest results.
        """
        t = numpy.array(self.times)
        keyvals = {}
        results  = []

        if not self.done:
            self.done = True
        # times 2 the sleep time in order to allow for readings as well.
        self.join(timeout=self.seconds_period * 2)

        for i, domain_readings in enumerate(zip(*self.readings)):
            power = numpy.array(domain_readings)
            domain = self.domains[i]

            for tname, tstart, tend in self._checkpoint_data:
                prefix = '%s_%s' % (tname, domain)
                keyvals[prefix+'_duration'] = tend - tstart
                # Select all readings taken between tstart and tend timestamps
                pwr_array = power[numpy.bitwise_and(tstart < t, t < tend)]
                # If sub-test terminated early, avoid calculating avg, std and
                # min
                if not pwr_array.size:
                    continue
                pwr_mean = pwr_array.mean()
                pwr_std = pwr_array.std()

                # Results list can be used for pretty printing and saving as csv
                results.append((prefix, pwr_mean, pwr_std,
                                tend - tstart, tstart, tend))

                keyvals[prefix+'_power'] = pwr_mean
                keyvals[prefix+'_power_cnt'] = pwr_array.size
                keyvals[prefix+'_power_max'] = pwr_array.max()
                keyvals[prefix+'_power_min'] = pwr_array.min()
                keyvals[prefix+'_power_std'] = pwr_std

        self._results = results
        return keyvals


    def save_results(self, resultsdir, fname=None):
        """Save computed results in a nice tab-separated format.
        This is useful for long manual runs.

        Args:
            resultsdir: String, directory to write results to
            fname: String name of file to write results to
        """
        if not fname:
            fname = 'power_results_%.0f.txt' % time.time()
        fname = os.path.join(resultsdir, fname)
        with file(fname, 'wt') as f:
            for row in self._results:
                # First column is name, the rest are numbers. See _calc_power()
                fmt_row = [row[0]] + ['%.2f' % x for x in row[1:]]
                line = '\t'.join(fmt_row)
                f.write(line + '\n')
