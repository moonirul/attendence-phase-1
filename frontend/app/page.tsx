"use client";

import { useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Home() {
  const [status, setStatus] = useState<any>(null);
  const [report, setReport] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function request(path: string, method = "GET") {
    setBusy(true); setError("");
    try {
      const response = await fetch(`${API}${path}`, {
        method,
        headers: { "Content-Type": "application/json" },
        ...(path.includes("/session/start") ? { body: JSON.stringify({ headless: false }) } : {}),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Request failed");
      if (path.includes("status") || path.includes("start") || path.includes("stop")) setStatus(data);
      if (path.includes("inspect")) setReport(data.inspection);
      return data;
    } catch (e: any) { setError(e.message || "Unexpected error"); }
    finally { setBusy(false); }
  }

  return <main style={{ maxWidth: 1000, margin: "40px auto", padding: 24 }}>
    <header style={{ marginBottom: 28 }}>
      <p style={{ color: "#52627a", fontSize: 13, fontWeight: 700 }}>BETOPIA ERP · PHASE 1</p>
      <h1 style={{ margin: "8px 0" }}>Attendance Adapter</h1>
      <p style={{ color: "#52627a" }}>Manual login, session status and read-only dashboard inspection.</p>
    </header>

    <section style={card}>
      <h2 style={h2}>ERP browser session</h2>
      <p style={muted}>Start a visible browser, then complete username/password and Microsoft MFA yourself.</p>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        <button disabled={busy} onClick={() => request("/api/erp/session/start", "POST")} style={button}>Open ERP login</button>
        <button disabled={busy} onClick={() => request("/api/erp/session/status")} style={secondary}>Refresh status</button>
        <button disabled={busy} onClick={() => request("/api/erp/session/stop", "POST")} style={secondary}>Stop session</button>
      </div>
      {status && <pre style={pre}>{JSON.stringify(status, null, 2)}</pre>}
    </section>

    <section style={card}>
      <h2 style={h2}>Dashboard inspection</h2>
      <p style={muted}>After completing login manually, inspect visible buttons, inputs, status candidates and session-expiration text.</p>
      <button disabled={busy} onClick={() => request("/api/erp/dashboard/inspect", "POST")} style={button}>Inspect current page</button>
      {report && <pre style={{ ...pre, maxHeight: 480 }}>{JSON.stringify(report, null, 2)}</pre>}
    </section>

    {error && <p role="alert" style={{ color: "#b42318", background: "#fee4e2", padding: 12, borderRadius: 8 }}>{error}</p>}
    <p style={{ color: "#667085", fontSize: 12 }}>Safety: no attendance buttons are clicked; no punch-in/out functionality is included in Phase 1.</p>
  </main>;
}

const card: React.CSSProperties = { background: "white", padding: 24, borderRadius: 14, marginBottom: 18, boxShadow: "0 2px 12px #1018280a" };
const h2: React.CSSProperties = { marginTop: 0, fontSize: 18 };
const muted: React.CSSProperties = { color: "#667085", lineHeight: 1.5 };
const button: React.CSSProperties = { background: "#175cd3", color: "white", border: 0, borderRadius: 8, padding: "11px 16px", cursor: "pointer" };
const secondary: React.CSSProperties = { background: "#eef2f6", color: "#344054", border: 0, borderRadius: 8, padding: "11px 16px", cursor: "pointer" };
const pre: React.CSSProperties = { background: "#101828", color: "#d1e9ff", padding: 16, borderRadius: 8, overflow: "auto", fontSize: 12, marginTop: 16 };
