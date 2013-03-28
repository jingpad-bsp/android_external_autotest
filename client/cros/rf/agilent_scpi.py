#!/usr/bin/python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import bisect
import itertools
import math
from StringIO import StringIO

from autotest_lib.client.cros.rf import lan_scpi
from autotest_lib.client.cros.rf.lan_scpi import LANSCPI
from autotest_lib.client.cros.rf.lan_scpi import Error


def check_trace_valid(x_values, y_values):
    """
    Raises an exception if x_values and y_values cannot form a valid trace.

    Args:
        x_values: A list of X values.
        y_values: A list of Y values.

    Raises:
        An error raises if
        (1) x_values is empty.
        (2) x_values is not an increasing sequence.
        (3) x_values and y_values are not equal in length.
    """
    if not x_values:
        raise Error("Parameter x_values is empty")
    if len(x_values) != len(y_values):
        raise Error("Parameter x_values and y_values are not equal in length")
    if not all(x <= y for x, y in zip(x_values, x_values[1:])):
        raise Error("Parameter x_values is not an increasing sequence")


def interpolate(x_values, y_values, x_position):
    """
    Returns an interpolated (linear) y-value at x_position.

    This function is especially designed for interpolating values from a
    Network Analyzer. It happens in practice that x_values will have
    sorted, duplicated values. In addition, y_values may be different for
    identical x value. The function behavior under this situation is as follows:
        (1) The function finds a right sentinel for interpolating, which is the
            smallest index that less of equal to the x_position.
        (2) If it is exactly the x_position, returns the y_value.
        (3) Otherwise, interpolate values as the left sentinel is just the
            one before right sentinel.
    Example used in the unittest elaborates more on this.

    Args:
        x_values: A list of X values.
        y_values: A list of Y values.
        x_position: The position where we want to interpolate.

    Returns:
        Interpolated value. For example:
        interpolate([10, 20], [0, 10], 15) returns 5.0

    Raises:
        An error raises if
        (1) x_position is not in the range of x_values.
        (2) Arguments failed to pass check_trace_valid().
    """
    check_trace_valid(x_values, y_values)

    # Check if the x_position is inside some interval in the trace
    if x_position < x_values[0] or x_position > x_values[-1]:
        raise Error(
            "x_position is not in the current range of x_values[%s,%s]" %
            (x_values[0], x_values[-1]))

    # Binary search where to interpolate the x_position
    right_index = bisect.bisect_left(x_values, x_position)
    if x_position == x_values[right_index]:
        return y_values[right_index]

    # Interpolate the value according to the x_position
    delta_interval = (float(x_position - x_values[right_index - 1]) /
            float(x_values[right_index] - x_values[right_index - 1]))
    return (y_values[right_index - 1] +
        (y_values[right_index] - y_values[right_index - 1]) * delta_interval)


def enum(*elements):
    """
    Returns an enumeration of the given elements.
    """
    return type('Enum', (),
                dict([(i, i) for i in elements]))


class POD(object):
    """
    A POD (plain-old-data) object containing arbitrary fields.
    """
    def __init__(self, **args):
        self.__dict__.update(args)

    def __repr__(self):
        """
        Returns a representation of the object, including its properties.
        """
        return (self.__class__.__name__ + '(' +
                ', '.join('%s=%s' % (k, repr(getattr(self, k)))
                          for k in sorted(self.__dict__.keys())
                          if k[0] != '_')
                + ')')


class AgilentSCPI(LANSCPI):
    """
    An Agilent device that supports SCPI.
    """
    def __init__(self, expected_model, *args, **kwargs):
        super(AgilentSCPI, self).__init__(*args, **kwargs)
        self.id_fields = [x.strip() for x in self.id.split(',')]
        model = self.id_fields[1]
        if model != expected_model:
            raise Error('Expected model %s but got %s' % (
                    expected_model, model))

    def get_serial_number(self):
        """Returns the serial number of the device."""
        return self.id_fields[2]


class N4010ASCPI(AgilentSCPI):
    """
    An Agilent Wireless Connectivity Set (N4010A) device.
    """
    MISSING_HARDWARE_ERROR_ID = -241

    def __init__(self, *args, **kwargs):
        super(N4010ASCPI, self).__init__('N4010A', *args, **kwargs)

    def quick_calibrate(self):
        self.Send('CAL:QUICk')

    def initialize(self, message):
        """
        Set the front panel message, turn off the output,
        detect the IO port, load the loss table,
        set the trigger type and clock.
        """
        self.send([
           'DIAG:FPAN:MESS:CLE',
           'DIAG:FPAN:MESS:SET "%s"' % message,
           'OUTPut OFF',
           'DIAGnostic:HW:SCAR:PORT:STATe Port1',
           'DIAG:HW:SCAR:LCOM:COUP ON',
           'SOURce:RADio:ARB:TRIGger:TYPE SING',
           'SOURce:RADio:ARB:CLOCK:SRATe 40000000'])

    def set_frequency(self, freq):
        self.send(['SOURce:FREQuency:FIXed %d' % freq])

    def set_waveform(self, data_rate):
        self.send([
            'SOURce:RADio:ARB:WAVEform "SEQ:%s-20MHZ.SEQ"' % data_rate])

    def set_amplitude(self, power):
        self.send([
            'SOURce:RADio:ARB:STATe ON',
            'SOURce:POWer:LEVel:IMMediate:AMPLitude %d' % power])

    def output_on(self):
        self.send([
            'OUTPut ON',
            'SOURce:RADio:ARB:TRIGger:SOFT'])

    def output_off(self):
        self.send([
            'OUTPut OFF'])

    def clear_message(self):
        self.send(['DIAG:FPAN:MESS:CLE'])

    def DSSS_demod(self, freq):
        class DSSS(POD):
            pass
        ret = DSSS()

        self.send([
                'DIAG:HW:BAND 22.0e6',
                'DIAG:HW:FEA:RANG 19',
                'DIAG:HW:DAP:ACQ:TIME 0.005',
                'DIAG:HW:FEA:FREQ %d' % freq,
                'DIAG:HW:DAP:TRIG:DELay -2E-06',
                'DIAG:HW:DAP:DEC 2',
                ':DIAG:HW:DAP:MEAS:RESULTS 0,0'])
        ret.iq = self.query('DIAG:HW:DAP:READ:GEN:BBIQ? 1',
                            lan_scpi.BINARY_FLOATS_WITH_LENGTH(500000))

        self._check_overrange()
        return ret

    def OFDM_demod(self, freq):
        self.send([
                'DIAG:HW:SCAR:LCOM:COUP ON',
                'DIAG:HW:BAND 22e6',
                'DIAG:HW:FEA:FREQ %d' % freq,
                'DIAG:HW:DAP:DEC 1',
                'DIAG:HW:FEA:RANG 19',
                'DIAG:HW:DAP:ACQ:TIME 0.005',  # a.k.a. MaxPacketLength
                'DIAG:HW:DAP:TRIG:SOUR BURSt',
                'DIAG:HW:DAP:TRIG:SLOPe POS',
                'DIAG:HW:DAP:TRIG:LEVel -13',
                'DIAG:HW:DAP:TRIG:DELay -2E-06',
                'DIAG:HW:DAP:TRIG:IDLE 1E-06',
                'DIAG:HW:DAP:MODE WLAN,OFDM',
                'DIAG:HW:DAP:MEAS:WLAN:OFDM:OPT 0,1,1,0,1,1',
                # Note: 205 corresponds to MaxSymbolsUsed (50=49+1)
                ('DIAG:HW:DAP:MEAS:WLAN:OFDM:DEM 0,206,205,0,'
                 '312500,1E+08,-3.125,1,0,1,1,1,0,2,0'),
                'DIAG:HW:DAP:MEAS:RES 0,0'])

        class OFDM(POD):
            pass
        ret = OFDM()
        ret.scale = self.query('DIAG:HW:DAP:READ:WLAN:OFDM:SCAL?',
                               lan_scpi.FLOATS)
        ret.vector = self.query(
            'DIAG:HW:DAP:FETCh:WLAN:OFDM:VECT:FLAT?',
            lan_scpi.BINARY_FLOATS_WITH_LENGTH(106))

        self._check_overrange()

        return ret

    def measure_power(self, freq, range=19, level=-14):
        """
        Returns an object containing avg and peak power.

        Args:
            freq: frequency at which to measure power.
            range: ADC max range (dBm).
            level: Trigger level (dBm).

        Returns:
            An object with the following attributes:
                avg_power: Average power (dBm).
                peak_power: Peak power (dBm).
        """
        try:
            self.send('DIAG:HW:SCAR:LCOM:COUP ON')
        except Error as e:
            if e.error_id == self.MISSING_HARDWARE_ERROR_ID:
                pass  # No worries, there is just no N4011 attached
            else:
                raise

        self.send(
            [
             'DIAG:HW:BAND 22e6',
             'DIAG:HW:FEA:FREQ %d' % freq,
             'DIAG:HW:FEA:RANG %d' % range,
             'DIAG:HW:DAP:ACQ:TIME  0.0002',
             'DIAG:HW:DAP:TRIG:SOUR BURSt',
             'DIAG:HW:DAP:TRIG:SLOPe POS',
             'DIAG:HW:DAP:TRIG:LEVel %d' % level,
             'DIAG:HW:DAP:TRIG:DELay 0',
             'DIAG:HW:DAP:TRIG:IDLE 1E-06',
             'DIAG:HW:DAP:MEAS:RESULTS 0,0',
             'DIAG:HW:DAP:DEC 1',
             'DIAG:HW:DAP:MODE generic,off',
             'DIAG:HW:DAP:MEAS:RESULTS 1,1',
             'DIAG:HW:DAP:MEAS:RESULTS 65537,1'
             ])

        class Power(POD):
            pass
        ret = Power(
            avg_power=self.query('DIAG:HW:DAP:READ:MISC:APOW? 1', float),
            peak_power=self.query('DIAG:HW:DAP:READ:MISC:PPOW? 1', float))

        self.send('DIAG:HW:DAP:MEAS:RESULTS 1,1')
        self._check_overrange()
        return ret

    def _check_overrange(self):
        """
        Raises an exception if an ADC overrange has occurred.
        """
        if self.query('DIAG:HW:DAP:ACQ:ADC:OVERrange?', int):
            raise Error('ADC overrange')


class EXTSCPI(AgilentSCPI):
    """
    An Agilent EXT (E6607A) device.
    """
    MODES = enum('LTE', 'CDMA1XEV', 'WCDMA', 'GSM')
    PORTS = enum('RFIn', 'RFOut', 'RFIO1', 'RFIO2')

    def __init__(self, *args, **kwargs):
        super(EXTSCPI, self).__init__('E6607A', *args, **kwargs)

    def measure_channel_power(self, mode, freq, port=PORTS.RFIn):
        """
        Measures channel power in the given mode and center frequency.

        Mode is an element of the MODES enumeration.
        """
        if port == self.PORTS.RFIn:
            port = 'RF'

        self.send(['INST:SEL %s' % mode,
                   'OUTP OFF',
                   'FEED:RF:PORT %s' % port,
                   'FREQ:CENT %d' % freq])
        return self.query('MEAS:CHP:CHP?', float)

    def enable_source(self, mode, freq, port=PORTS.RFOut, power_dbm=-45):
        # Sanity check power to avoid frying anything.
        assert power_dbm < -25, (
            'Power output is capped at -25 dBm')
        self.send(['INST:SEL %s' % mode,
                   'OUTP ON',
                   'FEED:RF:PORT:OUTP %s' % port,
                   'SOUR:POW %d' % power_dbm,
                   'OUTP:MOD OFF',
                   'SOUR:FREQ %d' % freq])

    def disable_source(self):
        self.send(['OUTP:OFF'])

    def measure_LTE_EVM(self, freq):
        """Returns an object containing EVM information.

        The information is measured in LTE mode at the given
        frequency.

        Attributes of the returned object are:

          evm: The EVM, in percent (%)
          ofdm_sym_tx_power: The OFDM symbol transmit power,
            (dBm)
        """
        self.send(['INST:SEL LTE',
                   'FREQ:CENT %d' % freq])

        data = self.query('MEAS:EVM?').split(',')

        field_map = {'evm': 0,
                     'ofdm_sym_tx_power': 11}

        class EVM(POD):
            pass

        return EVM(
            **dict([(k, float(data[index]))
                    for k, index in field_map.iteritems()]))

    def auto_align(self, enabled):
        """Enables or disables auto-alignments."""
        self.send(':CAL:AUTO %S' % ('ON' if enabled else 'OFF'))

    def save_state(self, state_file):
        """Saves the state of the machine to the given path."""
        self.send(':MMEM:STOR:STAT %s' % self.Quote(state_file))

    def load_state(self, state_file):
        """Saves the state of the machine from the given path."""
        self.send(':MMEM:STOR:STAT %s' % self.Quote(state_file))


class ENASCPI(AgilentSCPI):
    """
    An Agilent ENA (E5071C) device.
    """
    PARAMETERS = enum('S11', 'S12', 'S21', 'S22')

    def __init__(self, *args, **kwargs):
        super(ENASCPI, self).__init__('E5071C', *args, **kwargs)

    def load_state(self, state):
        """
        Loads saved state from a file.

        Args:
            state: The file name for the state; or a number indicating
                the state in the "Recall State" menu.
        """
        if type(state) == int:
            state = 'STATE%02d.STA' % state
        self.send(':MMEM:LOAD %s' % self.Quote(state))

    def save_screen(self, filename):
        """
        Saves the current screen to a portable network graphics (PNG) file.
        The default store path in E5071C is under disk D.
        """
        self.send([':MMEMory:STORe:IMAGe "%s.png"' % filename])

    def set_marker(self, channel, marker_num, marker_freq):
        """
        Saves the marker at channel.
        Usage:
        Set marker 5 to 600MHz on channel 1.

        set_marker(1, 5, 600*1e6)
        """
        # TODO(itspeter): understand why channel doesn't make a difference.

        # http://ena.tm.agilent.com/e5061b/manuals/webhelp/eng/
        # programming/command_reference/calculate/scpi_calculate
        # _ch_selected_marker_mk_x.htm#Syntax

        #:CALCulate{[1]-4}[:SELected]:MARKer{[1]-10}:X <numeric>
        buffer_str = ':CALCulate%d:SELected:MARKer%d:X %f' % (
            channel, marker_num, float(marker_freq))
        self.send([buffer_str])

    def set_linear_sweep(self, min_freq, max_freq):
        """
        Sets the range to be a linear sweep between min_freq and max_freq.

        Args:
            min_freq: The minimum frequency in Hz.
            max_freq: The maximum frequency in Hz.
        """
        self.send([':SENS:SWEep:TYPE LINear',
                   ':SENS:FREQ:STAR %d' % min_freq,
                   ':SENS:FREQ:STOP %d' % max_freq])

    def set_sweep_segments(self, segments):
        """
        Sets a collection of sweep segments.

        Args:
            segments: An array of 3-tuples.  Each tuple is of the
                form (min_freq, max_freq, points) as follows:

                    min_freq: The segment's minimum frequency in Hz.
                    max_freq: The segment's maximum frequency in Hz.
                    points: The number of points in the segment.

                The frequencies must be monotonically increasing.
        """
        # Check that the segments are all 3-tuples and that they are
        # in increasing order of frequency.
        for i in xrange(len(segments)):
            min_freq, max_freq, pts = segments[i]
            assert max_freq >= min_freq
            if i < len(segments) - 1:
                assert segments[i+1][0] >= min_freq

        data = [
            5,              # Magic number from the device documentation
            0,              # Stop/stop values
            0,              # No per-segment IF bandwidth setting
            0,              # No per-segment sweep delay setting
            0,              # No per-segment sweep mode setting
            0,              # No per-segment sweep time setting
            len(segments),  # Number of segments
        ] + list(sum(segments, ()))
        self.send([':SENS:SWEep:TYPE SEGMent',
                   (':SENS:SEGMent:DATA %s' %
                    ','.join(str(x) for x in data))])

    def get_traces(self, parameters):
        """
        Collects a set of traces based on the current sweep.

        Returns:
            A Traces object containing the following attributes:
                x_axis: An array of X-axis values.
                traces: A map from each parameter name to an array
                    of values for that trace.

            Example:
                ena.set_linear_sweep(700e6, 2200e6)
                data = ena.get_traces(['S11', 'S12', 'S22'])
                print zip(data.x_axis, data.traces['S11'])
        """
        assert len(parameters) > 0
        assert len(parameters) <= 4

        commands = [':CALC:PAR:COUN %d' % len(parameters)]
        for i, p in zip(itertools.count(1), parameters):
            commands.append(':CALC:PAR%d:DEF %s' % (i, p))
        self.send(commands)

        class Traces(POD):
            def tsv(self):
                """
                Returns the traces in TSV (tab-separated values) format.  The
                first column is the frequency, and each trace is in a separate
                column.
                """
                ret = StringIO()
                print >>ret, "\t".join(["freq"] + self.parameters)
                for row in zip(self.x_axis,
                               *[self.traces[p] for p in self.parameters]):
                    print >>ret, "\t".join(str(c) for c in row)
                return ret.getvalue()

            def get_freq_response(self, freq, parameter):
                """
                Returns corresponding frequency response given the parameter.

                If the particular frequency was not sampled, uses linear
                interpolation to estimate the response.

                Args:
                    freq: The frequency we want to obtain from the traces.
                    parameter: One of the parameters provided in
                        ENASCPI.PARAMETERS.

                Returns:
                    A floating point value in dB at freq.
                """
                if parameter not in self.traces:
                    raise Error("No trace available for parameter %s" %
                                parameter)
                return interpolate(self.x_axis, self.traces[parameter], freq)

        ret = Traces()
        ret.parameters = parameters
        ret.x_axis = self.query(":CALC:SEL:DATA:XAX?", lan_scpi.FLOATS)
        ret.traces = {}
        for i, p in zip(itertools.count(1), parameters):
            ret.traces[p] = (
                self.query(":CALC:TRACE%d:DATA:FDAT?" % i,
                           lan_scpi.FLOATS)[0::2])
            if len(ret.x_axis) != len(ret.traces[p]):
                raise Error("x_axis has %d elements but trace has %d" %
                            (len(x_axis, len_trace)))
            check_trace_valid(ret.x_axis, ret.traces[p])
        return ret
