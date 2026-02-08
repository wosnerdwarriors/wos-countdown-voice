export function computeRallyView({ state, nowMs, fallbackRallyDurationMs }) {
  const activeRally = state?.rally;
  if (!activeRally) return null;

  const starter = state.players.find((p) => p.id === activeRally.starterId);
  if (!starter || !Number.isFinite(starter.marchMs)) return null;
  if (!Number.isFinite(activeRally.launchAt)) return null;

  const rallyDurationMs = Number.isFinite(activeRally.rallyDurationMs)
    ? activeRally.rallyDurationMs
    : fallbackRallyDurationMs;
  if (!Number.isFinite(rallyDurationMs) || rallyDurationMs < 0) return null;

  const launchAt = activeRally.launchAt;
  const rallyStartAt = launchAt - rallyDurationMs;
  const arrivalAt = Number.isFinite(activeRally.arrivalAt)
    ? activeRally.arrivalAt
    : launchAt + starter.marchMs;

  const joinRemainingMs = launchAt - nowMs;
  let phase = joinRemainingMs > 0 ? "JOIN" : "MARCH";
  if (arrivalAt <= nowMs) phase = "LANDED";

  const rows = state.players
    .filter((p) => Number.isFinite(p.marchMs))
    .map((p) => {
      const startAt = arrivalAt - p.marchMs;
      const playerRallyStartAt = startAt - rallyDurationMs;
      const diffMs = startAt - nowMs;
      const diffToRallyStartMs = playerRallyStartAt - nowMs;
      const diffFromLaunchMs = startAt - launchAt;
      const landInMs = arrivalAt - nowMs;

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
}
