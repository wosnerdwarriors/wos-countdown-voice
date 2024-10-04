#!/usr/bin/env python3

from gtts import gTTS
from pydub import AudioSegment
import os

# Configuration options
cleanup = False  # Set this to True if you want to clean up the temporary files after generation
debug = True     # Enable debug mode to print additional information

def generate_countdown(start_num, interval, output_file):
	countdown_audio = AudioSegment.silent(duration=0)  # Initialize empty audio segment
	durations = []

	# Step 1: Generate speech for each number and measure its duration
	for i in range(start_num, -1, -1):
		if debug: print(f"Generating speech for number {i}")
		tts = gTTS(text=str(i), lang='en')
		tts.save(f"round1_{i}.mp3")  # Save the first-round audio for this number

		# Load the mp3 file into pydub
		number_audio = AudioSegment.from_mp3(f"round1_{i}.mp3")

		# Measure and store the duration
		duration = len(number_audio)
		durations.append(duration)
		if debug: print(f"Number {i}: Speech duration: {duration}ms")

	# Step 2: Determine the longest duration and calculate the required speed factor
	max_duration = max(durations)
	speed_factor = max_duration / (interval * 1000)
	if debug: print(f"Maximum duration among all numbers: {max_duration}ms, Speed factor: {speed_factor:.2f}")

	# Step 3: Adjust speed and pad to exactly fit 1 second for all numbers
	for i in range(start_num, -1, -1):
		number_audio = AudioSegment.from_mp3(f"round1_{i}.mp3")  # Load from round 1 audio

		# Apply the same speed adjustment to all numbers
		number_audio = number_audio.speedup(playback_speed=speed_factor)
		if debug: print(f"Number {i}: Adjusted speed with factor {speed_factor:.2f}")

		# Add silence to make each number's segment exactly 1 second
		duration = len(number_audio)
		if duration < interval * 1000:
			silence_duration = interval * 1000 - duration
			number_audio += AudioSegment.silent(duration=silence_duration)
			if debug: print(f"Number {i}: Padding with {silence_duration}ms of silence")

		# Save the adjusted number audio for inspection
		number_audio.export(f"round2_{i}.mp3", format="mp3")
		if debug: print(f"Number {i}: Saved adjusted audio as round2_{i}.mp3")

		# Append the adjusted number to the final countdown audio segment
		countdown_audio += number_audio

	# Step 4: Export the final countdown audio to mp3
	countdown_audio.export(output_file, format="mp3")
	if debug: print(f"Final countdown saved as {output_file}")

	# Step 5: Cleanup temporary files if cleanup flag is set to True
	if cleanup:
		for i in range(start_num, -1, -1):
			os.remove(f"round1_{i}.mp3")
			os.remove(f"round2_{i}.mp3")
			if debug: print(f"Temporary files for number {i} deleted")

if __name__ == "__main__":
	start_num = 50  # Starting number for the countdown
	interval = 1  # Time in seconds between each number
	output_file = "countdown.mp3"  # Output file

	generate_countdown(start_num, interval, output_file)

