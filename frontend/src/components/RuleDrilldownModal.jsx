import { motion, AnimatePresence } from "framer-motion";
import { XMarkIcon } from "@heroicons/react/24/outline";

export default function RuleDrilldownModal({ data, onClose }) {
  const {
    sender,
    subject,
    score,
    risk_level,
    timestamp,
    ensemble_reasons = "AI identified phishing indicators from content and metadata analysis.",
    triggered_rules = ["Header anomaly", "Phishing keywords", "Reputation match"],
    sources = ["OpenPhish", "URLhaus", "Abuse.ch"],
  } = data;

  return (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
      >
        <motion.div
          className="bg-zinc-900 text-gray-100 rounded-2xl shadow-2xl p-6 w-full max-w-lg relative"
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.9, opacity: 0 }}
          transition={{ type: "spring", damping: 20, stiffness: 300 }}
        >
          <button
            onClick={onClose}
            className="absolute top-3 right-3 text-gray-400 hover:text-white"
          >
            <XMarkIcon className="h-5 w-5" />
          </button>

          <h3 className="text-xl font-semibold mb-4">
            Scan Details — <span className="text-blue-400">{sender}</span>
          </h3>

          <div className="space-y-3 text-sm">
            <p>
              <span className="font-semibold text-gray-300">Subject:</span>{" "}
              {subject}
            </p>
            <p>
              <span className="font-semibold text-gray-300">Risk Level:</span>{" "}
              <span
                className={`${
                  risk_level === "High"
                    ? "text-red-400"
                    : risk_level === "Suspicious"
                    ? "text-yellow-400"
                    : "text-green-400"
                }`}
              >
                {risk_level}
              </span>
            </p>
            <p>
              <span className="font-semibold text-gray-300">Confidence:</span>{" "}
              {(score * 100).toFixed(1)}%
            </p>
            <p>
              <span className="font-semibold text-gray-300">Timestamp:</span>{" "}
              {timestamp}
            </p>
          </div>

          <hr className="my-4 border-gray-700" />

          <div>
            <h4 className="text-sm font-semibold text-gray-300 mb-1">
              🧠 AI Explanation
            </h4>
            <p className="text-gray-400 text-sm">{ensemble_reasons}</p>
          </div>

          <div className="mt-4">
            <h4 className="text-sm font-semibold text-gray-300 mb-1">
              🧷 Triggered Rules
            </h4>
            <ul className="list-disc list-inside text-gray-400 text-sm">
              {triggered_rules.map((rule, i) => (
                <li key={i}>{rule}</li>
              ))}
            </ul>
          </div>

          <div className="mt-4">
            <h4 className="text-sm font-semibold text-gray-300 mb-1">
              🌐 Threat Intel Sources
            </h4>
            <div className="flex flex-wrap gap-2">
              {sources.map((src, i) => (
                <span
                  key={i}
                  className="px-2 py-1 bg-blue-500/20 text-blue-300 rounded-lg text-xs"
                >
                  {src}
                </span>
              ))}
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
