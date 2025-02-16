#include "aprs.h"

void usage()
{
    fprintf(stderr, "Usage: aprs -c <callsign> [-d <destination>] [-p <path>] [-o <output>] [-f <format>] <message>\n"
                    "   -c callsign    - your callsign\n"
                    "   -d destination - AX.25 destination address (default 'APRS')\n"
                    "   -p path        - Digipeater path to use (default 'WIDE1-1,WIDE2-1')\n"
                    "   -o output      - output file (default stdout)\n"
                    "   -f format      - output format: f32(default), s8(HackRF), pcm\n"
                    "   -v             - print debug info\n");
    exit(1);
}

std::vector<int8_t> f32_to_s8(const std::vector<std::complex<float>> &input)
{
    std::vector<int8_t> result(input.size() * 2);
    for (int i = 0; i < (int)input.size(); i++)
    {
        result[i * 2] = input[i].real() * SCHAR_MAX;
        result[i * 2 + 1] = input[i].imag() * SCHAR_MAX;
    }
    return result;
}

// FM modulation + interpolation (x50)
// output sample rate: 48000 * 50 = 2400000
void modulate(const std::vector<float> &waveform, FILE *fout, OutputFormat iq_sf)
{
    float max_deviation = 5000; // 5kHz deviation
    float sensitivity = 2 * M_PI * max_deviation / (float)AUDIO_SAMPLE_RATE;
    float factor = 50.0;
    float fractional_bw = 0.4;
    float halfband = 0.5;
    float trans_width = halfband - fractional_bw;
    float mid_transition_band = halfband - trans_width / 2.0;
    std::vector<float> taps = lowpass(factor, factor, mid_transition_band, trans_width);

    Ringbuffer_t mod_buf;
    FIRInterpolator interp(factor, taps);
    float last_phase = 0;
    int offset = 0;
    while (offset < (int)waveform.size())
    {
        int input_size = std::min(BUFSIZE, (int)waveform.size() - offset);
        last_phase = fmmod(waveform.data() + offset, input_size, mod_buf, sensitivity, last_phase);

        std::vector<std::complex<float>> interp_buf;
        int processed = interp.interpolate(mod_buf, interp_buf);
        if (!processed)
        {
            break;
        }
        mod_buf.remove(processed);
        if (iq_sf == IQ_S8)
        {
            auto samples_s8 = f32_to_s8(interp_buf);
            fwrite(samples_s8.data(), sizeof(int8_t), samples_s8.size(), fout);
        }
        else
        {
            fwrite(interp_buf.data(), sizeof(std::complex<float>), interp_buf.size(), fout);
        }
        offset += input_size;
    }
}

extern "C"
{
    int8_t *gen_iq_s8(const char *callsign, const char *user_path, const char *info, int32_t *total)
    {
        const char *dest = "APRS";
        char path[64];
        strncpy(path, user_path, 63);

        auto frame = ax25frame(callsign, dest, path, info, false);
        auto frame_nrzi = nrzi(frame);
        auto wave = afsk(frame_nrzi);

        // interpolation factor is 50 and each sample is 2 bytes
        *total = wave.size() * 50 * 2;
        int8_t *samples = (int8_t *)malloc(*total);
        if (!samples)
        {
            return 0;
        }
        FILE *f = fmemopen(samples, *total, "wb");
        modulate(wave, f, IQ_S8);
        fclose(f);
        return samples;
    }
}