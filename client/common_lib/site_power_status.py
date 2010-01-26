import glob, logging, os, re
from autotest_lib.client.common_lib import error, utils


battery_fields = {
    'charge_full':          ['charge_full', float],
    'charge_full_design':   ['charge_full_design', float],
    'charge_now':           ['charge_now', float],
    'current_now':          ['current_now', float],
    'voltage_min_design':   ['voltage_min_design', float],
    'voltage_now':          ['voltage_now', float],
    'energy':               ['', ''],
    'energy_full':          ['', ''],
    'energy_full_design':   ['', ''],
    'energy_rate':          ['', ''],
    'remaining_time':       ['', '']
    }

linepower_fields = {
    'is_online':             ['online', int]
    }


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
    float remaining_time:     Remaining discharging time [h]
    float voltage_min_design: Minimum voltage by design [V]
    float voltage_now:        Voltage now [V]
    """

    def __init__(self, path=None):
        super(BatteryStat, self).__init__(battery_fields, path)
        self.update()


    def update(self):
        self.read_all_vals()

        self.charge_full = self.charge_full / 1000000
        self.charge_full_design = self.charge_full_design / 1000000
        self.charge_now = self.charge_now / 1000000
        self.current_now = self.current_now / 1000000
        self.voltage_min_design = self.voltage_min_design / 1000000
        self.voltage_now = self.voltage_now / 1000000

        self.energy =  self.voltage_now * self.charge_now
        self.energy_full = self.voltage_now * self.charge_full
        self.energy_full_design = self.voltage_now * self.charge_full_design
        self.energy_rate =  self.voltage_now * self.current_now

        self.remaining_time = 0
        if self.current_now:
            self.remaining_time =  self.energy / self.energy_rate


class LineStat(DevStat):
    """
    Power line status.

    Fields:

    bool online:              Line power online
    """

    def __init__(self, path=None):
        super(LineStat, self).__init__(linepower_fields, path)
        self.update()


    def update(self):
        self.read_all_vals()
        self.online = self.is_online == 1


class SysStat(object):
    """
    System power status for a given host.

    Fields:

    battery:   A list of BatteryStat objects.
    linepower: A list of LineStat opbjects.
    """

    def __init__(self):
        self.battery = None
        self.linepower = None
        battery_path = glob.glob('/sys/class/power_supply/BAT*')
        linepower_path = glob.glob('/sys/class/power_supply/AC*')
        if battery_path and linepower_path:
            self.battery_path = battery_path[0]
            self.linepower_path = linepower_path[0]
        else:
            raise error.TestError('Battery or Linepower path not found')


    def refresh(self):
        """
        Initialize device power status objects for a single battery and a
        single power line by parsing the output of devkit-power -d.
        """
        self.battery = [ BatteryStat(self.battery_path) ]
        self.linepower = [ LineStat(self.linepower_path) ]


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
