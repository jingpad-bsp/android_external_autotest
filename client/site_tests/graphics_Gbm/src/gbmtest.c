/*
 * Copyright 2014 The Chromium OS Authors. All rights reserved.
 * Use of this source code is governed by a BSD-style license that can be
 * found in the LICENSE file.
 */

#include <fcntl.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>

#include <gbm.h>

#define CHECK(cond) do {\
	if (!(cond)) {\
		printf("CHECK failed in %s() %s:%d\n", __func__, __FILE__, __LINE__);\
		return 0;\
	}\
} while(0)

#define ARRAY_SIZE(A) (sizeof(A)/sizeof(*(A)))

static int fd;
static struct gbm_device *gbm;

static const uint32_t format_list[] = {
	GBM_BO_FORMAT_XRGB8888,
	GBM_BO_FORMAT_ARGB8888,
	GBM_FORMAT_C8,
	GBM_FORMAT_RGB332,
	GBM_FORMAT_BGR233,
	GBM_FORMAT_XRGB4444,
	GBM_FORMAT_XBGR4444,
	GBM_FORMAT_RGBX4444,
	GBM_FORMAT_BGRX4444,
	GBM_FORMAT_ARGB4444,
	GBM_FORMAT_ABGR4444,
	GBM_FORMAT_RGBA4444,
	GBM_FORMAT_BGRA4444,
	GBM_FORMAT_XRGB1555,
	GBM_FORMAT_XBGR1555,
	GBM_FORMAT_RGBX5551,
	GBM_FORMAT_BGRX5551,
	GBM_FORMAT_ARGB1555,
	GBM_FORMAT_ABGR1555,
	GBM_FORMAT_RGBA5551,
	GBM_FORMAT_BGRA5551,
	GBM_FORMAT_RGB565,
	GBM_FORMAT_BGR565,
	GBM_FORMAT_RGB888,
	GBM_FORMAT_BGR888,
	GBM_FORMAT_XRGB8888,
	GBM_FORMAT_XBGR8888,
	GBM_FORMAT_RGBX8888,
	GBM_FORMAT_BGRX8888,
	GBM_FORMAT_ARGB8888,
	GBM_FORMAT_ABGR8888,
	GBM_FORMAT_RGBA8888,
	GBM_FORMAT_BGRA8888,
	GBM_FORMAT_XRGB2101010,
	GBM_FORMAT_XBGR2101010,
	GBM_FORMAT_RGBX1010102,
	GBM_FORMAT_BGRX1010102,
	GBM_FORMAT_ARGB2101010,
	GBM_FORMAT_ABGR2101010,
	GBM_FORMAT_RGBA1010102,
	GBM_FORMAT_BGRA1010102,
	GBM_FORMAT_YUYV,
	GBM_FORMAT_YVYU,
	GBM_FORMAT_UYVY,
	GBM_FORMAT_VYUY,
	GBM_FORMAT_AYUV,
};

static const uint32_t usage_list[] = {
	GBM_BO_USE_SCANOUT,
	GBM_BO_USE_CURSOR_64X64,
	GBM_BO_USE_RENDERING,
	GBM_BO_USE_WRITE,
};

static int check_bo(struct gbm_bo *bo)
{
	CHECK(bo);
	CHECK(gbm_bo_get_width(bo) >= 0);
	CHECK(gbm_bo_get_height(bo) >= 0);
	CHECK(gbm_bo_get_stride(bo) >= gbm_bo_get_width(bo));
	CHECK(gbm_bo_get_fd(bo) == fd);

	return 1;
}

/*
 * Tests initialization.
 */
static int test_init()
{
	fd = open("/dev/dri/card0", O_RDWR);
	CHECK(fd >= 0);

	gbm = gbm_create_device(fd);

	CHECK(gbm_device_get_fd(gbm) == fd);

	const char* backend_name = gbm_device_get_backend_name(gbm);

	CHECK(backend_name);

	return 1;
}

/*
 * Tests reinitialization.
 */
static int test_reinit()
{
	gbm_device_destroy(gbm);
	close(fd);

	fd = open("/dev/dri/card0", O_RDWR);
	CHECK(fd >= 0);

	gbm = gbm_create_device(fd);

	CHECK(gbm_device_get_fd(gbm) == fd);

	struct gbm_bo *bo;
	bo = gbm_bo_create(gbm, 1024, 1024, GBM_FORMAT_XRGB8888, GBM_BO_USE_RENDERING);
	CHECK(check_bo(bo));
	gbm_bo_destroy(bo);

	return 1;
}

/*
 * Tests repeated alloc/free.
 */
static int test_alloc_free()
{
	int i;
	for(i = 0; i < 1000; i++) {
		struct gbm_bo *bo;
		bo = gbm_bo_create(gbm, 1024, 1024, GBM_FORMAT_XRGB8888, GBM_BO_USE_RENDERING);
		CHECK(check_bo(bo));
		gbm_bo_destroy(bo);
	}
	return 1;
}

/*
 * Tests that we can allocate different buffer dimensions.
 */
static int test_alloc_free_sizes()
{
	int i;
	for(i = 1; i < 1920; i++) {
		struct gbm_bo *bo;
		bo = gbm_bo_create(gbm, i, i, GBM_FORMAT_XRGB8888, GBM_BO_USE_RENDERING);
		CHECK(check_bo(bo));
		gbm_bo_destroy(bo);
	}

	for(i = 1; i < 1920; i++) {
		struct gbm_bo *bo;
		bo = gbm_bo_create(gbm, i, 1, GBM_FORMAT_XRGB8888, GBM_BO_USE_RENDERING);
		CHECK(check_bo(bo));
		gbm_bo_destroy(bo);
	}

	for(i = 1; i < 1920; i++) {
		struct gbm_bo *bo;
		bo = gbm_bo_create(gbm, 1, i, GBM_FORMAT_XRGB8888, GBM_BO_USE_RENDERING);
		CHECK(check_bo(bo));
		gbm_bo_destroy(bo);
	}

	return 1;
}

/*
 * Tests that we can allocate different buffer formats.
 */
static int test_alloc_free_formats()
{
	int i;

	for(i = 0; i < ARRAY_SIZE(format_list); i++) {
		uint32_t format = format_list[i];
		if (gbm_device_is_format_supported(gbm, format, GBM_BO_USE_RENDERING)) {
			struct gbm_bo *bo;
			bo = gbm_bo_create(gbm, 1024, 1024, format, GBM_BO_USE_RENDERING);
			CHECK(check_bo(bo));
		}
	}

	return 1;
}

/*
 * Tests that we find at least one working format for each usage.
 */
static int test_alloc_free_usage()
{
	int i, j;

	for(i = 0; i < ARRAY_SIZE(usage_list); i++) {
		uint32_t usage = usage_list[i];
		int found = 0;
		for(j = 0; j < ARRAY_SIZE(format_list); j++) {
			uint32_t format = format_list[j];
			if (gbm_device_is_format_supported(gbm, format, usage)) {
				struct gbm_bo *bo;
				bo = gbm_bo_create(gbm, 1024, 1024, format, usage);
				CHECK(check_bo(bo));
				found = 1;
			}
		}
		CHECK(found);
	}

	return 1;
}

/*
 * Tests user data.
 */
static int been_there1;
static int been_there2;

void destroy_data1(struct gbm_bo *bo, void *data)
{
	been_there1 = 1;
}

void destroy_data2(struct gbm_bo *bo, void *data)
{
	been_there2 = 1;
}

static int test_user_data()
{
	struct gbm_bo *bo1, *bo2;
	char *data1, *data2;

	been_there1 = 0;
	been_there2 = 0;

	bo1 = gbm_bo_create(gbm, 1024, 1024, GBM_FORMAT_XRGB8888, GBM_BO_USE_RENDERING);
	bo2 = gbm_bo_create(gbm, 1024, 1024, GBM_FORMAT_XRGB8888, GBM_BO_USE_RENDERING);
	data1 = (char*)malloc(1);
	data2 = (char*)malloc(1);
	CHECK(data1);
	CHECK(data2);

	gbm_bo_set_user_data(bo1, data1, destroy_data1);
	gbm_bo_set_user_data(bo2, data2, destroy_data2);

	CHECK((char*)gbm_bo_get_user_data(bo1) == data1);
	CHECK((char*)gbm_bo_get_user_data(bo2) == data2);

	gbm_bo_destroy(bo1);
	CHECK(been_there1 == 1);

	gbm_bo_set_user_data(bo2, NULL, NULL);
	gbm_bo_destroy(bo2);
	CHECK(been_there2 == 0);

	free(data1);
	free(data2);

	return 1;
}

/*
 * Tests destruction.
 */
static int test_destroy()
{
	gbm_device_destroy(gbm);
	close(fd);

	return 1;
}

int main(int argc, char *argv[])
{
	int result = 1;

	result &= test_init();
	result &= test_reinit();
	result &= test_alloc_free();
	result &= test_alloc_free_sizes();
	result &= test_alloc_free_formats();
	result &= test_alloc_free_usage();
	result &= test_user_data();
	result &= test_destroy();

	if (!result) {
		printf("[  FAILED  ] graphics_Gbm test failed\n");
		return EXIT_FAILURE;
	} else {
		printf("[  PASSED  ] graphics_Gbm test success\n");
		return EXIT_SUCCESS;
	}
}

