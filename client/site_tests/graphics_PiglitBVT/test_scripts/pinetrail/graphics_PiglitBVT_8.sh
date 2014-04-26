#!/bin/bash


need_pass=84
failures=0
PIGLIT_PATH=/usr/local/autotest/deps/piglit/piglit/
export PIGLIT_SOURCE_DIR=/usr/local/autotest/deps/piglit/piglit/
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$PIGLIT_PATH/lib


function run_test()
{
  local name="$1"
  local time="$2"
  local command="$3"
  echo "++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++"
  echo "Running test "$name" of expected runtime $time sec: $command"
  sync
  $command
  if [ $? == 0 ] ; then
    let "need_pass--"
  else
    let "failures++"
  fi
}


pushd $PIGLIT_PATH
run_test "spec/ARB_vertex_program/vp-arl-constant-array" 0.0 "framework/../bin/vpfp-generic -auto tests/shaders/generic/vp-arl-constant-array.vpfp"
run_test "spec/ARB_vertex_program/vp-arl-constant-array-huge" 0.0 "framework/../bin/vpfp-generic -auto tests/shaders/generic/vp-arl-constant-array-huge.vpfp"
run_test "spec/ARB_vertex_program/vp-arl-constant-array-huge-offset" 0.0 "framework/../bin/vpfp-generic -auto tests/shaders/generic/vp-arl-constant-array-huge-offset.vpfp"
run_test "spec/ARB_vertex_program/vp-arl-constant-array-huge-offset-neg" 0.0 "framework/../bin/vpfp-generic -auto tests/shaders/generic/vp-arl-constant-array-huge-offset-neg.vpfp"
run_test "spec/ARB_vertex_program/vp-arl-constant-array-huge-overwritten" 0.0 "framework/../bin/vpfp-generic -auto tests/shaders/generic/vp-arl-constant-array-huge-overwritten.vpfp"
run_test "spec/ARB_vertex_program/vp-arl-constant-array-huge-relative-offset" 0.0 "framework/../bin/vpfp-generic -auto tests/shaders/generic/vp-arl-constant-array-huge-relative-offset.vpfp"
run_test "spec/ARB_vertex_program/vp-arl-constant-array-huge-varying" 0.0 "framework/../bin/vpfp-generic -auto tests/shaders/generic/vp-arl-constant-array-huge-varying.vpfp"
run_test "spec/ARB_vertex_program/vp-arl-constant-array-varying" 0.0 "framework/../bin/vpfp-generic -auto tests/shaders/generic/vp-arl-constant-array-varying.vpfp"
run_test "spec/ARB_vertex_program/vp-arl-env-array" 0.0 "framework/../bin/vpfp-generic -auto tests/shaders/generic/vp-arl-env-array.vpfp"
run_test "spec/ARB_vertex_program/vp-arl-local-array" 0.0 "framework/../bin/vpfp-generic -auto tests/shaders/generic/vp-arl-local-array.vpfp"
run_test "spec/ARB_vertex_program/vp-arl-neg-array" 0.0 "framework/../bin/vpfp-generic -auto tests/shaders/generic/vp-arl-neg-array.vpfp"
run_test "spec/ARB_vertex_program/vp-arl-neg-array-2" 0.0 "framework/../bin/vpfp-generic -auto tests/shaders/generic/vp-arl-neg-array-2.vpfp"
run_test "spec/ARB_vertex_program/vp-bad-program" 0.0 "framework/../bin/vp-bad-program -auto"
run_test "spec/ARB_vertex_program/vp-constant-array" 0.0 "framework/../bin/vpfp-generic -auto tests/shaders/generic/vp-constant-array.vpfp"
run_test "spec/ARB_vertex_program/vp-constant-array-huge" 0.0 "framework/../bin/vpfp-generic -auto tests/shaders/generic/vp-constant-array-huge.vpfp"
run_test "spec/ARB_vertex_program/vp-constant-negate" 0.0 "framework/../bin/vpfp-generic -auto tests/shaders/generic/vp-constant-negate.vpfp"
run_test "spec/ARB_vertex_program/vp-exp-alias" 0.0 "framework/../bin/vpfp-generic -auto tests/shaders/generic/vp-exp-alias.vpfp"
run_test "spec/ARB_vertex_program/vp-max" 0.0 "framework/../bin/vpfp-generic -auto tests/shaders/generic/vp-max.vpfp"
run_test "spec/ARB_vertex_program/vp-max-array" 0.0 "framework/../bin/vp-max-array -auto"
run_test "spec/ARB_vertex_program/vp-min" 0.0 "framework/../bin/vpfp-generic -auto tests/shaders/generic/vp-min.vpfp"
run_test "spec/ARB_vertex_program/vp-sge-alias" 0.0 "framework/../bin/vpfp-generic -auto tests/shaders/generic/vp-sge-alias.vpfp"
run_test "spec/ARB_vertex_program/vp-two-constants" 0.0 "framework/../bin/vpfp-generic -auto tests/shaders/generic/vp-two-constants.vpfp"
run_test "spec/ARB_vertex_type_2_10_10_10_rev/attribs" 0.0 "framework/../bin/attribs GL_ARB_vertex_type_2_10_10_10_rev -auto -fbo"
run_test "spec/ATI_texture_compression_3dc/invalid formats" 0.0 "framework/../bin/arb_texture_compression-invalid-formats 3dc"
run_test "spec/EXT_fog_coord/ext_fog_coord-modes" 0.0 "framework/../bin/ext_fog_coord-modes -auto"
run_test "spec/EXT_framebuffer_blit/fbo-blit" 0.0 "framework/../bin/fbo-blit -auto"
run_test "spec/EXT_framebuffer_blit/fbo-copypix" 0.0 "framework/../bin/fbo-copypix -auto"
run_test "spec/EXT_framebuffer_blit/fbo-readdrawpix" 0.0 "framework/../bin/fbo-readdrawpix -auto"
run_test "spec/EXT_framebuffer_blit/fbo-sys-blit" 0.0 "framework/../bin/fbo-sys-blit -auto"
run_test "spec/EXT_framebuffer_blit/fbo-sys-sub-blit" 0.0 "framework/../bin/fbo-sys-sub-blit -auto"
run_test "spec/EXT_framebuffer_object/fbo-1d" 0.0 "framework/../bin/fbo-1d -auto"
run_test "spec/EXT_framebuffer_object/fbo-3d" 0.0 "framework/../bin/fbo-3d -auto"
run_test "spec/EXT_framebuffer_object/fbo-alphatest-formats" 0.0 "framework/../bin/fbo-alphatest-formats -auto"
run_test "spec/EXT_framebuffer_object/fbo-alphatest-nocolor" 0.0 "framework/../bin/fbo-alphatest-nocolor -auto"
run_test "spec/EXT_framebuffer_object/fbo-alphatest-nocolor-ff" 0.0 "framework/../bin/fbo-alphatest-nocolor-ff -auto"
run_test "spec/EXT_framebuffer_object/fbo-bind-renderbuffer" 0.0 "framework/../bin/fbo-bind-renderbuffer -auto"
run_test "spec/EXT_framebuffer_object/fbo-clear-formats" 0.0 "framework/../bin/fbo-clear-formats -auto"
run_test "spec/EXT_framebuffer_object/fbo-clearmipmap" 0.0 "framework/../bin/fbo-clearmipmap -auto"
run_test "spec/EXT_framebuffer_object/fbo-copyteximage-simple" 0.0 "framework/../bin/fbo-copyteximage-simple -auto"
run_test "spec/EXT_framebuffer_object/fbo-cubemap" 0.0 "framework/../bin/fbo-cubemap -auto"
run_test "spec/EXT_framebuffer_object/fbo-depthtex" 0.0 "framework/../bin/fbo-depthtex -auto"
run_test "spec/EXT_framebuffer_object/fbo-finish-deleted" 0.0 "framework/../bin/fbo-finish-deleted -auto"
run_test "spec/EXT_framebuffer_object/fbo-flushing" 0.0 "framework/../bin/fbo-flushing -auto"
run_test "spec/EXT_framebuffer_object/fbo-flushing-2" 0.0 "framework/../bin/fbo-flushing-2 -auto"
run_test "spec/EXT_framebuffer_object/fbo-fragcoord" 0.0 "framework/../bin/fbo-fragcoord -auto"
run_test "spec/EXT_framebuffer_object/fbo-generatemipmap" 0.0 "framework/../bin/fbo-generatemipmap -auto"
run_test "spec/EXT_framebuffer_object/fbo-generatemipmap-filtering" 0.0 "framework/../bin/fbo-generatemipmap-filtering -auto"
run_test "spec/EXT_framebuffer_object/fbo-generatemipmap-noimage" 0.0 "framework/../bin/fbo-generatemipmap-noimage -auto -fbo"
run_test "spec/EXT_framebuffer_object/fbo-generatemipmap-nonsquare" 0.0 "framework/../bin/fbo-generatemipmap-nonsquare -auto"
run_test "spec/EXT_framebuffer_object/fbo-generatemipmap-npot" 0.0 "framework/../bin/fbo-generatemipmap-npot -auto"
run_test "spec/EXT_framebuffer_object/fbo-generatemipmap-scissor" 0.0 "framework/../bin/fbo-generatemipmap-scissor -auto"
run_test "spec/EXT_framebuffer_object/fbo-generatemipmap-viewport" 0.0 "framework/../bin/fbo-generatemipmap-viewport -auto"
run_test "spec/EXT_framebuffer_object/fbo-maxsize" 0.0 "framework/../bin/fbo-maxsize -auto"
run_test "spec/EXT_framebuffer_object/fbo-nodepth-test" 0.0 "framework/../bin/fbo-nodepth-test -auto"
run_test "spec/EXT_framebuffer_object/fbo-nostencil-test" 0.0 "framework/../bin/fbo-nostencil-test -auto"
run_test "spec/EXT_framebuffer_object/fbo-readpixels" 0.0 "framework/../bin/fbo-readpixels -auto"
run_test "spec/EXT_framebuffer_object/fbo-readpixels-depth-formats" 0.0 "framework/../bin/fbo-readpixels-depth-formats -auto"
run_test "spec/EXT_framebuffer_object/fbo-scissor-bitmap" 0.0 "framework/../bin/fbo-scissor-bitmap -auto"
run_test "spec/EXT_framebuffer_object/fbo-stencil-GL_STENCIL_INDEX1-clear" 0.0 "framework/../bin/fbo-stencil -auto clear GL_STENCIL_INDEX1"
run_test "spec/EXT_framebuffer_object/fbo-stencil-GL_STENCIL_INDEX1-copypixels" 0.0 "framework/../bin/fbo-stencil -auto copypixels GL_STENCIL_INDEX1"
run_test "spec/EXT_framebuffer_object/fbo-stencil-GL_STENCIL_INDEX1-drawpixels" 0.0 "framework/../bin/fbo-stencil -auto drawpixels GL_STENCIL_INDEX1"
run_test "spec/EXT_framebuffer_object/fbo-stencil-GL_STENCIL_INDEX1-readpixels" 0.0 "framework/../bin/fbo-stencil -auto readpixels GL_STENCIL_INDEX1"
run_test "spec/EXT_framebuffer_object/fbo-stencil-GL_STENCIL_INDEX16-clear" 0.0 "framework/../bin/fbo-stencil -auto clear GL_STENCIL_INDEX16"
run_test "spec/EXT_framebuffer_object/fbo-stencil-GL_STENCIL_INDEX16-copypixels" 0.0 "framework/../bin/fbo-stencil -auto copypixels GL_STENCIL_INDEX16"
run_test "spec/EXT_framebuffer_object/fbo-stencil-GL_STENCIL_INDEX16-drawpixels" 0.0 "framework/../bin/fbo-stencil -auto drawpixels GL_STENCIL_INDEX16"
run_test "spec/EXT_framebuffer_object/fbo-stencil-GL_STENCIL_INDEX16-readpixels" 0.0 "framework/../bin/fbo-stencil -auto readpixels GL_STENCIL_INDEX16"
run_test "spec/EXT_framebuffer_object/fbo-stencil-GL_STENCIL_INDEX4-clear" 0.0 "framework/../bin/fbo-stencil -auto clear GL_STENCIL_INDEX4"
run_test "spec/EXT_framebuffer_object/fbo-stencil-GL_STENCIL_INDEX4-copypixels" 0.0 "framework/../bin/fbo-stencil -auto copypixels GL_STENCIL_INDEX4"
run_test "spec/EXT_framebuffer_object/fbo-stencil-GL_STENCIL_INDEX4-drawpixels" 0.0 "framework/../bin/fbo-stencil -auto drawpixels GL_STENCIL_INDEX4"
run_test "spec/EXT_framebuffer_object/fbo-stencil-GL_STENCIL_INDEX4-readpixels" 0.0 "framework/../bin/fbo-stencil -auto readpixels GL_STENCIL_INDEX4"
run_test "spec/EXT_framebuffer_object/fbo-stencil-GL_STENCIL_INDEX8-clear" 0.0 "framework/../bin/fbo-stencil -auto clear GL_STENCIL_INDEX8"
run_test "spec/EXT_framebuffer_object/fbo-stencil-GL_STENCIL_INDEX8-copypixels" 0.0 "framework/../bin/fbo-stencil -auto copypixels GL_STENCIL_INDEX8"
run_test "spec/EXT_framebuffer_object/fbo-stencil-GL_STENCIL_INDEX8-drawpixels" 0.0 "framework/../bin/fbo-stencil -auto drawpixels GL_STENCIL_INDEX8"
run_test "spec/EXT_framebuffer_object/fbo-stencil-GL_STENCIL_INDEX8-readpixels" 0.0 "framework/../bin/fbo-stencil -auto readpixels GL_STENCIL_INDEX8"
run_test "spec/EXT_framebuffer_object/fbo-storage-completeness" 0.0 "framework/../bin/fbo-storage-completeness -auto"
run_test "spec/EXT_framebuffer_object/fbo-storage-formats" 0.0 "framework/../bin/fbo-storage-formats -auto"
run_test "spec/EXT_framebuffer_object/fdo20701" 0.0 "framework/../bin/fdo20701 -auto"
run_test "spec/EXT_packed_depth_stencil/fbo-depth-GL_DEPTH24_STENCIL8-clear" 0.0 "framework/../bin/fbo-depth -auto clear GL_DEPTH24_STENCIL8"
run_test "spec/EXT_packed_depth_stencil/fbo-depth-GL_DEPTH24_STENCIL8-readpixels" 0.0 "framework/../bin/fbo-depth -auto readpixels GL_DEPTH24_STENCIL8"
run_test "spec/EXT_packed_depth_stencil/fbo-depth-GL_DEPTH24_STENCIL8-tex1d" 0.0 "framework/../bin/fbo-depth-tex1d -auto GL_DEPTH24_STENCIL8"
run_test "spec/EXT_packed_depth_stencil/fbo-depthstencil-GL_DEPTH24_STENCIL8-blit" 0.0 "framework/../bin/fbo-depthstencil -auto blit GL_DEPTH24_STENCIL8"
run_test "spec/EXT_packed_depth_stencil/fbo-depthstencil-GL_DEPTH24_STENCIL8-clear" 0.0 "framework/../bin/fbo-depthstencil -auto clear GL_DEPTH24_STENCIL8"
run_test "spec/EXT_packed_depth_stencil/fbo-depthstencil-GL_DEPTH24_STENCIL8-drawpixels-24_8" 0.0 "framework/../bin/fbo-depthstencil -auto drawpixels GL_DEPTH24_STENCIL8 24_8"
run_test "spec/EXT_packed_depth_stencil/fbo-depthstencil-GL_DEPTH24_STENCIL8-readpixels-24_8" 0.0 "framework/../bin/fbo-depthstencil -auto readpixels GL_DEPTH24_STENCIL8 24_8"
popd

if [ $need_pass == 0 ] ; then
  echo "+---------------------------------------------+"
  echo "| Overall pass, as all 84 tests have passed. |"
  echo "+---------------------------------------------+"
else
  echo "+-----------------------------------------------------------+"
  echo "| Overall failure, as $need_pass tests did not pass and $failures failed. |"
  echo "+-----------------------------------------------------------+"
fi
exit $need_pass

