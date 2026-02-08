import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  callName,
  preloadCountdownSounds,
  playCountdownTest,
  scheduleCountdownToTarget,
  unlockAudio,
  unlockTTS,
} from "../audio/index.js";
import { useLocalSettings } from "../hooks/useLocalSettings.js";
import { computeRallyView } from "../utils/rally.js";
import { leaveRoom } from "../utils/room.js";
import {
  shouldScheduleAudio,
  shouldTriggerTts,
} from "../utils/scheduling.js";
import {
  computeOffsetAndRtt,
  createServerClockAnchor,
  getServerNowMs,
  isSyncFresh,
  isSyncReliable,
  updateBestSyncSample,
} from "../utils/sync.js";
import { formatMs, formatTimeOfDay } from "../utils/time.js";

const SYNC_SAMPLE_COUNT = 6;
const SYNC_INTERVAL_MS = 5000; // every 5 seconds
const SYNC_MAX_AGE_MS = 15000;
const SYNC_MAX_RTT_MS = 250;
const CLOCK_TICK_MS = 100;

function perfNowMs() {
  if (typeof performance !== "undefined" && typeof performance.now === "function") {
    return performance.now();
  }
  return Date.now();
}

const isEmbedded = (() => {
  try {
    return window.top !== window.self;
  } catch {
    return true;
  }
})();

function buildWsUrl(roomId) {
  const isDev = typeof import.meta !== "undefined" && import.meta.env && import.meta.env.DEV;
  const host = isDev ? "localhost:8787" : window.location.host;
  const proto = isDev ? "ws" : window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${host}/ws?instance_id=${encodeURIComponent(roomId)}`;
}

export default function RallyApp({ roomId }) {
  const [ws, setWs] = useState(null);
  const [state, setState] = useState({ players: [], rally: null });
  const [now, setNow] = useState(Date.now());
  const [timeOffsetMs, setTimeOffsetMs] = useState(0);
  const [lastSyncAt, setLastSyncAt] = useState(null);
  const [bestRttMs, setBestRttMs] = useState(null);
  const [audioEnabled, setAudioEnabled] = useState(false);
  const syncSamplesRef = useRef([]);
  const clockAnchorRef = useRef(null);
  const audioScheduledRef = useRef(new Set());
  const ttsCalledRef = useRef(new Set());

  // Player input.
  const [name, setName] = useState("");
  const [seconds, setSeconds] = useState(32);

  // Rally setup.
  const [starterId, setStarterId] = useState("");
  const [delay, setDelay] = useState(5);

  // Pre-start countdown (seconds).
  const [preDelaySec, setPreDelaySec] = useState(10);

  // TTS toggles.
  const [ttsEnabled, setTtsEnabled] = useState(true);
  const [ttsRallyCalls, setTtsRallyCalls] = useState(true);
  const [ttsMarchCalls, setTtsMarchCalls] = useState(false);

  // Local settings (volume + local player selection).
  const {
    beepLevel,
    setBeepLevel,
    ttsLevel,
    setTtsLevel,
    selectedIds,
    setSelectedIds,
  } = useLocalSettings();

  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds]);
  const selectedInRoom = useMemo(
    () => selectedIds.filter((id) => state.players.some((p) => p.id === id)),
    [selectedIds, state.players]
  );
  const sortedPlayers = useMemo(
    () => state.players.slice().sort((a, b) => a.name.localeCompare(b.name)),
    [state.players]
  );

  const beepGainFactor = Math.max(0, Math.min(1, beepLevel / 100));
  const ttsVolume = Math.max(0, Math.min(1, ttsLevel / 100));

  function toggleNotifyPlayer(playerId) {
    setSelectedIds((prev) => {
      const set = new Set(prev);
      if (set.has(playerId)) {
        set.delete(playerId);
      } else {
        set.add(playerId);
      }
      return Array.from(set);
    });
  }

  function setOffsetSample(offsetMs, rttMs) {
    const { samples, best } = updateBestSyncSample(
      syncSamplesRef.current,
      { offsetMs, rttMs },
      SYNC_SAMPLE_COUNT
    );
    syncSamplesRef.current = samples;
    if (!best) return;

    const localNowMs = Date.now();
    const anchor = createServerClockAnchor({
      localNowMs,
      perfNowMs: perfNowMs(),
      offsetMs: best.offsetMs,
    });
    if (!anchor) return;

    clockAnchorRef.current = anchor;
    setNow(anchor.serverNowMs);
    setTimeOffsetMs(best.offsetMs);
    setBestRttMs(best.rttMs);
    setLastSyncAt(localNowMs);
  }

  function handleTimeSyncResponse(payload) {
    if (!payload) return;
    const { t0, t1, t2 } = payload;
    const sample = computeOffsetAndRtt({ t0, t1, t2, t3: Date.now() });
    if (!sample) return;
    setOffsetSample(sample.offsetMs, sample.rttMs);
  }

  function requestTimeSync(socket) {
    if (!socket || socket.readyState !== WebSocket.OPEN) return;
    socket.send(
      JSON.stringify({ type: "TIME_SYNC_REQUEST", roomId, payload: { t0: Date.now() } })
    );
  }

  function runSyncBurst(socket) {
    for (let i = 0; i < SYNC_SAMPLE_COUNT; i += 1) {
      setTimeout(() => requestTimeSync(socket), i * 250);
    }
  }

  useEffect(() => {
    const socket = new WebSocket(buildWsUrl(roomId));
    let syncInterval = null;

    const handleVisibility = () => {
      if (document.visibilityState === "visible") {
        runSyncBurst(socket);
      }
    };

    const handleOpen = () => {
      socket.send(JSON.stringify({ type: "STATE_REQUEST", roomId }));
      runSyncBurst(socket);
      syncInterval = window.setInterval(
        () => runSyncBurst(socket),
        SYNC_INTERVAL_MS
      );
    };

    const handleMessage = (e) => {
      let msg;
      try {
        msg = JSON.parse(e.data);
      } catch {
        return;
      }
      if (msg?.type === "STATE") {
        setState(msg.payload);
        return;
      }
      if (msg?.type === "TIME_SYNC_RESPONSE") {
        handleTimeSyncResponse(msg.payload);
      }
    };

    socket.addEventListener("open", handleOpen);
    socket.addEventListener("message", handleMessage);
    socket.addEventListener("error", () => {});
    document.addEventListener("visibilitychange", handleVisibility);
    setWs(socket);

    return () => {
      if (syncInterval) window.clearInterval(syncInterval);
      socket.removeEventListener("open", handleOpen);
      socket.removeEventListener("message", handleMessage);
      document.removeEventListener("visibilitychange", handleVisibility);
      socket.close();
    };
  }, [roomId]);

  useEffect(() => {
    void preloadCountdownSounds();
  }, []);

  const enableAudio = () => {
    unlockAudio();
    if (ttsEnabled) unlockTTS();
    void preloadCountdownSounds();
    setAudioEnabled(true);
  };

  const testAudio = () => {
    if (!audioEnabled) return;
    void playCountdownTest({
      name: "Testname",
      ttsVolume,
      gainFactor: beepGainFactor,
    });
  };

  useEffect(() => {
    const tick = () => {
      const serverNowMs = getServerNowMs(clockAnchorRef.current, perfNowMs());
      if (Number.isFinite(serverNowMs)) {
        setNow(serverNowMs);
      } else {
        setNow(Date.now());
      }
    };

    tick();
    const t = setInterval(tick, CLOCK_TICK_MS);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    const rallyMs = state.rally?.rallyDurationMs;
    if (!Number.isFinite(rallyMs)) return;
    const minutes = Math.round(rallyMs / 60000);
    if (minutes && minutes !== delay) {
      setDelay(minutes);
    }
  }, [state.rally?.rallyDurationMs, delay]);

  const canAdd =
    ws &&
    name.trim().length > 0 &&
    Number.isFinite(Number(seconds)) &&
    Number(seconds) > 0 &&
    Number(seconds) <= 24 * 60 * 60;

  const localNowMs = Date.now();
  const hasFreshSync = isSyncFresh({
    lastSyncAtMs: lastSyncAt,
    nowMs: localNowMs,
    maxAgeMs: SYNC_MAX_AGE_MS,
  });
  const isSynced = isSyncReliable({
    lastSyncAtMs: lastSyncAt,
    nowMs: localNowMs,
    maxAgeMs: SYNC_MAX_AGE_MS,
    bestRttMs: bestRttMs,
    maxRttMs: SYNC_MAX_RTT_MS,
  });
  const hasStarter = !!starterId && state.players.some((p) => p.id === starterId);

  const canStartRally =
    ws &&
    state.players.length > 0 &&
    hasStarter &&
    isSynced;
  const startRallyTitle = !ws
    ? "Connecting..."
    : state.players.length === 0
      ? "Add at least one player"
      : !hasStarter
        ? "Choose Starter"
        : !hasFreshSync
          ? "Clock sync in progress"
          : !Number.isFinite(bestRttMs) || bestRttMs > SYNC_MAX_RTT_MS
            ? `Clock sync unstable (RTT > ${SYNC_MAX_RTT_MS} ms)`
            : "Start Rally";

  function addPlayer() {
    if (!canAdd) return;
    const marchMs = Math.round(Number(seconds) * 1000);

    ws.send(
      JSON.stringify({
        roomId,
        type: "PLAYER_ADD",
        payload: {
          id: crypto.randomUUID(),
          name: name.trim(),
          marchMs,
        },
      })
    );

    setName("");
  }

  function removePlayer(id) {
    if (!ws) return;
    ws.send(JSON.stringify({ roomId, type: "PLAYER_REMOVE", payload: id }));
  }

  function sendRallyStart() {
    if (!canStartRally) return;

    const rallyDurationMs = delay * 60 * 1000;
    const preDelayMs = Math.max(0, preDelaySec) * 1000;

    ws.send(
      JSON.stringify({
        roomId,
        type: "RALLY_START",
        payload: { starterId, rallyDurationMs, preDelayMs },
      })
    );
  }

  function startRally() {
    if (!canStartRally) return;

    if (ttsEnabled && audioEnabled) unlockTTS();
    if (audioEnabled) unlockAudio();

    sendRallyStart();
  }

  function endRally() {
    if (!ws) return;
    ws.send(JSON.stringify({ roomId, type: "RALLY_END" }));
    audioScheduledRef.current = new Set();
    ttsCalledRef.current = new Set();
  }

  const rallyComputed = useMemo(
    () =>
      computeRallyView({
        state,
        nowMs: now,
        fallbackRallyDurationMs: delay * 60 * 1000,
      }),
    [state, now, delay]
  );

  // Hybrid scheduler for local audio only.
  const effectiveOnlySelected = selectedInRoom.length > 0;
  const hasGoodRtt = Number.isFinite(bestRttMs) && bestRttMs <= SYNC_MAX_RTT_MS;
  const syncLabel = isSynced ? "Live" : hasFreshSync && !hasGoodRtt ? "High RTT" : "Syncing";

  useEffect(() => {
    if (!audioEnabled) return;
    if (!rallyComputed) return;

    for (const r of rallyComputed.rows) {
      // When any player is selected, only call selected players.
      if (effectiveOnlySelected && !selectedSet.has(r.id)) {
        continue;
      }

      let targetTs = null;
      let phaseKey = null;
      let allowTtsForPhase = false;

      if (rallyComputed.phase === "JOIN" && ttsRallyCalls) {
        targetTs = r.rallyStartAt;
        phaseKey = "rally";
        allowTtsForPhase = true;
      } else if (rallyComputed.phase === "MARCH" && ttsMarchCalls) {
        targetTs = r.startAt;
        phaseKey = "march";
        allowTtsForPhase = true;
      } else {
        continue;
      }

      const msLeft = targetTs - now;
      const audioKey = `${phaseKey}:audio:${r.id}:${targetTs}`;
      const ttsKey = `${phaseKey}:tts:${r.id}:${targetTs}`;

      if (
        !audioScheduledRef.current.has(audioKey) &&
        shouldScheduleAudio(msLeft)
      ) {
        audioScheduledRef.current.add(audioKey);
        scheduleCountdownToTarget(targetTs, now, { gainFactor: beepGainFactor });
      }

      if (
        ttsEnabled &&
        allowTtsForPhase &&
        !ttsCalledRef.current.has(ttsKey) &&
        shouldTriggerTts(msLeft)
      ) {
        ttsCalledRef.current.add(ttsKey);
        callName(r.name, { ttsVolume });
      }
    }
  }, [
    audioEnabled,
    ttsEnabled,
    ttsRallyCalls,
    ttsMarchCalls,
    rallyComputed,
    now,
    ttsVolume,
    beepGainFactor,
    effectiveOnlySelected,
    selectedSet,
  ]);

  useEffect(() => {
    if (rallyComputed) return;
    audioScheduledRef.current = new Set();
    ttsCalledRef.current = new Set();
  }, [rallyComputed]);

  useEffect(() => {
    if (selectedIds.length === 0) return;
    if (selectedInRoom.length === selectedIds.length) return;
    setSelectedIds(selectedInRoom);
  }, [selectedIds, selectedInRoom, setSelectedIds]);

  return (
    <div className="page">
      <header className="header">
        <div>
          <div className="kicker">WOS Rally Sync</div>
          <h1 className="title">Time your rally</h1>
          <div className="sub">
            Room: <span className="mono">{roomId}</span>
          </div>
          <div style={{ marginTop: 6, color: "var(--muted)", fontSize: 13 }}>
            Time is shown in UTC
          </div>
        </div>
        <div className="headerActions">
          {!isEmbedded && (
            <button
              className="btn ghost leaveBtn"
              type="button"
              onClick={leaveRoom}
            >
              Leave Room
            </button>
          )}
          <div
            className={`chip ${isSynced ? "ok" : "warn"}`}
            title={`Clock offset: ${Math.round(timeOffsetMs)} ms, RTT: ${
              bestRttMs ?? "?"
            } ms, sync age: ${
              Number.isFinite(lastSyncAt) ? `${Math.round(localNowMs - lastSyncAt)} ms` : "?"
            }`}
          >
            <span className="dot" />
            {syncLabel}
          </div>
        </div>
      </header>

      <main className="grid">
        {!audioEnabled && (
          <section className="card audioGate">
            <div>
              <div className="metaLabel">Audio locked</div>
              <div className="metaValue">Enable Audio</div>
              <p>
                Make sure to enable audio to hear countdowns
              </p>
            </div>
            <button className="btn primary" type="button" onClick={enableAudio}>
              Enable Audio
            </button>
          </section>
        )}

        {/* Players and local notify selection */}
        <section className="card">
          <div className="cardHead">
            <div>
              <h2>Player</h2>
              <p>Enter march time in seconds.</p>
            </div>
          </div>

          <div className="formRow">
            <div className="field">
              <label>Name</label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Speed"
                onKeyDown={(e) => {
                  if (e.key === "Enter") addPlayer();
                }}
              />
            </div>

            <div className="field">
              <label>March (Sec.)</label>
              <input
                type="number"
                min={1}
                max={24 * 60 * 60}
                step={1}
                value={seconds}
                onChange={(e) => setSeconds(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") addPlayer();
                }}
              />
            </div>

            <button className="btn primary" onClick={addPlayer} disabled={!canAdd}>
              + Add
            </button>
          </div>

          <div className="tableWrap">
            {sortedPlayers.length === 0 ? (
              <div className="empty">No Players added.</div>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>Player</th>
                    <th>March</th>
                    <th>Notify only for</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {sortedPlayers.map((p) => {
                    const checked = selectedSet.has(p.id);
                    return (
                      <tr key={p.id}>
                        <td className="strong">{p.name}</td>
                        <td className="mono">{formatMs(p.marchMs)}</td>
                        <td>
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => toggleNotifyPlayer(p.id)}
                            title="Local: receive calls for this player"
                          />
                        </td>
                        <td className="right">
                          <button
                            className="btn ghost"
                            onClick={() => removePlayer(p.id)}
                            title="Remove"
                          >
                            Remove
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </section>

        {/* Rally controls and countdown */}
        <section className="card">
          <div className="cardHead">
            <div>
              <h2>Countdown</h2>
              <p>Starter is used as reference for march time. Select starter and delay.</p>
            </div>

            <div className="ttsRow">
              <label className="ttsToggle">
                <input
                  type="checkbox"
                  checked={ttsEnabled}
                  onChange={(e) => setTtsEnabled(e.target.checked)}
                />
                <span>Voice + Countdown</span>
              </label>

              <label className="ttsToggle">
                <input
                  type="checkbox"
                  checked={ttsRallyCalls}
                  onChange={(e) => setTtsRallyCalls(e.target.checked)}
                />
                <span>Call Rally Start</span>
              </label>

              <label className="ttsToggle">
                <input
                  type="checkbox"
                  checked={ttsMarchCalls}
                  onChange={(e) => setTtsMarchCalls(e.target.checked)}
                />
                <span>Call March Start</span>
              </label>
            </div>

            {/* Local audio settings (per device) */}
            <div className="localSettings">
              <div className="localSettingsCol">
                <label className="localLabel">Countdown Volume</label>
                <input
                  type="range"
                  min={0}
                  max={100}
                  value={beepLevel}
                  onChange={(e) => setBeepLevel(Number(e.target.value))}
                />
              </div>
              <div className="localSettingsCol">
                <label className="localLabel">Voice Volume</label>
                <input
                  type="range"
                  min={0}
                  max={100}
                  value={ttsLevel}
                  onChange={(e) => setTtsLevel(Number(e.target.value))}
                />
              </div>
              <div className="localSettingsCol" style={{ display: "flex", alignItems: "flex-end" }}>
                <button
                  className="btn"
                  type="button"
                  onClick={testAudio}
                  disabled={!audioEnabled}
                  title={!audioEnabled ? "Enable Audio first" : "Play countdown sample"}
                >
                  Test Audio
                </button>
              </div>
            </div>
          </div>

          <div className="controls">
            <div className="field starterField">
              <label>Starter</label>
              <select value={starterId} onChange={(e) => setStarterId(e.target.value)}>
                <option value="">Choose Starter</option>
                {sortedPlayers.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({formatMs(p.marchMs)})
                  </option>
                ))}
              </select>
            </div>

            <div className="field">
              <label>Rally-Time (min)</label>
              <div className="field rallyTime">
                <button
                  className={`segBtn ${delay === 5 ? "active" : ""}`}
                  onClick={() => setDelay(5)}
                  type="button"
                >
                  5 min
                </button>
                <button
                  className={`segBtn ${delay === 10 ? "active" : ""}`}
                  onClick={() => setDelay(10)}
                  type="button"
                >
                  10 min
                </button>
              </div>
            </div>

            <div className="field">
              <label>Delay to start (Sec.)</label>
              <div className="delayInput">
                <input
                  type="number"
                  min={0}
                  step={1}
                  value={preDelaySec}
                  onChange={(e) => setPreDelaySec(Number(e.target.value))}
                />
              </div>
            </div>

            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <button
                className="btn primary"
                onClick={startRally}
                disabled={!canStartRally}
                title={startRallyTitle}
              >
                Start Rally
              </button>
            </div>
          </div>

          {rallyComputed ? (
            <>
              <div className="metaRow">
                <div className="meta">
                  <div className="metaLabel">Starter</div>
                  <div className="metaValue">{rallyComputed.starter.name}</div>
                </div>

                <div className="meta">
                  <div className="metaLabel">Rally-Start at</div>
                  <div className="metaValue mono">
                    {formatTimeOfDay(rallyComputed.rallyStartAt)}
                  </div>
                </div>

                <div className="meta">
                  <div className="metaLabel">March-Start at</div>
                  <div className="metaValue mono">
                    {formatTimeOfDay(rallyComputed.launchAt)}
                  </div>
                </div>

                <div className="meta">
                  <div className="metaLabel">Hit at</div>
                  <div className="metaValue mono">
                    {formatTimeOfDay(rallyComputed.arrivalAt)}
                  </div>
                </div>
              </div>

              <div className="tableWrap" style={{ marginTop: 10 }}>
                <div style={{ padding: "12px 12px" }}>
                  {rallyComputed.phase === "JOIN" ? (
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        gap: 12,
                        alignItems: "center",
                      }}
                    >
                      <div>
                        <div className="metaLabel">Join Phase</div>
                        <div className="metaValue mono">
                          March starts in {formatMs(rallyComputed.joinRemainingMs)}
                        </div>
                      </div>
                      <span className="badge ok">JOIN</span>
                    </div>
                  ) : rallyComputed.phase === "MARCH" ? (
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        gap: 12,
                        alignItems: "center",
                      }}
                    >
                      <div>
                        <div className="metaLabel">March Phase</div>
                        <div className="metaValue mono">
                          March started at {formatTimeOfDay(rallyComputed.launchAt)}
                        </div>
                      </div>
                      <span className="badge warn">MARCH</span>
                    </div>
                  ) : (
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        gap: 12,
                        alignItems: "center",
                      }}
                    >
                      <div>
                        <div className="metaLabel">Landed</div>
                        <div className="metaValue mono">
                          All marches landed at {formatTimeOfDay(rallyComputed.arrivalAt)}
                        </div>
                      </div>
                      <span className="badge bad">LANDED</span>
                    </div>
                  )}
                </div>
              </div>

              <div style={{ marginTop: 8, textAlign: "right" }}>
                <button className="btn ghost" onClick={endRally} title="End Rally">
                  End Rally
                </button>
              </div>

              {rallyComputed.phase === "LANDED" ? (
                <div className="empty">All marches have landed. Rally will auto-clear.</div>
              ) : rallyComputed.rows.length === 0 ? (
                <div className="empty">No active marches left.</div>
              ) : (
                <div className="tableWrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Player</th>
                        <th>Rally-Start</th>
                        <th>Countdown</th>
                        <th>Land in</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rallyComputed.rows.map((r) => {
                        const isJoin = rallyComputed.phase === "JOIN";
                        const landInText =
                          r.landInMs >= 0
                            ? formatMs(r.landInMs)
                            : `-${formatMs(-r.landInMs)}`;

                        let countdownText = "";
                        if (isJoin) {
                          if (r.diffToRallyStartMs > 0) {
                            countdownText = `in ${formatMs(r.diffToRallyStartMs)}`;
                          } else {
                            countdownText = `running ${formatMs(-r.diffToRallyStartMs)}`;
                          }
                          if (r.diffFromLaunchMs < 0) countdownText += ` (before March)`;
                        } else {
                          countdownText =
                            r.diffMs > 0
                              ? formatMs(r.diffMs)
                              : `since ${formatMs(-r.diffMs)}`;
                        }

                        let badgeClass = "ok";
                        let badgeText = "";

                        if (isJoin) {
                          if (r.diffToRallyStartMs > 0) {
                            badgeClass = "warn";
                            badgeText = "RALLY PENDING";
                          } else {
                            badgeClass = "ok";
                            badgeText = "RALLY RUNNING";
                          }
                        } else {
                          if (r.diffMs > 0) {
                            badgeClass = "ok";
                            badgeText = "WAIT";
                          } else {
                            badgeClass = "warn";
                            badgeText = "MARCHING";
                          }
                        }

                        return (
                          <tr key={r.id}>
                            <td className="strong">{r.name}</td>
                            <td className="mono">{formatTimeOfDay(r.rallyStartAt)}</td>
                            <td className="mono">{countdownText}</td>
                            <td className="mono">{landInText}</td>
                            <td>
                              <span className={`badge ${badgeClass}`}>{badgeText}</span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          ) : (
            <div className="empty">No rally started yet. Select starter → "Start Rally".</div>
          )}
        </section>
      </main>

      <footer className="footer">
        <span className="mono">now (UTC): {formatTimeOfDay(now)}</span>
      </footer>
    </div>
  );
}
