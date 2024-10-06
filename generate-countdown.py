#!/usr/bin/env python3

import argparse
from gtts import gTTS
from pydub import AudioSegment
import os

# Configuration options
debug = False  # Enable debug mode to print additional information

def generate_countdown(start_num, end_num, output_file):
	countdown_audio = AudioSegment.silent(duration=0)  # Initialize empty audio segment
	durations = []

	# Create tmp-data directory if it doesn't exist
	if not os.path.exists("tmp-data"):
		os.makedirs("tmp-data")
		if debug: print("Created directory: tmp-data")

	# Step 1: Generate speech for each number and measure its duration
	for i in range(start_num, end_num - 1, -1):
		if debug: print(f"Generating speech for number {i}")
		tts = gTTS(text=str(i), lang='en')
		tmp_file = f"tmp-data/countdown-{start_num}-{end_num}-round1_{i}.mp3"
		tts.save(tmp_file)  # Save the first-round audio with updated naming convention

		# Load the mp3 file into pydub
		number_audio = AudioSegment.from_mp3(tmp_file)

		# Measure and store the duration
		duration = len(number_audio)
		durations.append(duration)
		if debug: print(f"Number {i}: Speech duration: {duration}ms")

	# Step 2: Determine the longest duration and calculate the required speed factor
	max_duration = max(durations)
	speed_factor = max_duration / 1000  # Use 1 second as the interval
	if debug: print(f"Maximum duration among all numbers: {max_duration}ms, Speed factor: {speed_factor:.2f}")

	# Step 3: Adjust speed and pad to exactly fit 1 second for all numbers
	for i in range(start_num, end_num - 1, -1):
		tmp_file = f"tmp-data/countdown-{start_num}-{end_num}-round1_{i}.mp3"
		number_audio = AudioSegment.from_mp3(tmp_file)  # Load from round 1 audio

		# Apply the same speed adjustment to all numbers
		number_audio = number_audio.speedup(playback_speed=speed_factor)
		if debug: print(f"Number {i}: Adjusted speed with factor {speed_factor:.2f}")

		# Add silence to make each number's segment exactly 1 second
		duration = len(number_audio)
		if duration < 1000:  # 1 second interval
			silence_duration = 1000 - duration
			number_audio += AudioSegment.silent(duration=silence_duration)
			if debug: print(f"Number {i}: Padding with {silence_duration}ms of silence")

		# Save the adjusted number audio for inspection
		tmp_file_adjusted = f"tmp-data/countdown-{start_num}-{end_num}-round2_{i}.mp3"
		number_audio.export(tmp_file_adjusted, format="mp3")
		if debug: print(f"Number {i}: Saved adjusted audio as {tmp_file_adjusted}")

		# Append the adjusted number to the final countdown audio segment
		countdown_audio += number_audio

	# Step 4: Export the final countdown audio to mp3 with proper naming
	final_output_file = f"countdown-{start_num}-{end_num}.mp3"
	countdown_audio.export(final_output_file, format="mp3")
	if debug: print(f"Final countdown saved as {final_output_file}")

	# Step 5: Cleanup temporary files if debug is False
	if not debug:
		for i in range(start_num, end_num - 1, -1):
			os.remove(f"tmp-data/countdown-{start_num}-{end_num}-round1_{i}.mp3")
			os.remove(f"tmp-data/countdown-{start_num}-{end_num}-round2_{i}.mp3")
			if debug: print(f"Temporary files for number {i} deleted")

if __name__ == "__main__":
	# Parse command-line arguments
	parser = argparse.ArgumentParser(description="Generate a countdown MP3 with specified start and end numbers.")
	parser.add_argument("--start", type=int, required=True, help="The starting number of the countdown.")
	parser.add_argument("--end", type=int, required=True, help="The ending number of the countdown.")
	parser.add_argument("--debug", action="store_true", help="Enable debug mode to print process and keep temp files.")
	args = parser.parse_args()

	# Set global debug variable based on the command-line argument
	debug = args.debug

	start_num = args.start
	end_num = args.end

	# Generate countdown with provided arguments
	generate_countdown(start_num, end_num, f"countdown-{start_num}-{end_num}.mp3")

