// src/components/Topbar.js
import { useEffect, useState } from "react";
import ThemeToggle from "./ThemeToggle";

export default function Topbar() {
  const [userPlan, setUserPlan] = useState(null);
  const [loading, setLoading] = useState(true);

  // Fetch plan from API
  const fetchUser = async () => {
    try {
      const res = await fetch("http://127.0.0.1:5000/api/me", {
        credentials: "include",
      });
      const json = await res.json();

      const normalized =
        (json.plan || "free").charAt(0).toUpperCase() +
        (json.plan || "free").slice(1);

      setUserPlan(normalized);
    } catch (err) {
      console.error("Failed to load user plan:", err);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchUser();
  }, []);

  return (
    <header className="sticky top-0 z-30 px-6 py-3 backdrop-blur-md bg-black/20 border-b border-white/10">
      <div className="max-w-7xl mx-auto flex items-center justify-between">

        {/* LEFT: LOGO + TITLE */}
        <div className="flex items-center gap-3">

          {/* SVG LOGO (same as Sidebar) */}
          <div className="relative h-9 w-9 flex items-center justify-center">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 64 64"
              className="h-8 w-8"
            >
              <path
                d="M32 4l22 8v14c0 14-9 26-22 34C19 52 10 40 10 26V12l22-8z"
                fill="url(#grad)"
              />
              <defs>
                <linearGradient id="grad" x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0%" stopColor="#4f46e5" />
                  <stop offset="100%" stopColor="#06b6d4" />
                </linearGradient>
              </defs>
              <path
                d="M20 34h24l2 6H18l2-6zm4-8h16l4 8H20l4-8z"
                fill="rgba(255,255,255,0.9)"
              />
              <circle cx="24" cy="44" r="2.5" fill="#93c5fd" />
              <circle cx="40" cy="44" r="2.5" fill="#93c5fd" />
            </svg>
            <div className="absolute inset-0 rounded-full bg-blue-500/30 blur-xl" />
          </div>

          {/* Title */}
          <h1 className="text-xl font-semibold tracking-tight">
            AutoGuardian <span className="text-indigo-300">AI</span>
          </h1>

          {/* PLAN BADGE (dynamic) */}
          <span
            className="
              ml-2 text-xs px-2 py-0.5 rounded 
              bg-white/10 border border-white/15 text-indigo-200
            "
          >
            {loading ? "…" : userPlan}
          </span>
        </div>

        {/* RIGHT: CONTROLS */}
        <div className="flex items-center gap-3">
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
