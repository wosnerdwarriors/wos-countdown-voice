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

		# 🔹 Debugging: Ensure we reach the prompt
		print_safe("\n🔹 DEBUG: About to prompt user for Python module installation...\n")
		sys.stdout.flush()

		if prompt_for_install("\nWould you like to install the missing Python modules now? (y/n) "):
			print_safe("\n🔹 DEBUG: User chose to install Python modules.")
			try:
				print_safe("\n🔹 Running: pip3 install -r requirements.txt\n")
				sys.stdout.flush()

				# Run pip3 install in the foreground
				subprocess.run(["pip3", "install", "-r", REQUIREMENTS_FILE], check=True)

				print_safe("\n✅ Python modules installed successfully. Please restart the script.\n")
				sys.exit(0)
			except subprocess.CalledProcessError as e:
				print_safe("\n❌ Failed to install Python modules. Please run manually:\n")
				print_safe("   pip3 install -r requirements.txt\n")
				print_safe(f"\n🔹 DEBUG: Install failed with error -> {e}\n")
				sys.exit(1)
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

		if prompt_for_install("\nWould you like to install missing system dependencies now? (y/n) "):
			print("you said yes so now installing missing dependencies")
			install_missing_dependencies(missing_deps)
			print_safe("\n✅ System dependencies installed successfully. Please restart the script.\n")
			sys.exit(0)
		else:
			print_safe("\n⚠️ Skipping system dependency installation. The program may not work correctly.\n")
			sys.exit(1)

def prompt_for_install(prompt_text):
	"""Prompt the user with Y/N to install missing dependencies, with added debugging."""
	print_safe(f"\n🔹 DEBUG: Reached prompt_for_install with prompt -> {prompt_text}")
	sys.stdout.flush()  # Ensure output flushes before asking for input

	while True:
		print_safe("🔹 DEBUG: Waiting for user input... (y/n)")
		sys.stdout.flush()  # Force output to show immediately
		answer = input(prompt_text).strip().lower()
		print_safe(f"🔹 DEBUG: User entered -> '{answer}'")  # Debugging line

		if answer in ["y", "yes"]:
			print_safe("✅ DEBUG: User chose to install dependencies.")
			return True
		elif answer in ["n", "no"]:
			print_safe("🚫 DEBUG: User declined installation.")
			return False
		else:
			print_safe("❌ Invalid input. Please enter 'y' or 'n'.")



def install_missing_dependencies(missing_deps):
	"""Attempts to install missing dependencies based on OS."""
	os_name = platform.system().lower()
	for dep in missing_deps:
		if dep == "ffmpeg":
			try:
				print_safe(f"\n📥 Installing {dep} on {os_name}...\n")

				if os_name == "linux":
					cmd = ["sudo", "apt", "install", "-y", "ffmpeg"]
				elif os_name == "darwin":
					cmd = ["brew", "install", "ffmpeg"]
				elif os_name == "windows":
					# Run via PowerShell explicitly
					cmd = ["powershell", "Start-Process", "winget", "-ArgumentList", "'install -e --id Gyan.FFmpeg'", "-Wait", "-NoNewWindow"]

				# Run the command and capture output
				process = subprocess.run(cmd, text=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

				# Print the full stdout and stderr
				print_safe(f"✅ Installation output:\n{process.stdout}")
				if process.stderr:
					print_safe(f"⚠️ Installation warnings:\n{process.stderr}")

				print_safe(f"\n✅ {dep} installed successfully!")

			except subprocess.CalledProcessError as e:
				print_safe("\n❌ Automatic installation failed. Error details:\n")
				print_safe(f"   Command: {e.cmd}")
				print_safe(f"   Return Code: {e.returncode}")
				print_safe(f"   Error Output: {e.stderr or 'No additional error output.'}")

				print_safe("\n🔹 Please install FFmpeg manually using one of the following commands:\n")
				if os_name == "linux":
					print_safe("   sudo apt install ffmpeg  # For Debian/Ubuntu")
					print_safe("   sudo dnf install ffmpeg  # For Fedora")
					print_safe("   sudo pacman -S ffmpeg    # For Arch")
				elif os_name == "darwin":
					print_safe("   brew install ffmpeg  # For macOS (Homebrew required)")
				elif os_name == "windows":
					print_safe("   Open PowerShell and run: winget install -e --id Gyan.FFmpeg\n")

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
