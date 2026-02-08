import test from "node:test";
import assert from "node:assert/strict";
import {
  computeOffsetAndRtt,
  createServerClockAnchor,
  getServerNowMs,
  isSyncFresh,
  isSyncReliable,
  updateBestSyncSample,
} from "./sync.js";

test("computeOffsetAndRtt calculates NTP-style offset and RTT", () => {
  const result = computeOffsetAndRtt({
    t0: 1000,
    t1: 1120,
    t2: 1120,
    t3: 1080,
  });

  assert.deepEqual(result, { offsetMs: 80, rttMs: 80 });
});

test("updateBestSyncSample keeps a bounded sample list and picks lowest RTT", () => {
  const initial = [];
  const first = updateBestSyncSample(initial, { offsetMs: 35, rttMs: 120 }, 3);
  const second = updateBestSyncSample(first.samples, { offsetMs: 40, rttMs: 90 }, 3);
  const third = updateBestSyncSample(second.samples, { offsetMs: 45, rttMs: 140 }, 3);
  const fourth = updateBestSyncSample(third.samples, { offsetMs: 50, rttMs: 80 }, 3);

  assert.equal(fourth.samples.length, 3);
  assert.equal(fourth.best.offsetMs, 50);
  assert.equal(fourth.best.rttMs, 80);
});

test("server clock anchor advances monotonically from perf time", () => {
  const anchor = createServerClockAnchor({
    localNowMs: 10_000,
    perfNowMs: 5_000,
    offsetMs: 125,
  });

  assert.ok(anchor);
  assert.equal(getServerNowMs(anchor, 5_500), 10_625);
  assert.equal(getServerNowMs(anchor, 6_000), 11_125);
});

test("sync freshness and reliability gate behave as expected", () => {
  assert.equal(
    isSyncFresh({ lastSyncAtMs: 10_000, nowMs: 11_000, maxAgeMs: 2_000 }),
    true
  );
  assert.equal(
    isSyncFresh({ lastSyncAtMs: 10_000, nowMs: 13_000, maxAgeMs: 2_000 }),
    false
  );

  assert.equal(
    isSyncReliable({
      lastSyncAtMs: 10_000,
      nowMs: 11_000,
      maxAgeMs: 2_000,
      bestRttMs: 150,
      maxRttMs: 250,
    }),
    true
  );
  assert.equal(
    isSyncReliable({
      lastSyncAtMs: 10_000,
      nowMs: 11_000,
      maxAgeMs: 2_000,
      bestRttMs: 320,
      maxRttMs: 250,
    }),
    false
  );
});
