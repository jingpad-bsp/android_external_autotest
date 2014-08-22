#!/bin/bash


need_pass=17
failures=0
PIGLIT_PATH=/usr/local/piglit/lib64/piglit/
export PIGLIT_SOURCE_DIR=/usr/local/piglit/lib64/piglit/
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$PIGLIT_PATH/lib
export DISPLAY=:0
export XAUTHORITY=/home/chronos/.Xauthority


function run_test()
{
  local name="$1"
  local time="$2"
  local command="$3"
  echo "++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++"
  echo "+ Running test [$name] of expected runtime $time sec: [$command]"
  sync
  $command
  if [ $? == 0 ] ; then
    let "need_pass--"
    echo "+ pass :: $name"
  else
    let "failures++"
    echo "+ fail :: $name"
  fi
}


pushd $PIGLIT_PATH
run_test "spec/EXT_transform_feedback/discard-drawarrays" 0.0 "bin/ext_transform_feedback-discard-drawarrays -fbo -auto"
run_test "spec/EXT_transform_feedback/discard-drawpixels" 0.0 "bin/ext_transform_feedback-discard-drawpixels -fbo -auto"
run_test "spec/EXT_transform_feedback/generatemipmap buffer" 0.0 "bin/ext_transform_feedback-generatemipmap buffer -fbo -auto"
run_test "spec/EXT_transform_feedback/generatemipmap discard" 0.0 "bin/ext_transform_feedback-generatemipmap discard -fbo -auto"
run_test "spec/EXT_transform_feedback/generatemipmap prims_written" 0.0 "bin/ext_transform_feedback-generatemipmap prims_written -fbo -auto"
run_test "spec/EXT_transform_feedback/get-buffer-state buffer_size" 0.0 "bin/ext_transform_feedback-get-buffer-state buffer_size -fbo -auto"
run_test "spec/EXT_transform_feedback/get-buffer-state buffer_start" 0.0 "bin/ext_transform_feedback-get-buffer-state buffer_start -fbo -auto"
run_test "spec/EXT_transform_feedback/get-buffer-state indexed_binding" 0.0 "bin/ext_transform_feedback-get-buffer-state indexed_binding -fbo -auto"
run_test "spec/EXT_transform_feedback/get-buffer-state main_binding" 0.0 "bin/ext_transform_feedback-get-buffer-state main_binding -fbo -auto"
run_test "spec/EXT_transform_feedback/immediate-reuse" 0.0 "bin/ext_transform_feedback-immediate-reuse -fbo -auto"
run_test "spec/EXT_transform_feedback/interleaved-attribs" 0.0 "bin/ext_transform_feedback-interleaved -fbo -auto"
run_test "spec/EXT_transform_feedback/max-varyings" 0.0 "bin/ext_transform_feedback-max-varyings -fbo -auto"
run_test "spec/EXT_transform_feedback/negative-prims" 0.0 "bin/ext_transform_feedback-negative-prims -fbo -auto"
run_test "spec/EXT_transform_feedback/nonflat-integral" 0.0 "bin/ext_transform_feedback-nonflat-integral -fbo -auto"
run_test "spec/EXT_transform_feedback/order arrays lines" 0.0 "bin/ext_transform_feedback-order arrays lines -fbo -auto"
run_test "spec/EXT_transform_feedback/order arrays points" 0.0 "bin/ext_transform_feedback-order arrays points -fbo -auto"
run_test "spec/EXT_transform_feedback/order arrays triangles" 0.0 "bin/ext_transform_feedback-order arrays triangles -fbo -auto"
popd

if [ $need_pass == 0 ] ; then
  echo "+---------------------------------------------+"
  echo "| Overall pass, as all 17 tests have passed. |"
  echo "+---------------------------------------------+"
else
  echo "+-----------------------------------------------------------+"
  echo "| Overall failure, as $need_pass tests did not pass and $failures failed. |"
  echo "+-----------------------------------------------------------+"
fi
exit $need_pass

