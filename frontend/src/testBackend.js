import { useEffect, useState } from "react";

export default function TestBackend() {
  const [message, setMessage] = useState("Connecting...");
  const [data, setData] = useState(null);

  useEffect(() => {
    fetch("http://127.0.0.1:5000/api/dashboard-data")
      .then((res) => res.json())
      .then((json) => {
        setMessage("✅ Backend connected!");
        setData(json);
      })
      .catch((err) => {
        console.error("Backend error:", err);
        setMessage("❌ Could not reach backend (check console)");
      });
  }, []);

  return (
    <div style={{ textAlign: "center", fontFamily: "Segoe UI, sans-serif" }}>
      <h1>AutoGuardian Frontend</h1>
      <h2>{message}</h2>
      {data && (
        <pre
          style={{
            textAlign: "left",
            margin: "20px auto",
            padding: "10px",
            background: "#111",
            color: "#0f0",
            width: "80%",
            borderRadius: "8px",
            overflowX: "auto",
          }}
        >
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
    </div>
  );
}
