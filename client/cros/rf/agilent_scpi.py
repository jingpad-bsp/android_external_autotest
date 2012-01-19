#!/usr/bin/python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import itertools

from autotest_lib.client.cros.rf import scpi
from autotest_lib.client.cros.rf.lan_scpi import LanScpi


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


class AgilentScpi(LanScpi):
    '''
    An Agilent device that supports SCPI.
    '''
    def __init__(self, expected_model, *args, **kwargs):
        super(AgilentScpi, self).__init__(*args, **kwargs)
        model = self.id.split(',')[1]
        if model != expected_model:
            raise scpi.Error('Expected model %s but got %s' % (
                    expected_model, model))

    def GetSerialNumber(self):
        '''Returns the serial number of the device.'''
        return self.id.split(',')[2]


class EXTScpi(AgilentScpi):
    '''
    An Agilent EXT (E6607A) device.
    '''
    def __init__(self, *args, **kwargs):
        super(EXTScpi, self).__init__('E6607A', *args, **kwargs)

    def SetupLTE(self, freq):
        '''Sets up LTE mode with the given center frequency.'''
        self.Send(['INST:SEL LTE',
                   'FREQ:CENT %d' % freq])

    def MeasureEVM(self):
        '''Returns an object containing EVM information.

        Attributes include:

          evm: The EVM, in percent (%)
          ofdm_sym_tx_power: The OFDM symbol transmit power,
            (dBm)
        '''
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


class ENAScpi(AgilentScpi):
    '''
    An Agilent ENA (E5071C) device.
    '''
    def __init__(self, *args, **kwargs):
        super(ENAScpi, self).__init__('E5071C', *args, **kwargs)

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
        ret.x_axis = self.Query(":CALC:SEL:DATA:XAX?", scpi.FLOATS)
        ret.traces = {}
        for i, p in zip(itertools.count(1), parameters):
            ret.traces[p] = (
                self.Query(":CALC:TRACE%d:DATA:FDAT?" % i, scpi.FLOATS)[0::2])
            if len(ret.x_axis) != len(ret.traces[p]):
                raise scpi.Error("x_axis has %d elements but trace has %d" %
                                 (len(x_axis, len_trace)))
        return ret
