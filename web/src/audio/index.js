let audioCtx = null;
let countdownBuffers = null;
let countdownLoadPromise = null;
const COUNTDOWN_FILES = ["5", "4", "3", "2", "1"];
const GO_FILE = "AirHorn";
const COUNTDOWN_EXT = "ogg";
const GO_GAIN_FACTOR = 0.6;

function ensureAudio() {
  const Ctx = window.AudioContext || window.webkitAudioContext;
  if (!Ctx) return null;
  if (!audioCtx) audioCtx = new Ctx();
  if (audioCtx.state === "suspended") {
    audioCtx.resume().catch(() => {});
  }
  return audioCtx;
}

function scheduleBuffer(buffer, timeSec, { gain = 1.0 } = {}) {
  const ctx = ensureAudio();
  if (!ctx) return;
  const source = ctx.createBufferSource();
  const g = ctx.createGain();
  source.buffer = buffer;
  g.gain.value = gain;
  source.connect(g).connect(ctx.destination);
  source.start(timeSec);
}

function beepAt(
  timeSec,
  { freq = 800, duration = 0.085, gain = 0.06 } = {}
) {
  const ctx = ensureAudio();
  if (!ctx) return;

  const osc = ctx.createOscillator();
  const g = ctx.createGain();

  osc.type = "sine";
  osc.frequency.setValueAtTime(freq, timeSec);

  g.gain.setValueAtTime(0.0001, timeSec);
  g.gain.linearRampToValueAtTime(gain, timeSec + 0.006);
  g.gain.exponentialRampToValueAtTime(0.0001, timeSec + duration);

  osc.connect(g).connect(ctx.destination);
  osc.start(timeSec);
  osc.stop(timeSec + duration + 0.03);
}

export function unlockAudio() {
  try {
    const ctx = ensureAudio();
    if (!ctx) return;
    const t = ctx.currentTime + 0.01;
    beepAt(t, { freq: 30, duration: 0.02, gain: 0.000001 });
    void preloadCountdownSounds();
  } catch {}
}

// TTS: name only.
export function speakName(
  name,
  { rate = 1.05, pitch = 1.0, volume = 1.0, lang = "en-US" } = {}
) {
  try {
    if (!("speechSynthesis" in window)) return;
    const u = new SpeechSynthesisUtterance(`${name}, get ready`);
    u.rate = rate;
    u.pitch = pitch;
    u.volume = volume;
    u.lang = lang;
    window.speechSynthesis.speak(u);
  } catch {}
}

export function unlockTTS() {
  try {
    if (!("speechSynthesis" in window)) return;
    const u = new SpeechSynthesisUtterance(" ");
    u.volume = 0;
    window.speechSynthesis.speak(u);
  } catch {}
}

function scheduleBeepsToTarget(
  targetTs,
  nowTs,
  {
    spacingSec = 0.75,
    leadSec = 5 * 0.75,
    freqCount = 720,
    freqGo = 1100,
    gain = 0.065,
    gainFactor = 1.0,
  } = {}
) {
  const ctx = ensureAudio();
  if (!ctx) return;

  const secUntilTarget = Math.max(0, (targetTs - nowTs) / 1000);
  const base = ctx.currentTime + secUntilTarget;

  const first = base - leadSec;
  const startTime = Math.max(ctx.currentTime + 0.02, first);
  const goTime = Math.max(ctx.currentTime + 0.02, base);

  const times = [];
  for (let i = 5; i >= 1; i--) {
    const t = goTime - (6 - i) * spacingSec;
    times.push({ n: i, t });
  }

  const filtered = times
    .filter((x) => x.t >= startTime && x.t <= goTime - 0.01)
    .sort((a, b) => a.t - b.t);

  for (const x of filtered) {
    beepAt(x.t, {
      freq: freqCount,
      duration: 0.085,
      gain: gain * gainFactor,
    });
  }
  beepAt(goTime, {
    freq: freqGo,
    duration: 0.12,
    gain: gain * 1.1 * gainFactor,
  });
}

export async function preloadCountdownSounds() {
  if (countdownBuffers || countdownLoadPromise) return countdownLoadPromise;
  const ctx = ensureAudio();
  if (!ctx) return null;

  const loadFile = async (name) => {
    const res = await fetch(`/countdown/${name}.${COUNTDOWN_EXT}`);
    if (!res.ok) throw new Error(`Failed to load countdown audio: ${name}`);
    const buf = await res.arrayBuffer();
    return ctx.decodeAudioData(buf);
  };

  countdownLoadPromise = Promise.all([
    ...COUNTDOWN_FILES.map((n) => loadFile(n)),
    loadFile(GO_FILE),
  ])
    .then((buffers) => {
      countdownBuffers = {
        numbers: buffers.slice(0, COUNTDOWN_FILES.length),
        go: buffers[buffers.length - 1],
      };
      return countdownBuffers;
    })
    .catch((err) => {
      console.warn("Failed to preload countdown sounds", err);
      countdownBuffers = null;
      return null;
    });

  return countdownLoadPromise;
}

export function scheduleCountdownToTarget(
  targetTs,
  nowTs,
  { gainFactor = 1.0 } = {}
) {
  const ctx = ensureAudio();
  if (!ctx) return;
  if (!countdownBuffers) return;

  const secUntilTarget = Math.max(0, (targetTs - nowTs) / 1000);
  const base = ctx.currentTime + secUntilTarget;
  const startTime = ctx.currentTime + 0.02;

  for (let i = 0; i < COUNTDOWN_FILES.length; i += 1) {
    const n = COUNTDOWN_FILES[i];
    const timeSec = base - Number(n);
    if (timeSec >= startTime) {
      scheduleBuffer(countdownBuffers.numbers[i], timeSec, { gain: gainFactor });
    }
  }

  if (base >= startTime) {
    scheduleBuffer(countdownBuffers.go, base, { gain: gainFactor * GO_GAIN_FACTOR });
  }
}

export function callName(name, { ttsVolume = 1.0 } = {}) {
  speakName(name, { lang: "en-US", rate: 1.05, volume: ttsVolume });
}

export async function playCountdownTest({
  name = "Testname",
  ttsVolume = 1.0,
  gainFactor = 1.0,
} = {}) {
  const ctx = ensureAudio();
  if (!ctx) return;

  if (!countdownBuffers) {
    await preloadCountdownSounds();
  }
  if (!countdownBuffers) return;

  speakName(name, { lang: "en-US", rate: 1.05, volume: ttsVolume });

  const start = ctx.currentTime + 0.2;
  const startIdx = 2; // "3"
  for (let i = 0; i < 3; i += 1) {
    const idx = startIdx + i;
    scheduleBuffer(countdownBuffers.numbers[idx], start + i, {
      gain: gainFactor,
    });
  }
}
