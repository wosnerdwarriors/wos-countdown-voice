export const DEFAULT_SYNC_SAMPLE_COUNT = 6;

export function computeOffsetAndRtt({ t0, t1, t2, t3 }) {
  if (![t0, t1, t2, t3].every((v) => Number.isFinite(v))) return null;
  const rttMs = Math.max(0, (t3 - t0) - (t2 - t1));
  const offsetMs = ((t1 - t0) + (t2 - t3)) / 2;
  return { offsetMs, rttMs };
}

export function updateBestSyncSample(
  samples,
  sample,
  maxSamples = DEFAULT_SYNC_SAMPLE_COUNT
) {
  if (
    !sample ||
    !Number.isFinite(sample.offsetMs) ||
    !Number.isFinite(sample.rttMs)
  ) {
    return { samples: [...samples], best: null };
  }

  const cap = Math.max(1, Math.floor(maxSamples));
  const nextSamples = [...samples.slice(-cap + 1), sample];
  const best = nextSamples.reduce(
    (min, next) => (next.rttMs < min.rttMs ? next : min),
    nextSamples[0]
  );

  return { samples: nextSamples, best };
}

export function createServerClockAnchor({ localNowMs, perfNowMs, offsetMs }) {
  if (![localNowMs, perfNowMs, offsetMs].every((v) => Number.isFinite(v))) {
    return null;
  }
  return { serverNowMs: localNowMs + offsetMs, perfNowMs };
}

export function getServerNowMs(anchor, perfNowMs) {
  if (
    !anchor ||
    !Number.isFinite(anchor.serverNowMs) ||
    !Number.isFinite(anchor.perfNowMs) ||
    !Number.isFinite(perfNowMs)
  ) {
    return null;
  }
  return anchor.serverNowMs + (perfNowMs - anchor.perfNowMs);
}

export function isSyncFresh({ lastSyncAtMs, nowMs, maxAgeMs }) {
  if (![lastSyncAtMs, nowMs, maxAgeMs].every((v) => Number.isFinite(v))) {
    return false;
  }
  return nowMs - lastSyncAtMs <= maxAgeMs;
}

export function isSyncReliable({
  lastSyncAtMs,
  nowMs,
  maxAgeMs,
  bestRttMs,
  maxRttMs,
}) {
  if (!isSyncFresh({ lastSyncAtMs, nowMs, maxAgeMs })) return false;
  if (!Number.isFinite(bestRttMs) || !Number.isFinite(maxRttMs)) return false;
  return bestRttMs <= maxRttMs;
}
