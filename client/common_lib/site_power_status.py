import logging, re
from autotest_lib.client.common_lib import utils


battery_fields = {
    'energy':             [ re.compile(r'energy:\s*'
                                       r'([0-9.]+)\s*Wh'),
                            float ],
    'energy_full':        [ re.compile(r'energy-full:\s*'
                                       r'([0-9.]+)\s*Wh'),
                            float ],
    'energy_full_design': [ re.compile(r'energy-full-design:\s*'
                                       r'([0-9.]+)\s*Wh'),
                            float ],
    'energy_rate':        [ re.compile(r'energy-rate:\s*'
                                       r'([0-9.]+)\s*W'),
                            float ],
    }


linepower_fields = {
    'online':             [ re.compile(r'online:\s*(yes|no)'),
                            bool ],
    }


class DevStat(object):
    """
    Device power status. This class implements generic status initialization
    and parsing routines.
    """

    def __init__(self, fields, status=None):
        self.fields = fields
        self.parse_status(status)


    def reset_fields(self):
        """
        Reset all class fields to None to mark their status as unknown.
        """
        for field in self.fields.iterkeys():
            setattr(self, field, None)


    def parse_status(self, status):
        """
        Parse the power status output and initialize all class fields.
        """
        self.reset_fields()

        if status is None:
            return

        for line in status.split('\n'):
            line = line.strip()
            self.parse_line(line)


    def parse_line(self, line):
        """
        Parse a line from the power status output.
        """
        for field, prop in self.fields.iteritems():
            match = prop[0].search(line)
            if match:
                field_type = prop[1]
                field_val = match.group(1)
                val = None
                if field_type is bool:
                    val = field_val == "yes"
                else:
                    val = field_type(field_val)
                setattr(self, field, val)
                logging.info("%s: %s" % (field, getattr(self, field)))
                break


class BatteryStat(DevStat):
    """
    Battery status.

    Fields:

    float energy:             Current battery charge [Wh]
    float energy_full:        Last full capacity reached [Wh]
    float energy_full_design: Full capacity by design [Wh]
    float energy_rate:        Batter discharge rate [W]
    """

    def __init__(self, status=None):
        super(BatteryStat, self).__init__(battery_fields, status)


class LineStat(DevStat):
    """
    Power line status.

    Fields:

    bool online:              Line power online
    """

    def __init__(self, status=None):
        super(LineStat, self).__init__(linepower_fields, status)


class SysStat(object):
    """
    System power status for a given host.

    Fields:

    host:      Host associated with this status (None means local host)
    battery:   A list of BatteryStat objects.
    linepower: A list of LineStat opbjects.
    """

    def __init__(self, host=None):
        self.host = host
        self.battery = None
        self.linepower = None


    def refresh(self):
        """
        Initialize device power status objects for a single battery and a
        single power line by parsing the output of devkit-power -d.
        """
        status_cmd = "devkit-power -d"
        if self.host is None:
            status = utils.run(status_cmd)
        else:
            status = self.host.run(status_cmd)
        logging.info(status.stdout)
        self.battery = [ BatteryStat(status.stdout) ]
        self.linepower = [ LineStat(status.stdout) ]


def get_status(host=None):
    """
    Return a new power status object (SysStat) for the given host. If a host is
    not specified, assume the local host. A new power status snapshot for a
    given host can be obtained by either calling this routine again and
    constructing a new SysStat object, or by using the refresh method of the
    SysStat object.
    """
    status = SysStat(host)
    status.refresh()
    return status
