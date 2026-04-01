#!/usr/bin/env python3

import argparse
import pyttsx3
import tempfile
from pydub import AudioSegment
import os

def list_voices():
	engine = pyttsx3.init()
	voices = engine.getProperty('voices')
	for idx, voice in enumerate(voices):
		print(f"{idx}: {voice.name} ({voice.languages}) - {voice.id}")

def get_default_voice_idx():
	engine = pyttsx3.init()
	voices = engine.getProperty('voices')
	if len(voices) > 1:
		return 1	# Use second voice if available (almost always different)
	return 0		# Otherwise, fallback to default

def generate_tts(text, voice_idx, out_wav):
	engine = pyttsx3.init()
	voices = engine.getProperty('voices')
	if voice_idx is not None and 0 <= voice_idx < len(voices):
		engine.setProperty('voice', voices[voice_idx].id)
	engine.save_to_file(text, out_wav)
	engine.runAndWait()

def shorten_audio(input_wav, output_mp3, target_seconds=None):
	audio = AudioSegment.from_file(input_wav)
	if target_seconds:
		current_length = len(audio) / 1000
		if current_length > target_seconds:
			factor = current_length / target_seconds
			audio = audio.speedup(playback_speed=factor)
	audio.export(output_mp3, format="mp3")

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="Generate MP3 from text using a non-Google voice and optionally limit duration.")
	parser.add_argument('-m', '--message', required=True, help='Text message to convert to speech.')
	parser.add_argument('-s', '--seconds', type=float, help='Maximum duration of the MP3 file in seconds.')
	parser.add_argument('-v', '--voice', type=int, help='Voice index to use (see --list-voices).')
	parser.add_argument('--list-voices', action='store_true', help='List available voices and exit.')
	parser.add_argument('-o', '--output', default='output.mp3', help='Output mp3 filename.')
	args = parser.parse_args()

	if args.list_voices:
		list_voices()
		exit(0)

	voice_idx = args.voice if args.voice is not None else get_default_voice_idx()

	with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tf:
		tmp_wav = tf.name

	try:
		generate_tts(args.message, voice_idx, tmp_wav)
		shorten_audio(tmp_wav, args.output, args.seconds)
	finally:
		if os.path.exists(tmp_wav):
			os.remove(tmp_wav)

