#!/usr/bin/env python3
import asyncio
import importlib
import sys
import shutil
import platform
import os
import subprocess

REQUIREMENTS_FILE = "requirements.txt"
SYSTEM_DEPENDENCIES = ["ffmpeg"]  # Add more if needed

# Detect if the system supports emojis
SUPPORTS_EMOJIS = sys.stdout.encoding.lower().startswith("utf")

# Define emoji-aware print function
def print_safe(text):
	"""Prints text without emojis if the system doesn't support them."""
	if not SUPPORTS_EMOJIS:
		text = text.encode("ascii", "ignore").decode()  # Remove emojis
	print(text)

def get_required_modules():
	"""Read required modules from requirements.txt"""
	modules = []
	if not os.path.exists(REQUIREMENTS_FILE):
		print_safe("❌ requirements.txt not found. Please make sure it exists.")
		sys.exit(1)

	with open(REQUIREMENTS_FILE, "r") as f:
		for line in f:
			# Extract only the package name (remove versions like "package>=1.0")
			line = line.strip()
			if line and not line.startswith("#"):
				modules.append(line.split("==")[0].split(">=")[0].split("<=")[0])

	return modules

def check_python_modules():
	"""Check if required Python modules are installed BEFORE importing anything."""
	print_safe("\n🔍 Checking required Python modules...\n")

	required_modules = get_required_modules()
	missing_modules = []

	for module in required_modules:
		try:
			importlib.import_module(module)
			print_safe(f"✅ {module} is installed.")
		except ImportError:
			print_safe(f"❌ {module} is **MISSING**.")
			missing_modules.append(module)

	if missing_modules:
		print_safe("\n🚨 Missing Python modules:")
		for mod in missing_modules:
			print_safe(f"   - {mod}")

		print_safe("\n⚠️ The script requires these modules to function correctly.")
		print_safe("   To install missing Python modules, run the following command:\n")
		print_safe("   pip3 install -r requirements.txt\n")
		sys.exit(1)


def check_system_dependencies():
	"""Check if required system dependencies (like ffmpeg) are installed."""
	print_safe("\n🔍 Checking required system dependencies...\n")

	missing_deps = []
	for dep in SYSTEM_DEPENDENCIES:
		if shutil.which(dep) is None:
			print_safe(f"❌ {dep} is **MISSING**.")
			missing_deps.append(dep)
		else:
			print_safe(f"✅ {dep} is installed.")

	if missing_deps:
		print_safe("\n🚨 Missing system dependencies:")
		for dep in missing_deps:
			print_safe(f"   - {dep}")

		print_safe("\n⚠️ These dependencies are required for the script to work.")
		print_safe("   Please install them manually using the appropriate command for your OS:\n")

		os_name = platform.system().lower()
		if os_name == "linux":
			print_safe("   sudo apt install ffmpeg  # For Debian/Ubuntu")
			print_safe("   sudo dnf install ffmpeg  # For Fedora")
			print_safe("   sudo pacman -S ffmpeg    # For Arch")
		elif os_name == "darwin":
			print_safe("   brew install ffmpeg  # For macOS (Homebrew required)")
		elif os_name == "windows":
			print_safe("   Open PowerShell and run:\n")
			print_safe("   winget install -e --id Gyan.FFmpeg\n")

		sys.exit(1)


async def main():
	# Run checks before importing other modules
	check_python_modules()
	check_system_dependencies()

	# Now we safely import everything
	from discord_bot import main_bot
	from web_server import main_web

	# Start bot and web server
	await asyncio.gather(
		main_bot(),
		main_web()
	)

if __name__ == "__main__":
	# Ensure UTF-8 encoding on Windows
	if os.name == "nt":
		sys.stdout.reconfigure(encoding="utf-8")

	asyncio.run(main())
