#!/usr/bin/env python3

import pyttsx3
import wave
import sys
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def text_to_speech(text: str, wav_filename: str, sample_rate: int = 16000, volume: float = 1.0):
    """
    Convert a given text string to a WAV file using TTS.

    :param text: The input string to convert to speech.
    :param wav_filename: The output WAV file path.
    :param sample_rate: The sample rate for the output WAV file.
    :param volume: Volume level (0.0 to 1.0).
    """
    engine = pyttsx3.init()
    
    # Set properties
    engine.setProperty('rate', 150)      # Speech rate
    engine.setProperty('volume', volume) # Volume (0.0 to 1.0)
    
    # Save the speech to a temporary WAV file
    temp_wav = "temp_voice.wav"
    try:
        engine.save_to_file(text, temp_wav)
        engine.runAndWait()
    except Exception as e:
        logger.error(f"[TTS] Error during TTS conversion: {e}")
        sys.exit(1)
    
    # Read the temporary WAV and resample if necessary
    try:
        with wave.open(temp_wav, 'rb') as wf:
            channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            nframes = wf.getnframes()
            audio_data = wf.readframes(nframes)
    except Exception as e:
        logger.error(f"[TTS] Cannot read temporary WAV file '{temp_wav}': {e}")
        sys.exit(1)

    # Save to the desired WAV file
    try:
        with wave.open(wav_filename, 'wb') as wf_out:
            wf_out.setnchannels(channels)
            wf_out.setsampwidth(sampwidth)
            wf_out.setframerate(sample_rate)
            wf_out.writeframes(audio_data)
    except Exception as e:
        logger.error(f"[TTS] Cannot write to WAV file '{wav_filename}': {e}")
        sys.exit(1)
    
    # Remove the temporary WAV file
    Path(temp_wav).unlink(missing_ok=True)
    
    logger.info(f"[TTS] Successfully generated WAV file '{wav_filename}'.")
