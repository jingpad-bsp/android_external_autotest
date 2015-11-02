#!/usr/bin/python
import logging
import numpy
import unittest

import common
from autotest_lib.client.cros.audio import audio_analysis
from autotest_lib.client.cros.audio import audio_data

class SpectralAnalysisTest(unittest.TestCase):
    def testSpectralAnalysis(self):
        rate = 48000
        length_in_secs = 0.5
        freq_1 = 490.0
        freq_2 = 60.0
        coeff_1 = 1
        coeff_2 = 0.3
        samples = length_in_secs * rate
        noise = numpy.random.standard_normal(samples) * 0.005
        x = numpy.linspace(0.0, (samples - 1) * 1.0 / rate, samples)
        y = (coeff_1 * numpy.sin(freq_1 * 2.0 * numpy.pi * x) +
             coeff_2 * numpy.sin(freq_2 * 2.0 * numpy.pi * x)) + noise
        results = audio_analysis.spectral_analysis(y, rate)
        # Results should contains
        # [(490, 1*k), (60, 0.3*k), (0, 0.1*k)] where 490Hz is the dominant
        # frequency with coefficient 1, 60Hz is the second dominant frequency
        # with coefficient 0.3, 0Hz is from Gaussian noise with coefficient
        # around 0.1. The k constant is resulted from window function.
        logging.debug('Results: %s', results)
        self.assertTrue(abs(results[0][0]-freq_1) < 1)
        self.assertTrue(abs(results[1][0]-freq_2) < 1)
        self.assertTrue(
                abs(results[0][1] / results[1][1] - coeff_1 / coeff_2) < 0.01)


    def testSpectralAnalysisRealData(self):
        """This unittest checks the spectral analysis works on real data."""
        binary = open('client/cros/audio/test_data/1k_2k.raw', 'r').read()
        data = audio_data.AudioRawData(binary, 2, 'S32_LE')
        saturate_value = audio_data.get_maximum_value_from_sample_format(
                'S32_LE')
        golden_frequency = [1000, 2000]
        for channel in [0, 1]:
            normalized_signal = audio_analysis.normalize_signal(
                    data.channel_data[channel],saturate_value)
            spectral = audio_analysis.spectral_analysis(
                    normalized_signal, 48000, 0.02)
            logging.debug('channel %s: %s', channel, spectral)
            self.assertTrue(abs(spectral[0][0] - golden_frequency[channel]) < 5,
                            'Dominant frequency is not correct')


    def testNotMeaningfulData(self):
        """Checks that sepectral analysis rejects not meaningful data."""
        rate = 48000
        length_in_secs = 0.5
        samples = length_in_secs * rate
        noise_amplitude = audio_analysis.MEANINGFUL_RMS_THRESHOLD * 0.5
        noise = numpy.random.standard_normal(samples) * noise_amplitude
        with self.assertRaises(audio_analysis.RMSTooSmallError):
            results = audio_analysis.spectral_analysis(noise, rate)


class NormalizeTest(unittest.TestCase):
    def testNormalize(self):
        y = [1, 2, 3, 4, 5]
        normalized_y = audio_analysis.normalize_signal(y, 10)
        expected = numpy.array([0.1, 0.2, 0.3, 0.4, 0.5])
        for i in xrange(len(y)):
            self.assertEqual(expected[i], normalized_y[i])


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
