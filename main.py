#!/usr/bin/env python3
import asyncio
import signal
import importlib
import sys
import shutil
import platform
import os
import subprocess
import threading
import time
import argparse

from config_enums import DebugSection, is_debug_section_enabled

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
    """Read required modules from requirements.txt and normalize names"""
    modules = []
    if not os.path.exists(REQUIREMENTS_FILE):
        print_safe("❌ requirements.txt not found. Please make sure it exists.")
        sys.exit(1)

    with open(REQUIREMENTS_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                package_name = line.split("==")[0].split(">=")[0].split("<=")[0].lower()
                if package_name == "pynacl":
                    package_name = "nacl"  # Normalize PyNaCl to nacl for import
                modules.append(package_name)

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


def parse_args():
	parser = argparse.ArgumentParser(description="WOS Countdown Voice")
	parser.add_argument("--config", default="config.json", help="Path to config file (default: config.json)")
	parser.add_argument("--asyncio-debug", dest="asyncio_debug", action="store_true", help="Enable asyncio loop debug mode")
	parser.add_argument("--no-asyncio-debug", dest="asyncio_debug", action="store_false", help="Disable asyncio loop debug mode")
	parser.set_defaults(asyncio_debug=None)
	return parser.parse_args()


_parsed_args = None
_loaded_config = None

def _debug_enabled(section=None):
	cfg = _loaded_config or {}
	return is_debug_section_enabled(cfg, section)

def load_config(path: str):
	global _loaded_config
	if not os.path.exists(path):
		print_safe(f"❌ Config file not found: {path}")
		sys.exit(2)
	import json as _json
	with open(path, 'r', encoding='utf-8') as f:
		_loaded_config = _json.load(f)
	return _loaded_config


async def main():
	# Run checks before importing other modules
	check_python_modules()
	check_system_dependencies()

	# Import after dependency checks
	from discord_bot import main_bot
	from web_server import main_web

	# Launch both tasks and keep references for cancellation
	bot_task = asyncio.create_task(main_bot(), name="bot_task")
	web_task = asyncio.create_task(main_web(), name="web_task")

	# Determine whether we should be quiet on shutdown: when no debug sections
	# are enabled we want a single-line shutdown message only.
	quiet_shutdown = not _debug_enabled(None)

	# Heartbeat to show loop is alive
	heartbeat_task = None
	if _debug_enabled(DebugSection.HEARTBEAT):
		async def heartbeat():
			while True:
				print_safe(f"[HB] loop alive {time.strftime('%H:%M:%S')} tasks={len(asyncio.all_tasks())}")
				await asyncio.sleep(5)
		heartbeat_task = asyncio.create_task(heartbeat(), name="heartbeat")

	def dump_state(tag):
		# Only emit the full dump if heartbeat or perf debugging is enabled.
		if _debug_enabled(DebugSection.HEARTBEAT) or _debug_enabled(DebugSection.PERF):
			print_safe(f"[DUMP:{tag}] --- TASKS ---")
			for t in asyncio.all_tasks():
				print_safe(f"  * {t.get_name()} done={t.done()} cancelled={t.cancelled()} repr={t}")
			print_safe(f"[DUMP:{tag}] --- THREADS ---")
			for th in threading.enumerate():
				print_safe(f"  * Thread name={th.name} daemon={th.daemon}")
			print_safe(f"[DUMP:{tag}] --------------")
		else:
			print_safe(f"[DUMP:{tag}] suppressed; enable heartbeat/perf debug for full dump")

	try:
		# Wait until one finishes (error or normal). If one errors, cancel the others.
		done, pending = await asyncio.wait({bot_task, web_task}, return_when=asyncio.FIRST_EXCEPTION)
		for d in done:
			exc = d.exception()
			if exc:
				print_safe(f"❌ Startup task failed: {exc}")
				dump_state("startup-fail-before-cancel")
				for p in pending:
					print_safe(f"[CANCEL] cancelling {p.get_name()}")
					p.cancel()
				await asyncio.gather(*pending, return_exceptions=True)
				dump_state("startup-fail-after-cancel")
				# stop heartbeat
				if heartbeat_task:
					heartbeat_task.cancel()
					await asyncio.gather(heartbeat_task, return_exceptions=True)
				print_safe("[EXIT] calling sys.exit(3)")
				sys.exit(3)
		# If we get here both finished cleanly (unlikely)
		print_safe("[INFO] Both primary tasks ended normally")
	except asyncio.CancelledError:
		if quiet_shutdown:
			# Perform minimal (silent) shutdown: request web server shutdown
			try:
				from web_server import web_shutdown_event
				if web_shutdown_event is not None and not web_shutdown_event.is_set():
					web_shutdown_event.set()
			except Exception:
				pass
			for t in (bot_task, web_task, heartbeat_task):
				if t and not t.done():
					t.cancel()
			await asyncio.gather(*(t for t in (bot_task, web_task, heartbeat_task) if t), return_exceptions=True)
			# no prints; runner will emit the single shutdown line
			raise
		else:
			print_safe("[SHUTDOWN] main() received cancellation")
			dump_state("cancelled")
			# Signal the web server to shutdown via its shutdown trigger (if present)
			try:
				from web_server import web_shutdown_event
				if web_shutdown_event is not None and not web_shutdown_event.is_set():
					print_safe("[CANCEL] setting web shutdown event")
					web_shutdown_event.set()
			except Exception:
				# ignore if web_server is not importable or the symbol is missing
				pass
			for t in (bot_task, web_task, heartbeat_task):
				if t and not t.done():
					print_safe(f"[CANCEL] {t.get_name()}")
					t.cancel()
			await asyncio.gather(*(t for t in (bot_task, web_task, heartbeat_task) if t), return_exceptions=True)
			dump_state("post-cancel-gather")
			raise
	finally:
		# final state snapshot
		dump_state("main-final")



def _resolve_asyncio_debug_flag():
	# precedence: CLI flag (if set) > config file key > default False
	if _parsed_args and _parsed_args.asyncio_debug is not None:
		return _parsed_args.asyncio_debug
	if isinstance(_loaded_config, dict) and 'asyncio_debug' in _loaded_config:
		return bool(_loaded_config['asyncio_debug'])
	return False


def _run():
	"""Custom runner with signal handling for clean Ctrl+C shutdown."""
	loop = asyncio.new_event_loop()
	asyncio.set_event_loop(loop)
	if _resolve_asyncio_debug_flag():
		print_safe("[DEBUG] asyncio debug mode enabled")
		loop.set_debug(True)

	main_task = loop.create_task(main(), name="main_entry")

	# Signal handlers (Unix only; on Windows SIGTERM may not be available):
	def _cancel():
		if _debug_enabled(None):
			print_safe("\n[SIGNAL] received, initiating cancellation...")
		if not main_task.done():
			main_task.cancel()

	def _cancel_from_signal(signum, frame):  # pragma: no cover - signal bridge
		loop.call_soon_threadsafe(_cancel)

	for sig in (getattr(signal, 'SIGINT', None), getattr(signal, 'SIGTERM', None)):
		if sig is not None:
			try:
				loop.add_signal_handler(sig, _cancel)
			except (NotImplementedError, RuntimeError, ValueError):
				# Fallback when event loop signal handlers are unavailable (e.g. debugpy)
				signal.signal(sig, _cancel_from_signal)
	try:
		loop.run_until_complete(main_task)
	except asyncio.CancelledError:
		if _debug_enabled(None):
			print_safe("[RUNNER] main task cancelled; exiting")
		else:
			# Minimal message when quiet
			print_safe("[RUNNER] shutting down.")
	except KeyboardInterrupt:
		if _debug_enabled(None):
			print_safe("\n[KEYBOARD] KeyboardInterrupt fallback")
		else:
			print_safe("[RUNNER] shutting down.")
		if not main_task.done():
			main_task.cancel()
			loop.run_until_complete(main_task)
	finally:
		# Print a short shutdown summary by default. If heartbeat or perf
		# debugging is enabled, emit the full task/thread dump for diagnosis.
		if _debug_enabled(DebugSection.HEARTBEAT) or _debug_enabled(DebugSection.PERF):
			print_safe("[RUNNER] final task/thread dump before closing loop")
			for t in asyncio.all_tasks(loop):
				print_safe(f"  loop-final-task name={t.get_name()} done={t.done()} cancelled={t.cancelled()} {t}")
			for th in threading.enumerate():
				print_safe(f"  loop-final-thread name={th.name} daemon={th.daemon}")
		else:
			# Minimal one-line shutdown summary when not debugging
			print_safe("[RUNNER] shutting down.")
		pending = [t for t in asyncio.all_tasks(loop) if t is not main_task and not t.done()]
		for p in pending:
			p.cancel()
		if pending:
			loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
		loop.close()

if __name__ == "__main__":
	# Ensure UTF-8 encoding on Windows
	if os.name == "nt":
		sys.stdout.reconfigure(encoding="utf-8")

	_parsed_args = parse_args()
	load_config(_parsed_args.config)
	_run()
