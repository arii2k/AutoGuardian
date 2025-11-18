// src/pages/Dashboard.js — Clean Final Version (Single Recent Scans Table + Timestamp Fix)
import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import ThreatChart from "../components/ThreatChart";
import BehaviorRing from "../components/BehaviorRing";
import AIRiskCard from "../components/AIRiskCard";
import ScanTable from "../components/ScanTable";

function ShimmerBox({ height = "h-6", className = "" }) {
  return <div className={`shimmer bg-white/5 rounded-xl ${height} ${className}`} />;
}

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [rescanLoading, setRescanLoading] = useState(false);
  const [exporting, setExporting] = useState(false);

  // -------------------------------
  // Fetch dashboard data
  // -------------------------------
  const fetchDashboardData = async () => {
    try {
      const res = await fetch("http://127.0.0.1:5000/api/dashboard-data");
      if (!res.ok) throw new Error("Failed to fetch dashboard data");
      const json = await res.json();
      console.log("✅ Dashboard data received:", json);
      setData(json);
    } catch (err) {
      console.error("❌ Dashboard data fetch failed:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, []);

  // -------------------------------
  // Handle Rescan
  // -------------------------------
  const handleRescan = async () => {
    try {
      setRescanLoading(true);
      const res = await fetch("http://127.0.0.1:5000/rescan", { method: "POST" });
      if (!res.ok) throw new Error("Rescan request failed");
      console.log("✅ Rescan started");

      let polls = 0;
      const interval = setInterval(async () => {
        polls++;
        await fetchDashboardData();
        if (polls >= 5) {
          clearInterval(interval);
          setRescanLoading(false);
        }
      }, 2000);
    } catch (err) {
      console.error("Rescan error:", err);
      setRescanLoading(false);
    }
  };

  // -------------------------------
  // Export functions
  // -------------------------------
  const exportCSV = async () => {
    try {
      setExporting(true);
      const res = await fetch("http://127.0.0.1:5000/api/export-csv");
      if (!res.ok) throw new Error("CSV export failed");
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "AutoGuardian_Collective_Report.csv";
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert("CSV export failed: " + err.message);
    } finally {
      setExporting(false);
    }
  };

  const exportPDF = async () => {
    try {
      setExporting(true);
      const res = await fetch("http://127.0.0.1:5000/api/export-pdf");
      if (!res.ok) throw new Error("PDF export failed");
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "AutoGuardian_Report.pdf";
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert("PDF export failed: " + err.message);
    } finally {
      setExporting(false);
    }
  };

  // -------------------------------
  // Loading screen
  // -------------------------------
  if (loading && !data) {
    return (
      <div className="flex flex-col items-center justify-center h-screen bg-surface-dark text-gray-300">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ repeat: Infinity, duration: 1.5, ease: "linear" }}
          className="w-12 h-12 border-4 border-primary-light border-t-transparent rounded-full mb-6"
        />
        <p className="text-lg">Loading AutoGuardian AI Dashboard...</p>
      </div>
    );
  }

  // -------------------------------
  // Normalize data
  // -------------------------------
  const threatIndex = Math.round(data?.collective_stats?.threat_index ?? 0);
  const behaviorValue = Math.round(data?.behavior?.behavior_risk ?? 0);
  const collectiveStats = (data?.collective_stats?.records || []).map((record) => ({
    ...record,
    formatted_time: record.timestamp
      ? new Date(record.timestamp).toLocaleString(undefined, {
          dateStyle: "medium",
          timeStyle: "short",
        })
      : "Unknown",
  }));

  // -------------------------------
  // Render
  // -------------------------------
  return (
    <div className="p-10 min-h-screen bg-gradient-to-br from-[#0a0f24] to-[#12224d] text-white">
      {/* ===== HEADER ===== */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex justify-between items-center mb-10"
      >
        <h1 className="text-3xl font-bold tracking-tight drop-shadow-md">
          AutoGuardian AI Security Dashboard
        </h1>

        <button
          onClick={handleRescan}
          disabled={rescanLoading}
          className={`text-sm px-5 py-2 rounded-xl font-medium transition-all shadow-lg ${
            rescanLoading
              ? "bg-gray-600 cursor-not-allowed"
              : "bg-blue-600 hover:bg-blue-500 active:scale-95"
          }`}
        >
          {rescanLoading ? "Scanning..." : "Rescan"}
        </button>
      </motion.div>

      {/* ===== SUMMARY CARDS ===== */}
      <AnimatePresence mode="wait">
        <motion.div
          key="top-section"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-10"
        >
          <AIRiskCard threatIndex={threatIndex} label="AI Detection Risk" />

          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.8, ease: "easeOut" }}
            className="relative flex flex-col items-center justify-center rounded-3xl p-6 text-center bg-gradient-to-b from-[#0d1a2e] to-[#0a192f] border border-[#1e3a8a]/30 shadow-glow"
          >
            <motion.div
              animate={{ opacity: [0.6, 1, 0.6], scale: [1, 1.03, 1] }}
              transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut" }}
              className="absolute w-52 h-52 rounded-full bg-emerald-500/10 blur-3xl"
            />
            <BehaviorRing value={behaviorValue} />
            <h2 className="mt-3 text-lg font-semibold text-white">Behavior Risk</h2>
            <p className="text-sm text-gray-300">User activity pattern & anomaly risk</p>
          </motion.div>

          {/* Threat Activity Trend */}
          <motion.div
            whileHover={{ scale: 1.02 }}
            transition={{ duration: 0.3 }}
            className="rounded-3xl bg-gradient-to-b from-[#0d1a2e] to-[#0a192f] p-5 border border-[#1e3a8a]/30 shadow-inner"
          >
            <h2 className="text-lg font-semibold mb-3 text-gray-200">
              Threat Activity Trend
            </h2>
            <ThreatChart data={collectiveStats} />
          </motion.div>
        </motion.div>
      </AnimatePresence>

      {/* ===== RECENT SCANS (single clean table) ===== */}
      <AnimatePresence mode="wait">
        <motion.div
          key="recent-scans"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.8 }}
          className="rounded-3xl bg-gradient-to-b from-[#0d1a2e] to-[#0a192f] p-6 border border-[#1e3a8a]/30 shadow-lg"
        >
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-lg font-semibold text-gray-200">Recent Scans</h2>
            <div className="flex gap-2">
              <button
                onClick={exportCSV}
                disabled={exporting}
                className="text-xs px-3 py-1.5 bg-blue-600 hover:bg-blue-500 rounded-lg shadow"
              >
                {exporting ? "Exporting..." : "Export CSV"}
              </button>
              <button
                onClick={exportPDF}
                disabled={exporting}
                className="text-xs px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 rounded-lg shadow"
              >
                PDF Report
              </button>
            </div>
          </div>

          <p className="text-xs text-gray-400 mb-3 italic">
            Emails are scanned automatically upon receipt by AutoGuardian AI.
          </p>

          {collectiveStats.length === 0 ? (
            <div className="space-y-3">
              {[...Array(6)].map((_, i) => (
                <ShimmerBox key={i} height="h-8" className="w-full" />
              ))}
            </div>
          ) : (
            <ScanTable data={collectiveStats} />
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
