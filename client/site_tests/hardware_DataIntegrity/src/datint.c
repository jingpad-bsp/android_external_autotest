/* Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
 * Use of this source code is governed by a BSD-style license that can be
 * found in the LICENSE file.
 */

/* Implements datint.h. */

#define _GNU_SOURCE		/* obtain O_DIRECT definition from fcntl.h */
#define _LARGEFILE64_SOURCE	/* Enable lseek64() and off64_t */

#include "datint.h"
#include <stdlib.h>
#include <sys/ioctl.h>
#include <fcntl.h>
#include <unistd.h>
#include <assert.h>
#include <linux/fs.h>		/* provides: BLKGETSIZE64 */
#include <stdio.h>
#include <time.h>
#include <string.h>
#include <malloc.h>
#include <errno.h>
#include <limits.h>
#include <inttypes.h>
#include <ctype.h>		/* provides: isprint */

/* Define debugging macros. */
#ifdef NDEBUG
#define DEBUG(M, ...)
#define LOG_CHUNK(format, chunk)
#define ASSERT(x)
#else
#define DEBUG(M, ...)							\
	fprintf(stderr,"DEBUG %s:%d: " M "\n", __FILE__, __LINE__,	\
	##__VA_ARGS__)
#define LOG_CHUNK(format, chunk) fprintf_chunk(stderr, format, chunk)
#define ASSERT(x) assert(x)
#endif

/* Define error macro. */
#define abort(M, ...)						\
	do {							\
		fprintf(stderr, "ABORT: " M, ##__VA_ARGS__);	\
		exit(1);					\
	} while(0)

#define STR_LENGTH 512

void print_help()
{
	puts(
		"Usage:\n"
		" datint [options] file          data integrity test\n\n"
		"Options:\n"
		" -h            print this menu\n"
		" -s            seed for random number gen. (default is 0)\n"
		" -m            random LBA (default is serialized)\n"
		" -r            read-only (default is read/write)\n"
		" -w            write-only (default is read/write)\n"
		" -x            random r/w (default is read/write)\n"
		" -b <number>   begining LBA (default is 0)\n"
		" -e <number>   bounding LBA (default is file size)\n"
		" -i <number>   number of test iterations (default is 1)\n"
		" -z <number>   i/o block size (multiple of default 512) \n"
	);
}

void init_params(struct param *p)
{
	p->par = NULL;
	p->ptz = 0;
	p->bkz = 0;
	p->beg = 0;
	p->end = 0;
	p->seq = &lba_serialized;
	p->wrk = &rw_serialized;
	p->itr = 1;
	p->seed = 0;
}

void init_stats(struct stats *s, const struct param * p)
{
	s->tks = 0;
	s->rtm = 0;
	s->rds = 0;
	s->wrs = 0;
	s->gen = calloc(p->ptz / p->bkz, sizeof(*s->gen));
	s->fls = 0;
}

void parse_command_line_arguments(struct param * p, int argc, char *argv[])
{
	opterr = 0;

	/* Get options. */
	while (1) {
		int c = getopt(argc, argv, "hs:mrwxb:e:i:z:");
		if (c == -1)
			break;
		switch (c) {
		case 'h':
			print_help();
			exit(0);
		case 's':
			p->seed = (uint16_t)strtoul(optarg, NULL, 0);
			if (p->seed == 0)
				abort("-s range: 1-%u\n", UINT16_MAX);
			break;
		case 'm':
			p->seq = &lba_randomized;
			break;
		case 'r':
			p->wrk = &r_only;
			break;
		case 'w':
			p->wrk = &w_only;
			break;
		case 'x':
			p->wrk = &rw_randomized;
			break;
		case 'b':
			p->beg = strtoull(optarg, NULL, 0);
			if (p->beg == 0ull)
				abort("Error reading -b argument\n");
			if (p->beg == ULLONG_MAX)
				abort("Error -b value out of range\n");
			break;
		case 'e':
			p->end = strtoull(optarg, NULL, 0);
			if (p->end == 0ull)
				abort("Error reading -e argument\n");
			if (p->end == ULLONG_MAX)
				abort("Error -e value out of range\n");
			break;
		case 'i':
			p->itr = strtoull(optarg, NULL, 0);
			if (p->itr == 0ull)
				abort("Error reading -i argument\n");
			if (p->itr == ULLONG_MAX)
				abort("Error -i value out of range\n");
			break;
		case 'z':
			p->bkz = strtoull(optarg, NULL, 0);
			if (p->bkz == 0ull)
				abort("Error reading -z argument\n");
			if (p->bkz == ULLONG_MAX)
				abort("Error -z value out of range\n");
			break;
		case '?':
			if (optopt == 's' || optopt == 'b' || optopt == 'e' ||
				optopt == 'i' || optopt == 'z')
				abort("Option -%c requires an argument\n",
					optopt);
			else if (isprint(optopt))
				abort("Unknown option -%c\n", optopt);
			else
				abort("Unknown option character \\x%x\n",
					optopt);
		default:
			fprintf(stderr, "Error parsing options\n");
			print_help();
			exit(1);
		}
	}

	/* Get partition name. */
	if (optind != argc - 1) {
		fprintf(stderr, "Missing file name\n");
		print_help();
		exit(1);
	}
	fprintf(stderr, "file %s.\n", argv[optind]);
	p->par = argv[optind];
}

uint64_t partition_size(const char *pathname)
{
	int fd = open(pathname, O_RDONLY);
	if (fd == -1)
		abort("Error opening %s\n", pathname);
	uint64_t bytes = 0;
	if (ioctl(fd, BLKGETSIZE64, &bytes) == -1)
		abort("Error getting partition size\n");
	if (close(fd) == -1)
		abort("Error closing %s\n", pathname);
	return bytes;
}

uint64_t sector_size(const char *pathname)
{
	int fd = open(pathname, O_RDONLY);
	if (fd == -1)
		abort("Error opening %s\n", pathname);
	uint64_t size;
	if (ioctl(fd, BLKSSZGET, &size) == -1)
		abort("Error getting sector size\n");
	if (close(fd) == -1)
		abort("Error closing %s\n", pathname);
	return size;
}

uint64_t pagesize()
{
	long size = sysconf(_SC_PAGESIZE);
	if (size == -1)
		abort("Error getting page size\n");
	return (uint64_t)size;
}

uint64_t rand64()
{
	uint64_t num = rand();
	return (num << 32) | rand();
}

uint64_t l_rand()
{
	char file[] = "/dev/urandom";
	int fd = open(file, O_RDONLY);
	if (fd == -1)
		abort("Error opening %s\n", file);

	uint64_t random_number;
	ssize_t read_count = read(fd, &random_number, sizeof(random_number));
	if (read_count != (ssize_t)sizeof(random_number))
		abort("Error obtaining random number\n");

	if (close(fd) == -1)
		abort("Error closing %s\n",file);

	return random_number;
}

void set_params(struct param * p)
{
	p->ptz = partition_size(p->par);

	/* Get i/o block size if not specified by user. */
	if (p->bkz == 0)
		p->bkz = sector_size(p->par);

	/* Set LBA range for i/o if not specified by user. */
	if(p->end == 0)
		p->end = p->ptz / p->bkz;

	if (p->end < p->beg)
		abort("Error end lba is smaller than beginning lba\n");

	/* Determine the sequence for random workload/LBAs. */
	srand(p->seed);

	/* Set the run id. */
	p->rid = rand64();
}

void setup(struct param * p, int argc, char *argv[])
{
	init_params(p);
	parse_command_line_arguments(p, argc, argv);
	set_params(p);
}

void fprintf_chunk(FILE *stream,
	const char *format, const struct data *chunk)
{
	char *str = malloc(STR_LENGTH);
	sprintf(str,
		"lba:%"PRIu64" gen:%"PRIu64" run id:%"PRIu64" tim:%"PRIu64,
		chunk->lba, chunk->gen, chunk->rid, chunk->tim);
	fprintf(stream, format, str);
	free(str);
}

static int chunk_cmp(const struct data *a, const struct data *b)
{
	return a->lba != b->lba || a->gen != b->gen;
}

void verify_chunk(struct stats *s,
	const struct param *p, const struct data *chunk, uint64_t lba)
{
	/* Construct expected chunk according to lba. */
	struct data test = {.lba = lba, .gen = s->gen[lba], .rid = p->rid};

	/* Verify chunk and log if fail. */
	if (chunk_cmp(chunk, &test) != 0) {
		s->fls++;
		fprintf_chunk(stdout, "Expect: %s\n", &test);
		fprintf_chunk(stdout, "Actual: %s\n", chunk);
	}
}

void write_chunk(struct stats *s, struct data *chunk, const struct param *p)
{
	/*
	 * There are a number of restrictions with direct I/O (O_DIRECT):
	 * -Data buffer must be aligned on memory boundary,
	 *  a multiple of block size.
	 * -Length of data transfers must be a multiple of block size.
	 * -Offset (lba) must be a multiple of block size.
	 */
	size_t alignment = p->bkz;
	size_t size = p->bkz;
	int origin = SEEK_SET;
	off64_t offset = chunk->lba * p->bkz;

	/* Construct aligned data buffer. */
	void *buffer = memalign(alignment, size);
	if (buffer == NULL)
		abort("Error with memory align for write\n");
	memcpy(buffer, chunk, sizeof(*chunk));
	LOG_CHUNK("writing %s\n", chunk);

	/* Write data buffer to partition. */
	int fd = open(p->par, O_WRONLY | O_DIRECT | O_DSYNC);
	if (fd == -1)
		abort("Error opening %s for write\n", p->par);
	if (lseek64(fd, offset, origin) != offset)
		abort("Error seeking write location %"PRId64"\n", offset);
	ssize_t num_written = write(fd, buffer, size);
	if (num_written == -1)
		abort("Error writing block\n");
	if (num_written != (ssize_t)size)
		abort("Error write incomplete\n");
	if (close(fd) == -1)
		abort("Error closing %s\n", p->par);
	free(buffer);

	/* Increment write counter. */
	s->wrs++;
}

void read_chunk(struct stats *s, struct data *chunk, const struct param *p)
{
	/*
	 * There are a number of restrictions with direct I/O (O_DIRECT):
	 * -Data buffer must be aligned on memory boundary,
	 *  a multiple of block size.
	 * -Length of data transfer must be a multiple of block size.
	 * -Offset must be a multiple of block size.
	 */
	size_t alignment = p->bkz;
	size_t size = p->bkz;
	int origin = SEEK_SET;
	off64_t offset = chunk->lba * p->bkz;

	/* Read aligned data block. */
	int fd = open(p->par, O_RDONLY | O_DIRECT | O_DSYNC);
	if (fd == -1)
		abort("Error opening %s for read\n", p->par);
	if (lseek64(fd, offset, origin) != offset)
		abort("Error seeking read location %"PRId64"\n", offset);
	void *buffer = memalign(alignment, size);
	ssize_t num_read = read(fd, buffer, size);
	if (num_read == -1)
		abort("Error reading block\n");
	if (num_read != (ssize_t)size)
		abort("Error read incomplete\n");
	memcpy(chunk, buffer, sizeof(*chunk));
	LOG_CHUNK("reading %s\n", chunk);
	if (close(fd) == -1)
		abort("Error closing %s\n", p->par);
	free(buffer);

	/* Increment read counter. */
	s->rds++;
}

uint64_t lba_serialized(const struct param *p)
{
	static uint64_t count = 0;
	if (count == (p->end - p->beg))
		count = 0;
	return count++ + p->beg;
}

uint64_t lba_randomized(const struct param *p)
{
	uint64_t rand_number = rand64() % (p->end - p->beg);
	return rand_number + p->beg;
}

int w_only(uint64_t *lba, iop *op, uint64_t i,
	sequence next, const struct param *p)
{
	/* For each iteration i, do (end - beg) writes. */
	static uint64_t iter = ULLONG_MAX;
	static uint64_t count = 0;
	if (iter != i) {
		count = 0;
		iter = i;
	}

	/* Check terminal condition (number of lBAs to write). */
	if (count++ == p->end - p->beg)
		return 0;

	/* The iop will always be write. */
	*op = &write_chunk;

	*lba = next(p);

	return 1;
}

int r_only(uint64_t *lba, iop *op, uint64_t i,
	sequence next, const struct param *p)
{
	/* For each iteration i, do (end - beg) writes. */
	static uint64_t iter = ULLONG_MAX;
	static uint64_t count = 0;
	if (iter != i) {
		count = 0;
		iter = i;
	}

	/* Check terminal condition (number of lBAs to read). */
	if (count++ == p->end - p->beg)
		return 0;

	/* Select iop: first iterations to recreate LBAs, last to read LBAs. */
	*op = iter == p->itr ? &read_chunk : &write_chunk;

	*lba = next(p);

	return 1;
}

int rw_serialized(uint64_t *lba, iop *op, uint64_t i,
	sequence next, const struct param *p)
{
	/* For each iteration i, do (end - beg) writes and reads. */
	static uint64_t iter = ULLONG_MAX;
	static uint64_t count = 0;
	if (iter != i) {
		count = 0;
		iter = i;
	}

	/* Check terminal condition (number of lBAs to read/write). */
	if (count == (p->end - p->beg) * 2)
		return 0;

	/* Select iop: first pass, writes, second pass, reads. */
	if (count++ < p->end - p->beg)
		*op = &write_chunk;
	else
		*op = &read_chunk;

	*lba = next(p);

	return 1;
}

int rw_randomized(uint64_t *lba, iop *op, uint64_t i,
	sequence next, const struct param *p)
{
	/* For each iteration i, do (end - beg) writes and reads. */
	static uint64_t iter = ULLONG_MAX;
	static uint64_t count = 0;
	if (iter != i) {
		count = 0;
		iter = i;
	}

	/* Check terminal condition (number of lBAs to read/write). */
	if (count++ == (p->end - p->beg) * 2)
		return 0;

	/* Select iop uniformly at random. */
	*op = rand64() % 2 ? &read_chunk : &write_chunk;

	*lba = next(p);

	return 1;
}

void print_parameters(FILE *stream, const struct param *p)
{
	fprintf(stream, "     partition=%s\n", p->par);
	fprintf(stream, "partition_size=%"PRIu64"\n", p->ptz);
	fprintf(stream, "i/o block_size=%"PRIu64"\n", p->bkz);
	char str[STR_LENGTH];
	if (p->wrk == &r_only)
		strcpy(str, "read-only");
	else if (p->wrk == &w_only)
		strcpy(str, "write-only");
	else if (p->wrk == &rw_serialized)
		strcpy(str, "serialized read-write");
	else if (p->wrk == &rw_randomized)
		strcpy(str, "randomized read/write");
	else
		abort("Unexpected workload error\n");
	fprintf(stream, "      workload=%s\n", str);
	if (p->seq == &lba_serialized)
		strcpy(str, "serialized LBAs");
	else if (p->seq == &lba_randomized)
		strcpy(str, "randomized LBAs");
	else
		abort("Unexpected sequence error\n");
	fprintf(stream, "      sequence=%s\n", str);
	fprintf(stream, "     LBA_range=%"PRIu64
		"-%"PRIu64"\n", p->beg, p->end - 1);
	fprintf(stream, "    iterations=%"PRIu64"\n", p->itr);
	fprintf(stream, "        run_id=%"PRIu64"\n", p->rid);
	fprintf(stream, "          seed=%u\n", p->seed);
}

void print_results(FILE *stream, const struct stats *s)
{
	fprintf(stream, "iops=%"PRIu64
		" reads=%"PRIu64" writes=%"PRIu64" failed=%"PRIu64"\n",
		s->rds + s->wrs, s->rds, s->wrs, s->fls);
	fprintf(stream,
		"cpu clicks=%lu (%f seconds) overall=%lu seconds\n",
		s->tks, (float)s->tks / CLOCKS_PER_SEC, s->rtm);
}

void do_workload(struct stats *s, const struct param *p, uint64_t i)
{
	iop op;
	uint64_t lba;
	while ((*p->wrk)(&lba, &op, i, p->seq, p)) {
		/*
		 * Verify:
		 * If doing random LBAs, skip previously unwritten lbas.
		 */
		if (p->wrk == &r_only &&
			op == &read_chunk && s->gen[lba] == 0)
			continue;

		/* 
		 * Normal:
		 * If reading previously unwritten lba, switch to write.
		 */
		if (p->wrk != &r_only && op == &read_chunk &&
			s->gen[lba] == 0)
			op = &write_chunk;

		/*
		 * Create data chunk, either for writing or reading.
		 * If for reading, the lba detemines which location
		 * on disk to read, then it gets overwritten by the
		 * actual contents on disk.
		 */
		if (op == &write_chunk)
			++s->gen[lba]; /* Increment gen for write. */
		struct data chunk =
			{lba, s->gen[lba], time(NULL), p->rid};

		/*
		 * Verify:
		 * Iterations simulate writes to compute the
		 * generations, but not really write the blocks.
		 * One additional iteration is used to read the blocks.
		 */
		if (p->wrk == &r_only && op == &write_chunk)
			continue;

		/*  Perform iop. */
		op(s, &chunk, p);

		/* Check data integrity/retention. */
		if (op == &read_chunk)
			verify_chunk(s, p, &chunk, lba);
	}
}

void execute(const struct param *p)
{
	struct stats *s = malloc(sizeof(*s));
	init_stats(s, p);

	print_parameters(stdout, p);

	s->rtm = time(NULL);
	s->tks = clock();

	/*
	 * If read-only workload,
	 * iterations are used to recreate LBAs,
	 * then one additional iteration to verify.
	 */
	uint64_t iterations = p->itr;
	if (p->wrk == &r_only)
		iterations = p->itr + 1;

	/* Perform itertions of workload. */
	uint64_t i;
	for (i = 0; i < iterations; i++)
		do_workload(s, p, i);

	s->tks = clock() - s->tks;
	s->rtm = time(NULL) - s->rtm;

	print_results(stdout, s);
}

int main(int argc, char *argv[])
{
	struct param *p = malloc(sizeof(*p));
	setup(p, argc, argv);

	execute(p);

	return 0;
}
