// src/components/ScanModal.js
import { motion, AnimatePresence } from "framer-motion";

export default function ScanModal({ selected, onClose }) {
  if (!selected) return null;

  const rules = (selected.matched_rules || "").split(",").filter(Boolean);
  const reasons =
    selected.ai_details?._ensemble_reasons ||
    selected.ai_details?.ensemble_reasons ||
    [];

  return (
    <AnimatePresence>
      <motion.div
        key="backdrop"
        className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      >
        <motion.div
          key="modal"
          onClick={(e) => e.stopPropagation()}
          className="bg-surface-dark/90 text-white w-[90%] max-w-2xl rounded-2xl shadow-xl border border-white/10 p-6"
          initial={{ y: 40, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 40, opacity: 0 }}
        >
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-bold">
              {selected.subject || "Untitled Email"}
            </h2>
            <button
              className="text-gray-400 hover:text-white text-lg"
              onClick={onClose}
            >
              ✕
            </button>
          </div>

          <div className="grid grid-cols-2 gap-3 text-sm">
            <div><span className="text-gray-400">Sender:</span> {selected.sender}</div>
            <div><span className="text-gray-400">Timestamp:</span> {selected.timestamp?.slice(0,19)}</div>
            <div><span className="text-gray-400">Score:</span> {selected.score}</div>
            <div><span className="text-gray-400">Risk Level:</span> {selected.risk_level}</div>
          </div>

          {/* Rules */}
          <div className="mt-5">
            <h3 className="text-lg font-semibold mb-2">Matched Rules</h3>
            {rules.length > 0 ? (
              <ul className="space-y-1 text-sm">
                {rules.map((r, i) => (
                  <li
                    key={i}
                    className="bg-white/10 px-3 py-2 rounded-lg flex justify-between items-center"
                  >
                    <span>{r}</span>
                    <a
                      href={`https://www.openphish.com/?query=${encodeURIComponent(r)}`}
                      target="_blank"
                      rel="noreferrer"
                      className="text-indigo-400 hover:text-indigo-300 text-xs"
                    >
                      View Source ↗
                    </a>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-gray-400 text-sm">No rules matched.</p>
            )}
          </div>

          {/* AI reasons */}
          <div className="mt-6">
            <h3 className="text-lg font-semibold mb-2">AI Reasoning</h3>
            {reasons.length > 0 ? (
              <ul className="list-disc list-inside text-gray-300 space-y-1 text-sm">
                {reasons.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            ) : (
              <p className="text-gray-400 text-sm">No AI reasons recorded.</p>
            )}
          </div>

          {/* Close Button */}
          <div className="flex justify-end mt-6">
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium"
            >
              Close
            </button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
