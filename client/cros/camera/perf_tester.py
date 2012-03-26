# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Import guard for OpenCV.
try:
    import cv
    import cv2
except ImportError:
    pass

import math
import numpy as np
import sys

import mtf_calculator
import grid_mapper

from camera_utils import Pod
from camera_utils import Pad
from camera_utils import Unpad

_CORNER_MAX_NUM = 1000000
_CORNER_QUALITY_RATIO = 0.05
_CORNER_MIN_DISTANCE_RATIO = 0.016

_EDGE_LINK_THRESHOLD = 2000
_EDGE_DETECT_THRESHOLD = 4000
_EDGE_MIN_SQUARE_SIZE_RATIO = 0.024

_POINT_MATCHING_MAX_TOLERANCE_RATIO = 0.020

_MTF_DEFAULT_MAX_CHECK_NUM = 40
_MTF_DEFAULT_PATCH_WIDTH = 20
_MTF_DEFAULT_CHECK_PASS_VALUE = 0.30

_SHADING_DOWNSAMPLE_SIZE = 250.0
_SHADING_BILATERAL_SPATIAL_SIGMA = 20
_SHADING_BILATERAL_RANGE_SIGMA = 0.15
_SHADING_DEFAULT_MAX_RESPONSE = 0.01
_SHADING_DEFAULT_MAX_TOLERANCE_RATIO = 0.15


def _FindCornersOnConvexHull(hull):
    '''Find the four corners of a rectangular point grid.'''
    # Compute the inner angle of each point on the hull.
    hull_left = np.roll(hull, -1, axis=0)
    hull_right = np.roll(hull, 1, axis=0)

    hull_dl = hull_left - hull
    hull_dr = hull_right - hull

    angle = np.sum(hull_dl * hull_dr, axis=1)
    angle /= np.sum(hull_dl ** 2, axis=1) ** (1./2)
    angle /= np.sum(hull_dr ** 2, axis=1) ** (1./2)

    # Take the top four sharpest angle points and
    # arrange them in the same order as on the hull.
    corners = hull[np.sort(np.argsort(angle)[:-5:-1])]
    return corners


def _CheckSquareness(contour, min_square_area):
    '''Check the squareness of a contour.'''
    if len(contour) != 4:
        return False

    # Filter out noise squares.
    if cv2.contourArea(Pad(contour)) < min_square_area:
        return False

    # Check convexity.
    if not cv2.isContourConvex(Pad(contour)):
        return False

    min_angle = 0
    for i in range(0, 4):
        # Find the minimum inner angle.
        dl = contour[i] - contour[i-1]
        dr = contour[i-2] - contour[i-1]
        angle = np.sum(dl * dr) / math.sqrt(np.sum(dl ** 2) * np.sum(dr ** 2) +
                                            1e-10)

        ac = abs(angle)
        if ac > min_angle:
            min_angle = ac

    # If the absolute value of cosines of all angles are small, then all angles
    # are ~90 degree -> implies a square.
    if min_angle > 0.3:
        return False
    return True


def _ExtractEdgeSegments(edge_map, min_square_size_ratio):
    '''Extract robust edges of squares from a binary edge map.'''
    diag_len = math.sqrt(edge_map.shape[0] ** 2 + edge_map.shape[1] ** 2)
    min_square_area = int(round(diag_len * min_square_size_ratio)) ** 2

    # Dilate the output from Canny to fix broken edge segments.
    edge_map = edge_map.copy()
    cv.Dilate(edge_map, edge_map, None, 1)

    # Find contours of the binary edge map.
    squares = []
    storage = cv.CreateMemStorage()
    contours = cv.FindContours(edge_map, storage, cv.CV_RETR_TREE,
                               cv.CV_CHAIN_APPROX_SIMPLE)

    # Check if each contour is a square.
    storage = cv.CreateMemStorage()
    while contours:
        # Approximate contour with an accuracy proportional to the contour
        # perimeter length.
        arc_len = cv.ArcLength(contours)
        polygon = cv.ApproxPoly(contours, storage, cv.CV_POLY_APPROX_DP,
                                arc_len * 0.02)
        polygon = np.array(polygon, dtype=np.float32)

        # If the contour passes the squareness check, add it to the list.
        if _CheckSquareness(polygon, min_square_area):
            sq_edges = np.hstack((polygon, np.roll(polygon, -1, axis=0)))
            for t in range(4):
                squares.append(sq_edges[t])

        contours = contours.h_next()

    return np.array(squares, dtype=np.float32)


def _StratifiedSample2D(xys, n, dims=None, strict=False):
    '''Do stratified random sampling on a 2D point set.

    The algorithm will try to spread the samples around the plane.

    Args:
        n: Sample count requested.
        dims: The x-y plane size that is used to normalize the coordinates.
        strict: Should we fall back to the pure random sampling on failure.

    Returns:
        A list of indexes of sampled points.
    '''
    if not dims:
        dims = np.array([1, 1.0])

    # Place the points onto the grid in a random order.
    ln = xys.shape[0]
    perm = np.random.permutation(ln)
    grid_size = math.ceil(math.sqrt(n))
    taken = np.zeros((grid_size, grid_size), dtype=np.bool)
    result = []
    for t in perm:
        # Normalize the coordinates to [0, 1).
        gx = int(xys[t, 0] * grid_size / dims[1])
        gy = int(xys[t, 1] * grid_size / dims[0])
        if not taken[gy, gx]:
            taken[gy, gx] = True
            result.append(t)
            if len(result) == n:
                break

    # Fall back to the pure random sampling on failure.
    if len(result) != n:
        if not strict:
            return perm[0:n]
        return None
    return np.array(result)


def PrepareTest(pat_file):
    '''Extract information from the reference test pattern.

    The data will be used in the actual test as the ground truth.
    '''
    class CamTestData(Pod):
        pass
    ret = CamTestData()

    # Locate corners.
    pat = cv2.imread(pat_file, cv.CV_LOAD_IMAGE_GRAYSCALE)
    diag_len = math.sqrt(pat.shape[0] ** 2 + pat.shape[1] ** 2)
    min_corner_dist = diag_len * _CORNER_MIN_DISTANCE_RATIO

    ret.corners = Unpad(
        cv2.goodFeaturesToTrack(pat, _CORNER_MAX_NUM, _CORNER_QUALITY_RATIO,
                                min_corner_dist))

    ret.pmatch_tol = diag_len * _POINT_MATCHING_MAX_TOLERANCE_RATIO

    # Locate four corners of the corner grid.
    hull = Unpad(cv2.convexHull(Pad(ret.corners)))
    ret.four_corners = _FindCornersOnConvexHull(hull)

    # Locate edges.
    edge_map = cv2.Canny(pat, _EDGE_LINK_THRESHOLD, _EDGE_DETECT_THRESHOLD,
                         apertureSize=5)

    ret.edges = _ExtractEdgeSegments(edge_map, _EDGE_MIN_SQUARE_SIZE_RATIO)
    return ret


def CheckLensShading(sample, check_low_freq=True,
                     max_response=_SHADING_DEFAULT_MAX_RESPONSE,
                     max_shading_ratio=_SHADING_DEFAULT_MAX_TOLERANCE_RATIO):
    '''Check if lens shading is present.

    Args:
        sample: The test target image. It needs to be single-channel.
        check_low_freq: Check low frequency variation or not. The low frequency
                        is very sensitive to uneven illumination so one may want
                        to turn it off when a fixture is not available.
        max_response: Maximum acceptable response of low frequency variation.
        max_shading_ratio: Maximum acceptable shading ratio value of boundary
                           pixels.

    Returns:
        1: Pass or Fail.
        2: A structure contains the response value and the error message in case
           the test failed.
    '''
    class ReturnValue(Pod):
        pass
    ret = ReturnValue(msg=None)

    # Downsample for speed.
    ratio = _SHADING_DOWNSAMPLE_SIZE / max(sample.shape)
    img = cv2.resize(sample, None, fx=ratio, fy=ratio,
                     interpolation=cv2.INTER_AREA)
    img = img.astype(np.float32)

    # Method 1 - Low-frequency variation check:
    ret.check_low_freq = False
    if check_low_freq:
        ret.check_low_freq = True
        # Homomorphic filtering.
        ilog = np.log(0.001 + img)
        # Substract a bilateral smoothed version.
        ismooth = cv2.bilateralFilter(ilog,
                                      _SHADING_BILATERAL_SPATIAL_SIGMA * 3,
                                      _SHADING_BILATERAL_RANGE_SIGMA,
                                      _SHADING_BILATERAL_SPATIAL_SIGMA,
                                      borderType=cv2.BORDER_REFLECT)
        ihigh = ilog - ismooth

        # Check if there are significant response.
        # The response is computed as the 95th pencentile minus the median.
        ihsorted = np.sort(ihigh, axis=None)
        N = ihsorted.shape[0]
        peak_to_med = ihsorted[int(0.95 * N)] - ihsorted[int(0.5 * N)]
        ret.response = peak_to_med
        if peak_to_med > max_response:
            ret.msg = 'Found significant low-frequency variation.'
            return False, ret

    # Method 2 - Boundary scan:
    # Get the mean of top 5 percent pixels.
    ihsorted = np.sort(img, axis=None)
    mtop = np.mean(ihsorted[int(0.95 * ihsorted.shape[0]):ihsorted.shape[0]])
    pass_value = mtop * (1.0 - max_shading_ratio)

    # Check if any pixel on the boundary is lower than the threshold.
    # A little smoothing to deal with the possible noise.
    k_size = (7, 7)
    ret.msg = 'Found dark pixels on the boundary.'
    if np.any(cv2.blur(img[0, :], k_size) < pass_value):
        return False, ret
    if np.any(cv2.blur(img[-1, :], k_size) < pass_value):
        return False, ret
    if np.any(cv2.blur(img[:, 0], k_size) < pass_value):
        return False, ret
    if np.any(cv2.blur(img[:, -1], k_size) < pass_value):
        return False, ret

    ret.msg = None
    return True, ret


def CheckVisualCorrectness(
    sample, ref_data, register_grid=False,
    min_corner_quality_ratio=_CORNER_QUALITY_RATIO,
    min_square_size_ratio=_EDGE_MIN_SQUARE_SIZE_RATIO,
    min_corner_distance_ratio=_CORNER_MIN_DISTANCE_RATIO):
    '''Check if the test pattern is present.

    Args:
        sample: The test target image. It needs to be single-channel.
        ref_data: A struct that contains information extracted from the
                  reference pattern using PrepareTest.
        register_grid: Check if the point grid can be matched to the reference
                       one, i.e. whether they are of the same type.
        min_corner_quality_ratio: Minimum acceptable relative corner quality
                                  difference.
        min_square_size_ratio: Minimum allowed square edge length in relative
                               to the image diagonal length.
        min_corner_distance_ratio: Minimum allowed corner distance in relative
                                   to the image diagonal length.

    Returns:
        1: Pass or Fail.
        2: A structure contains the found corners and edges and the error
           message in case the test failed.
    '''
    class ReturnValue(Pod):
        pass
    ret = ReturnValue(msg=None)

    # CHECK 1:
    # a) See if all corners are present with reasonable strength.
    edge_map = cv2.Canny(sample, _EDGE_LINK_THRESHOLD, _EDGE_DETECT_THRESHOLD,
                         apertureSize=5)
    dilator = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    edge_mask = cv2.dilate(edge_map, dilator)

    diag_len = math.sqrt(sample.shape[0] ** 2 + sample.shape[1] ** 2)
    min_corner_dist = diag_len * min_corner_distance_ratio

    sample_corners = cv2.goodFeaturesToTrack(sample, ref_data.corners.shape[0],
                                             min_corner_quality_ratio,
                                             min_corner_dist, mask=edge_mask)
    if sample_corners is None:
        ret.msg = "Can't find strong corners."
        return False, ret
    sample_corners = Unpad(sample_corners)
    ret.sample_corners = sample_corners

    # b) Same amount corners as the reference data.
    if sample_corners.shape[0] != ref_data.corners.shape[0]:
        ret.msg = "Can't find the same amount of corners."
        return False, ret
    # c) They spread sufficiently across the whole image (at least one for
    #    each cell of a 6x6 grid).
    if _StratifiedSample2D(sample_corners, 36, sample.shape, True) is None:
        ret.msg = 'The pattern may be mis-aligned.'
        return False, ret
    # TODO(sheckylin) Refine points locations.

    # Perform point grid registration if requested. This can confirm that the
    # desired test pattern is correctly found (i.e. not fooled by some other
    # stuff) and also that the geometric distortion is small. However, we
    # choose to skip it by default due to the heavy computation demands.
    # TODO(sheckylin) Enable it after the C++ registration module is done.
    ret.register_grid = False
    if register_grid:
        ret.register_grid = True
        # We now check if all the corners are in the correct place.
        # First, we find the 4 corners of the square grid.
        hull = Unpad(cv2.convexHull(Pad(sample_corners)))
        four_corners = _FindCornersOnConvexHull(hull)

        # There are 4 possible mappings of the 4 corners between the reference
        # and the sample due to rotation because we can't tell the starting
        # point of the convex hull on the rectangle grid.
        match = False
        for i in range(0,4):
            success, homography, _ = grid_mapper.Register(
                four_corners, sample_corners, ref_data.four_corners,
                ref_data.corners, ref_data.pmatch_tol)
            if success:
                match = True
                break

            four_corners = np.roll(four_corners, 1, axis=0)

        # CHECK 2:
        # Check if all corners are successfully mapped.
        if not match:
            ret.msg = "Can't match the sample to the reference."
            return False, ret
        ret.homography = homography

    # Find squares on the edge map.
    edges = _ExtractEdgeSegments(edge_map, min_square_size_ratio)

    # CHECK 3:
    # Check if we can find the same amount of edges on the target.
    ret.edges = edges
    if edges.shape[0] != ref_data.edges.shape[0]:
        ret.msg = "Can't find the same amount of squares/edges."
        return False, ret
    return True, ret


def CheckSharpness(sample, edges,
                   min_pass_mtf=_MTF_DEFAULT_CHECK_PASS_VALUE,
                   mtf_sample_count=_MTF_DEFAULT_MAX_CHECK_NUM,
                   mtf_patch_width=_MTF_DEFAULT_PATCH_WIDTH,
                   use_50p=True):
    '''Check if the captured image is sharp.

    Args:
        sample: The test target image. It needs to be single-channel.
        edges: A list of edges on the test image. Should be extracted with
               CheckVisualCorrectness.
        min_pass_mtf: Minimum acceptable MTF value.
        mtf_sample_count: How many edges we are going to compute MTF values.
        mtf_patch_width: The desired margin on the both side of an edge. Larger
                         margins provides more precise MTF values.
        use_50p: Compute whether the MTF50P value or the MTF50 value.

    Returns:
        1: Pass or Fail.
        2: A structure contains the median MTF value (MTF50P) and the error
           message in case the test failed.
    '''
    class ReturnValue(Pod):
        pass
    ret = ReturnValue(msg=None)

    if mtf_sample_count <= 0 or mtf_patch_width <= 0 or edges is None:
        ret.msg = 'Input values are invalid.'
        return False, ret
    line_start = edges[:, [0, 1]]
    line_end = edges[:, [2, 3]]
    ln = line_start.shape[0]

    # Compute MTF for some edges.
    # Random sample a few edges to work on.
    n_check = min(ln, mtf_sample_count)
    mids = (line_start + line_end) / 2
    mids = mids - np.amin(mids, axis=0)
    new_dim = np.amax(mids, axis=0) + 1
    perm = _StratifiedSample2D(mids, n_check, tuple([new_dim[1], new_dim[0]]))
    mtfs = [mtf_calculator.Compute(sample, line_start[t], line_end[t],
                                   mtf_patch_width, use_50p)[0] for t in perm]

    # CHECK 1:
    # Check if the median of MTF values pass the threshold.
    ret.mtf = np.median(np.array(mtfs))
    if  ret.mtf < min_pass_mtf:
        ret.msg = 'The MTF values are too low.'
        return False, ret
    return True, ret
