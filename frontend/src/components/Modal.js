// src/components/Modal.js
import { motion, AnimatePresence } from "framer-motion";

export default function Modal({ open, onClose, scan }) {
  if (!open || !scan) return null;

  const reasons = scan._ensemble_reasons || [];
  const matched = scan.matched_rules || "";

  return (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      >
        <motion.div
          onClick={(e) => e.stopPropagation()}
          className="bg-surface-light dark:bg-surface-dark text-gray-800 dark:text-gray-100 rounded-2xl p-6 w-[90%] max-w-2xl shadow-2xl"
          initial={{ y: 40, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 40, opacity: 0 }}
        >
          <h2 className="text-xl font-bold mb-2">
            {scan.subject || "Untitled Email"}
          </h2>
          <p className="text-sm text-gray-400 mb-4">{scan.sender}</p>

          <div className="border-t border-gray-700 pt-3 mb-3">
            <p className="font-medium text-primary-light">
              Score: {scan.score} / Risk: {scan.risk_level}
            </p>
          </div>

          {reasons.length > 0 && (
            <div className="mb-4">
              <h3 className="font-semibold mb-1">AI Analysis</h3>
              <ul className="list-disc ml-5 text-sm space-y-1">
                {reasons.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </div>
          )}

          {matched && (
            <div className="mb-4">
              <h3 className="font-semibold mb-1">Matched Rules</h3>
              <pre className="bg-gray-900/30 p-2 rounded text-xs overflow-x-auto">
                {matched}
              </pre>
            </div>
          )}

          <button
            onClick={onClose}
            className="bg-primary-light hover:bg-primary-dark text-white px-4 py-2 rounded-lg"
          >
            Close
          </button>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
