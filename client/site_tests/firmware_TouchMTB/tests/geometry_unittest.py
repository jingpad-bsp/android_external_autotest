# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module contains unit tests for geometry module."""


import unittest

import common_unittest_utils

from math import sqrt

from geometry.elements import Circle, Point
from geometry.minicircle import minicircle


class MinicircleTest(unittest.TestCase):
    """A class for FirwareSummary unit tests."""

    def test_minicircle(self):
        # a list of points: [center, radius]
        tests = [
            # a right triagnle
            ([(0, 0), (3, 0), (0, 4)], [(1.5, 2), 2.5]),

            # an obtuse triagnle
            ([(1, 1), (3, 0), (0, 4)], [(1.5, 2), 2.5]),

            # a right triagnle with one point inside
            ([(0, 0), (1, 1), (3, 0), (0, 4)], [(1.5, 2), 2.5]),

            # three points at the same coordinates
            ([(5, 3), (5, 3), (5, 3)], [(5, 3), 0]),

            # two points at the same coordinates, a diagonal line
            ([(0, 0), (0, 0), (4, 4)], [(2, 2), 2 * sqrt(2)]),

            # two points at the same coordinates, a vertical line
            ([(0, 2), (0, 2), (0, 12)], [(0, 7), 5]),

            # two points at the same coordinates, a vertical line, one outlier
            ([(0, 2), (0, 2), (1, 5), (0, 12)], [(0, 7), 5]),

            # an equilateral triangle
            ([(0, 0), (10, 0), (5, 5 * sqrt(3))],
                    [(5, 5 * sqrt(3) / 3), 5 * sqrt(3) * 2 / 3]),

            # an equilateral triangle with a few points inside
            ([(0, 0), (10, 0), (5, 5 * sqrt(3)), (4, 1), (6, 2), (4.5, 3),
              (5.2, 2.99), (4.33, 1.78), (5.65, 3.1)],
                    [(5, 5 * sqrt(3) / 3), 5 * sqrt(3) * 2 / 3]),

            # a list of random points:
            #   Verify with octave geometry package:
            #   > points = [1,1; 1,0; 2,1; 2,2;  12,22; 11,21; 30,30; 31,30;
            #               30,31; 31,31; 5,35]
            #   > enclosingCircle(points)
            ([(1, 1), (1, 0), (2, 1), (2, 2), (12, 22), (11, 21), (30, 30),
              (31, 30), (30, 31), (31, 31), (5, 35)],
                    [(15.39740821, 16.08315335), 21.58594878]),

            # another list of random points:
            #   Verify with octave geometry package:
            #   > points = [11,11; 11,15; 12,11; 12.5,21.25; 12.77,22.84; 11,21;
            #               13.3,31; 13.7,33; 14.9,29; 15,10.9; 12.5,13.55]
            #   > enclosingCircle(points)
            ([(11, 11), (11, 15), (12, 11), (12.5, 21.25), (12.77, 22.84),
              (11, 21), (13.3, 31), (13.7, 33), (14.9, 29), (15, 10.9),
              (12.5, 13.55)],
                    [(13.27341679, 21.88667158), 11.12151257]),
        ]
        for points, circle_values in tests:
            center_values, radius = circle_values
            expected_circle = Circle(Point(*center_values), radius)
            actual_circle = minicircle(points)
            self.assertTrue(actual_circle == expected_circle)


if __name__ == '__main__':
  unittest.main()
