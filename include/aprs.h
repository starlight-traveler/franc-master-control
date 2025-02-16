#pragma once

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <unistd.h>
#include <cstdint>
#include <climits>
#include "ax25.h"
#include "dsp.h"

typedef enum
{
    IQ_S8,
    IQ_F32,
    PCM_F32,
} OutputFormat;

void usage();
std::vector<int8_t> f32_to_s8(const std::vector<std::complex<float>> &input);
void modulate(const std::vector<float> &waveform, FILE *fout, OutputFormat iq_sf);

extern "C" {
    int8_t *gen_iq_s8(const char *callsign, const char *user_path, const char *info, int32_t *total);
}