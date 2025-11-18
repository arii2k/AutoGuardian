// src/App.js
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import { useEffect } from "react";

// Pages
import Dashboard from "./pages/Dashboard";
import Analytics from "./pages/Analytics";
import Settings from "./pages/Settings";
import Pricing from "./pages/Pricing";

// Layout
import Topbar from "./components/Topbar";
import Sidebar from "./components/Sidebar";

export default function App() {
  // Ensure dark mode on first load
  useEffect(() => {
    const theme = localStorage.getItem("theme");
    if (
      theme === "dark" ||
      (!theme && window.matchMedia("(prefers-color-scheme: dark)").matches)
    ) {
      document.documentElement.classList.add("dark");
    }
  }, []);

  return (
    <Router>
      <div className="min-h-screen flex">
        {/* Sidebar always visible */}
        <Sidebar />

        <div className="flex-1 min-w-0">
          {/* Topbar always visible */}
          <Topbar />

          {/* Routed pages */}
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/settings" element={<Settings />} />

            {/* ⭐ FIXED: Now Pricing Page Works */}
            <Route path="/pricing" element={<Pricing />} />
          </Routes>
        </div>
      </div>
    </Router>
  );
}
