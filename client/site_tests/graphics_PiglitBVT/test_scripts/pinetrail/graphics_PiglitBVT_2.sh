#!/bin/bash


need_pass=137
failures=0
PIGLIT_PATH=/usr/local/piglit/lib/piglit/
export PIGLIT_SOURCE_DIR=/usr/local/piglit/lib/piglit/
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
run_test "glean/glsl1-gl_FragDepth writing" 0.0 "bin/glean -o -v -v -v -t +glsl1 --quick"
run_test "glean/glsl1-gl_Position not written check" 0.0 "bin/glean -o -v -v -v -t +glsl1 --quick"
run_test "glean/glsl1-if (boolean-scalar) check" 0.0 "bin/glean -o -v -v -v -t +glsl1 --quick"
run_test "glean/glsl1-illegal assignment" 0.0 "bin/glean -o -v -v -v -t +glsl1 --quick"
run_test "glean/glsl1-linear fog" 0.0 "bin/glean -o -v -v -v -t +glsl1 --quick"
run_test "glean/glsl1-matrix column check (1)" 0.0 "bin/glean -o -v -v -v -t +glsl1 --quick"
run_test "glean/glsl1-matrix column check (2)" 0.0 "bin/glean -o -v -v -v -t +glsl1 --quick"
run_test "glean/glsl1-matrix, vector multiply (1)" 0.0 "bin/glean -o -v -v -v -t +glsl1 --quick"
run_test "glean/glsl1-matrix, vector multiply (3)" 0.0 "bin/glean -o -v -v -v -t +glsl1 --quick"
run_test "glean/glsl1-nested function calls (1)" 0.0 "bin/glean -o -v -v -v -t +glsl1 --quick"
run_test "glean/glsl1-nested function calls (2)" 0.0 "bin/glean -o -v -v -v -t +glsl1 --quick"
run_test "glean/glsl1-nested function calls (3)" 0.0 "bin/glean -o -v -v -v -t +glsl1 --quick"
run_test "glean/glsl1-sequence (comma) operator" 0.0 "bin/glean -o -v -v -v -t +glsl1 --quick"
run_test "glean/glsl1-shadow2D(): 2" 0.0 "bin/glean -o -v -v -v -t +glsl1 --quick"
run_test "glean/glsl1-shadow2D(): 4" 0.0 "bin/glean -o -v -v -v -t +glsl1 --quick"
run_test "glean/glsl1-struct (1)" 0.0 "bin/glean -o -v -v -v -t +glsl1 --quick"
run_test "glean/glsl1-struct (2)" 0.0 "bin/glean -o -v -v -v -t +glsl1 --quick"
run_test "glean/glsl1-struct (3)" 0.0 "bin/glean -o -v -v -v -t +glsl1 --quick"
run_test "glean/glsl1-struct (4)" 0.0 "bin/glean -o -v -v -v -t +glsl1 --quick"
run_test "glean/glsl1-syntax error check (1)" 0.0 "bin/glean -o -v -v -v -t +glsl1 --quick"
run_test "glean/glsl1-syntax error check (2)" 0.0 "bin/glean -o -v -v -v -t +glsl1 --quick"
run_test "glean/glsl1-syntax error check (3)" 0.0 "bin/glean -o -v -v -v -t +glsl1 --quick"
run_test "glean/glsl1-texcoord varying" 0.0 "bin/glean -o -v -v -v -t +glsl1 --quick"
run_test "glean/glsl1-texture1D()" 0.0 "bin/glean -o -v -v -v -t +glsl1 --quick"
run_test "glean/glsl1-texture2D()" 0.0 "bin/glean -o -v -v -v -t +glsl1 --quick"
run_test "glean/glsl1-texture2D(), computed coordinate" 0.0 "bin/glean -o -v -v -v -t +glsl1 --quick"
run_test "glean/glsl1-texture2D(), with bias" 0.0 "bin/glean -o -v -v -v -t +glsl1 --quick"
run_test "glean/glsl1-texture2DProj()" 0.0 "bin/glean -o -v -v -v -t +glsl1 --quick"
run_test "glean/glsl1-texture3D()" 0.0 "bin/glean -o -v -v -v -t +glsl1 --quick"
run_test "glean/glsl1-texture3D(), computed coord" 0.0 "bin/glean -o -v -v -v -t +glsl1 --quick"
run_test "glean/glsl1-undefined variable" 0.0 "bin/glean -o -v -v -v -t +glsl1 --quick"
run_test "glean/glsl1-uniform matrix" 0.0 "bin/glean -o -v -v -v -t +glsl1 --quick"
run_test "glean/glsl1-uniform matrix, transposed" 0.0 "bin/glean -o -v -v -v -t +glsl1 --quick"
run_test "glean/glsl1-varying read but not written" 0.0 "bin/glean -o -v -v -v -t +glsl1 --quick"
run_test "glean/glsl1-varying var mismatch" 0.0 "bin/glean -o -v -v -v -t +glsl1 --quick"
run_test "glean/glsl1-|| operator, short-circuit" 0.0 "bin/glean -o -v -v -v -t +glsl1 --quick"
run_test "glean/makeCurrent" 0.0 "bin/glean -o -v -v -v -t +makeCurrent --quick"
run_test "glean/orthoPosHLines" 0.0 "bin/glean -o -v -v -v -t +orthoPosHLines --quick"
run_test "glean/orthoPosPoints" 0.0 "bin/glean -o -v -v -v -t +orthoPosPoints --quick"
run_test "glean/orthoPosRandRects" 0.0 "bin/glean -o -v -v -v -t +orthoPosRandRects --quick"
run_test "glean/orthoPosRandTris" 0.0 "bin/glean -o -v -v -v -t +orthoPosRandTris --quick"
run_test "glean/orthoPosVLines" 0.0 "bin/glean -o -v -v -v -t +orthoPosVLines --quick"
run_test "glean/pixelFormats" 0.0 "bin/glean -o -v -v -v -t +pixelFormats --quick"
run_test "glean/pointSprite" 0.0 "bin/glean -o -v -v -v -t +pointSprite --quick"
run_test "glean/readPixSanity" 0.0 "bin/glean -o -v -v -v -t +readPixSanity --quick"
run_test "glean/shaderAPI" 0.0 "bin/glean -o -v -v -v -t +shaderAPI --quick"
run_test "glean/texCombine" 0.0 "bin/glean -o -v -v -v -t +texCombine --quick"
run_test "glean/texCombine4" 0.0 "bin/glean -o -v -v -v -t +texCombine4 --quick"
run_test "glean/texEnv" 0.0 "bin/glean -o -v -v -v -t +texEnv --quick"
run_test "glean/texUnits" 0.0 "bin/glean -o -v -v -v -t +texUnits --quick"
run_test "glean/texgen" 0.0 "bin/glean -o -v -v -v -t +texgen --quick"
run_test "glean/texture_srgb" 0.0 "bin/glean -o -v -v -v -t +texture_srgb --quick"
run_test "glean/vertArrayBGRA" 0.0 "bin/glean -o -v -v -v -t +vertArrayBGRA --quick"
run_test "glean/vertProg1-ABS test" 0.0 "bin/glean -o -v -v -v -t +vertProg1 --quick"
run_test "glean/vertProg1-ADD test" 0.0 "bin/glean -o -v -v -v -t +vertProg1 --quick"
run_test "glean/vertProg1-ARL test" 0.0 "bin/glean -o -v -v -v -t +vertProg1 --quick"
run_test "glean/vertProg1-DP3 test" 0.0 "bin/glean -o -v -v -v -t +vertProg1 --quick"
run_test "glean/vertProg1-DP4 test" 0.0 "bin/glean -o -v -v -v -t +vertProg1 --quick"
run_test "glean/vertProg1-DPH test" 0.0 "bin/glean -o -v -v -v -t +vertProg1 --quick"
run_test "glean/vertProg1-DST test" 0.0 "bin/glean -o -v -v -v -t +vertProg1 --quick"
run_test "glean/vertProg1-Divide by zero test" 0.0 "bin/glean -o -v -v -v -t +vertProg1 --quick"
run_test "glean/vertProg1-EX2 test" 0.0 "bin/glean -o -v -v -v -t +vertProg1 --quick"
run_test "glean/vertProg1-EXP test" 0.0 "bin/glean -o -v -v -v -t +vertProg1 --quick"
run_test "glean/vertProg1-FLR test" 0.0 "bin/glean -o -v -v -v -t +vertProg1 --quick"
run_test "glean/vertProg1-FRC test" 0.0 "bin/glean -o -v -v -v -t +vertProg1 --quick"
run_test "glean/vertProg1-Infinity and nan test" 0.0 "bin/glean -o -v -v -v -t +vertProg1 --quick"
run_test "glean/vertProg1-LG2 test" 0.0 "bin/glean -o -v -v -v -t +vertProg1 --quick"
run_test "glean/vertProg1-LIT test 1" 0.0 "bin/glean -o -v -v -v -t +vertProg1 --quick"
run_test "glean/vertProg1-LIT test 2 (degenerate case: 0 ^ 0 -> 1)" 0.0 "bin/glean -o -v -v -v -t +vertProg1 --quick"
run_test "glean/vertProg1-LIT test 3 (case x < 0)" 0.0 "bin/glean -o -v -v -v -t +vertProg1 --quick"
run_test "glean/vertProg1-LOG test" 0.0 "bin/glean -o -v -v -v -t +vertProg1 --quick"
run_test "glean/vertProg1-MAD test" 0.0 "bin/glean -o -v -v -v -t +vertProg1 --quick"
run_test "glean/vertProg1-MAX test" 0.0 "bin/glean -o -v -v -v -t +vertProg1 --quick"
run_test "glean/vertProg1-MIN test" 0.0 "bin/glean -o -v -v -v -t +vertProg1 --quick"
run_test "glean/vertProg1-MOV test (with swizzle)" 0.0 "bin/glean -o -v -v -v -t +vertProg1 --quick"
run_test "glean/vertProg1-MUL test (with swizzle and masking)" 0.0 "bin/glean -o -v -v -v -t +vertProg1 --quick"
run_test "glean/vertProg1-POW test (exponentiation)" 0.0 "bin/glean -o -v -v -v -t +vertProg1 --quick"
run_test "glean/vertProg1-Position write test (compute position from texcoord)" 0.0 "bin/glean -o -v -v -v -t +vertProg1 --quick"
run_test "glean/vertProg1-RCP test (reciprocal)" 0.0 "bin/glean -o -v -v -v -t +vertProg1 --quick"
run_test "glean/vertProg1-RSQ test 1 (reciprocal square root)" 0.0 "bin/glean -o -v -v -v -t +vertProg1 --quick"
run_test "glean/vertProg1-RSQ test 2 (reciprocal square root of negative value)" 0.0 "bin/glean -o -v -v -v -t +vertProg1 --quick"
run_test "glean/vertProg1-SGE test" 0.0 "bin/glean -o -v -v -v -t +vertProg1 --quick"
run_test "glean/vertProg1-SLT test" 0.0 "bin/glean -o -v -v -v -t +vertProg1 --quick"
run_test "glean/vertProg1-SUB test (with swizzle)" 0.0 "bin/glean -o -v -v -v -t +vertProg1 --quick"
run_test "glean/vertProg1-SWZ test 1" 0.0 "bin/glean -o -v -v -v -t +vertProg1 --quick"
run_test "glean/vertProg1-SWZ test 2" 0.0 "bin/glean -o -v -v -v -t +vertProg1 --quick"
run_test "glean/vertProg1-SWZ test 3" 0.0 "bin/glean -o -v -v -v -t +vertProg1 --quick"
run_test "glean/vertProg1-SWZ test 4" 0.0 "bin/glean -o -v -v -v -t +vertProg1 --quick"
run_test "glean/vertProg1-SWZ test 5" 0.0 "bin/glean -o -v -v -v -t +vertProg1 --quick"
run_test "glean/vertProg1-State reference test 1 (material ambient)" 0.0 "bin/glean -o -v -v -v -t +vertProg1 --quick"
run_test "glean/vertProg1-State reference test 2 (light products)" 0.0 "bin/glean -o -v -v -v -t +vertProg1 --quick"
run_test "glean/vertProg1-State reference test 3 (fog params)" 0.0 "bin/glean -o -v -v -v -t +vertProg1 --quick"
run_test "glean/vertProg1-XPD test 1" 0.0 "bin/glean -o -v -v -v -t +vertProg1 --quick"
run_test "glean/vertProg1-XPD test 2 (same src and dst arg)" 0.0 "bin/glean -o -v -v -v -t +vertProg1 --quick"
run_test "glean/vertProg1-Z-write test" 0.0 "bin/glean -o -v -v -v -t +vertProg1 --quick"
run_test "glean/vertattrib" 0.0 "bin/glean -o -v -v -v -t +vertattrib --quick"
run_test "glx/GLX_EXT_import_context/free context" 0.0 "bin/glx-free-context"
run_test "glx/GLX_EXT_import_context/get context ID" 0.0 "bin/glx-get-context-id"
run_test "glx/GLX_EXT_import_context/get current display" 0.0 "bin/glx-get-current-display-ext"
run_test "glx/GLX_EXT_import_context/import context, multi process" 0.0 "bin/glx-import-context-multi-process"
run_test "glx/GLX_EXT_import_context/import context, single process" 0.0 "bin/glx-import-context-single-process"
run_test "glx/GLX_EXT_import_context/imported context has same context ID" 0.0 "bin/glx-import-context-has-same-context-id"
run_test "glx/GLX_EXT_import_context/make current, single process" 0.0 "bin/glx-make-current-single-process"
run_test "glx/GLX_EXT_import_context/query context info" 0.0 "bin/glx-query-context-info-ext"
run_test "glx/GLX_OML_sync_control/swapbuffersmsc-return swap_interval 1" 0.0 "bin/glx-oml-sync-control-swapbuffersmsc-return 1 -fbo -auto"
run_test "glx/extension string sanity" 0.0 "bin/glx-string-sanity -fbo -auto"
run_test "glx/glx-close-display" 0.0 "bin/glx-close-display -auto"
run_test "glx/glx-copy-sub-buffer" 0.0 "bin/glx-copy-sub-buffer -auto"
run_test "glx/glx-destroycontext-1" 0.0 "bin/glx-destroycontext-1 -auto"
run_test "glx/glx-destroycontext-2" 0.0 "bin/glx-destroycontext-2 -auto"
run_test "glx/glx-dont-care-mask" 0.0 "bin/glx-dont-care-mask -auto"
run_test "glx/glx-fbconfig-compliance" 0.0 "bin/glx-fbconfig-compliance -fbo -auto"
run_test "glx/glx-fbconfig-sanity" 0.0 "bin/glx-fbconfig-sanity -fbo -auto"
run_test "glx/glx-fbo-binding" 0.0 "bin/glx-fbo-binding -auto"
run_test "glx/glx-multi-context-ib-1" 0.0 "bin/glx-multi-context-ib-1 -auto"
run_test "glx/glx-multithread" 0.0 "bin/glx-multithread -auto"
run_test "glx/glx-multithread-makecurrent-1" 0.0 "bin/glx-multithread-makecurrent-1 -auto"
run_test "glx/glx-multithread-makecurrent-2" 0.0 "bin/glx-multithread-makecurrent-2 -auto"
run_test "glx/glx-multithread-makecurrent-3" 0.0 "bin/glx-multithread-makecurrent-3 -auto"
run_test "glx/glx-multithread-makecurrent-4" 0.0 "bin/glx-multithread-makecurrent-4 -auto"
run_test "glx/glx-multithread-texture" 0.0 "bin/glx-multithread-texture -auto"
run_test "glx/glx-pixmap-crosscheck" 0.0 "bin/glx-pixmap-crosscheck -fbo -auto"
run_test "glx/glx-pixmap-life" 0.0 "bin/glx-pixmap-life -fbo -auto"
run_test "glx/glx-pixmap13-life" 0.0 "bin/glx-pixmap13-life -fbo -auto"
run_test "glx/glx-query-drawable-GLXBadDrawable" 0.0 "bin/glx-query-drawable --bad-drawable -auto"
run_test "glx/glx-shader-sharing" 0.0 "bin/glx-shader-sharing -auto"
run_test "glx/glx-swap-event_async" 0.0 "bin/glx-swap-event --async -auto"
run_test "glx/glx-swap-event_event" 0.0 "bin/glx-swap-event --event -auto"
run_test "glx/glx-swap-pixmap" 0.0 "bin/glx-swap-pixmap -auto"
run_test "glx/glx-swap-singlebuffer" 0.0 "bin/glx-swap-singlebuffer -auto"
run_test "glx/glx-visuals-depth" 0.0 "bin/glx-visuals-depth -auto"
run_test "glx/glx-visuals-depth -pixmap" 0.0 "bin/glx-visuals-depth -pixmap -fbo -auto"
run_test "glx/glx-visuals-stencil" 0.0 "bin/glx-visuals-stencil -auto"
run_test "glx/glx-visuals-stencil -pixmap" 0.0 "bin/glx-visuals-stencil -pixmap -fbo -auto"
run_test "glx/glx-window-life" 0.0 "bin/glx-window-life -fbo -auto"
run_test "hiz/hiz-depth-read-fbo-d24-s0" 0.0 "bin/hiz-depth-read-fbo-d24-s0 -auto"
run_test "hiz/hiz-depth-read-fbo-d24s8" 0.0 "bin/hiz-depth-read-fbo-d24s8 -auto"
popd

if [ $need_pass == 0 ] ; then
  echo "+---------------------------------------------+"
  echo "| Overall pass, as all 137 tests have passed. |"
  echo "+---------------------------------------------+"
else
  echo "+-----------------------------------------------------------+"
  echo "| Overall failure, as $need_pass tests did not pass and $failures failed. |"
  echo "+-----------------------------------------------------------+"
fi
exit $need_pass

