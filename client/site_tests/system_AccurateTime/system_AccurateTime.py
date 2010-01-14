import commands, math, re
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

class system_AccurateTime(test.test):
    version = 1


    def __get_offset(self, string):
        offset = re.search(r'(-?[\d+\.]+)s', string)
        if offset is None:
            raise error.TestError('Unable to find offset in %s' % string)
        return float(offset.group(1))


    def run_once(self, max_offset):
        # Check ntpd is currently running
        if commands.getstatusoutput('pgrep ntpd')[0] != 0:
            raise error.TestError('NTP server was not already running')
        # Stop it since we cannot force ntp requests unless its not running
        if commands.getstatusoutput('initctl stop ntp')[0] != 0:
            raise error.TestError('NTP server could not be stopped')
        # Now grab the current time and get its offset
        (status, output) = commands.getstatusoutput('ntpd -g -u ntp:ntp -q')
        if status != 0:
            raise error.TestError('NTP current-time check failed')
        server_offset = self.__get_offset(output)
        logging.info("server time offset: %f" % server_ffset)

        if (abs(server_offset) > max_offset):
            raise error.TestError(
                'NTP server time offset was %fs > max offset %ds' %
                (server_offset, max_offset))
        # Restart server
        if commands.getstatusoutput('initctl start ntp')[0] != 0:
            raise error.TestError('NTP server could not be restarted')
