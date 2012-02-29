/* Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
 * This program is free software, released under the GPL.
 * Based on code by Minchan Kim
 *
 * User program that tests low-memory notifications.
 *
 * Compile with -lpthread
 * for instance
 * i686-pc-linux-gnu-gcc low-mem-test.c -o low-mem-test -lpthread
 *
 * Run as: low-mem-test <allocation size> <allocation interval (microseconds)>
 *
 * This program runs in two threads.  One thread continuously allocates memory
 * in the given chunk size, waiting for the specified microsecond interval
 * between allocations.  The other runs in a loop that waits for a low-memory
 * notification, then frees some of the memory that the first thread has
 * allocated.
 *
 * Also can be run as: low-mem-test autotesting
 *
 * In autotesting mode, this program first makes a non-blocking call to ensure
 * that no low-memory notification is pending.  (The autotest expects the
 * system is not under memory pressure.)  Then it allocates memory with some
 * default size and interval between allocations until memory pressure is
 * reached.  Then it checks that we are indeed low on memory (*).  Then it frees
 * some memory and again checks that no low-memory notification is pending.
 *
 * (*) Note: there is a flaw with this check, because it uses exactly the same
 * formula used by the kernel to check for low-memory conditions.  If the
 * formula itself is wrong, the check is useless.  A more complete test needs
 * to involve the Chrome browser.
 */

#include <poll.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <stdio.h>
#include <pthread.h>
#include <stdlib.h>
#include <string.h>

int memory_chunk_size = 10000000;
int wait_time_us = 10000;
int autotesting;

pthread_mutex_t mutex = PTHREAD_MUTEX_INITIALIZER;

struct node {
  void* memory;
  struct node* prev;
  struct node* next;
};

struct node head, tail;

void work(void) {
  int i;

  while (1) {
    struct node* new = malloc(sizeof(struct node));
    if (new == NULL) {
      perror("allocating node");
      exit(1);
    }
    new->memory = malloc(memory_chunk_size);
    if (new->memory == NULL) {
      perror("allocating chunk");
      exit(1);
    }

    pthread_mutex_lock(&mutex);
    new->next = &head;
    new->prev = head.prev;
    new->prev->next = new;
    new->next->prev = new;
    for (i = 0; i < memory_chunk_size / 4096; i++) {
      /* touch page */
      ((unsigned char*) new->memory)[i * 4096] = 1;
    }

    pthread_mutex_unlock(&mutex);

    if (!autotesting) {
      printf("+");
      fflush(stdout);
    }

    usleep(wait_time_us);
  }
}

void free_memory(void) {
  struct node* old;
  pthread_mutex_lock(&mutex);
  old = tail.next;
  if (old == &head) {
    fprintf(stderr, "no memory left to free\n");
    exit(1);
  }
  old->prev->next = old->next;
  old->next->prev = old->prev;
  free(old->memory);
  free(old);
  pthread_mutex_unlock(&mutex);
  if (!autotesting) {
    printf("-");
    fflush(stdout);
  }
}

/* Returns file content as a string.  Caller must free returned string. */
char* get_file(const char* path) {
  char buffer[4096];
  char* s;
  FILE* f;
  int n;

  f = fopen(path, "r");
  if (f == NULL) {
    perror(path);
    exit(1);
  }
  n = fread(buffer, 1, sizeof(buffer), f);
  if (n <= 0) {
    fprintf(stderr, "error reading %s\n", path);
    perror(path);
    exit(1);
  }
  s = strndup(buffer, n);
  if (s == NULL) {
    perror("strdup");
    exit(1);
  }
  return s;
}

unsigned int get_low_mem_margin(void) {
  char* s = get_file("/sys/kernel/mm/chromeos-low_mem/margin");
  char* endp;
  unsigned long int n = strtoul(s, &endp, 10);
  if (*endp != '\n') {
    fprintf(stderr, "cannot parse margin file\n");
    exit(1);
  }
  free(s);
  return (unsigned int) n;
}

/* Stores in *C the value with name NAME from the output of /proc/meminfo.  S
 * points anywhere in the output of /proc/meminfo.  Returns the position in S
 * after the requested value is scanned.
 */
char* find_mem_field(char* s, const char* name, unsigned int* p) {
  unsigned long int n;
  char* endp;

  s = strstr(s, name);
  if (s == NULL) {
    fprintf(stderr, "could not find %s mem field\n", name);
    exit(1);
  }
  /* skip name */
  s += strlen(name);

  /* check for colon and skip it */
  if (*s != ':') {
    fprintf(stderr, "missing colon in %s mem field\n", name);
    exit(1);
  }
  s++;
  n = strtoul(s, &endp, 10);

  /* check for line end */
  char* line_end = " kB\n";
  if (strncmp(endp, line_end, strlen(line_end))) {
    fprintf(stderr, "bad line end for %s mem field\n", name);
    exit(1);
  }

  *p = (unsigned int) n;
  return endp;
}

void get_mem(unsigned int* pmem_total,
             unsigned int* pmem_free,
             unsigned int* pactive_file,
             unsigned int* pinactive_file,
             unsigned int* pdirty) {
  char* meminfo = get_file("/proc/meminfo");
  char* s = meminfo;
  s = find_mem_field(s, "MemTotal", pmem_total);
  s = find_mem_field(s, "MemFree", pmem_free);
  s = find_mem_field(s, "Active(file)", pactive_file);
  s = find_mem_field(s, "Inactive(file)", pinactive_file);
  s = find_mem_field(s, "Dirty", pdirty);
  free(meminfo);
}

void autotest_process_low_memory_event(struct pollfd* ppfd) {
  /* Check that the free memory situation is more or less what we expect.
   *
   * Note for the uninitiated.  It would be nice to do these calculations
   * in a shell script.  Unfortunately this process is now huge, and
   * attempting to call system() results in ENOMEM (because of the
   * clone() call, can't Linux do better?).  We could ask the parent
   * process (a python autotest script) to do these calculations, but the
   * synchronization is messier than a bit of extra code in here.
   */
  unsigned int margin = get_low_mem_margin();
  unsigned int mem_total, mem_free, active_file,
      inactive_file, dirty, available_mem, ratio;
  unsigned int min_file_mem = 50000;

  get_mem(&mem_total, &mem_free, &active_file, &inactive_file, &dirty);

  if (margin != 10) {
    fprintf(stderr, "expected margin = 10, found %d\n", margin);
    exit(1);
  }

  /* This formula is the same used by the kernel to decide when to fire
   * the notification.
   */
  available_mem = mem_free + active_file + inactive_file - dirty - min_file_mem;
  ratio = mem_total / available_mem;

  if (ratio < 8 || ratio > 12) {
    fprintf(stderr, "unexpected ratio: %d\n"
            "total: %d\n"
            "free: %d\n"
            "active(file): %d\n"
            "inactive(file): %d\n"
            "dirty: %d\n",
            ratio, mem_total, mem_free,
            active_file, inactive_file, dirty);
    exit(1);
  }

  /* Free several chunks and check that the notification is gone.
   */
  free_memory();
  free_memory();
  free_memory();
  free_memory();
  free_memory();
  poll(ppfd, 1, 0);
  if (ppfd->revents != 0) {
    fprintf(stderr, "expected no events but poll() returned 0x%x\n",
            ppfd->revents);
    exit(1);
  }
}

void* poll_thread(void* dummy) {
  struct pollfd pfd;
  int fd = open("/dev/chromeos-low-mem", O_RDONLY);
  if (fd == -1) {
    perror("/dev/chromeos-low-mem");
    exit(1);
  }

  pfd.fd = fd;
  pfd.events = POLLIN;

  if (autotesting) {
    /* Check that there is no memory shortage yet. */
    poll(&pfd, 1, 0);
    if (pfd.revents != 0) {
      fprintf(stderr, "expected no events but poll() returned 0x%x\n",
              pfd.revents);
      exit(1);
    }
  }

  while (1) {
    poll(&pfd, 1, -1);
    if (autotesting) {
      autotest_process_low_memory_event(&pfd);
      exit(0);
    } else {
      free_memory();
    }
  }
}

int main(int argc, char** argv) {
  pthread_t threadid;

  head.next = NULL;
  head.prev = &tail;
  tail.next = &head;
  tail.prev = NULL;

  if (argc != 3 && (argc != 2 || strcmp(argv[1], "autotesting"))) {
    fprintf(stderr,
            "usage: low-mem-test <alloc size in bytes> "
            "<alloc interval in microseconds>\n"
            "or:    low-mem-test autotesting\n");
    exit(1);
  }

  if (argc == 2) {
    autotesting = 1;
  } else {
    memory_chunk_size = atoi(argv[1]);
    wait_time_us = atoi(argv[2]);
  }

  if (pthread_create(&threadid, NULL, poll_thread, NULL)) {
    perror("pthread");
    return 1;
  }

  work();
  return 0;
}
