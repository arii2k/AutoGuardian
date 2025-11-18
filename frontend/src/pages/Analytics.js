// src/pages/Analytics.js — Final Fixed Version (Hover bug fixed + Export buttons for all charts)
import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
} from "recharts";

export default function Analytics() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);

  // -----------------------------
  // Fetch Analytics Data
  // -----------------------------
  const fetchAnalytics = async () => {
    try {
      const res = await fetch("http://127.0.0.1:5000/api/dashboard-data");
      const json = await res.json();
      console.log("📊 Analytics data:", json);
      setData(json);
    } catch (err) {
      console.error("❌ Failed to load analytics:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnalytics();
  }, []);

  // -----------------------------
  // Export CSV / PDF
  // -----------------------------
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

  // -----------------------------
  // Loading State
  // -----------------------------
  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-screen text-gray-300">
        <p>Loading analytics...</p>
      </div>
    );
  }

  // -----------------------------
  // Safe Data Defaults
  // -----------------------------
  const highRiskTrend =
    (data?.collective_stats?.high_risk_trend || []).map((item, i) => ({
      time: item[0] || i,
      count: item[1] || 0,
    })) || [];
  const topSenders = data?.collective_stats?.top_senders || [];
  const topRules = data?.collective_stats?.top_rules || [];

  const ruleSummary = {
    OpenPhish: 300,
    URLhaus: 23421,
    TotalRules: 72969,
  };

  // -----------------------------
  // Reusable Chart Header
  // -----------------------------
  const ChartHeader = ({ title }) => (
    <div className="flex items-center justify-between mb-4">
      <h2 className="text-lg font-semibold text-gray-200">{title}</h2>
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
  );

  // -----------------------------
  // UI
  // -----------------------------
  return (
    <div className="p-10 min-h-screen bg-gradient-to-br from-[#0a0f24] to-[#12224d] text-white">
      {/* ====== PAGE TITLE ====== */}
      <motion.h1
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8 }}
        className="text-3xl font-bold mb-10"
      >
        Analytics Overview
      </motion.h1>

      {/* ====== SCANS OVER TIME ====== */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="rounded-3xl bg-gradient-to-b from-[#0d1a2e] to-[#0a192f] p-6 mb-10 border border-[#1e3a8a]/30 relative overflow-hidden"
      >
        <ChartHeader title="Scans Over Time" />
        <ResponsiveContainer width="100%" height={300} className="z-0">
          <LineChart data={highRiskTrend}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
            <XAxis dataKey="time" stroke="#aaa" />
            <YAxis stroke="#aaa" />
            <Tooltip
              wrapperStyle={{ zIndex: 9999 }}
              contentStyle={{
                backgroundColor: "rgba(17,24,39,0.9)",
                border: "none",
                borderRadius: "8px",
                color: "#fff",
              }}
            />
            <Line
              type="monotone"
              dataKey="count"
              stroke="#60a5fa"
              strokeWidth={3}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </motion.div>

      {/* ====== TOP RISKY SENDERS ====== */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="rounded-3xl bg-gradient-to-b from-[#0d1a2e] to-[#0a192f] p-6 mb-10 border border-[#1e3a8a]/30 relative overflow-hidden"
      >
        <ChartHeader title="Top Risky Senders" />
        <ResponsiveContainer width="100%" height={300} className="z-0">
          <BarChart data={topSenders}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
            <XAxis dataKey="sender" stroke="#aaa" />
            <YAxis stroke="#aaa" />
            <Tooltip
              wrapperStyle={{ zIndex: 9999 }}
              contentStyle={{
                backgroundColor: "rgba(17,24,39,0.9)",
                border: "none",
                borderRadius: "8px",
                color: "#fff",
              }}
            />
            <Bar dataKey="count" fill="#f87171" radius={[6, 6, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </motion.div>

      {/* ====== TOP MATCHED RULES ====== */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="rounded-3xl bg-gradient-to-b from-[#0d1a2e] to-[#0a192f] p-6 mb-10 border border-[#1e3a8a]/30 relative overflow-hidden"
      >
        <ChartHeader title="Top Matched Rules" />
        <ResponsiveContainer width="100%" height={300} className="z-0">
          <BarChart data={topRules}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
            <XAxis dataKey="rule" stroke="#aaa" />
            <YAxis stroke="#aaa" />
            <Tooltip
              wrapperStyle={{ zIndex: 9999 }}
              contentStyle={{
                backgroundColor: "rgba(17,24,39,0.9)",
                border: "none",
                borderRadius: "8px",
                color: "#fff",
              }}
            />
            <Bar dataKey="count" fill="#34d399" radius={[6, 6, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </motion.div>

      {/* ====== RULE SOURCE SUMMARY ====== */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="rounded-3xl bg-gradient-to-b from-[#0d1a2e] to-[#0a192f] p-6 border border-[#1e3a8a]/30"
      >
        <h2 className="text-lg font-semibold mb-4 text-gray-200">
          Rules Source Summary
        </h2>
        <div className="grid grid-cols-3 gap-6 text-center">
          {Object.entries(ruleSummary).map(([label, val]) => (
            <div key={label} className="bg-[#12224d]/40 rounded-xl p-4 shadow-inner">
              <p className="text-sm text-gray-400">{label}</p>
              <p className="text-2xl font-bold text-blue-400 mt-1">{val}</p>
            </div>
          ))}
        </div>
      </motion.div>
    </div>
  );
}
