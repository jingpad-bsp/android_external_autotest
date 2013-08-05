/* Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
 * Use of this source code is governed by a BSD-style license that can be
 * found in the LICENSE file.
 */

/* Interface for data integrity tester. Refer to the README file for details. */

#ifndef DATINT_H_
#define DATINT_H_

#include <stdio.h>
#include <sys/types.h>
#include <inttypes.h>

#ifdef __cplusplus
extern "C" {
#endif

struct param;
struct data;
struct stats;

/* Sequencing Functions: */
typedef uint64_t (*sequence)(const struct param *);
uint64_t lba_serialized(const struct param *p);
uint64_t lba_randomized(const struct param *p);

/* I/O Functions: */
typedef void (*iop)(struct stats *, struct data *, const struct param *);
void write_chunk(struct stats *s, struct data *chunk, const struct param *p);
void read_chunk(struct stats *s, struct data *chunk, const struct param *p);

/* Workflow Functions */
typedef int (*workload)(uint64_t *, iop *, uint64_t,
	sequence, const struct param *);
int w_only(uint64_t *lba, iop *op, uint64_t i,
	sequence, const struct param *p);
int r_only(uint64_t *lba, iop *op, uint64_t i,
	sequence, const struct param *p);
int rw_serialized(uint64_t *lba, iop *op, uint64_t i,
	sequence, const struct param *p);
int rw_randomized(uint64_t *lba, iop *op, uint64_t i,
	sequence, const struct param *p);

/* Data Chunk used in Data Integrity Test: */
struct data
{
	uint64_t lba;	/* logical block address */
	uint64_t gen;	/* generation number: number of times lba is written */
	uint64_t tim;	/* generation timestamp: number seconds since 1970 */
	uint64_t rid;	/* test run identification number */
};

/* Test Parameters: */
struct param
{
	char *par;	/* partition name */
	uint64_t rid;	/* unique test number (included in each data chunk) */
	uint16_t seed;	/* seed for random number generator */
	uint64_t ptz;	/* partition size */
	sequence seq;	/* LBA sequence: random; sequential */
	workload wrk;	/* workload: read; write; serial r-w; shuffled r/w */
	uint64_t beg;	/* beginning LBA */
	uint64_t end;	/* ending LBA */
	uint64_t itr;	/* number of iterations to test */
	uint64_t bkz;	/* i/o block size */
};

/* Run data. */
struct stats
{
	clock_t tks;	/* program cpu clock ticks */
	time_t rtm;	/* program runtime */
	uint64_t rds;	/* total number of reads performed */
	uint64_t wrs;	/* total number of writes performed */
	uint64_t *gen;	/* last generation number for each lba */
	uint64_t fls;	/* number of failed verifications */
};

void execute(const struct param *p);

#ifdef __cplusplus
}  /* extern "C" */
#endif

#endif  /* DATINT_H_ */
