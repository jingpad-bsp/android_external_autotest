#!/bin/bash

# Find files >1M in size.
find . -size +1000k -printf '%s %p\n' > /tmp/largeresultfileslist.txt
