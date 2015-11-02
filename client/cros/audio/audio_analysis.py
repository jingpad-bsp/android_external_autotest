# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module provides utilities to do audio data analysis."""

import logging
import numpy
import operator

# Only peaks with coefficient greater than 0.01 of the first peak should be
# considered. Note that this correspond to -40dB in the spectrum.
DEFAULT_MIN_PEAK_RATIO = 0.01

PEAK_WINDOW_SIZE_HZ = 20 # Window size for peak detection.

# The minimum RMS value of meaningful audio data.
MEANINGFUL_RMS_THRESHOLD = 0.001

class RMSTooSmallError(Exception):
    """Error when signal RMS is too small."""
    pass


def normalize_signal(signal, saturate_value):
    """Normalizes the signal with respect to the saturate value.

    @param signal: A list for one-channel PCM data.
    @param saturate_value: The maximum value that the PCM data might be.

    @returns: A numpy array containing normalized signal. The normalized signal
              has value -1 and 1 when it saturates.

    """
    signal = numpy.array(signal)
    return signal / float(saturate_value)


def spectral_analysis(signal, rate, min_peak_ratio=DEFAULT_MIN_PEAK_RATIO,
                      peak_window_size_hz=PEAK_WINDOW_SIZE_HZ):
    """Gets the dominant frequencies by spectral analysis.

    @param signal: A list of numbers for one-channel PCM data. This should be
                   normalized to [-1, 1] so the function can check if signal RMS
                   is too small to be meaningful.
    @param rate: Sampling rate.
    @param min_peak_ratio: The minimum peak_0/peak_i ratio such that the
                           peaks other than the greatest one should be
                           considered.
                           This is to ignore peaks that are too small compared
                           to the first peak peak_0.
    @param peak_window_size_hz: The window size in Hz to find the peaks.
                                The minimum differences between found peaks will
                                be half of this value.

    @returns: A list of tuples:
              [(peak_frequency_0, peak_coefficient_0),
               (peak_frequency_1, peak_coefficient_1),
               (peak_frequency_2, peak_coefficient_2), ...]
              where the tuples are sorted by coefficients.
              The last peak_coefficient will be no less than
              peak_coefficient * min_peak_ratio.

    """
    # Checks the signal is meaningful.
    signal_rms = numpy.linalg.norm(signal) / numpy.sqrt(len(signal))
    logging.debug('signal RMS = %s', signal_rms)
    if signal_rms < MEANINGFUL_RMS_THRESHOLD:
        raise RMSTooSmallError(
                'RMS %s is too small to be meaningful' % signal_rms)

    # First, pass signal through a window function to mitigate spectral leakage.
    y_conv_w = signal * numpy.hanning(len(signal))

    length = len(y_conv_w)

    # x_f is the frequency in Hz, y_f is the transformed coefficient.
    x_f = _rfft_freq(length, rate)
    y_f = 2.0 / length * numpy.fft.rfft(y_conv_w)

    # y_f is complex so consider its absolute value for magnitude.
    abs_y_f = numpy.abs(y_f)
    threshold = max(abs_y_f) * min_peak_ratio

    # Suppresses all coefficients that are below threshold.
    for i in xrange(len(abs_y_f)):
        if abs_y_f[i] < threshold:
            abs_y_f[i] = 0

    # Gets the peak detection window size in indice.
    # x_f[1] is the frequency difference per index.
    peak_window_size = int(peak_window_size_hz / x_f[1])

    # Detects peaks.
    peaks = _peak_detection(abs_y_f, peak_window_size)

    # Transform back the peak location from index to frequency.
    results = []
    for index, value in peaks:
        results.append((x_f[index], value))
    return results


def _rfft_freq(length, rate):
    """Gets the frequency at each index of real FFT.

    @param length: The window length of FFT.
    @param rate: Sampling rate.

    @returns: A numpy array containing frequency corresponding to
              numpy.fft.rfft result at each index.

    """
    # The difference in Hz between each index.
    val = rate / float(length)
    # Only care half of frequencies for FFT on real signal.
    result_length = length // 2 + 1
    return numpy.linspace(0, (result_length - 1) * val, result_length)


def _peak_detection(array, window_size):
    """Detects peaks in an array.

    A point (i, array[i]) is a peak if array[i] is the maximum among
    array[i - half_window_size] to array[i + half_window_size].
    If array[i - half_window_size] to array[i + half_window_size] are all equal,
    then there is no peak in this window.

    @param window_size: The window to detect peaks.

    @returns: A list of tuples:
              [(peak_index_1, peak_value_1), (peak_index_2, peak_value_2), ...]
              where the tuples are sorted by peak values.

    """
    half_window_size = window_size / 2
    length = len(array)

    def find_max(numbers):
        """Gets the index where maximum value happens.

        @param numbers: A list of numbers.

        @returns: (index, value) where value = numbers[index] is the maximum
                  among numbers.

        """
        index, value = max(enumerate(numbers), key=lambda x: x[1])
        return index, value

    results = []
    for mid in xrange(length):
        left = max(0, mid - half_window_size)
        right = min(length - 1, mid + half_window_size)
        numbers_in_window = array[left:right + 1]
        max_index, max_value = find_max(numbers_in_window)

        # Add the offset back.
        max_index = max_index + left

        # If all values are the same then there is no peak in this window.
        if max_value != min(numbers_in_window) and max_index == mid:
            results.append((mid, max_value))

    # Sort the peaks by values.
    return sorted(results, key=lambda x: x[1], reverse=True)
