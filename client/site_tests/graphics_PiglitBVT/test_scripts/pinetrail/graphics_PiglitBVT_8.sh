#!/bin/bash


need_pass=78
failures=0
PIGLIT_PATH=/usr/local/autotest/deps/piglit/piglit/
export PIGLIT_SOURCE_DIR=/usr/local/autotest/deps/piglit/piglit/
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$PIGLIT_PATH/lib
export DISPLAY=:0
export XAUTHORITY=/home/chronos/.Xauthority


function run_test()
{
  local name="$1"
  local time="$2"
  local command="$3"
  echo "++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++"
  echo "+ Running test "$name" of expected runtime $time sec: $command"
  sync
  $command
  if [ $? == 0 ] ; then
    let "need_pass--"
    echo "+ Return code 0 -> Test passed. ($name)"
  else
    let "failures++"
    echo "+ Return code not 0 -> Test failed. ($name)"
  fi
}


pushd $PIGLIT_PATH
run_test "spec/ARB_vertex_program/vp-max" 0.0 "bin/vpfp-generic -auto tests/shaders/generic/vp-max.vpfp"
run_test "spec/ARB_vertex_program/vp-max-array" 0.0 "bin/vp-max-array -auto"
run_test "spec/ARB_vertex_program/vp-min" 0.0 "bin/vpfp-generic -auto tests/shaders/generic/vp-min.vpfp"
run_test "spec/ARB_vertex_program/vp-sge-alias" 0.0 "bin/vpfp-generic -auto tests/shaders/generic/vp-sge-alias.vpfp"
run_test "spec/ARB_vertex_program/vp-two-constants" 0.0 "bin/vpfp-generic -auto tests/shaders/generic/vp-two-constants.vpfp"
run_test "spec/ARB_vertex_type_2_10_10_10_rev/attribs" 0.0 "bin/attribs GL_ARB_vertex_type_2_10_10_10_rev -auto -fbo"
run_test "spec/ATI_texture_compression_3dc/invalid formats" 0.0 "bin/arb_texture_compression-invalid-formats 3dc"
run_test "spec/EXT_fog_coord/ext_fog_coord-modes" 0.0 "bin/ext_fog_coord-modes -auto"
run_test "spec/EXT_framebuffer_blit/fbo-blit" 0.0 "bin/fbo-blit -auto"
run_test "spec/EXT_framebuffer_blit/fbo-copypix" 0.0 "bin/fbo-copypix -auto"
run_test "spec/EXT_framebuffer_blit/fbo-readdrawpix" 0.0 "bin/fbo-readdrawpix -auto"
run_test "spec/EXT_framebuffer_blit/fbo-sys-blit" 0.0 "bin/fbo-sys-blit -auto"
run_test "spec/EXT_framebuffer_blit/fbo-sys-sub-blit" 0.0 "bin/fbo-sys-sub-blit -auto"
run_test "spec/EXT_framebuffer_object/fbo-1d" 0.0 "bin/fbo-1d -auto"
run_test "spec/EXT_framebuffer_object/fbo-3d" 0.0 "bin/fbo-3d -auto"
run_test "spec/EXT_framebuffer_object/fbo-alphatest-formats" 0.0 "bin/fbo-alphatest-formats -auto"
run_test "spec/EXT_framebuffer_object/fbo-alphatest-nocolor" 0.0 "bin/fbo-alphatest-nocolor -auto"
run_test "spec/EXT_framebuffer_object/fbo-alphatest-nocolor-ff" 0.0 "bin/fbo-alphatest-nocolor-ff -auto"
run_test "spec/EXT_framebuffer_object/fbo-clear-formats" 0.0 "bin/fbo-clear-formats -auto"
run_test "spec/EXT_framebuffer_object/fbo-clearmipmap" 0.0 "bin/fbo-clearmipmap -auto"
run_test "spec/EXT_framebuffer_object/fbo-copyteximage-simple" 0.0 "bin/fbo-copyteximage-simple -auto"
run_test "spec/EXT_framebuffer_object/fbo-cubemap" 0.0 "bin/fbo-cubemap -auto"
run_test "spec/EXT_framebuffer_object/fbo-depthtex" 0.0 "bin/fbo-depthtex -auto"
run_test "spec/EXT_framebuffer_object/fbo-finish-deleted" 0.0 "bin/fbo-finish-deleted -auto"
run_test "spec/EXT_framebuffer_object/fbo-flushing" 0.0 "bin/fbo-flushing -auto"
run_test "spec/EXT_framebuffer_object/fbo-flushing-2" 0.0 "bin/fbo-flushing-2 -auto"
run_test "spec/EXT_framebuffer_object/fbo-fragcoord" 0.0 "bin/fbo-fragcoord -auto"
run_test "spec/EXT_framebuffer_object/fbo-generatemipmap" 0.0 "bin/fbo-generatemipmap -auto"
run_test "spec/EXT_framebuffer_object/fbo-generatemipmap-noimage" 0.0 "bin/fbo-generatemipmap-noimage -auto -fbo"
run_test "spec/EXT_framebuffer_object/fbo-generatemipmap-nonsquare" 0.0 "bin/fbo-generatemipmap-nonsquare -auto"
run_test "spec/EXT_framebuffer_object/fbo-generatemipmap-npot" 0.0 "bin/fbo-generatemipmap-npot -auto"
run_test "spec/EXT_framebuffer_object/fbo-generatemipmap-scissor" 0.0 "bin/fbo-generatemipmap-scissor -auto"
run_test "spec/EXT_framebuffer_object/fbo-generatemipmap-viewport" 0.0 "bin/fbo-generatemipmap-viewport -auto"
run_test "spec/EXT_framebuffer_object/fbo-maxsize" 0.0 "bin/fbo-maxsize -auto"
run_test "spec/EXT_framebuffer_object/fbo-nodepth-test" 0.0 "bin/fbo-nodepth-test -auto"
run_test "spec/EXT_framebuffer_object/fbo-nostencil-test" 0.0 "bin/fbo-nostencil-test -auto"
run_test "spec/EXT_framebuffer_object/fbo-readpixels" 0.0 "bin/fbo-readpixels -auto"
run_test "spec/EXT_framebuffer_object/fbo-readpixels-depth-formats" 0.0 "bin/fbo-readpixels-depth-formats -auto"
run_test "spec/EXT_framebuffer_object/fbo-scissor-bitmap" 0.0 "bin/fbo-scissor-bitmap -auto"
run_test "spec/EXT_framebuffer_object/fbo-stencil-GL_STENCIL_INDEX1-clear" 0.0 "bin/fbo-stencil -auto clear GL_STENCIL_INDEX1"
run_test "spec/EXT_framebuffer_object/fbo-stencil-GL_STENCIL_INDEX1-copypixels" 0.0 "bin/fbo-stencil -auto copypixels GL_STENCIL_INDEX1"
run_test "spec/EXT_framebuffer_object/fbo-stencil-GL_STENCIL_INDEX1-drawpixels" 0.0 "bin/fbo-stencil -auto drawpixels GL_STENCIL_INDEX1"
run_test "spec/EXT_framebuffer_object/fbo-stencil-GL_STENCIL_INDEX1-readpixels" 0.0 "bin/fbo-stencil -auto readpixels GL_STENCIL_INDEX1"
run_test "spec/EXT_framebuffer_object/fbo-stencil-GL_STENCIL_INDEX16-clear" 0.0 "bin/fbo-stencil -auto clear GL_STENCIL_INDEX16"
run_test "spec/EXT_framebuffer_object/fbo-stencil-GL_STENCIL_INDEX16-copypixels" 0.0 "bin/fbo-stencil -auto copypixels GL_STENCIL_INDEX16"
run_test "spec/EXT_framebuffer_object/fbo-stencil-GL_STENCIL_INDEX16-drawpixels" 0.0 "bin/fbo-stencil -auto drawpixels GL_STENCIL_INDEX16"
run_test "spec/EXT_framebuffer_object/fbo-stencil-GL_STENCIL_INDEX16-readpixels" 0.0 "bin/fbo-stencil -auto readpixels GL_STENCIL_INDEX16"
run_test "spec/EXT_framebuffer_object/fbo-stencil-GL_STENCIL_INDEX4-clear" 0.0 "bin/fbo-stencil -auto clear GL_STENCIL_INDEX4"
run_test "spec/EXT_framebuffer_object/fbo-stencil-GL_STENCIL_INDEX4-copypixels" 0.0 "bin/fbo-stencil -auto copypixels GL_STENCIL_INDEX4"
run_test "spec/EXT_framebuffer_object/fbo-stencil-GL_STENCIL_INDEX4-drawpixels" 0.0 "bin/fbo-stencil -auto drawpixels GL_STENCIL_INDEX4"
run_test "spec/EXT_framebuffer_object/fbo-stencil-GL_STENCIL_INDEX4-readpixels" 0.0 "bin/fbo-stencil -auto readpixels GL_STENCIL_INDEX4"
run_test "spec/EXT_framebuffer_object/fbo-stencil-GL_STENCIL_INDEX8-clear" 0.0 "bin/fbo-stencil -auto clear GL_STENCIL_INDEX8"
run_test "spec/EXT_framebuffer_object/fbo-stencil-GL_STENCIL_INDEX8-copypixels" 0.0 "bin/fbo-stencil -auto copypixels GL_STENCIL_INDEX8"
run_test "spec/EXT_framebuffer_object/fbo-stencil-GL_STENCIL_INDEX8-drawpixels" 0.0 "bin/fbo-stencil -auto drawpixels GL_STENCIL_INDEX8"
run_test "spec/EXT_framebuffer_object/fbo-stencil-GL_STENCIL_INDEX8-readpixels" 0.0 "bin/fbo-stencil -auto readpixels GL_STENCIL_INDEX8"
run_test "spec/EXT_framebuffer_object/fbo-storage-completeness" 0.0 "bin/fbo-storage-completeness -auto"
run_test "spec/EXT_framebuffer_object/fbo-storage-formats" 0.0 "bin/fbo-storage-formats -auto"
run_test "spec/EXT_framebuffer_object/fdo20701" 0.0 "bin/fdo20701 -auto"
run_test "spec/EXT_packed_depth_stencil/fbo-depth-GL_DEPTH24_STENCIL8-clear" 0.0 "bin/fbo-depth -auto clear GL_DEPTH24_STENCIL8"
run_test "spec/EXT_packed_depth_stencil/fbo-depth-GL_DEPTH24_STENCIL8-readpixels" 0.0 "bin/fbo-depth -auto readpixels GL_DEPTH24_STENCIL8"
run_test "spec/EXT_packed_depth_stencil/fbo-depth-GL_DEPTH24_STENCIL8-tex1d" 0.0 "bin/fbo-depth-tex1d -auto GL_DEPTH24_STENCIL8"
run_test "spec/EXT_packed_depth_stencil/fbo-depthstencil-GL_DEPTH24_STENCIL8-blit" 0.0 "bin/fbo-depthstencil -auto blit GL_DEPTH24_STENCIL8"
run_test "spec/EXT_packed_depth_stencil/fbo-depthstencil-GL_DEPTH24_STENCIL8-clear" 0.0 "bin/fbo-depthstencil -auto clear GL_DEPTH24_STENCIL8"
run_test "spec/EXT_packed_depth_stencil/fbo-depthstencil-GL_DEPTH24_STENCIL8-drawpixels-24_8" 0.0 "bin/fbo-depthstencil -auto drawpixels GL_DEPTH24_STENCIL8 24_8"
run_test "spec/EXT_packed_depth_stencil/fbo-depthstencil-GL_DEPTH24_STENCIL8-readpixels-24_8" 0.0 "bin/fbo-depthstencil -auto readpixels GL_DEPTH24_STENCIL8 24_8"
run_test "spec/EXT_packed_depth_stencil/fbo-depthstencil-GL_DEPTH24_STENCIL8-readpixels-FLOAT-and-USHORT" 0.0 "bin/fbo-depthstencil -auto readpixels GL_DEPTH24_STENCIL8 FLOAT-and-USHORT"
run_test "spec/EXT_packed_depth_stencil/fbo-generatemipmap-formats" 0.0 "bin/fbo-generatemipmap-formats -auto GL_EXT_packed_depth_stencil"
run_test "spec/EXT_packed_depth_stencil/fbo-stencil-GL_DEPTH24_STENCIL8-clear" 0.0 "bin/fbo-stencil -auto clear GL_DEPTH24_STENCIL8"
run_test "spec/EXT_packed_depth_stencil/fbo-stencil-GL_DEPTH24_STENCIL8-copypixels" 0.0 "bin/fbo-stencil -auto copypixels GL_DEPTH24_STENCIL8"
run_test "spec/EXT_packed_depth_stencil/fbo-stencil-GL_DEPTH24_STENCIL8-drawpixels" 0.0 "bin/fbo-stencil -auto drawpixels GL_DEPTH24_STENCIL8"
run_test "spec/EXT_packed_depth_stencil/fbo-stencil-GL_DEPTH24_STENCIL8-readpixels" 0.0 "bin/fbo-stencil -auto readpixels GL_DEPTH24_STENCIL8"
run_test "spec/EXT_packed_depth_stencil/get-renderbuffer-internalformat" 0.0 "bin/get-renderbuffer-internalformat GL_EXT_packed_depth_stencil -auto -fbo"
run_test "spec/EXT_packed_depth_stencil/readpixels-24_8" 0.0 "bin/ext_packed_depth_stencil-readpixels-24_8 -auto"
run_test "spec/EXT_packed_depth_stencil/texwrap formats" 0.0 "bin/texwrap -fbo -auto GL_EXT_packed_depth_stencil"
run_test "spec/EXT_texture_compression_latc/invalid formats" 0.0 "bin/arb_texture_compression-invalid-formats latc"
run_test "spec/EXT_texture_compression_rgtc/invalid formats" 0.0 "bin/arb_texture_compression-invalid-formats rgtc"
run_test "spec/EXT_texture_compression_s3tc/invalid formats" 0.0 "bin/arb_texture_compression-invalid-formats s3tc"
run_test "spec/EXT_texture_lod_bias/lodbias" 0.0 "bin/lodbias -auto"
popd

if [ $need_pass == 0 ] ; then
  echo "+---------------------------------------------+"
  echo "| Overall pass, as all 78 tests have passed. |"
  echo "+---------------------------------------------+"
else
  echo "+-----------------------------------------------------------+"
  echo "| Overall failure, as $need_pass tests did not pass and $failures failed. |"
  echo "+-----------------------------------------------------------+"
fi
exit $need_pass

