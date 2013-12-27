/* Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
 * Use of this source code is governed by a BSD-style license that can be
 * found in the LICENSE file.
 */

#include <stdio.h>
#include <alsa/asoundlib.h>

int main(int argc, char *argv[])
{
	const char *alsa_dev;
	snd_pcm_stream_t direction;
	snd_pcm_t *pcm;
	snd_pcm_hw_params_t *hw_params;
	unsigned i;
	unsigned channels;
	int ret = 0;

	static const unsigned rates[] = {
		4000,
		8000,
		32000,
		44100,
		48000,
		96000,
		192000,
		0
	};

	static const snd_pcm_format_t formats[] = {
		SND_PCM_FORMAT_S8,
		SND_PCM_FORMAT_S16_LE,
		SND_PCM_FORMAT_S24_LE,
		SND_PCM_FORMAT_S32_LE,
		SND_PCM_FORMAT_UNKNOWN
	};

	if (argc < 3) {
		fprintf(stderr, "Usage: %s device [playback|capture]\n",
			argv[0]);
		return 1;
	}

	alsa_dev = argv[1];
	if (strcmp(argv[2], "capture") == 0)
		direction = SND_PCM_STREAM_CAPTURE;
	else
		direction = SND_PCM_STREAM_PLAYBACK;

	ret = snd_pcm_open(&pcm, alsa_dev, direction, SND_PCM_NONBLOCK);
	if (ret < 0) {
		fprintf(stderr, "can't open device\n");
		return 1;
	}

	snd_pcm_hw_params_alloca(&hw_params);
	ret = snd_pcm_hw_params_any(pcm, hw_params);
	if (ret < 0) {
		fprintf(stderr, "can't get hardware params\n");
		goto exit_close;
	}

	printf("Formats:");
	for (i = 0; formats[i] != SND_PCM_FORMAT_UNKNOWN; ++i) {
		if (!snd_pcm_hw_params_test_format(pcm, hw_params, formats[i]))
			printf(" %s", snd_pcm_format_name(formats[i]));
	}
	printf("\n");

	ret = snd_pcm_hw_params_get_channels_max(hw_params, &channels);
	if (ret < 0) {
		fprintf(stderr, "can't get channels count\n");
		goto exit_close;
	}
	printf("Channels: %u\n", channels);

	printf("Rates:");
	for (i = 0; rates[i] != 0; ++i) {
		int err = snd_pcm_hw_params_test_rate(pcm, hw_params,
						      rates[i], 0);
		if (err == 0)
			printf(" %u", rates[i]);
	}
	printf("\n");

exit_close:
	snd_pcm_close(pcm);
	return ret;
}
