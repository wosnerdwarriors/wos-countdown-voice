import test from "node:test";
import assert from "node:assert/strict";
import { computeRallyView } from "./rally.js";

function buildState({ arrivalAt = 232_000 } = {}) {
  return {
    players: [
      { id: "starter", name: "Starter", marchMs: 32_000 },
      { id: "fast", name: "Fast", marchMs: 20_000 },
      { id: "slow", name: "Slow", marchMs: 40_000 },
    ],
    rally: {
      starterId: "starter",
      launchAt: 200_000,
      rallyDurationMs: 300_000,
      preDelayMs: 10_000,
      arrivalAt,
    },
  };
}

test("scenario: join phase computes per-player start times to same arrival", () => {
  const result = computeRallyView({
    state: buildState(),
    nowMs: 199_000,
    fallbackRallyDurationMs: 300_000,
  });

  assert.ok(result);
  assert.equal(result.phase, "JOIN");
  assert.equal(result.joinRemainingMs, 1_000);
  assert.equal(result.arrivalAt, 232_000);

  const fast = result.rows.find((r) => r.id === "fast");
  const slow = result.rows.find((r) => r.id === "slow");
  assert.ok(fast && slow);
  assert.equal(fast.startAt, 212_000);
  assert.equal(slow.startAt, 192_000);
});

test("scenario: phase switches from join to march to landed", () => {
  const state = buildState();

  const join = computeRallyView({
    state,
    nowMs: 199_999,
    fallbackRallyDurationMs: 300_000,
  });
  const march = computeRallyView({
    state,
    nowMs: 200_001,
    fallbackRallyDurationMs: 300_000,
  });
  const landed = computeRallyView({
    state,
    nowMs: 232_100,
    fallbackRallyDurationMs: 300_000,
  });

  assert.equal(join.phase, "JOIN");
  assert.equal(march.phase, "MARCH");
  assert.equal(landed.phase, "LANDED");
});

test("scenario: expired rows are filtered after arrival", () => {
  const result = computeRallyView({
    state: buildState(),
    nowMs: 231_500,
    fallbackRallyDurationMs: 300_000,
  });

  assert.ok(result);
  assert.equal(result.phase, "MARCH");
  assert.equal(result.rows.length, 3);

  const afterLanding = computeRallyView({
    state: buildState(),
    nowMs: 232_500,
    fallbackRallyDurationMs: 300_000,
  });
  assert.equal(afterLanding.phase, "LANDED");
  assert.equal(afterLanding.rows.length, 0);
});
