"""Central definitions for configuration flags and helpers.

This module centralizes all config keys used across the codebase so we avoid
sprinkling magic strings through the application.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Iterable, Iterator, Tuple

try:  # Python 3.11+
	from enum import StrEnum  # type: ignore
except ImportError:  # pragma: no cover - fallback for <3.11
	class StrEnum(str, Enum):
		"""Minimal StrEnum backport for Python < 3.11."""
		pass


class DebugSection(StrEnum):
	"""Named debug sections exposed in config.json."""

	WEB = "web"
	DISCORD = "discord"
	AUDIO_SCHEDULER = "audio_scheduler"
	RALLY_STORE = "rally_store"
	TTS = "tts"
	GENERATION = "generation"
	PLAYBACK_SEEK = "playback_seek"
	DB = "db"
	PERF = "perf"
	HEARTBEAT = "heartbeat"
	WEB_ACCESS = "web_access"


def _debug_section_mapping(config: Dict[str, Any] | None) -> Dict[str, Any]:
	if isinstance(config, dict):
		sections = config.get("debug_sections")
		if isinstance(sections, dict):
			return sections
	return {}


def _normalize_section(section: DebugSection | str | None) -> str | None:
	if section is None:
		return None
	if isinstance(section, Enum):
		return str(section.value)
	return str(section)


def iter_debug_sections(config: Dict[str, Any] | None) -> Iterator[Tuple[str, bool]]:
	"""Yield configured debug sections with boolean state."""
	for name, value in _debug_section_mapping(config).items():
		yield name, bool(value)


def is_debug_section_enabled(
	config: Dict[str, Any] | None,
	section: DebugSection | str | None = None,
) -> bool:
	"""Check if a specific (or any) debug section is enabled."""
	sections = _debug_section_mapping(config)
	name = _normalize_section(section)
	if name is None:
		return any(bool(v) for v in sections.values())
	return bool(sections.get(name))


def any_debug_section_enabled(
	config: Dict[str, Any] | None,
	sections: Iterable[DebugSection | str] | None = None,
) -> bool:
	"""Check if any of the supplied sections are enabled (all when None)."""
	mapping = _debug_section_mapping(config)
	if sections is None:
		return any(bool(v) for v in mapping.values())
	normalized = [_normalize_section(section) for section in sections]
	return any(bool(mapping.get(name)) for name in normalized if name is not None)


def is_debug_category_enabled(config: Dict[str, Any] | None, category: str) -> bool:
	"""Determine whether logging should treat *category* as debug-worthy.

	Checks for a direct section match, then falls back to prefix heuristics to
	support existing categorisation behaviour.
	"""
	if not category:
		return False
	sections = _debug_section_mapping(config)
	try:
		section = DebugSection(category)
	except ValueError:
		section = None
	if section and bool(sections.get(section.value)):
		return True
	for name, enabled in sections.items():
		if enabled and category.startswith(name):
			return True
	return False
