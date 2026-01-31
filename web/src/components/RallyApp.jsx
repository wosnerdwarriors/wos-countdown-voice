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
import { leaveRoom } from "../utils/room.js";
import { formatMs, formatTimeOfDay } from "../utils/time.js";

const SYNC_SAMPLE_COUNT = 6;
const SYNC_INTERVAL_MS = 5000; // every 5 seconds

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
  const offsetRef = useRef(0);
  const syncSamplesRef = useRef([]);

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

  const announcedRef = useRef(new Set());

  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds]);
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

  function setOffsetSample(offsetMs, rttMs, atTs) {
    const samples = syncSamplesRef.current.slice(-SYNC_SAMPLE_COUNT + 1);
    samples.push({ offsetMs, rttMs, atTs });
    const best = samples.reduce(
      (min, next) => (next.rttMs < min.rttMs ? next : min),
      samples[0]
    );
    syncSamplesRef.current = samples;
    if (best) {
      offsetRef.current = best.offsetMs;
      setTimeOffsetMs(best.offsetMs);
      setBestRttMs(best.rttMs);
      setLastSyncAt(atTs);
    }
  }

  function handleTimeSyncResponse(payload) {
    if (!payload) return;
    const { t0, t1, t2 } = payload;
    if (![t0, t1, t2].every((v) => Number.isFinite(v))) return;
    const t3 = Date.now();
    const rtt = Math.max(0, (t3 - t0) - (t2 - t1));
    const offset = ((t1 - t0) + (t2 - t3)) / 2;
    setOffsetSample(offset, rtt, t3);
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
    const t = setInterval(() => setNow(Date.now() + offsetRef.current), 200);
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

  const canStartRally =
    ws &&
    state.players.length > 0 &&
    starterId &&
    state.players.some((p) => p.id === starterId);

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
    announcedRef.current = new Set();
  }

  const rallyComputed = useMemo(() => {
    const activeRally = state.rally;
    if (!activeRally) return null;

    const starter = state.players.find((p) => p.id === activeRally.starterId);
    if (!starter) return null;

    const launchAt = activeRally.launchAt; // server timestamp (UTC ms)
    const rallyDurationMs = Number.isFinite(activeRally.rallyDurationMs)
      ? activeRally.rallyDurationMs
      : delay * 60 * 1000;
    const rallyStartAt = launchAt - rallyDurationMs;
    const arrivalAt = Number.isFinite(activeRally.arrivalAt)
      ? activeRally.arrivalAt
      : launchAt + starter.marchMs;

    const joinRemainingMs = launchAt - now;
    let phase = joinRemainingMs > 0 ? "JOIN" : "MARCH";
    if (arrivalAt <= now) phase = "LANDED";

    const rows = state.players
      .map((p) => {
        const startAt = arrivalAt - p.marchMs;
        const playerRallyStartAt = startAt - rallyDurationMs;
        const diffMs = startAt - now;
        const diffToRallyStartMs = playerRallyStartAt - now;
        const diffFromLaunchMs = startAt - launchAt;
        const landInMs = arrivalAt - now;

        return {
          ...p,
          startAt,
          rallyStartAt: playerRallyStartAt,
          diffMs,
          diffToRallyStartMs,
          diffFromLaunchMs,
          landInMs,
        };
      })
      .filter((r) => r.landInMs >= 0)
      .sort((a, b) => a.startAt - b.startAt);

    return {
      starter,
      launchAt,
      rallyStartAt,
      arrivalAt,
      rows,
      joinRemainingMs,
      phase,
    };
  }, [state, now, delay]);

  // Hybrid scheduler for local audio only.
  const effectiveOnlySelected = selectedIds.length > 0;
  const syncFreshMs = 60000;
  const isSynced = lastSyncAt && Date.now() - lastSyncAt < syncFreshMs;
  const syncLabel = isSynced ? "Live" : "Syncing";

  useEffect(() => {
    if (!ttsEnabled) return;
    if (!rallyComputed) return;

    const triggerMs = 5200;
    const toleranceMs = 350;

  const callFor = (playerName, targetTs) => {
    callName(playerName, { ttsVolume });
    scheduleCountdownToTarget(targetTs, now, { gainFactor: beepGainFactor });
  };

    for (const r of rallyComputed.rows) {
      // When any player is selected, only call selected players.
      if (effectiveOnlySelected && !selectedSet.has(r.id)) {
        continue;
      }

      let targetTs = null;
      let key = null;

      if (rallyComputed.phase === "JOIN" && ttsRallyCalls) {
        targetTs = r.rallyStartAt;
        key = `rally:${r.id}:${targetTs}`;
      } else if (rallyComputed.phase === "MARCH" && ttsMarchCalls) {
        targetTs = r.startAt;
        key = `march:${r.id}:${targetTs}`;
      } else {
        continue;
      }

      if (announcedRef.current.has(key)) continue;

      const msLeft = targetTs - now;

      if (msLeft <= triggerMs && msLeft > 600) {
        announcedRef.current.add(key);
        callFor(r.name, targetTs);
      }
    }
  }, [
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
            } ms`}
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
                title={!canStartRally ? "Choose Starter" : "Start Rally"}
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
