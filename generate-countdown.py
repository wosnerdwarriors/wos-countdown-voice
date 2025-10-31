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

	# Validate start/end to avoid empty ranges
	if start_num < end_num:
		print(f"Error: start ({start_num}) must be >= end ({end_num})")
		exit(2)

	# Create tmp-data directory if it doesn't exist
	if not os.path.exists("tmp-data"):
		os.makedirs("tmp-data")
		if debug: print("Created directory: tmp-data")

	# Preload all file paths
	round1_files = {i: f"tmp-data/countdown-{start_num}-{end_num}-round1_{i}.mp3" for i in range(start_num, end_num - 1, -1)}
	round2_files = {i: f"tmp-data/countdown-{start_num}-{end_num}-round2_{i}.wav" for i in range(start_num, end_num - 1, -1)}

	# Step 1: Ensure we have raw (round1) audio for each number and collect raw durations
	raw_segments = {}
	raw_durations = []
	for i in range(start_num, end_num - 1, -1):
		# Ensure round1 exists (generate if needed)
		if not (reuse_cache and os.path.exists(round1_files[i])):
			if debug: print(f"Generating speech for number {i} with language '{language}'")
			tts = gTTS(text=str(i), lang=language)
			tts.save(round1_files[i])
		else:
			if debug: print(f"Reusing cached raw file: {round1_files[i]}")

		# Load raw segment and record its duration (used to compute speed factor)
		raw_segments[i] = AudioSegment.from_mp3(round1_files[i])
		duration = len(raw_segments[i])
		raw_durations.append(duration)
		if debug: print(f"Number {i}: Raw speech duration: {duration}ms")

	# Step 2: Determine the longest duration and calculate the required speed factor
	# Compute speed factor based on raw durations so we normalize to 1000ms
	if not raw_durations:
		print("Error: No raw audio segments produced or found. Check start/end values and cache files.")
		exit(2)

	max_duration = max(raw_durations)
	# Only speed up (playback_speed > 1). If max_duration <= 1000ms, we won't slow anything (playback_speed=1.0)
	speed_factor = max(1.0, max_duration / 1000.0)
	if debug: print(f"Maximum raw duration among all numbers: {max_duration}ms, Speed factor: {speed_factor:.2f}")

	# Step 3: Adjust speed and pad to exactly fit 1 second for all numbers
	# Step 3: Create or reuse adjusted (round2) files, ensuring each is exactly 1000ms
	audio_segments = {}
	for i in range(start_num, end_num - 1, -1):
		use_cached_round2 = False
		if reuse_cache and os.path.exists(round2_files[i]):
			# Verify cached round2 (WAV) is exactly 1000ms before reusing
			cached = AudioSegment.from_wav(round2_files[i])
			cached_len = len(cached)
			if cached_len == 1000:
				if debug: print(f"Reusing cached adjusted file (valid 1000ms): {round2_files[i]}")
				audio_segments[i] = cached
				use_cached_round2 = True
			else:
				if debug: print(f"Cached adjusted file {round2_files[i]} has length {cached_len}ms (not 1000ms); regenerating")

		if not use_cached_round2:
			# Adjust from raw segment
			adjusted = raw_segments[i].speedup(playback_speed=speed_factor)
			if debug: print(f"Number {i}: Adjusted speed with factor {speed_factor:.2f}")

			# Enforce exact 1000ms length by trimming or padding
			adj_len = len(adjusted)
			if adj_len > 1000:
				adjusted = adjusted[:1000]
				if debug: print(f"Number {i}: Trimmed from {adj_len}ms to 1000ms")
			elif adj_len < 1000:
				silence_duration = 1000 - adj_len
				adjusted += AudioSegment.silent(duration=silence_duration)
				if debug: print(f"Number {i}: Padded with {silence_duration}ms of silence to reach 1000ms")

			# Export adjusted clip to round2 cache as WAV (lossless, preserves exact length)
			adjusted.export(round2_files[i], format="wav")
			if debug: print(f"Number {i}: Saved adjusted audio as {round2_files[i]}")
			audio_segments[i] = adjusted

		# Safety check: audio_segments[i] must be exactly 1000ms now
		final_clip_len = len(audio_segments[i])
		if final_clip_len != 1000:
			print(f"Error: clip for {i} has length {final_clip_len}ms after adjustment; expected 1000ms")
			exit(3)

		countdown_audio += audio_segments[i]

	# Step 4: Export the final countdown audio to mp3 with proper naming
	# We'll perform a post-export verify-and-fix loop to account for MP3 encoder timing differences
	expected_length = (start_num - end_num + 1) * 1000
	max_retries = 5
	for attempt in range(1, max_retries + 1):
		countdown_audio.export(output_file, format="mp3")
		if debug: print(f"Exported final audio (attempt {attempt}) as {output_file}")

		# Load exported file to check actual length reported after MP3 encoding
		reloaded = AudioSegment.from_mp3(output_file)
		exported_length = len(reloaded)
		if debug: print(f"Exported file length: {exported_length}ms, expected: {expected_length}ms")

		# If lengths match exactly, we're done
		if exported_length == expected_length:
			print(f"Final countdown saved as {output_file}")
			break

		# If we shouldn't verify, or debug mode is on, just show a warning and exit accordingly
		if not verify_final_file and not debug:
			print(f"Final countdown saved as {output_file}")
			break

		# Compute delta and adjust in-memory AudioSegment accordingly
		delta = expected_length - exported_length
		# If delta is zero we've handled it above; otherwise trim or pad countdown_audio
		if delta > 0:
			# exported is shorter than expected -> pad
			if debug: print(f"Exported audio is {delta}ms short; padding in-memory audio and retrying")
			countdown_audio += AudioSegment.silent(duration=delta)
		elif delta < 0:
			# exported is longer than expected -> trim
			trim_ms = abs(delta)
			if debug: print(f"Exported audio is {trim_ms}ms too long; trimming in-memory audio and retrying")
			if trim_ms >= len(countdown_audio):
				print("Error: cannot trim more than the total audio length")
				exit(4)
			countdown_audio = countdown_audio[:-trim_ms]

		# If this was the last attempt, report and exit if still mismatched
		if attempt == max_retries:
			print(f"Warning: after {max_retries} attempts exported length {exported_length}ms != expected {expected_length}ms")
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

