export default function ActionsBar({ onRescan, rescanLoading, lastUpdated }) {
  return (
    <div className="flex items-center gap-3">
      <button
        type="button"
        onClick={onRescan}
        disabled={rescanLoading}
        className={`btn btn-sm rounded-xl ${rescanLoading ? "bg-gray-600 cursor-not-allowed" : "btn-primary"}`}
      >
        {rescanLoading ? "Scanning…" : "Rescan"}
      </button>
      <span className="text-xs text-slate-300/80">
        Last updated: {lastUpdated || "—"}
      </span>
    </div>
  );
}
