#!/usr/bin/python2.7
# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import itertools
import subprocess
import sys

import numpy


class Error(Exception):
    """Module error class."""


def LinearRegression(x, y):
    """Perform a linear regression using numpy.

    @param x: Array of x-coordinates of the samples
    @param y: Array of y-coordinates of the samples
    @return: ((slope, intercept), r-squared)
    """
    # p(x) = p[0]*x**1 + p[1]
    p, (residual,) = numpy.polyfit(x, y, 1, full=True)[:2]
    # Calculate the coefficient of determination (R-squared) from the
    # "residual sum of squares"
    # Reference:
    # http://en.wikipedia.org/wiki/Coefficient_of_determination
    r2 = 1 - (residual / (y.size*y.var()))

    # Alternate calculation for R-squared:
    #
    # Calculate the coefficient of determination (R-squared) as the
    # square of the  sample correlation coefficient,
    # which can be calculated from the variances and covariances.
    # Reference:
    # http://en.wikipedia.org/wiki/Correlation#Pearson.27s_product-moment_coefficient
    #V = numpy.cov(x, y, ddof=0)
    #r2 = (V[0,1]*V[1,0]) / (V[0,0]*V[1,1])

    return p, r2


def GatherPerfStats(noploop, events, progress_func=lambda i, j: None):
    """Run perf stat with the given events and noploop program.

    @param noploop: path to noploop binary. It should take one argument (number
        of loop iterations) and produce no output.
    @param events: value to pass to '-e' arg of perf stat.
    @param progress_func: function that tracks progress of running the
        benchmark. takes two arguments for the outer and inner iteration
        numbers.
    @returns: List of dicts.
    """
    facts = []
    for i, j in itertools.product(xrange(10), xrange(5)):
        progress_func(i, j)
        loops = (i+1) * 10000000  # (i+1) * 10 million
        out = subprocess.check_output(
                ('perf', 'stat', '-x', ',',
                 '-e', events,
                 noploop, '%d' % loops),
                stderr=subprocess.STDOUT)
        f = {'loops': loops}
        for line in out.splitlines():
            fields = line.split(',')
            count, unit, event = None, None, None
            if len(fields) == 2:
                count, event = fields
            elif len(fields) == 3:
                count, unit, event = fields
            else:
                raise Error('Unable to parse perf stat output')
            f[event] = int(count)
        facts.append(f)
    progress_func(-1, -1)  # Finished
    return facts


def FactsToNumpyArray(facts, dtype):
    """Convert "facts" (list of dicts) to a numpy array.

    @param facts: A list of dicts. Each dict must have keys matching the field
            names in dtype.
    @param dtype: A numpy.dtype used to fill the array from facts. The dtype
            must be a "structured array". ie:
            numpy.dtype([('loops', numpy.int), ('cycles', numpy.int)])
    @returns: A numpy.ndarray with dtype=dtype filled with facts.
    """
    a = numpy.zeros(len(facts), dtype=dtype)
    for i, f in enumerate(facts):
        a[i] = tuple(f[n] for n in dtype.names)
    return a


def main():
    """This can be run stand-alone."""
    def _Progress(i, j):
        if i == -1 and j == -1:  # Finished
            print
            return
        if j == 0:
            if i != 0:
                print
            print i, ':',
        print j,
        sys.stdout.flush()

    events = ('cycles', 'instructions')
    facts = GatherPerfStats('src/noploop', ','.join(events),
                            progress_func=_Progress)

    dt = numpy.dtype([('loops', numpy.int)] +
                     [(e, numpy.int) for e in events])
    a = FactsToNumpyArray(facts, dt)
    for y_var in events:
        print y_var
        (slope, intercept), r2 = LinearRegression(a['loops'], a[y_var])
        print "slope:", slope
        print "intercept:", intercept
        print "r-squared:", r2


if __name__ == '__main__':
    main()
