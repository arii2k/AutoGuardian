import { useState } from "react";
import RuleDrilldownModal from "./RuleDrilldownModal";

export default function ScanTable({ data = [] }) {
  const [selectedRow, setSelectedRow] = useState(null);

  return (
    <div>
      <h2 className="text-xl font-semibold mb-4">Recent Scans</h2>
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm text-left border-separate border-spacing-y-2">
          <thead className="text-gray-300 uppercase text-xs tracking-wider">
            <tr>
              <th className="px-4 py-2">Sender</th>
              <th className="px-4 py-2">Subject</th>
              <th className="px-4 py-2">Score</th>
              <th className="px-4 py-2">Risk Level</th>
              <th className="px-4 py-2">Timestamp</th>
            </tr>
          </thead>
          <tbody>
            {data.map((item, i) => (
              <tr
                key={i}
                onClick={() => setSelectedRow(item)}
                className="bg-white/5 hover:bg-white/10 transition-all rounded-lg cursor-pointer"
              >
                <td className="px-4 py-2 text-gray-100">{item.sender}</td>
                <td className="px-4 py-2 text-gray-200">{item.subject}</td>
                <td className="px-4 py-2 text-center text-blue-400">
                  {item.score}
                </td>
                <td
                  className={`px-4 py-2 font-semibold ${
                    item.risk_level === "High"
                      ? "text-red-400"
                      : item.risk_level === "Suspicious"
                      ? "text-yellow-400"
                      : "text-green-400"
                  }`}
                >
                  {item.risk_level}
                </td>
                <td className="px-4 py-2 text-gray-400">{item.timestamp}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Modal */}
      {selectedRow && (
        <RuleDrilldownModal
          data={selectedRow}
          onClose={() => setSelectedRow(null)}
        />
      )}
    </div>
  );
}
