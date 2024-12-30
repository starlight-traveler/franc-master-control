#!/usr/bin/env python3

import sys
import configparser
import logging
from pathlib import Path
import numpy as np
import subprocess

'''
##################
General Imports
##################
'''

# General
from src.modulator import parse_bitstream

# HackRF
from src.transmission import transmit_hackrf

# APRS
from src.modulator import aprs_encode

# GFSK
from src.gfsk.dsp import gfsk_modulate, modulate as gfsk_modulate_func
from src.modulator import gfsk_modulator

# SimpleFM
from src.simplefm.dsp import voice_fm_encode

# Voice
from src.voice.dsp import voice_modulate
from src.voice.tts import text_to_speech
from src.qpsk.dsp import qpsk_modulator


'''
##################
Main
##################
'''

def main():
    config_path = 'config.cfg'

    # Check if configuration file exists
    if not Path(config_path).is_file():
        sys.stderr.write(f"Configuration file '{config_path}' does not exist.\n")
        sys.exit(1)

    # Load configuration
    config = configparser.ConfigParser()
    try:
        config.read(config_path)
    except configparser.Error as e:
        sys.stderr.write(f"Error parsing configuration file: {e}\n")
        sys.exit(1)

    # Retrieve general settings
    if 'general' not in config:
        sys.stderr.write("Missing [general] section in the configuration file.\n")
        sys.exit(1)

    general = config['general']
    modulation = general.get('modulation', 'gfsk').lower()
    data = general.get('data', '')
    output = general.get('output', 'stdout')
    output_format = general.get('format', 'f32')
    debug = general.getboolean('debug', False)

    # Setup logging
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=log_level, format='%(message)s')
    global logger
    logger = logging.getLogger(__name__)

    if not data:
        logger.error("No data specified in the 'general' section of the configuration file.")
        sys.exit(1)

    # Load HackRF configuration if output is 'hackrf'
    hackrf_config = {}
    if output.lower() == 'hackrf':
        if 'hackrf' not in config:
            logger.error("Missing [hackrf] section in the configuration file.")
            sys.exit(1)
        hackrf_params = config['hackrf']
        hackrf_config = {
            'frequency': hackrf_params.get('frequency', '144800000'),
            'sample_rate': hackrf_params.get('sample_rate', '2400000'),  # typical HackRF rate
            'txvga_gain': hackrf_params.get('txvga_gain', '20'),
            'txamp_enable': hackrf_params.get('txamp_enable', 'True')
        }

    ################
    # GFSK
    ################
    if modulation == 'gfsk':
        # Ensure [gfsk] section exists
        if 'gfsk' not in config:
            logger.error("Missing [gfsk] section in the configuration file.")
            sys.exit(1)
        gfsk_params = config['gfsk']
        gfsk_config = {
            'baud_rate': gfsk_params.get('baud_rate', '1200'),
            'sample_rate': gfsk_params.get('sample_rate', '48000'),
            'freq_deviation': gfsk_params.get('freq_deviation', '750.0'),
            'bt': gfsk_params.get('bt', '0.3'),
            'format': output_format,
            'output': output,
            'debug': debug
        }
        # Merge HackRF config if applicable
        if hackrf_config:
            gfsk_config.update(hackrf_config)
        gfsk_modulator(data, gfsk_config)
    
    ################
    # APRS
    ################
    elif modulation == 'aprs':
        # Build aprs_config from your config parser:
        aprs_params = config['aprs']
        aprs_config = {
            'callsign':    aprs_params.get('callsign', 'NOCALL'),
            'destination': aprs_params.get('destination', 'APRS'),
            'path':        aprs_params.get('path', 'WIDE1-1,WIDE2-1'),
            'format':      output_format,
            'output':      output,
            'debug':       debug
        }
        # If you're using HackRF:
        if output.lower() == 'hackrf':
            aprs_config.update({
                'frequency':    float(hackrf_params.get('frequency', '144800000')),
                'sample_rate':  float(hackrf_params.get('sample_rate', '2400000')),
                'txvga_gain':   int(hackrf_params.get('txvga_gain', '20')),
                'txamp_enable': hackrf_params.get('txamp_enable', 'True')
            })

        # Call aprs_encode
        aprs_encode(data, aprs_config)
        
    ################
    # FM
    ################
    elif modulation == 'fm':
        # FM
        fm_params = config['fm'] if 'fm' in config else {}
        fm_cfg = {
            'sample_rate': fm_params.get('sample_rate', '240000'),
            'freq_deviation': fm_params.get('freq_deviation', '5000'),
            'format': output_format,
            'output': output,
            'debug': debug
        }
        
        # Merge with hackrf if needed
        if hackrf_config:
            fm_cfg.update(hackrf_config)
        
        voice_fm_encode(
            data=data,
            config=fm_cfg,
            transmit_function=transmit_hackrf if output.lower() == 'hackrf' else None
        )
        
    ################
    # Voice
    ################    
    elif modulation == 'voice':
        if 'voice' not in config:
            logger.error("Missing [voice] section in the configuration file for voice modulation.")
            sys.exit(1)
        voice_cfg = config['voice']
        audio_file = voice_cfg.get('audio_file', 'voice.wav')  # Output WAV file

        # Generate WAV from text
        logger.info("[Voice] Converting text to speech...")
        text_to_speech(
            text=data,
            wav_filename=audio_file,
            sample_rate=int(voice_cfg.get('sample_rate', '16000')),
            volume=float(voice_cfg.get('volume', '1.0'))
        )

        # Prepare FM modulation config
        fm_config = {
            'sample_rate': voice_cfg.get('sample_rate', '240000'),
            'freq_deviation': voice_cfg.get('freq_deviation', '5000'),
            'output': output,
            'format': output_format
        }
        
        # Perform FM modulation and transmit/save
        voice_modulate(
            wav_filename=audio_file,
            config=fm_config,
            transmit_function=transmit_hackrf if output.lower() == 'hackrf' else None
        )
    ################
    # QPSK
    ################     
    elif modulation == 'qpsk':
        # Ensure we have a [qpsk] section or handle defaults
        if 'qpsk' in config:
            qpsk_sec = config['qpsk']
        else:
            qpsk_sec = {}
        # Prepare QPSK config
        qpsk_cfg = {
            'samples_per_symbol': qpsk_sec.get('samples_per_symbol', '4'),
            'output': output,
            'format': output_format,
            'debug': debug
        }
        if hackrf_config:
            qpsk_cfg.update(hackrf_config)

        qpsk_modulator(
            input_source=data,
            config=qpsk_cfg,
            parse_bitstream_func=parse_bitstream,
            transmit_func=transmit_hackrf if output.lower() == 'hackrf' else None
        )
            
    else:
        logger.error(f"Unsupported modulation scheme: '{modulation}'.")
        sys.exit(1)

if __name__ == "__main__":
    main()
