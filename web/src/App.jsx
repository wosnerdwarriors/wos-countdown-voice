import React, { useState } from "react";
import "./App.css";
import Landing from "./components/Landing.jsx";
import RallyApp from "./components/RallyApp.jsx";

export default function App() {
  const [instanceId] = useState(() => {
    return new URLSearchParams(window.location.search).get("instance_id") || "";
  });

  // If instance_id is present (Discord Activity), open the session directly.
  if (instanceId) {
    return <RallyApp roomId={instanceId} />;
  }

  // Otherwise show the landing page.
  return <Landing />;
}
