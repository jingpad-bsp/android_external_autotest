#!/bin/sh
#
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

PTH=${1}

${PTH}/nvmap_iovmm_stress &
${PTH}/nvmap_iovmm_stress -x 256 &
${PTH}/nvmap_iovmm_stress -y 256 &
${PTH}/nvmap_iovmm_stress -y 512 &
${PTH}/nvmap_iovmm_stress -x 512 &
${PTH}/nvmap_iovmm_stress -x 256 -y 256 -w 512 -h 512 &
${PTH}/nvmap_iovmm_stress -x 768 -w 512 -h 512 &
${PTH}/nvmap_iovmm_stress -x 1024 -y 512 &
${PTH}/nvmap_iovmm_stress -x 768 -y 512 &

wait
