// BehaviorRing.js — perfectly matched to AIRiskCard, with dynamic colors
import { motion, useAnimation } from "framer-motion";
import { useEffect } from "react";

export default function BehaviorRing({ value = 0 }) {
  const controls = useAnimation();
  const risk = Math.min(Math.max(value, 0), 100);

  // Dynamic color gradient
  const color =
    risk < 40 ? "#22c55e" : risk < 70 ? "#eab308" : "#ef4444";

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
      {/* Title */}
      <h2 className="text-lg font-semibold mb-4 text-white">
        Behavior Risk
      </h2>

      {/* Soft circular glow (matches AI Risk card) */}
      <motion.div
        className="absolute w-40 h-40 rounded-full blur-3xl"
        style={{ background: color }}
        animate={{ opacity: [0.25, 0.7, 0.25], scale: [1, 1.1, 1] }}
        transition={{ repeat: Infinity, duration: 2.8, ease: "easeInOut" }}
      ></motion.div>

      {/* Circular ring */}
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
            stroke="url(#gradBehavior)"
            strokeWidth="10"
            fill="none"
            strokeLinecap="round"
            strokeDasharray="283"
            strokeDashoffset="283"
            animate={controls}
            className="drop-shadow-[0_0_8px_rgba(34,197,94,0.7)]"
          />
          <defs>
            <linearGradient id="gradBehavior" x1="0" y1="0" x2="100" y2="100">
              <stop offset="0%" stopColor="#34d399" />
              <stop offset="100%" stopColor="#16a34a" />
            </linearGradient>
          </defs>
        </svg>

        {/* Inner glowing center (same layout as AI Risk card) */}
        <div className="absolute w-24 h-24 rounded-full bg-gradient-to-br from-[#065f46] to-[#064e3b] shadow-inner flex flex-col items-center justify-center">
          <span className="text-3xl font-extrabold text-white tracking-tight drop-shadow">
            {Math.round(risk)}%
          </span>
          <span className="text-xs text-green-300 mt-1">Behavior Index</span>
        </div>
      </div>

      {/* Description */}
      <p className="mt-4 text-sm text-gray-400 max-w-xs text-center">
        Live user behavior & anomaly detection score
      </p>
    </motion.div>
  );
}
