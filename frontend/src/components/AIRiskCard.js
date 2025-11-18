// AIRiskCard.js — Fixed version: accepts both `value` and `threatIndex` props
import { motion, useAnimation } from "framer-motion";
import { useEffect } from "react";

export default function AIRiskCard({ value, threatIndex }) {
  // allow either prop
  const finalValue = typeof threatIndex === "number" ? threatIndex : value || 0;
  const controls = useAnimation();
  const risk = Math.min(Math.max(finalValue, 0), 100);

  useEffect(() => {
    controls.start({
      strokeDashoffset: 283 - (283 * risk) / 100,
      transition: { duration: 1.3, ease: "easeOut" },
    });
  }, [risk, controls]);

  return (
    <motion.div
      className="relative flex flex-col items-center justify-center p-6 rounded-2xl bg-gradient-to-br from-[#0a1120] to-[#111c3d] shadow-[inset_0_0_15px_rgba(255,255,255,0.05)]"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.8 }}
    >
      <h2 className="text-lg font-semibold mb-4 text-white">
        AI Detection Risk
      </h2>

      {/* Pulsing glow */}
      <motion.div
        className="absolute w-40 h-40 rounded-full blur-3xl"
        style={{ background: "#3b82f6" }}
        animate={{ opacity: [0.25, 0.7, 0.25], scale: [1, 1.1, 1] }}
        transition={{ repeat: Infinity, duration: 2.8, ease: "easeInOut" }}
      />

      {/* Ring */}
      <div className="relative flex items-center justify-center">
        <svg
          className="w-36 h-36 transform -rotate-90"
          viewBox="0 0 100 100"
        >
          <circle
            cx="50"
            cy="50"
            r="45"
            stroke="rgba(255,255,255,0.1)"
            strokeWidth="10"
            fill="none"
          />
          <motion.circle
            cx="50"
            cy="50"
            r="45"
            stroke={`url(#gradAI)`}
            strokeWidth="10"
            fill="none"
            strokeLinecap="round"
            strokeDasharray="283"
            strokeDashoffset="283"
            animate={controls}
            className="drop-shadow-[0_0_8px_rgba(59,130,246,0.7)]"
          />
          <defs>
            <linearGradient id="gradAI" x1="0" y1="0" x2="100" y2="100">
              <stop offset="0%" stopColor="#60a5fa" />
              <stop offset="100%" stopColor="#2563eb" />
            </linearGradient>
          </defs>
        </svg>

        {/* Inner glowing center */}
        <div className="absolute w-24 h-24 rounded-full bg-gradient-to-br from-[#1e3a8a] to-[#172554] shadow-inner flex flex-col items-center justify-center">
          <span className="text-3xl font-extrabold text-white tracking-tight drop-shadow">
            {Math.round(risk)}%
          </span>
          <span className="text-xs text-blue-300 mt-1">Live Index</span>
        </div>
      </div>

      <p className="mt-4 text-sm text-gray-400 max-w-xs text-center">
        Live computed threat index powered by AutoGuardian AI
      </p>
    </motion.div>
  );
}
