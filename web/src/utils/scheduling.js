export const AUDIO_SCHEDULE_LEAD_MS = 30000;
export const TTS_TRIGGER_LEAD_MS = 5200;
export const LATE_GRACE_MS = 1500;

export function shouldScheduleAudio(
  msLeft,
  { leadMs = AUDIO_SCHEDULE_LEAD_MS, lateGraceMs = LATE_GRACE_MS } = {}
) {
  if (!Number.isFinite(msLeft)) return false;
  return msLeft <= leadMs && msLeft > -lateGraceMs;
}

export function shouldTriggerTts(
  msLeft,
  { leadMs = TTS_TRIGGER_LEAD_MS, lateGraceMs = LATE_GRACE_MS } = {}
) {
  if (!Number.isFinite(msLeft)) return false;
  return msLeft <= leadMs && msLeft > -lateGraceMs;
}
