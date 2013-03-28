import argparse
import pexpect
import sys
import time

import common
from autotest_lib.client.cros.rf import agilent_scpi

class Labtool8797(object):
    """Labtool commands to control Marvell 8797."""


    def __init__(self, labtool_dir):
        self.labtool8797 = pexpect.spawn(labtool_dir+'/labtool')
        self.labtool8797.expect('Enter option:')


    def enter_option(self, option_string, expected_string):
        """Wrapper of pexpect for labtool.

        This is a wrapper for the following:
        1) Send option_string to self.labtool8797.
        2) Wait expected_string, and 'Enter option:'
        3) Return the intermediate output from labtool.

        @param option_string: option string that labtool would process.
        @param expected_string: the specific pattern to wait from labtool.
        @return the string in between the expected string and 'Enter option:' 
        """
        self.labtool8797.sendline(option_string)
        self.labtool8797.expect(expected_string)
        self.labtool8797.expect('Enter option:')
        return self.labtool8797.before


    def enter_wifi_menu(self):
        returned_string = self.enter_option('1', 'W87xx')
        print 'Entering: W8797' + returned_string


    def set_path(self, path):
        """Setting and verifying the TxRx Path.

        @param path: Tx and Rx path. 1 means antenna 1, 2 means antenna 2,
        3 means both antennas are on.
        """
        self.enter_option('10 %d' % path, '0x0')
        returned_string = self.enter_option('9', 'GetTxRxPath :')
        print 'Setting TX RX Path:' + returned_string


    def set_band(self, band):
        """Setting and verifying the band.

        @param band: frequency band. 0 means 2.4 GHz, 1 means 5 GHz.
        """
        self.enter_option('30 %d' % band, '0x0')
        returned_string = self.enter_option('29', 'GetModeAG: 0x0 :')
        print 'Setting Frequency Band:' + returned_string


    def set_channel(self, channel_no):
        """Setting and verifying the channel."""
        self.enter_option('12 %d' % channel_no, '0x00000000')
        returned_string = self.enter_option('11', 'RF Channel:')
        print 'Setting RF Channel:' + returned_string


    def count(self):
        """Counting the packets and clearing the count."""
        self.labtool8797.sendline('32')
        self.labtool8797.expect('Rx Packet')


    def get_error_rate(self):
        """Counting the packets and calculating the error rate."""
        self.count()
        self.labtool8797.expect('Multi Cast')
        rxpacket = float(self.labtool8797.before)
        self.labtool8797.expect('Err Count')
        multicast = float(self.labtool8797.before)
        self.labtool8797.expect('Enter option:')
        error = float(self.labtool8797.before)
        error_rate = error / multicast
        return (rxpacket, multicast, error, error_rate)


    def exit_wifi_menu(self):
        self.enter_option('99', 'Exit')


    def exit_labtool(self):
        self.labtool8797.sendline('99')
        self.labtool8797.expect('Exiting')


def sweep_power_get_sensitivity(labtool, n4010a, rx_power):
    """
    Interacting with N4010A and Labtool, finding the RX
    sensitivity by sweeping the power down.
    Receiver sensitivty is the minimum received power at
    which the packet error rate (PER) shall not exceed 10%.

    @param labtool: call Labtool8797.
    @param n4010a: call agilent_scpi.N4010ASCPI.
    @param rx_power: the DUT received power sent by N4010A.
    @return rx_sensitivity.
    """
    error_rate = 0
    while error_rate < 0.1:
        # Clearing count twice before transmitting
        labtool.count()
        labtool.count()
        # N4010A starts to transmit
        n4010a.set_amplitude(rx_power)
        n4010a.output_on()

        # Getting received packet count and error rate
        (rxpacket, multicast, error, error_rate) = (
            labtool.get_error_rate())
        print ('Rx Power: %d Rx Packet: %d Multi Cast: %d '
               'Error Count: %d Error Rate: %.003f' %
               (rx_power, rxpacket, multicast,
                error, error_rate))
        # Sweeping the power down
        rx_power -= 1

    # Backing up 2 dB. When the while loop breaks, the rx_power
    # still reduces 1 dB before exiting; also PER >= 10%, need
    # to add 1dB to make PER < 10%
    rx_sensitivity = rx_power + 2
    return rx_sensitivity


def find_sensitivity_for_channels_rates(n4010a, labtool, wifi_bands,
                                        data_rate_power_info, TEST_2G, TEST_5G):
    """
    Finding RX sensivity for different channels, data rates.

    @param n4010a: call agilent_scpi.N4010ASCPI.
    @param labtool: call Labtool8797.
    @param wifi_bands: the channels that would be tested.
    @param data_rate_power_info: the matching table of the data rates.
    and the starting power for the test.
    @param TEST_2G: flag for enable or disable 2GHz test.
    @param TEST_5G: flag for enable or disable 5GHz test.
    """
    for band_info, channel_info in wifi_bands:
        # Only run test when the 2G or 5G test flag is true
        if (band_info == 0 and TEST_2G) or (band_info == 1 and TEST_5G):
            labtool.set_band(band_info)

            for channel_no, freq in channel_info:
                # Setting the channel on N4010A
                n4010a.set_frequency(freq)
                # Setting the channel on DUT
                labtool.set_channel(channel_no)

                for data_rate, rx_power in data_rate_power_info:
                    # Selecting the waveform/sequence
                    n4010a.set_waveform(data_rate)
                    # Finding RX sensitivity
                    rx_sensitivity = sweep_power_get_sensitivity(
                        labtool, n4010a, rx_power)
                    print('RX Sensitivity at %s at channel %d  = %d dBm\n'
                          %(data_rate, channel_no, rx_sensitivity))


def connect_and_initialize_n4010a(n4010a):
    print 'Connecting to %s' % args.n4010a_host
    print 'Connected, Tester ID: %s' % n4010a.id
    n4010a.initialize(
        'This instrument is being\noperated remotely by\nPython script')
    print 'N4010A initialized'

def launch_labtool(labtool):
    labtool.enter_wifi_menu()
    labtool.set_path(3)

def cleanup(labtool, n4010a):
    labtool.exit_wifi_menu()
    labtool.exit_labtool()
    n4010a.output_off()
    n4010a.clear_message()
    print 'Finished!'

def main():
    # Short pause for putting DUT into the shieldbox
    print 'Beginning test in %s secs' % args.sleeptime
    time.sleep(float(args.sleeptime))

    n4010a = agilent_scpi.N4010ASCPI(args.n4010a_host)   
    connect_and_initialize_n4010a(n4010a)

    labtool = Labtool8797(args.labtool_dir) 
    launch_labtool(labtool)

    # Finding RX sensivity for various channels, data rates
    BAND_2G = 0
    BAND_5G = 1
    TEST_2G = True
    TEST_5G = True
    wifi_bands = (
        (BAND_2G, ((1, 2412*1e6), (6, 2437*1e6), (11, 2462*1e6))),
        (BAND_5G, ((36, 5180*1e6), (64, 5320*1e6), (165, 5825*1e6))))
    data_rate_power_info = (('MCS0', -70), ('MCS7', -50))
    
    find_sensitivity_for_channels_rates(n4010a, labtool, wifi_bands,
                                        data_rate_power_info, TEST_2G, TEST_5G)

    cleanup(labtool, n4010a)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--sleep', '-s', dest='sleeptime', default=5,
                        help='pausing time for putting DUT into the shieldbox')
    parser.add_argument('--host', dest='n4010a_host',
                        default='172.22.52.96',
                        help='the IP address of N4010A')
    parser.add_argument('--dir', '-d', dest='labtool_dir',
                        default='/usr/local/third_party/marvell_labtool',
                        help='the labtool binary directory')
    args = parser.parse_args()
    main()
