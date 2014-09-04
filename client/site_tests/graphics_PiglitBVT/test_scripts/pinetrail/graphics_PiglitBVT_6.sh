#!/bin/bash


need_pass=100
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
run_test "spec/!OpenGL 1.2/mipmap-setup" 0.0 "bin/mipmap-setup -auto"
run_test "spec/!OpenGL 1.2/tex-skipped-unit" 0.0 "bin/tex-skipped-unit -auto"
run_test "spec/!OpenGL 1.2/texture-packed-formats" 0.0 "bin/texture-packed-formats -auto"
run_test "spec/!OpenGL 1.2/two-sided-lighting-separate-specular" 0.0 "bin/two-sided-lighting-separate-specular -auto"
run_test "spec/!OpenGL 1.3/tex-border-1" 0.0 "bin/tex-border-1 -auto"
run_test "spec/!OpenGL 1.3/tex3d-depth1" 0.0 "bin/tex3d-depth1 -fbo -auto"
run_test "spec/!OpenGL 1.3/texunits" 0.0 "bin/texunits -auto"
run_test "spec/!OpenGL 1.4/blendminmax" 0.0 "bin/blendminmax -auto"
run_test "spec/!OpenGL 1.4/blendsquare" 0.0 "bin/blendsquare -auto"
run_test "spec/!OpenGL 1.4/draw-batch" 0.0 "bin/draw-batch -auto"
run_test "spec/!OpenGL 1.4/fdo25614-genmipmap" 0.0 "bin/fdo25614-genmipmap -auto"
run_test "spec/!OpenGL 1.4/gl-1.4-dlist-multidrawarrays" 0.0 "bin/gl-1.4-dlist-multidrawarrays -fbo -auto"
run_test "spec/!OpenGL 1.4/stencil-wrap" 0.0 "bin/stencil-wrap -auto"
run_test "spec/!OpenGL 1.4/tex1d-2dborder" 0.0 "bin/tex1d-2dborder -auto"
run_test "spec/!OpenGL 1.4/triangle-rasterization" 0.0 "bin/triangle-rasterization -auto"
run_test "spec/!OpenGL 1.4/triangle-rasterization-fbo" 0.0 "bin/triangle-rasterization -auto -use_fbo"
run_test "spec/!OpenGL 1.4/triangle-rasterization-overdraw" 0.0 "bin/triangle-rasterization-overdraw -auto"
run_test "spec/!OpenGL 1.5/draw-elements" 0.0 "bin/draw-elements -auto"
run_test "spec/!OpenGL 1.5/draw-elements-user" 0.0 "bin/draw-elements -auto user"
run_test "spec/!OpenGL 1.5/draw-vertices" 0.0 "bin/draw-vertices -auto"
run_test "spec/!OpenGL 1.5/draw-vertices-user" 0.0 "bin/draw-vertices -auto user"
run_test "spec/!OpenGL 1.5/isbufferobj" 0.0 "bin/isbufferobj -auto"
run_test "spec/!OpenGL 1.5/normal3b3s-invariance-byte" 0.0 "bin/gl-1.5-normal3b3s-invariance GL_BYTE -auto"
run_test "spec/!OpenGL 1.5/normal3b3s-invariance-short" 0.0 "bin/gl-1.5-normal3b3s-invariance GL_SHORT -auto"
run_test "spec/!OpenGL 2.0/attrib-assignments" 0.0 "bin/attrib-assignments -auto"
run_test "spec/!OpenGL 2.0/attribs" 0.0 "bin/attribs -fbo -auto"
run_test "spec/!OpenGL 2.0/clear-varray-2.0" 0.0 "bin/clear-varray-2.0 -auto"
run_test "spec/!OpenGL 2.0/clip-flag-behavior" 0.0 "bin/clip-flag-behavior -auto"
run_test "spec/!OpenGL 2.0/depth-tex-modes-glsl" 0.0 "bin/depth-tex-modes-glsl -auto"
run_test "spec/!OpenGL 2.0/early-z" 0.0 "bin/early-z -auto"
run_test "spec/!OpenGL 2.0/fragment-and-vertex-texturing" 0.0 "bin/fragment-and-vertex-texturing -auto"
run_test "spec/!OpenGL 2.0/getattriblocation-conventional" 0.0 "bin/getattriblocation-conventional -auto"
run_test "spec/!OpenGL 2.0/gl-2.0-vertexattribpointer" 0.0 "bin/gl-2.0-vertexattribpointer -fbo -auto"
run_test "spec/!OpenGL 2.0/incomplete-texture-glsl" 0.0 "bin/incomplete-texture -auto glsl -fbo -auto"
run_test "spec/!OpenGL 2.0/vertex-program-two-side" 0.0 "bin/vertex-program-two-side -fbo -auto"
run_test "spec/!OpenGL 2.0/vertex-program-two-side back" 0.0 "bin/vertex-program-two-side back -fbo -auto"
run_test "spec/!OpenGL 2.0/vertex-program-two-side back back2" 0.0 "bin/vertex-program-two-side back back2 -fbo -auto"
run_test "spec/!OpenGL 2.0/vertex-program-two-side back2" 0.0 "bin/vertex-program-two-side back2 -fbo -auto"
run_test "spec/!OpenGL 2.0/vertex-program-two-side enabled" 0.0 "bin/vertex-program-two-side enabled -fbo -auto"
run_test "spec/!OpenGL 2.0/vertex-program-two-side enabled front" 0.0 "bin/vertex-program-two-side enabled front -fbo -auto"
run_test "spec/!OpenGL 2.0/vertex-program-two-side enabled front back" 0.0 "bin/vertex-program-two-side enabled front back -fbo -auto"
run_test "spec/!OpenGL 2.0/vertex-program-two-side front" 0.0 "bin/vertex-program-two-side front -fbo -auto"
run_test "spec/!OpenGL 2.0/vertex-program-two-side front back" 0.0 "bin/vertex-program-two-side front back -fbo -auto"
run_test "spec/!OpenGL 2.0/vertex-program-two-side front back back2" 0.0 "bin/vertex-program-two-side front back back2 -fbo -auto"
run_test "spec/!OpenGL 2.0/vertex-program-two-side front back2" 0.0 "bin/vertex-program-two-side front back2 -fbo -auto"
run_test "spec/!OpenGL 2.0/vs-point_size-zero" 0.0 "bin/vs-point_size-zero -auto"
run_test "spec/!OpenGL 2.1/minmax" 0.0 "bin/gl-2.1-minmax -fbo -auto"
run_test "spec/!OpenGL 3.0/genmipmap-errors" 0.0 "bin/genmipmap-errors -fbo -auto"
run_test "spec/3DFX_texture_compression_FXT1/invalid formats" 0.0 "bin/arb_texture_compression-invalid-formats fxt1 -fbo -auto"
run_test "spec/AMD_shader_stencil_export/arb-undefined.frag" 0.0 "bin/glslparsertest tests/spec/amd_shader_stencil_export/arb-undefined.frag fail 1.20"
run_test "spec/AMD_shader_trinary_minmax/compiler/define.frag" 0.0 "bin/glslparsertest tests/spec/amd_shader_trinary_minmax/compiler/define.frag pass 1.10 GL_AMD_shader_trinary_minmax"
run_test "spec/AMD_shader_trinary_minmax/compiler/define.vert" 0.0 "bin/glslparsertest tests/spec/amd_shader_trinary_minmax/compiler/define.vert pass 1.10 GL_AMD_shader_trinary_minmax"
run_test "spec/AMD_shader_trinary_minmax/execution/max3-basic" 0.0 "bin/shader_runner tests/spec/amd_shader_trinary_minmax/execution/max3-basic.shader_test -auto"
run_test "spec/AMD_shader_trinary_minmax/execution/mid3-basic" 0.0 "bin/shader_runner tests/spec/amd_shader_trinary_minmax/execution/mid3-basic.shader_test -auto"
run_test "spec/AMD_shader_trinary_minmax/execution/min3-basic" 0.0 "bin/shader_runner tests/spec/amd_shader_trinary_minmax/execution/min3-basic.shader_test -auto"
run_test "spec/APPLE_vertex_array_object/isvertexarray" 0.0 "bin/arb_vertex_array-isvertexarray apple -fbo -auto"
run_test "spec/APPLE_vertex_array_object/vao-01" 0.0 "bin/vao-01 -auto"
run_test "spec/APPLE_vertex_array_object/vao-02" 0.0 "bin/vao-02 -auto"
run_test "spec/ARB_ES2_compatibility/FBO blit from missing attachment (ES2 completeness rules)" 0.0 "bin/fbo-missing-attachment-blit es2 from -fbo -auto"
run_test "spec/ARB_ES2_compatibility/FBO blit to missing attachment (ES2 completeness rules)" 0.0 "bin/fbo-missing-attachment-blit es2 to -fbo -auto"
run_test "spec/ARB_ES2_compatibility/NUM_SHADER_BINARY_FORMATS over-run check" 0.0 "bin/arb_get_program_binary-overrun shader -fbo -auto"
run_test "spec/ARB_ES2_compatibility/arb_es2_compatibility-depthrangef" 0.0 "bin/arb_es2_compatibility-depthrangef -auto"
run_test "spec/ARB_ES2_compatibility/arb_es2_compatibility-drawbuffers" 0.0 "bin/arb_es2_compatibility-drawbuffers -auto"
run_test "spec/ARB_ES2_compatibility/arb_es2_compatibility-getshaderprecisionformat" 0.0 "bin/arb_es2_compatibility-getshaderprecisionformat -auto"
run_test "spec/ARB_ES2_compatibility/arb_es2_compatibility-maxvectors" 0.0 "bin/arb_es2_compatibility-maxvectors -auto"
run_test "spec/ARB_ES2_compatibility/arb_es2_compatibility-releaseshadercompiler" 0.0 "bin/arb_es2_compatibility-releaseshadercompiler -auto"
run_test "spec/ARB_ES2_compatibility/arb_es2_compatibility-shadercompiler" 0.0 "bin/arb_es2_compatibility-shadercompiler -auto"
run_test "spec/ARB_ES2_compatibility/fbo-alphatest-formats" 0.0 "bin/fbo-alphatest-formats GL_ARB_ES2_compatibility -fbo -auto"
run_test "spec/ARB_ES2_compatibility/fbo-blending-formats" 0.0 "bin/fbo-blending-formats GL_ARB_ES2_compatibility -fbo -auto"
run_test "spec/ARB_ES2_compatibility/fbo-clear-formats" 0.0 "bin/fbo-clear-formats GL_ARB_ES2_compatibility -fbo -auto"
run_test "spec/ARB_ES2_compatibility/fbo-colormask-formats" 0.0 "bin/fbo-colormask-formats GL_ARB_ES2_compatibility -fbo -auto"
run_test "spec/ARB_ES2_compatibility/get-renderbuffer-internalformat" 0.0 "bin/get-renderbuffer-internalformat GL_ARB_ES2_compatibility -fbo -auto"
run_test "spec/ARB_ES2_compatibility/texwrap formats" 0.0 "bin/texwrap GL_ARB_ES2_compatibility -fbo -auto"
run_test "spec/ARB_clear_buffer_object/arb_clear_buffer_object-invalid-internal-format" 0.0 "bin/arb_clear_buffer_object-invalid-internal-format -fbo -auto"
run_test "spec/ARB_color_buffer_float/GL_RGBA8-render-sanity" 0.0 "bin/arb_color_buffer_float-render GL_RGBA8 sanity -fbo -auto"
run_test "spec/ARB_color_buffer_float/GL_RGBA8-render-sanity-fog" 0.0 "bin/arb_color_buffer_float-render GL_RGBA8 sanity fog -fbo -auto"
run_test "spec/ARB_copy_buffer/copy_buffer_coherency" 0.0 "bin/copy_buffer_coherency -auto"
run_test "spec/ARB_copy_buffer/copybuffersubdata" 0.0 "bin/copybuffersubdata -auto"
run_test "spec/ARB_copy_buffer/dlist" 0.0 "bin/arb_copy_buffer-dlist -fbo -auto"
run_test "spec/ARB_copy_buffer/get" 0.0 "bin/arb_copy_buffer-get -fbo -auto"
run_test "spec/ARB_copy_buffer/negative-bound-zero" 0.0 "bin/arb_copy_buffer-negative-bound-zero -fbo -auto"
run_test "spec/ARB_copy_buffer/negative-bounds" 0.0 "bin/arb_copy_buffer-negative-bounds -fbo -auto"
run_test "spec/ARB_copy_buffer/negative-mapped" 0.0 "bin/arb_copy_buffer-negative-mapped -fbo -auto"
run_test "spec/ARB_copy_buffer/overlap" 0.0 "bin/arb_copy_buffer-overlap -fbo -auto"
run_test "spec/ARB_copy_buffer/targets" 0.0 "bin/arb_copy_buffer-targets -fbo -auto"
run_test "spec/ARB_depth_texture/depth-tex-modes" 0.0 "bin/depth-tex-modes -auto"
run_test "spec/ARB_depth_texture/fbo-depth-GL_DEPTH_COMPONENT16-blit" 0.0 "bin/fbo-depth blit GL_DEPTH_COMPONENT16 -fbo -auto"
run_test "spec/ARB_depth_texture/fbo-depth-GL_DEPTH_COMPONENT16-clear" 0.0 "bin/fbo-depth clear GL_DEPTH_COMPONENT16 -fbo -auto"
run_test "spec/ARB_depth_texture/fbo-depth-GL_DEPTH_COMPONENT16-readpixels" 0.0 "bin/fbo-depth readpixels GL_DEPTH_COMPONENT16 -fbo -auto"
run_test "spec/ARB_depth_texture/fbo-depth-GL_DEPTH_COMPONENT16-tex1d" 0.0 "bin/fbo-depth-tex1d GL_DEPTH_COMPONENT16 -fbo -auto"
run_test "spec/ARB_depth_texture/fbo-depth-GL_DEPTH_COMPONENT24-blit" 0.0 "bin/fbo-depth blit GL_DEPTH_COMPONENT24 -fbo -auto"
run_test "spec/ARB_depth_texture/fbo-depth-GL_DEPTH_COMPONENT24-clear" 0.0 "bin/fbo-depth clear GL_DEPTH_COMPONENT24 -fbo -auto"
run_test "spec/ARB_depth_texture/fbo-depth-GL_DEPTH_COMPONENT24-readpixels" 0.0 "bin/fbo-depth readpixels GL_DEPTH_COMPONENT24 -fbo -auto"
run_test "spec/ARB_depth_texture/fbo-depth-GL_DEPTH_COMPONENT24-tex1d" 0.0 "bin/fbo-depth-tex1d GL_DEPTH_COMPONENT24 -fbo -auto"
run_test "spec/ARB_depth_texture/fbo-depth-GL_DEPTH_COMPONENT32-blit" 0.0 "bin/fbo-depth blit GL_DEPTH_COMPONENT32 -fbo -auto"
run_test "spec/ARB_depth_texture/fbo-depth-GL_DEPTH_COMPONENT32-clear" 0.0 "bin/fbo-depth clear GL_DEPTH_COMPONENT32 -fbo -auto"
run_test "spec/ARB_depth_texture/fbo-depth-GL_DEPTH_COMPONENT32-readpixels" 0.0 "bin/fbo-depth readpixels GL_DEPTH_COMPONENT32 -fbo -auto"
run_test "spec/ARB_depth_texture/fbo-depth-GL_DEPTH_COMPONENT32-tex1d" 0.0 "bin/fbo-depth-tex1d GL_DEPTH_COMPONENT32 -fbo -auto"
run_test "spec/ARB_depth_texture/get-renderbuffer-internalformat" 0.0 "bin/get-renderbuffer-internalformat GL_ARB_depth_texture -fbo -auto"
run_test "spec/ARB_depth_texture/texwrap formats" 0.0 "bin/texwrap GL_ARB_depth_texture -fbo -auto"
popd

if [ $need_pass == 0 ] ; then
  echo "+---------------------------------------------+"
  echo "| Overall pass, as all 100 tests have passed. |"
  echo "+---------------------------------------------+"
else
  echo "+-----------------------------------------------------------+"
  echo "| Overall failure, as $need_pass tests did not pass and $failures failed. |"
  echo "+-----------------------------------------------------------+"
fi
exit $need_pass

