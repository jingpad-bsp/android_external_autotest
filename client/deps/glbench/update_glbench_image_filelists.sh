cd ../glbench-images/glbench_reference_images
ls *.png | sort > ../../glbench/glbench_reference_images.txt
ls *.png | sort > index.html
cd ..
cd ../glbench-images/glbench_knownbad_images
ls */*.png | sort > ../../glbench/glbench_knownbad_images.txt
ls */*.png | sort > index.html

