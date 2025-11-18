// ThreatChart.js — Glowing animated line chart (Microsoft + Apple hybrid)
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { motion } from "framer-motion";

export default function ThreatChart({ data }) {
  // Always ensure data is an array
  const safeData = Array.isArray(data) ? data : [];

  // If still empty, show placeholder
  if (!safeData || safeData.length === 0) {
    return (
      <div className="h-64 flex items-center justify-center text-gray-400">
        No recent threat data
      </div>
    );
  }

  // Normalize for Recharts
  const formattedData = safeData.map((item, i) => {
    if (Array.isArray(item)) {
      return { date: item[0] || `#${i}`, value: item[1] || 0 };
    } else if (typeof item === "object") {
      return {
        date: item.date || item.timestamp || `#${i}`,
        value: item.value ?? item.score ?? 0,
      };
    } else {
      return { date: `#${i}`, value: Number(item) || 0 };
    }
  });

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.8 }}
      className="relative p-6 rounded-2xl bg-gradient-to-br from-[#0a1120] to-[#111c3d] shadow-[inset_0_0_15px_rgba(255,255,255,0.05)] overflow-hidden"
    >
      {/* subtle backdrop glow */}
      <motion.div
        className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(37,99,235,0.15),transparent_70%)]"
        animate={{
          opacity: [0.3, 0.6, 0.3],
          scale: [1, 1.02, 1],
        }}
        transition={{ repeat: Infinity, duration: 4, ease: "easeInOut" }}
      />

      <h2 className="text-lg font-semibold text-white mb-4">
        Threat Activity Trend
      </h2>

      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={formattedData}>
          <defs>
            <linearGradient id="threatLine" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.9} />
              <stop offset="100%" stopColor="#1e3a8a" stopOpacity={0.1} />
            </linearGradient>
            <filter id="glow">
              <feGaussianBlur stdDeviation="3.5" result="coloredBlur" />
              <feMerge>
                <feMergeNode in="coloredBlur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          <CartesianGrid
            strokeDasharray="4 4"
            stroke="rgba(255,255,255,0.05)"
            vertical={false}
          />

          <XAxis
            dataKey="date"
            tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />

          <Tooltip
            contentStyle={{
              backgroundColor: "rgba(17,24,39,0.85)",
              border: "none",
              borderRadius: "8px",
              color: "#fff",
            }}
            labelStyle={{ color: "#60a5fa" }}
          />

          <Line
            type="monotone"
            dataKey="value"
            stroke="url(#threatLine)"
            strokeWidth={3}
            dot={false}
            isAnimationActive={true}
            filter="url(#glow)"
            activeDot={{
              r: 6,
              fill: "#60a5fa",
              stroke: "#93c5fd",
              strokeWidth: 3,
            }}
          />
        </LineChart>
      </ResponsiveContainer>
    </motion.div>
  );
}
