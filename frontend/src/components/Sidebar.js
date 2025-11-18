// src/components/Sidebar.js
import { Link, useLocation } from "react-router-dom";
import Logo from "../logo.svg";   // <-- add at top

import {
  ShieldCheckIcon,
  ChartBarIcon,
  Cog6ToothIcon,
} from "@heroicons/react/24/outline";

const Item = ({ icon: Icon, label, to }) => {
  const location = useLocation();
  const active = location.pathname === to;

  return (
    <Link
      to={to}
      className={`w-full flex items-center gap-3 px-4 py-2 rounded-lg transition text-sm ${
        active
          ? "bg-white/15 text-white shadow-sm shadow-blue-400/20"
          : "text-slate-300 hover:bg-white/10 hover:text-white"
      }`}
    >
      <Icon className="h-5 w-5" />
      <span>{label}</span>
    </Link>
  );
};

export default function Sidebar() {
  return (
    <aside className="hidden md:flex flex-col w-60 p-5 bg-black/20 border-r border-white/10 backdrop-blur-md">
      {/* LOGO HEADER */}
      <div className="flex items-center gap-3 mb-8">
        {/* Logo SVG */}
        <div className="relative h-9 w-9 flex items-center justify-center">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 64 64"
            className="h-8 w-8"
          >
            {/* Shield background */}
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

            {/* Car silhouette inside shield */}
            <path
              d="M20 34h24l2 6H18l2-6zm4-8h16l4 8H20l4-8z"
              fill="rgba(255,255,255,0.9)"
            />
            <circle cx="24" cy="44" r="2.5" fill="#93c5fd" />
            <circle cx="40" cy="44" r="2.5" fill="#93c5fd" />
          </svg>

          {/* Soft glow behind logo */}
          <div className="absolute inset-0 rounded-full bg-blue-500/30 blur-xl" />
        </div>

        {/* Brand text */}
        <div className="flex flex-col">
          <span className="text-[15px] font-semibold text-white leading-none">
            AutoGuardian
          </span>
          <span className="text-[12px] text-indigo-300 tracking-wide">
            AI
          </span>
        </div>
      </div>

      {/* NAVIGATION ITEMS */}
      <nav className="space-y-2 flex-1">
        <Item icon={ShieldCheckIcon} label="Dashboard" to="/" />
        <Item icon={ChartBarIcon} label="Analytics" to="/analytics" />
        <Item icon={Cog6ToothIcon} label="Settings" to="/settings" />
      </nav>

      {/* FOOTER TEXT */}
      <div className="mt-auto text-[11px] text-slate-400 pt-4 border-t border-white/10">
        v1.0 • Local only • Privacy-first
      </div>
    </aside>
  );
}
