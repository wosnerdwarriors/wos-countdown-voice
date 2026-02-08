import test from "node:test";
import assert from "node:assert/strict";
import {
  AUDIO_SCHEDULE_LEAD_MS,
  LATE_GRACE_MS,
  TTS_TRIGGER_LEAD_MS,
  shouldScheduleAudio,
  shouldTriggerTts,
} from "./scheduling.js";

test("shouldScheduleAudio schedules in the lead window", () => {
  assert.equal(shouldScheduleAudio(AUDIO_SCHEDULE_LEAD_MS - 1), true);
  assert.equal(shouldScheduleAudio(AUDIO_SCHEDULE_LEAD_MS + 1), false);
});

test("shouldScheduleAudio allows slight lateness but blocks very late triggers", () => {
  assert.equal(shouldScheduleAudio(-LATE_GRACE_MS + 1), true);
  assert.equal(shouldScheduleAudio(-LATE_GRACE_MS - 1), false);
});

test("shouldTriggerTts is bounded to its own lead window", () => {
  assert.equal(shouldTriggerTts(TTS_TRIGGER_LEAD_MS - 1), true);
  assert.equal(shouldTriggerTts(TTS_TRIGGER_LEAD_MS + 1), false);
  assert.equal(shouldTriggerTts(-LATE_GRACE_MS + 1), true);
  assert.equal(shouldTriggerTts(-LATE_GRACE_MS - 1), false);
});
