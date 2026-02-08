import React, { useState } from "react";
import { createRandomRoomId, navigateToRoom } from "../utils/room.js";
import { formatTimeOfDay } from "../utils/time.js";

export default function Landing() {
  const [roomInput, setRoomInput] = useState("");

  const handleJoin = () => {
    const trimmed = roomInput.trim();
    if (!trimmed) return;
    navigateToRoom(trimmed);
  };

  const handleCreate = () => {
    const id = createRandomRoomId();
    navigateToRoom(id);
  };

  return (
    <div className="page">
      <header className="header">
        <div>
          <div className="kicker">WOS Rally Sync</div>
          <h1 className="title">Coordinate your rallies</h1>
          <div className="sub">
            Create a room or join an existing one by ID.
          </div>
        </div>
      </header>

      <main style={{ maxWidth: 480, margin: "0 auto" }}>
        <section className="card">
          <div className="cardHead">
            <div>
              <h2>Start a session</h2>
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <button
              type="button"
              className="btn primary"
              onClick={handleCreate}
            >
              Create random room
            </button>

            <div className="field">
              <label>Join by room ID</label>
              <input
                value={roomInput}
                onChange={(e) => setRoomInput(e.target.value)}
                placeholder="Paste or type room ID"
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleJoin();
                }}
              />
            </div>

            <button
              type="button"
              className="btn"
              onClick={handleJoin}
              disabled={!roomInput.trim()}
            >
              Join room
            </button>

            <div className="empty">
              Tip: Share the URL (including <span className="mono">?instance_id=…</span>)
              so others land in exactly the same room.
            </div>
          </div>
        </section>
      </main>

      <footer className="footer">
        <span className="mono">now (UTC): {formatTimeOfDay(Date.now())}</span>
      </footer>
    </div>
  );
}
