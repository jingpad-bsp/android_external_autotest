#!/usr/bin/python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import itertools
import math

from autotest_lib.client.cros.rf import lan_scpi
from autotest_lib.client.cros.rf.lan_scpi import LANSCPI
from autotest_lib.client.cros.rf.lan_scpi import Error


def Enum(*elements):
    '''
    Returns an enumeration of the given elements.
    '''
    return type('Enum', (),
                dict([(i, i) for i in elements]))


class POD(object):
    '''
    A POD (plain-old-data) object containing arbitrary fields.
    '''
    def __init__(self, **args):
        self.__dict__.update(args)

    def __repr__(self):
        '''
        Returns a representation of the object, including its properties.
        '''
        return (self.__class__.__name__ + '(' +
                ', '.join('%s=%s' % (k, repr(getattr(self, k)))
                          for k in sorted(self.__dict__.keys())
                          if k[0] != '_')
                + ')')


class AgilentSCPI(LANSCPI):
    '''
    An Agilent device that supports SCPI.
    '''
    def __init__(self, expected_model, *args, **kwargs):
        super(AgilentSCPI, self).__init__(*args, **kwargs)
        self.id_fields = [x.strip() for x in self.id.split(',')]
        model = self.id_fields[1]
        if model != expected_model:
            raise Error('Expected model %s but got %s' % (
                    expected_model, model))

    def GetSerialNumber(self):
        '''Returns the serial number of the device.'''
        return self.id_fields[2]


class N4010ASCPI(AgilentSCPI):
    '''
    An Agilent Wireless Connectivity Set (N4010A) device.
    '''
    def __init__(self, *args, **kwargs):
        super(N4010ASCPI, self).__init__('N4010A', *args, **kwargs)

    def QuickCalibrate(self):
        self.Send('CAL:QUICk')

    def DSSSDemod(self, freq):
        class DSSS(POD):
            pass
        ret = DSSS()

        self.Send([
                'DIAG:HW:BAND 22.0e6',
                'DIAG:HW:FEA:RANG 19',
                'DIAG:HW:DAP:ACQ:TIME 0.005',
                'DIAG:HW:FEA:FREQ %d' % freq,
                'DIAG:HW:DAP:TRIG:DELay -2E-06',
                'DIAG:HW:DAP:DEC 2',
                ':DIAG:HW:DAP:MEAS:RESULTS 0,0'])
        ret.iq = self.Query('DIAG:HW:DAP:READ:GEN:BBIQ? 1',
                            lan_scpi.BINARY_FLOATS_WITH_LENGTH(500000))

        self._CheckOverrange()
        return ret

    def OFDMDemod(self, freq):
        self.Send([
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
        ret.scale = self.Query('DIAG:HW:DAP:READ:WLAN:OFDM:SCAL?',
                               lan_scpi.FLOATS)
        ret.vector = self.Query(
            'DIAG:HW:DAP:FETCh:WLAN:OFDM:VECT:FLAT?',
            lan_scpi.BINARY_FLOATS_WITH_LENGTH(106))

        self._CheckOverrange()

        return ret

    def MeasurePower(self, freq):
        '''
        Returns and object containing avg and peak power.

        Attributes of the returned object:

          avg_power: Average power (dBm)
          peak_power: Peak power (dBm)
        '''
        self.Send(
            ['DIAG:HW:SCAR:LCOM:COUP ON',
             'DIAG:HW:BAND 22e6',
             'DIAG:HW:FEA:FREQ %d' % freq,
             'DIAG:HW:FEA:RANG 19',
             'DIAG:HW:DAP:ACQ:TIME  0.0002',
             'DIAG:HW:DAP:TRIG:SOUR BURSt',
             'DIAG:HW:DAP:TRIG:SLOPe POS',
             'DIAG:HW:DAP:TRIG:LEVel -14',
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
            avg_power=self.Query('DIAG:HW:DAP:READ:MISC:APOW? 1', float),
            peak_power=self.Query('DIAG:HW:DAP:READ:MISC:PPOW? 1', float))

        self.Send('DIAG:HW:DAP:MEAS:RESULTS 1,1')
        self._CheckOverrange()
        return ret

    def _CheckOverrange(self):
        '''
        Raises an exception if an ADC overrange has occurred.
        '''
        if self.Query('DIAG:HW:DAP:ACQ:ADC:OVERrange?', int):
            raise Error('ADC overrange')


class EXTSCPI(AgilentSCPI):
    '''
    An Agilent EXT (E6607A) device.
    '''
    MODES = Enum('LTE', 'CDMA1XEV', 'WCDMA', 'GSM')
    PORTS = Enum('RFIn', 'RFOut', 'RFIO1', 'RFIO2')

    def __init__(self, *args, **kwargs):
        super(EXTSCPI, self).__init__('E6607A', *args, **kwargs)

    def MeasureChannelPower(self, mode, freq, port=PORTS.RFIn):
        '''
        Measures channel power in the given mode and center frequency.

        Mode is an element of the MODES enumeration.
        '''
        if port == self.PORTS.RFIn:
            port = 'RF'

        self.Send(['INST:SEL %s' % mode,
                   'OUTP OFF',
                   'FEED:RF:PORT %s' % port,
                   'FREQ:CENT %d' % freq])
        return self.Query('MEAS:CHP:CHP?', float)

    def EnableSource(self, mode, freq, port=PORTS.RFOut, power_dbm=-45):
        # Sanity check power to avoid frying anything.
        assert power_dbm < -25, (
            'Power output is capped at -25 dBm')
        self.Send(['INST:SEL %s' % mode,
                   'OUTP ON',
                   'FEED:RF:PORT:OUTP %s' % port,
                   'SOUR:POW %d' % power_dbm,
                   'OUTP:MOD OFF',
                   'SOUR:FREQ %d' % freq])

    def DisableSource(self):
        self.Send(['OUTP:OFF'])

    def MeasureLTEEVM(self, freq):
        '''Returns an object containing EVM information.

        The information is measured in LTE mode at the given
        frequency.

        Attributes of the returned object are:

          evm: The EVM, in percent (%)
          ofdm_sym_tx_power: The OFDM symbol transmit power,
            (dBm)
        '''
        self.Send(['INST:SEL LTE',
                   'FREQ:CENT %d' % freq])

        data = self.Query('MEAS:EVM?').split(',')

        field_map = {'evm': 0,
                     'ofdm_sym_tx_power': 11}

        class EVM(POD):
            pass

        return EVM(
            **dict([(k, float(data[index]))
                    for k, index in field_map.iteritems()]))

    def AutoAlign(self, enabled):
        '''Enables or disables auto-alignments.'''
        self.Send(':CAL:AUTO %S' % ('ON' if enabled else 'OFF'))

    def SaveState(self, state_file):
        '''Saves the state of the machine to the given path.'''
        self.Send(':MMEM:STOR:STAT %s' % self.Quote(state_file))

    def LoadState(self, state_file):
        '''Saves the state of the machine from the given path.'''
        self.Send(':MMEM:STOR:STAT %s' % self.Quote(state_file))


class ENASCPI(AgilentSCPI):
    '''
    An Agilent ENA (E5071C) device.
    '''
    def __init__(self, *args, **kwargs):
        super(ENASCPI, self).__init__('E5071C', *args, **kwargs)

    def LoadState(self, state):
        '''
        Loads saved state from a file.

        Parameters:
            state: The file name for the state; or a number indicating
                the state in the "Recall State" menu.
        '''
        if type(state) == int:
            state = 'STATE%02d.STA' % state
        self.Send(':MMEM:LOAD %s' % self.Quote(state))

    def GetTraces(self, min_freq, max_freq, parameters):
        '''
        Collects a set of traces.

        Parameters:
            min_freq: The minimum frequency in the span.
            max_freq: The maximum frequency in the span

        Returns:
            A Traces object containing the following attributes:
                x_axis: An array of X-axis values.
                traces: A map from each parameter name to an array
                    of values for that trace.

            Example:
                data = ena.GetTraces(700e6, 2200e6, ['S11', 'S12', 'S22'])
                print zip(data.x_axis, data.traces['S11'])
        '''
        assert len(parameters) > 0
        assert len(parameters) <= 4

        commands = [':CALC:PAR:COUN %d' % len(parameters),
                    ':SENS:FREQ:STAR %d' % min_freq,
                    ':SENS:FREQ:STOP %d' % max_freq]
        for i, p in zip(itertools.count(1), parameters):
            commands.append(':CALC:PAR%d:DEF %s' % (i, p))
        self.Send(commands)

        class Traces(POD):
            pass

        ret = Traces()
        ret.x_axis = self.Query(":CALC:SEL:DATA:XAX?", lan_scpi.FLOATS)
        ret.traces = {}
        for i, p in zip(itertools.count(1), parameters):
            ret.traces[p] = (
                self.Query(":CALC:TRACE%d:DATA:FDAT?" % i,
                           lan_scpi.FLOATS)[0::2])
            if len(ret.x_axis) != len(ret.traces[p]):
                raise Error("x_axis has %d elements but trace has %d" %
                            (len(x_axis, len_trace)))
        return ret
