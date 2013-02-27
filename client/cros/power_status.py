# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import ctypes, fcntl, glob, logging, math, numpy, os, struct, threading, time

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
        'status':               ['status', str],
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
            battery_type = BatteryDataReportType.ENERGY
        else:
            battery_type = BatteryDataReportType.CHARGE

        if self.voltage_min_design != 0:
            voltage_nominal = self.voltage_min_design
        else:
            voltage_nominal = self.voltage_now

        # Since charge data is present, calculate parameters based upon
        # reported charge data.
        if battery_type == BatteryDataReportType.CHARGE:
            self.charge_full = self.charge_full / BATTERY_DATA_SCALE
            self.charge_full_design = self.charge_full_design / \
                                      BATTERY_DATA_SCALE
            self.charge_now = self.charge_now / BATTERY_DATA_SCALE

            self.current_now = math.fabs(self.current_now) / \
                               BATTERY_DATA_SCALE

            self.energy =  voltage_nominal * \
                           self.charge_now / \
                           BATTERY_DATA_SCALE
            self.energy_full = voltage_nominal * \
                               self.charge_full / \
                               BATTERY_DATA_SCALE
            self.energy_full_design = voltage_nominal * \
                                      self.charge_full_design / \
                                      BATTERY_DATA_SCALE

        # Charge data not present, so calculate parameters based upon
        # reported energy data.
        elif battery_type == BatteryDataReportType.ENERGY:
            self.charge_full = self.energy_full / voltage_nominal
            self.charge_full_design = self.energy_full_design / \
                                      voltage_nominal
            self.charge_now = self.energy / voltage_nominal

            # TODO(shawnn): check if power_now can really be reported
            # as negative, in the same way current_now can
            self.current_now = math.fabs(self.power_now) / \
                               voltage_nominal

            self.energy = self.energy / BATTERY_DATA_SCALE
            self.energy_full = self.energy_full / BATTERY_DATA_SCALE
            self.energy_full_design = self.energy_full_design / \
                                      BATTERY_DATA_SCALE

        self.voltage_min_design = self.voltage_min_design / \
                                  BATTERY_DATA_SCALE
        self.voltage_now = self.voltage_now / \
                           BATTERY_DATA_SCALE
        voltage_nominal = voltage_nominal / \
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
        """
        Returns true if device is currently running from AC power.
        """
        on_ac = self.linepower[0].online
        # Butterfly can incorrectly report AC online for some time after
        # unplug. Check battery discharge state to confirm.
        if utils.get_board() == 'BUTTERFLY':
            on_ac &= (not self.battery_discharging())
        return on_ac

    def battery_discharging(self):
        """
        Returns true if battery is currently discharging.
        """
        return(self.battery[0].status.rstrip() == 'Discharging')

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
                'Running on AC power. Please remove AC power cable.')

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


class AbstractStats(object):
    """
    Common superclass for measurements of percentages per state over time.
    """

    @staticmethod
    def to_percent(stats):
        """
        Turns a dict with absolute time values into a dict with percentages.
        """
        total = sum(stats.itervalues())
        if total == 0: return {}
        return dict((k, v * 100.0 / total) for (k, v) in stats.iteritems())


    @staticmethod
    def do_diff(new, old):
        """
        Returns a dict with value deltas from two dicts with matching keys.
        """
        return dict((k, new[k] - old.get(k, 0)) for k in new.iterkeys())


    def __init__(self):
        self._stats = self._read_stats()


    def refresh(self, incremental=True):
        """
        Returns dict mapping state names to percentage of time spent in them.

        @incremental: If False, stats returned are from a single _read_stats.
                      Otherwise, stats are from the difference between the
                      current and last refresh.
        """
        raw_stats = result = self._read_stats()
        if incremental:
            result = self.do_diff(result, self._stats)
        self._stats = raw_stats
        return self.to_percent(result)


    def _read_stats(self):
        """
        Override! Reads the raw data values that shall be measured into a dict.
        """
        raise NotImplementedError('Override _read_stats in the subclass!')


class CPUFreqStats(AbstractStats):
    """
    CPU Frequency statistics
    """

    def __init__(self):
        cpufreq_stats_path = '/sys/devices/system/cpu/cpu*/cpufreq/stats/' + \
                             'time_in_state'
        self._file_paths = glob.glob(cpufreq_stats_path)
        if not self._file_paths:
            logging.debug('time_in_state file not found')
        super(CPUFreqStats, self).__init__()


    def _read_stats(self):
        stats = {}
        for path in self._file_paths:
            data = utils.read_file(path)
            for line in data.splitlines():
                pair = line.split()
                freq = int(pair[0])
                timeunits = int(pair[1])
                if freq in stats:
                    stats[freq] += timeunits
                else:
                    stats[freq] = timeunits
        return stats


class CPUIdleStats(AbstractStats):
    """
    CPU Idle statistics (refresh() will not work with incremental=False!)
    """
    # TODO (snanda): Handle changes in number of c-states due to events such
    # as ac <-> battery transitions.
    # TODO (snanda): Handle non-S0 states. Time spent in suspend states is
    # currently not factored out.

    def _read_stats(self):
        cpuidle_stats = {'C0': 0}
        cpuidle_path = '/sys/devices/system/cpu/cpu*/cpuidle'
        epoch_usecs = int(time.time() * 1000 * 1000)
        cpus = glob.glob(cpuidle_path)

        for cpu in cpus:
            state_path = os.path.join(cpu, 'state*')
            states = glob.glob(state_path)

            for state in states:
                if not int(utils.read_one_line(os.path.join(state, 'latency'))):
                    # C0 state. Kernel stats aren't right, so calculate by
                    # subtracting all other states from total time (using epoch
                    # timer since we calculate differences in the end anyway)
                    cpuidle_stats['C0'] += epoch_usecs
                    continue

                name = utils.read_one_line(os.path.join(state, 'name'))
                usecs = int(utils.read_one_line(os.path.join(state, 'time')))
                cpuidle_stats['C0'] -= usecs

                if name == '<null>':
                    # Kernel race condition that can happen while a new C-state
                    # gets added (e.g. AC->battery). Don't know the 'name' of
                    # the state yet, but its 'time' would be 0 anyway.
                    logging.warn('Read name: <null>, time: %d from %s'
                        % (usecs, state) + '... skipping.')
                    continue

                if name in cpuidle_stats:
                    cpuidle_stats[name] += usecs
                else:
                    cpuidle_stats[name] = usecs

        return cpuidle_stats


class CPUPackageStats(AbstractStats):
    """
    Package C-state residency statistics for modern Intel CPUs.
    """

    ATOM         =              {'C2': 0x3F8, 'C4': 0x3F9, 'C6': 0x3FA}
    NEHALEM      =              {'C3': 0x3F8, 'C6': 0x3F9, 'C7': 0x3FA}
    SANDY_BRIDGE = {'C2': 0x60D, 'C3': 0x3F8, 'C6': 0x3F9, 'C7': 0x3FA}

    def __init__(self):
        def _get_platform_states():
            """
            Helper to decide what set of microarchitecture-specific MSRs to use.

            Returns: dict that maps C-state name to MSR address, or None.
            """
            modalias = '/sys/devices/system/cpu/modalias'
            if not os.path.exists(modalias): return None

            values = utils.read_one_line(modalias).split(':')
            # values[2]: vendor, values[4]: family, values[6]: model (CPUID)
            if values[2] != '0000' or values[4] != '0006': return None

            return {
                # model groups pulled from Intel manual, volume 3 chapter 35
                '0027': self.ATOM,         # unreleased? (Next Generation Atom)
                '001A': self.NEHALEM,      # Bloomfield, Nehalem-EP (i7/Xeon)
                '001E': self.NEHALEM,      # Clarks-/Lynnfield, Jasper (i5/i7/X)
                '001F': self.NEHALEM,      # unreleased? (abandoned?)
                '0025': self.NEHALEM,      # Arran-/Clarksdale (i3/i5/i7/C/X)
                '002C': self.NEHALEM,      # Gulftown, Westmere-EP (i7/Xeon)
                '002E': self.NEHALEM,      # Nehalem-EX (Xeon)
                '002F': self.NEHALEM,      # Westmere-EX (Xeon)
                '002A': self.SANDY_BRIDGE, # SandyBridge (i3/i5/i7/C/X)
                '002D': self.SANDY_BRIDGE, # SandyBridge-E (i7)
                '003A': self.SANDY_BRIDGE, # IvyBridge (i3/i5/i7/X)
                '003C': self.SANDY_BRIDGE, # unclear (Haswell?)
                '003E': self.SANDY_BRIDGE, # IvyBridge (Xeon)
                }.get(values[6], None)

        self._platform_states = _get_platform_states()
        super(CPUPackageStats, self).__init__()


    def _read_stats(self):
        packages = set()
        template = '/sys/devices/system/cpu/cpu%s/topology/physical_package_id'
        if not self._platform_states: return {}
        stats = dict((state, 0) for state in self._platform_states)
        stats['C0_C1'] = 0

        for cpu in os.listdir('/dev/cpu'):
            if not os.path.exists(template % cpu): continue
            package = utils.read_one_line(template % cpu)
            if package in packages: continue
            packages.add(package)

            stats['C0_C1'] += utils.rdmsr(0x10, cpu) # TSC
            for (state, msr) in self._platform_states.iteritems():
                ticks = utils.rdmsr(msr, cpu)
                stats[state] += ticks
                stats['C0_C1'] -= ticks

        return stats


class USBSuspendStats(AbstractStats):
    """
    USB active/suspend statistics (over all devices)
    """
    # TODO (snanda): handle hot (un)plugging of USB devices
    # TODO (snanda): handle duration counters wraparound

    def __init__(self):
        usb_stats_path = '/sys/bus/usb/devices/*/power'
        self._file_paths = glob.glob(usb_stats_path)
        if not self._file_paths:
            logging.debug('USB stats path not found')
        super(USBSuspendStats, self).__init__()


    def _read_stats(self):
        usb_stats = {'active': 0, 'suspended': 0}

        for path in self._file_paths:
            active_duration_path = os.path.join(path, 'active_duration')
            total_duration_path = os.path.join(path, 'connected_duration')

            if not os.path.exists(active_duration_path) or \
               not os.path.exists(total_duration_path):
                logging.debug('duration paths do not exist for: %s', path)
                continue

            active = int(utils.read_file(active_duration_path))
            total = int(utils.read_file(total_duration_path))
            logging.debug('device %s active for %.2f%%',
                          path, active * 100.0 / total)

            usb_stats['active'] += active
            usb_stats['suspended'] += total - active

        return usb_stats


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

                keyvals[prefix+'_pwr'] = pwr_mean
                keyvals[prefix+'_pwr_cnt'] = pwr_array.size
                keyvals[prefix+'_pwr_max'] = pwr_array.max()
                keyvals[prefix+'_pwr_min'] = pwr_array.min()
                keyvals[prefix+'_pwr_std'] = pwr_std

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


class DiskStateLogger(threading.Thread):
    """Records the time percentages the disk stays in its different power modes.

    Example code snippet:
        mylogger = power_status.DiskStateLogger()
        mylogger.start()
        result = mylogger.result()

    Public methods:
        start: Launches the thread and starts measurements.
        result: Stops the thread if it's still running and returns measurements.
        get_error: Returns the exception in _error if it exists.

    Private functions:
        _get_disk_state: Returns the disk's current ATA power mode as a string.

    Private attributes:
        _seconds_period: Disk polling interval in seconds.
        _stats: Dict that maps disk states to seconds spent in them.
        _running: Flag that is True as long as the logger should keep running.
        _time: Timestamp of last disk state reading.
        _device_path: The file system path of the disk's device node.
        _error: Contains a TestError exception if an unexpected error occured
    """
    def __init__(self, seconds_period = 5.0, device_path = '/dev/sda'):
        """Initializes a logger.

        Args:
            seconds_period: Disk polling interval in seconds. Default 5.0
            device_path: The path of the disk's device node. Default '/dev/sda'
        """
        threading.Thread.__init__(self)
        self._seconds_period = seconds_period
        self._device_path = device_path
        self._stats = {}
        self._running = False
        self._error = None


    def _get_disk_state(self):
        """Checks the disk's power mode and returns it as a string.

        This uses the SG_IO ioctl to issue a raw SCSI command data block with
        the ATA-PASS-THROUGH command that allows SCSI-to-ATA translation (see
        T10 document 04-262r8). The ATA command issued is CHECKPOWERMODE1,
        which returns the device's current power mode.
        """

        def _addressof(obj):
            """Shortcut to return the memory address of an object as integer."""
            return ctypes.cast(obj, ctypes.c_void_p).value

        scsi_cdb = struct.pack("12B", # SCSI command data block (uint8[12])
                               0xa1, # SCSI opcode: ATA-PASS-THROUGH
                               3 << 1, # protocol: Non-data
                               1 << 5, # flags: CK_COND
                               0, # features
                               0, # sector count
                               0, 0, 0, # LBA
                               1 << 6, # flags: ATA-USING-LBA
                               0xe5, # ATA opcode: CHECKPOWERMODE1
                               0, # reserved
                               0, # control (no idea what this is...)
                              )
        scsi_sense = (ctypes.c_ubyte * 32)() # SCSI sense buffer (uint8[32])
        sgio_header = struct.pack("iiBBHIPPPIIiPBBBBHHiII", # see <scsi/sg.h>
                                  83, # Interface ID magic number (int32)
                                  -1, # data transfer direction: none (int32)
                                  12, # SCSI command data block length (uint8)
                                  32, # SCSI sense data block length (uint8)
                                  0, # iovec_count (not applicable?) (uint16)
                                  0, # data transfer length (uint32)
                                  0, # data block pointer
                                  _addressof(scsi_cdb), # SCSI CDB pointer
                                  _addressof(scsi_sense), # sense buffer pointer
                                  500, # timeout in milliseconds (uint32)
                                  0, # flags (uint32)
                                  0, # pack ID (unused) (int32)
                                  0, # user data pointer (unused)
                                  0, 0, 0, 0, 0, 0, 0, 0, 0, # output params
                                 )
        try:
            with open(self._device_path, 'r') as dev:
                result = fcntl.ioctl(dev, 0x2285, sgio_header)
        except IOError, e:
            raise error.TestError('ioctl(SG_IO) error: %s' % str(e))
        _, _, _, _, status, host_status, driver_status = \
            struct.unpack("4x4xxx2x4xPPP4x4x4xPBxxxHH4x4x4x", result)
        if status != 0x2: # status: CHECK_CONDITION
            raise error.TestError('SG_IO status: %d' % status)
        if host_status != 0:
            raise error.TestError('SG_IO host status: %d' % host_status)
        if driver_status != 0x8: # driver status: SENSE
            raise error.TestError('SG_IO driver status: %d' % driver_status)

        if scsi_sense[0] != 0x72: # resp. code: current error, descriptor format
            raise error.TestError('SENSE response code: %d' % scsi_sense[0])
        if scsi_sense[1] != 0: # sense key: No Sense
            raise error.TestError('SENSE key: %d' % scsi_sense[1])
        if scsi_sense[7] < 14: # additional length (ATA status is 14 - 1 bytes)
            raise error.TestError('ADD. SENSE too short: %d' % scsi_sense[7])
        if scsi_sense[8] != 0x9: # additional descriptor type: ATA Return Status
            raise error.TestError('SENSE descriptor type: %d' % scsi_sense[8])
        if scsi_sense[11] != 0: # errors: none
            raise error.TestError('ATA error code: %d' % scsi_sense[11])

        if scsi_sense[13] == 0x00: return 'standby'
        if scsi_sense[13] == 0x80: return 'idle'
        if scsi_sense[13] == 0xff: return 'active'
        return 'unknown(%d)' % scsi_sense[13]


    def run(self):
        """The Thread's run method."""
        try:
            self._time = time.time()
            self._running = True
            while(self._running):
                time.sleep(self._seconds_period)
                state = self._get_disk_state()
                new_time = time.time()
                if state in self._stats:
                    self._stats[state] += new_time - self._time
                else:
                    self._stats[state] = new_time - self._time
                self._time = new_time
        except error.TestError, e:
            self._error = e
            self._running = False


    def result(self):
        """Stop the logger and return dict with result percentages."""
        if (self._running):
            self._running = False
            self.join(self._seconds_period * 2)
        return AbstractStats.to_percent(self._stats)


    def get_error(self):
        """Returns the _error exception... please only call after result()."""
        return self._error
