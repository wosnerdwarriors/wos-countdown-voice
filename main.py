#!/usr/bin/env python3
import asyncio
import importlib
import sys
import shutil
import platform
import os
import subprocess

from discord_bot import main_bot
from web_server import main_web

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
	"""Check if required Python modules are installed."""
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

		if prompt_for_install("Would you like to install missing Python modules now? (y/n) "):
			subprocess.run(["pip3", "install", "-r", REQUIREMENTS_FILE], check=True)
			print_safe("\n✅ Python modules installed successfully. Please restart the script.\n")
			sys.exit(0)
		else:
			print_safe("\n⚠️ Skipping Python module installation. The program may not work correctly.\n")
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

		# Provide OS-specific installation instructions
		print_safe("\nTo install missing dependencies, run:")
		os_name = platform.system().lower()
		if os_name == "linux":
			print_safe("   sudo apt install ffmpeg  # For Debian/Ubuntu")
			print_safe("   sudo dnf install ffmpeg  # For Fedora")
			print_safe("   sudo pacman -S ffmpeg    # For Arch")
		elif os_name == "darwin":
			print_safe("   brew install ffmpeg  # For macOS (Homebrew required)")
		elif os_name == "windows":
			print_safe("   Run the following in PowerShell:\n")
			print_safe("   winget install -e --id Gyan.FFmpeg")

		if prompt_for_install("\nWould you like to install missing system dependencies now? (y/n) "):
			install_missing_dependencies(missing_deps, os_name)
			print_safe("\n✅ System dependencies installed successfully. Please restart the script.\n")
			sys.exit(0)
		else:
			print_safe("\n⚠️ Skipping system dependency installation. The program may not work correctly.\n")
			sys.exit(1)

def prompt_for_install(prompt_text):
	"""Prompt the user with Y/N to install missing dependencies."""
	while True:
		answer = input(prompt_text).strip().lower()
		if answer in ["y", "yes"]:
			return True
		elif answer in ["n", "no"]:
			return False
		else:
			print_safe("❌ Invalid input. Please enter 'y' or 'n'.")

def install_missing_dependencies(missing_deps, os_name):
	"""Attempts to install missing dependencies based on OS."""
	for dep in missing_deps:
		if dep == "ffmpeg":
			if os_name == "linux":
				subprocess.run(["sudo", "apt", "install", "-y", "ffmpeg"], check=True)
			elif os_name == "darwin":
				subprocess.run(["brew", "install", "ffmpeg"], check=True)
			elif os_name == "windows":
				print_safe("⚠️ Please install FFmpeg manually by running:")
				print_safe("   winget install -e --id Gyan.FFmpeg")
				input("\nPress Enter to continue after installation...")

async def main():
	# Run checks before starting
	check_python_modules()
	check_system_dependencies()

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

