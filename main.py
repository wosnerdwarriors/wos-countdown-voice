#!/usr/bin/env python3
import asyncio
import importlib
import sys
import shutil
import platform
import os
import argparse

from discord_bot import main_bot
from web_server import main_web

REQUIREMENTS_FILE = "requirements.txt"

# List of system dependencies
SYSTEM_DEPENDENCIES = ["ffmpeg"]  # Add more if needed

def get_required_modules():
	"""Read required modules from requirements.txt"""
	modules = []
	if not os.path.exists(REQUIREMENTS_FILE):
		print(f"❌ {REQUIREMENTS_FILE} not found. Please make sure it exists.")
		sys.exit(1)

	with open(REQUIREMENTS_FILE, "r") as f:
		for line in f:
			# Extract only the package name (remove versions like "package>=1.0")
			line = line.strip()
			if line and not line.startswith("#"):
				modules.append(line.split("==")[0].split(">=")[0].split("<=")[0])
	
	return modules

def check_python_modules():
	"""Check if required Python modules are installed."""
	print("\n🔍 Checking required Python modules...\n")
	required_modules = get_required_modules()
	missing_modules = []

	for module in required_modules:
		try:
			importlib.import_module(module)
			print(f"✅ {module} is installed.")
		except ImportError:
			print(f"❌ {module} is **MISSING**.")
			missing_modules.append(module)

	if missing_modules:
		print("\n🚨 Missing Python modules:")
		for mod in missing_modules:
			print(f"   - {mod}")
		print("\nRun the following command to install them:\n")
		print("   pip3 install -r requirements.txt")
		print("")
		sys.exit(1)

def check_system_dependencies():
	"""Check if required system dependencies (like ffmpeg) are installed."""
	print("\n🔍 Checking required system dependencies...\n")
	missing_deps = []

	for dep in SYSTEM_DEPENDENCIES:
		if shutil.which(dep) is None:
			print(f"❌ {dep} is **MISSING**.")
			missing_deps.append(dep)
		else:
			print(f"✅ {dep} is installed.")

	if missing_deps:
		print("\n🚨 Missing system dependencies:")
		for dep in missing_deps:
			print(f"   - {dep}")
		
		# Provide OS-specific installation instructions
		print("\nTo install missing dependencies, run:")
		os_name = platform.system().lower()
		if os_name == "linux":
			print("   sudo apt install ffmpeg  # For Debian/Ubuntu")
			print("   sudo dnf install ffmpeg  # For Fedora")
			print("   sudo pacman -S ffmpeg    # For Arch")
		elif os_name == "darwin":
			print("   brew install ffmpeg  # For macOS (Homebrew required)")
		elif os_name == "windows":
			print("   Download ffmpeg from https://ffmpeg.org/download.html")
		else:
			print("   Check your package manager for installation steps.")

		print("")
		sys.exit(1)

async def main():
	# Parse command-line arguments
	parser = argparse.ArgumentParser(description="Run the Discord bot and web server.")
	parser.add_argument("--bypass-module-check", action="store_true", help="Skip validation of required modules.")
	args = parser.parse_args()

	if not args.bypass_module_check:
		check_python_modules()
		check_system_dependencies()
	else:
		print("⚠️ Bypassing module and system dependency checks as requested.")

	# Start bot and web server
	await asyncio.gather(
		main_bot(),
		main_web()
	)

if __name__ == "__main__":
	asyncio.run(main())

