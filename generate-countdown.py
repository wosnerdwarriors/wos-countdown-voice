#!/usr/bin/env python3

import argparse
from gtts import gTTS
from gtts.lang import tts_langs
from pydub import AudioSegment
import os

# Configuration options
debug = False  # Enable debug mode to print additional information
def generate_countdown(start_num, end_num, output_file, language, reuse_cache, verify_final_file):
	countdown_audio = AudioSegment.silent(duration=0)  # Initialize empty audio segment

	# Create tmp-data directory if it doesn't exist
	if not os.path.exists("tmp-data"):
		os.makedirs("tmp-data")
		if debug: print("Created directory: tmp-data")

	# Preload all file paths and load audio into memory
	round1_files = {i: f"tmp-data/countdown-{start_num}-{end_num}-round1_{i}.mp3" for i in range(start_num, end_num - 1, -1)}
	round2_files = {i: f"tmp-data/countdown-{start_num}-{end_num}-round2_{i}.mp3" for i in range(start_num, end_num - 1, -1)}
	audio_segments = {}

	# Step 1: Check for existing round 2 files first
	durations = []
	for i in range(start_num, end_num - 1, -1):
		if reuse_cache and os.path.exists(round2_files[i]):
			if debug: print(f"Reusing cached adjusted file: {round2_files[i]}")
			audio_segments[i] = AudioSegment.from_mp3(round2_files[i])
		else:
			if reuse_cache and os.path.exists(round1_files[i]):
				if debug: print(f"Reusing cached file: {round1_files[i]}")
			else:
				if debug: print(f"Generating speech for number {i} with language '{language}'")
				tts = gTTS(text=str(i), lang=language)
				tts.save(round1_files[i])

			audio_segments[i] = AudioSegment.from_mp3(round1_files[i])
			duration = len(audio_segments[i])
			durations.append(duration)
			if debug: print(f"Number {i}: Speech duration: {duration}ms")

	# Step 2: Determine the longest duration and calculate the required speed factor
	max_duration = max(durations)
	speed_factor = max_duration / 1000  # Use 1 second as the interval
	if debug: print(f"Maximum duration among all numbers: {max_duration}ms, Speed factor: {speed_factor:.2f}")

	# Step 3: Adjust speed and pad to exactly fit 1 second for all numbers
	for i in range(start_num, end_num - 1, -1):
		if reuse_cache and os.path.exists(round2_files[i]):
			if debug: print(f"Reusing cached adjusted file: {round2_files[i]}")
		else:
			audio_segments[i] = audio_segments[i].speedup(playback_speed=speed_factor)
			if debug: print(f"Number {i}: Adjusted speed with factor {speed_factor:.2f}")

			duration = len(audio_segments[i])
			if duration < 1000:
				silence_duration = 1000 - duration
				audio_segments[i] += AudioSegment.silent(duration=silence_duration)
				if debug: print(f"Number {i}: Padding with {silence_duration}ms of silence")

			audio_segments[i].export(round2_files[i], format="mp3")
			if debug: print(f"Number {i}: Saved adjusted audio as {round2_files[i]}")

		countdown_audio += audio_segments[i]

	# Step 4: Export the final countdown audio to mp3 with proper naming
	countdown_audio.export(output_file, format="mp3")
	print(f"Final countdown saved as {output_file}")

	# Step 5: Verify final file length
	expected_length = (start_num - end_num + 1) * 1000
	final_length = len(countdown_audio)
	if verify_final_file or debug:
		if debug or abs(final_length - expected_length) > 1:
			print(f"Warning: Expected length {expected_length}ms, but got {final_length}ms")
			if not debug:
				exit(1)

	# Step 6: Cleanup temporary files if debug is False and reuse_cache is not set
	if not debug and not reuse_cache:
		for i in range(start_num, end_num - 1, -1):
			os.remove(round1_files[i])
			os.remove(round2_files[i])

if __name__ == "__main__":
	# Fetch supported languages for help text
	languages = tts_langs()
	language_help_text = "\nSupported languages:\n" + "\n".join([f"{code}: {name}" for code, name in languages.items()])

	# Parse command-line arguments
	parser = argparse.ArgumentParser(
		description="Generate a countdown MP3 with specified start and end numbers.\n" + language_help_text,
		formatter_class=argparse.RawTextHelpFormatter
	)
	parser.add_argument("--start", type=int, required=True, help="The starting number of the countdown.")
	parser.add_argument("--end", type=int, required=True, help="The ending number of the countdown.")
	parser.add_argument("--language", type=str, default="en", help="The language for the countdown speech. Default is 'en' (US English).")
	parser.add_argument("--debug", action="store_true", help="Enable debug mode to print process and keep temp files.")
	parser.add_argument("--reuse-cache", action="store_true", help="Reuse existing audio files to avoid redundant processing.")
	parser.add_argument("--verify-final-file", action="store_true", help="Verify the final audio length to match the expected value.")
	args = parser.parse_args()

	# Set global debug variable based on the command-line argument
	debug = args.debug

	start_num = args.start
	end_num = args.end
	language = args.language
	reuse_cache = args.reuse_cache
	verify_final_file = args.verify_final_file

	# Generate countdown with provided arguments
	generate_countdown(start_num, end_num, f"countdown-{language}-{start_num}-{end_num}.mp3", language, reuse_cache, verify_final_file)

