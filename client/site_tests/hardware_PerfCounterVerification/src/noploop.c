#include <stdlib.h>

int main(int argc, char *argv[]) {
  unsigned long loops = 10000000; // 10 million
  if (argc > 1) {
    loops = strtoul(argv[1], NULL, 10);
    if (loops < 1) {
      loops = 1;
    }
  }

  while (--loops) { /* nop */ }

  return 0;
}
