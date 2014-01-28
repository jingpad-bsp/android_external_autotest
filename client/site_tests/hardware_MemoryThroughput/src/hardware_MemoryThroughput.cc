// Copyright (c) 2009 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Compile: use the Makefile in the same folder.

// Commandline Usage: ./hardware_MemoryThroughput [num_iteration test-1 test-2 ...]
//   num_iteration : a positive integer number larger than 10,
//                   otherwise will use the default value 2010.
//   test-i        : the memory size, for example, if test-i = 12, then the
//                   memory size is 2^12 = 4k.
//                   Valid range is [12, 28], i.e., [4k, 256M]. The default
//                   test set includes all possible memory size, 4k, 8k, 16k,
//                   32k, 64k, ..., 128M, 256M.
// Examples of usage:
//   1) ./hardware_MemoryThroughput
//   2) ./hardware_MemoryThroughput 1000
//   3) ./hardware_MemoryThroughput -1 16 17 18
//
// Output semantics:
//   Action =   cp   : mem copy
//              set  : mem set
//              w    : mem write
//              r    : mem read
//              rw   : mem read+write
//              r7w3 : mem read:write = 0.7:0.3
//   Method =   seq  : sequential
//              ran  : random

#ifdef __SSE2__
#include <emmintrin.h>
#endif  // __SSE2__
#include <memory.h>
#include <stdio.h>
#include <sys/time.h>
#include <time.h>

#include <algorithm>

#include "base/logging.h"
#include "base/memory/scoped_ptr.h"

// The REPEAT_OP_x macros are defined to minimize the looping overhead
// to be less than 5% of the total memory operation time.
// We need to make sure the memory table size is always a multiple of 64.
#define REPEAT_OP_2(mem_op) mem_op; mem_op
#define REPEAT_OP_4(mem_op) REPEAT_OP_2(mem_op); REPEAT_OP_2(mem_op)
#define REPEAT_OP_8(mem_op) REPEAT_OP_4(mem_op); REPEAT_OP_4(mem_op)
#define REPEAT_OP_16(mem_op) REPEAT_OP_8(mem_op); REPEAT_OP_8(mem_op)
#define REPEAT_OP_32(mem_op) REPEAT_OP_16(mem_op); REPEAT_OP_16(mem_op)
#define REPEAT_OP_64(mem_op) REPEAT_OP_32(mem_op); REPEAT_OP_32(mem_op)

bool MemValueCheck(int** table,
                   int table_size,
                   const int* value) {
  for (int i = 0; i < table_size; ++i) {
    if (table[i] != value)
      return false;
  }
  return true;
}

void MemWriteSequential(int** table,
                        int table_size,
                        const int* value) {
  CHECK(table_size % 64 == 0);
  int* value_local = const_cast<int*>(value);
  int i = 0;
  while (i < table_size) {
    REPEAT_OP_64(table[i++] = value_local);
  }
}

void MemReadWriteSequential(int** table_dst,
                            int** table_src,
                            int table_size) {
  CHECK(table_size % 64 == 0);
  int i = 0;
  while (i < table_size) {
    REPEAT_OP_64(table_dst[i] = table_src[i]; ++i);
  }
}

// This function builds a table so that 4/7 of the entries are NULL,
// and 3/7 of the entries are non-NULL.
void Read7Write3TableSetup(int** table,
                           int table_size,
                           const int* value_non_null) {
  int* value_local = const_cast<int*>(value_non_null);
  int i = 0;
  while (i < table_size) {
    if (i % 7 < 4)
      table[i] = NULL;
    else
      table[i] = value_local;
    ++i;
  }
}

void MemRead7Write3Sequential(int** table,
                              int table_size,
                              const int* value) {
  CHECK(table_size % 64 == 0);
  int* value_local = const_cast<int*>(value);
  int i = 0;
  // We read every entry.  Among them 3/7 are non-NULL, and we reset their
  // value.  Therefore, read : write = 1 : 3/7 = 7 : 3.
  while (i < table_size) {
    REPEAT_OP_64(if (table[i] != NULL) table[i] = value_local; ++i);
  }
}

void MemCopySequential(int** table_dst,
                       int** table_src,
                       int table_size) {
  memcpy(table_dst, table_src, table_size);
}

void MemSetSequential(int** table,
                      int table_size,
                      const int value) {
  memset(table, value, table_size);
}

// This function builds a table so that each entry uniquely points to another
// entry. You can visulize the table as a link. The tail of the link points
// to NULL.
//
// Returns -1 if the algorithm goes wrong (for debugging purpose, shouldn't
// happen); otherwise returns the head entry index.
//
// Courtesy of kwaters@
int RandomWalkTableSetup(int** table,
                         int table_size) {
  for (int i = 0; i < table_size; ++i) {
    table[i] = NULL;
  }
  int done = 1;
  unsigned int seed = 2010;  // Any number works here.
  int tail_index = rand_r(&seed) % table_size;
  int head_index = tail_index;
  while (done < table_size) {
    int random_index = rand_r(&seed) % table_size;
    while (random_index == tail_index || table[random_index] != NULL) {
      // If the random entry is already filled, find the next available entry
      // sequentially.
      random_index = (random_index + 1) % table_size;
    }
    table[random_index] = reinterpret_cast<int*>(table + head_index);
    head_index = random_index;
    ++done;
  }
  // Double check whether the generated table is a fully covered random walk.
  int** holder = table + head_index;
  done = 0;
  while (holder != NULL) {
    holder = reinterpret_cast<int**>(*holder);
    ++done;
  }
  if (done != table_size) {
    return -1;
  }
  return head_index;
}

// This function should always return true. However, caller of this function
// must check the returned value, otherwise there might be undesired code
// optimization.
bool MemReadRandomWalk(int** table,
                       int table_size,
                       int entry_index) {
  CHECK(table_size % 64 == 0);
  int** holder = table + entry_index;
  int i = 0;
  while (i < table_size) {
    REPEAT_OP_64(holder = reinterpret_cast<int**>(*holder));
    i += 64;
  }
  // "holder" should always be NULL by the end, but to avoid undesired code
  // optimization, we have to check the value.
  if (holder == NULL)
    return true;
  return false;
}

// This function takes start/end time, and returns the difference between
// them in MicroSecond.
double GetPeriodInUS(const timeval& time_start,
                     const timeval& time_end) {
  double time_passed = time_end.tv_usec - time_start.tv_usec;
  time_passed += 1000000.0 * (time_end.tv_sec - time_start.tv_sec);
  return time_passed;
}

// @input total_time total time spent in operation (in MicroSecond);
// @input byte_size memory size (number of bytes);
// @return time of operation (in MicroSecond) per MegaByte per iteration.
double NormalizeTime(double total_time,
                     int byte_size) {
  double time_per = total_time / byte_size;
  time_per *= 1000000;
  return time_per;
}

// This function invalidate the memory from the cache.
//
// Courtesy of fbarchard@
void FlushCache(void* mem,
                int byte_size) {
#if defined(__i386__) || defined(__x86_64__)  // CPU type
#ifdef __SSE2__
  unsigned char* mem_uc = static_cast<unsigned char*>(mem);
  while (byte_size >= 32) {
    _mm_clflush(mem_uc);
    mem_uc += 32;
    byte_size -= 32;
  }
#endif  // __SSE2__
#elif defined(__arm__)  // CPU type
  // TODO(zmo@): figure out how to invalidate cache for ARM machines.
#else  // CPU type
#error Unrecognized CPU type!
#endif  // CPU type
}

// This function collects the time needed for
// sequential memory set operation.
//
// Test rule:
//   The test is performed "num_iteration" iterations.
//   The first "num_warm_up_iteration" iterations are ignored.
//   Returns the minimum one-iteration test time among the rest iterations.
// This rule applies to all the tests.
double TestMemSetSequential(int** table,
                            int num_table_entry,
                            const int value,
                            int num_iteration,
                            int num_warm_up_iteration) {
  double time_passed = 0.0;
  struct timeval time_start, time_end;
  int byte_size = num_table_entry * sizeof(int*);
  for (int iteration = 0; iteration < num_iteration; ++iteration) {
    FlushCache(table, byte_size);
    gettimeofday(&time_start, NULL);
    MemSetSequential(table, num_table_entry, value);
    gettimeofday(&time_end, NULL);
    if (iteration < num_warm_up_iteration) {
      continue;
    } else if (iteration == num_warm_up_iteration) {
      time_passed = GetPeriodInUS(time_start, time_end);
    } else {
      time_passed = std::min(time_passed,
                             GetPeriodInUS(time_start, time_end));
    }
  }
  return NormalizeTime(time_passed, byte_size);
}

// This function collects the time needed for
// sequential memory copy operation.
double TestMemCopySequential(int** table_dst,
                             int** table_src,
                             int num_table_entry,
                             int num_iteration,
                             int num_warm_up_iteration) {
  double time_passed = 0.0;
  struct timeval time_start, time_end;
  int byte_size = num_table_entry * sizeof(int*);
  for (int iteration = 0; iteration < num_iteration; ++iteration) {
    FlushCache(table_dst, byte_size);
    FlushCache(table_src, byte_size);
    gettimeofday(&time_start, NULL);
    MemCopySequential(table_dst, table_src, num_table_entry);
    gettimeofday(&time_end, NULL);
    if (iteration < num_warm_up_iteration) {
      continue;
    } else if (iteration == num_warm_up_iteration) {
      time_passed = GetPeriodInUS(time_start, time_end);
    } else {
      time_passed = std::min(time_passed,
                             GetPeriodInUS(time_start, time_end));
    }
  }
  return NormalizeTime(time_passed, byte_size);
}

// This function collects the time needed for
// sequential memory write operation.
double TestMemWriteSequential(int** table,
                              int num_table_entry,
                              const int* value,
                              int num_iteration,
                              int num_warm_up_iteration) {
  double time_passed = 0.0;
  struct timeval time_start, time_end;
  int byte_size = num_table_entry * sizeof(int*);
  for (int iteration = 0; iteration < num_iteration; ++iteration) {
    FlushCache(table, byte_size);
    gettimeofday(&time_start, NULL);
    MemWriteSequential(table, num_table_entry, value);
    gettimeofday(&time_end, NULL);
    if (iteration < num_warm_up_iteration) {
      continue;
    } else if (iteration == num_warm_up_iteration) {
      time_passed = GetPeriodInUS(time_start, time_end);
    } else {
      time_passed = std::min(time_passed,
                             GetPeriodInUS(time_start, time_end));
    }
  }
  return NormalizeTime(time_passed, byte_size);
}

// This function collects the time needed for
// sequential memory read+write operation.
double TestMemReadWriteSequential(int** table_dst,
                                  int** table_src,
                                  int num_table_entry,
                                  int num_iteration,
                                  int num_warm_up_iteration) {
  double time_passed = 0.0;
  struct timeval time_start, time_end;
  int byte_size = num_table_entry * sizeof(int*);
  for (int iteration = 0; iteration < num_iteration; ++iteration) {
    FlushCache(table_dst, byte_size);
    FlushCache(table_src, byte_size);
    gettimeofday(&time_start, NULL);
    MemReadWriteSequential(table_dst, table_src, num_table_entry);
    gettimeofday(&time_end, NULL);
    if (iteration < num_warm_up_iteration) {
      continue;
    } else if (iteration == num_warm_up_iteration) {
      time_passed = GetPeriodInUS(time_start, time_end);
    } else {
      time_passed = std::min(time_passed,
                             GetPeriodInUS(time_start, time_end));
    }
  }
  return NormalizeTime(time_passed, byte_size);
}

// This function collects the time needed for
// sequential memory read/write (70% read and 30% write) operation.
double TestMemRead7Write3Sequential(int** table,
                                    int num_table_entry,
                                    const int* value,
                                    int num_iteration,
                                    int num_warm_up_iteration) {
  double time_passed = 0.0;
  struct timeval time_start, time_end;
  int byte_size = num_table_entry * sizeof(int*);
  for (int iteration = 0; iteration < num_iteration; ++iteration) {
    FlushCache(table, byte_size);
    gettimeofday(&time_start, NULL);
    MemRead7Write3Sequential(table, num_table_entry, value);
    gettimeofday(&time_end, NULL);
    if (iteration < num_warm_up_iteration) {
      continue;
    } else if (iteration == num_warm_up_iteration) {
      time_passed = GetPeriodInUS(time_start, time_end);
    } else {
      time_passed = std::min(time_passed,
                             GetPeriodInUS(time_start, time_end));
    }
  }
  // We further divide the time by 10/7 because we read every entry, and
  // write to about 3/7 of them, so total operations are 1 + 3/7 instead
  // of 1.
  return NormalizeTime(time_passed, byte_size) * 7 / 10;
}

// This function collects the time needed for
// random memory read operation.
double TestMemReadRandomWalk(int** table,
                             int num_table_entry,
                             int entry_index,
                             int num_iteration,
                             int num_warm_up_iteration) {
  double time_passed = 0.0;
  struct timeval time_start, time_end;
  int byte_size = num_table_entry * sizeof(int*);
  for (int iteration = 0; iteration < num_iteration; ++iteration) {
    FlushCache(table, byte_size);
    gettimeofday(&time_start, NULL);
    bool return_code = MemReadRandomWalk(table,
                                         num_table_entry,
                                         entry_index);
    gettimeofday(&time_end, NULL);
    if (return_code == false) {
      // We have to check "return_code" value to avoid undesired code
      // optimization. However, "return_code" should always be true.
      return -1;
    }
    if (iteration < num_warm_up_iteration) {
      continue;
    } else if (iteration == num_warm_up_iteration) {
      time_passed = GetPeriodInUS(time_start, time_end);
    } else {
      time_passed = std::min(time_passed,
                             GetPeriodInUS(time_start, time_end));
    }
  }
  return NormalizeTime(time_passed, byte_size);
}

int main(int argc, char* argv[]) {
  const int kWordSize = sizeof(int*);
  const int kBitCountMin = 12;  // memory size = 4k
  const int kBitCountMax = 28;  // memory size = 256M
  const int kNumTestMax = kBitCountMax - kBitCountMin + 1;
  // It seems whether ingoring the first a few iterations nor not makes no
  // apparent difference. But I put 10 here anyway just to be safe.
  const int kNumWarmUpIterations = 10;
  // A reasonable iteration number could be anything between 1,000 and 10,000.
  // A number toward the end of 10,000 will make test runs very slow.
  int num_iteration = 2010;
  int test_list[kNumTestMax];
  // Initialize default tests.
  for (int test_index = 0; test_index < kNumTestMax; ++test_index) {
    test_list[test_index] = kBitCountMin + test_index;
  }
  // Process input parameters.
  if (argc > 1) {
    int argv1 = atoi(argv[1]);
    if (argv1 > kNumWarmUpIterations) {
      num_iteration = argv1;
    }
  }
  if (argc > 2) {
    int test_index = 0;
    for (int i = 2; i < argc; ++i) {
      int test = atoi(argv[i]);
      if (test < kBitCountMin || test > kBitCountMax)
        continue;
      test_list[test_index++] = test;
      if (test_index >= kNumTestMax)
        break;
    }
    for (int i = test_index; i < kNumTestMax; ++i)
      test_list[i] = -1;
  }

  printf("Memory Throughput Test: UNIT = MicroSecond/MegaBytes\n\n");
  for (int test_index = 0; test_index < kNumTestMax; ++test_index) {
    int bit_size = test_list[test_index];
    if (bit_size <= 0)  // All tests have been performed.
      break;
    int byte_size = 1 << bit_size;
    int num_table_entry = byte_size / kWordSize;
    int size_letter = ' ';
    int mem_size = byte_size;
    if (mem_size >= 1024) {
      size_letter = 'k';
      mem_size >>= 10;
    }
    if (mem_size >= 1024) {
      size_letter = 'M';
      mem_size >>= 10;
    }
    if (mem_size >= 1024) {
      size_letter = 'G';
      mem_size >>= 10;
    }
    // Any value is fine for "kValueInt" or "kValuePointer".
    const int kValueInt = 2010;
    const int* kValuePointer = reinterpret_cast<int*>(kValueInt);
    scoped_ptr<int*[]> table(new int*[num_table_entry]);
    scoped_ptr<int*[]> table2(new int*[num_table_entry]);
    if (table == NULL || table2 == NULL)
      continue;
    double time_passed;

    // Test 1.1: mem set sequential.
    time_passed = TestMemSetSequential(table.get(),
                                       num_table_entry,
                                       kValueInt,
                                       num_iteration,
                                       kNumWarmUpIterations);
    printf("Action = set, BlockSize = %d%c, Method = seq, Time = %.2f\n",
           mem_size,
           size_letter,
           time_passed);

    // Test 1.2: mem copy sequential.
    time_passed = TestMemCopySequential(table2.get(),
                                        table.get(),
                                        num_table_entry,
                                        num_iteration,
                                        kNumWarmUpIterations);
    printf("Action = cp, BlockSize = %d%c, Method = seq, Time = %.2f\n",
           mem_size,
           size_letter,
           time_passed);

    // Test 1.3: mem write sequential.
    time_passed = TestMemWriteSequential(table.get(),
                                         num_table_entry,
                                         kValuePointer,
                                         num_iteration,
                                         kNumWarmUpIterations);
    printf("Action = w, BlockSize = %d%c, Method = seq, Time = %.2f\n",
           mem_size,
           size_letter,
           time_passed);

    // Test 1.4: mem read+write sequential.
    time_passed = TestMemReadWriteSequential(table2.get(),
                                             table.get(),
                                             num_table_entry,
                                             num_iteration,
                                             kNumWarmUpIterations);
    printf("Action = rw, BlockSize = %d%c, Method = seq, Time = %.2f\n",
           mem_size,
           size_letter,
           time_passed);

    // Test 1.5: mem read/write correctness check.
    if (MemValueCheck(table.get(), num_table_entry, kValuePointer) == false ||
        MemValueCheck(table2.get(), num_table_entry, kValuePointer) == false) {
      // The value used here needs to be consistent with Test 1.3 & 1.4.
      printf("ERROR: [rw correctness check]\n");
    }

    // Test 2: mem read/write (0.7/0.3) sequential.
    Read7Write3TableSetup(table.get(),
                          num_table_entry,
                          kValuePointer);
    time_passed = TestMemRead7Write3Sequential(table.get(),
                                               num_table_entry,
                                               kValuePointer+1,  // Any value.
                                               num_iteration,
                                               kNumWarmUpIterations);
    printf("Action = r0.7w0.3, BlockSize = %d%c, Method = seq, Time = %.2f\n",
           mem_size,
           size_letter,
           time_passed);

    // Test 3: mem read randomwalk.
    int head_entry_index = RandomWalkTableSetup(table.get(), num_table_entry);
    if (head_entry_index < 0) {
      printf("ERROR: [randomwalk setup]\n");
    } else {
      time_passed = TestMemReadRandomWalk(table.get(),
                                          num_table_entry,
                                          head_entry_index,
                                          num_iteration,
                                          kNumWarmUpIterations);
      if (time_passed < 0)  // This should never happen.
        printf("ERROR: [randomwalk]\n");
      printf("Action = r, BlockSize = %d%c, Method = ran, Time = %.2f\n",
             mem_size,
             size_letter,
             time_passed);
    }
    printf("\n");
  }  // End of for-loop for each test.
  return 0;
}

