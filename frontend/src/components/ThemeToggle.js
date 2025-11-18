import { useEffect, useState } from "react";
import { MoonIcon, SunIcon } from "@heroicons/react/24/solid";

export default function ThemeToggle() {
  const getInitial = () => {
    const saved = localStorage.getItem("theme");
    if (saved) return saved;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  };
  const [theme, setTheme] = useState(getInitial);

  useEffect(() => {
    const root = document.documentElement;
    const isDark = theme === "dark";
    root.classList.toggle("dark", isDark);
    localStorage.setItem("theme", theme);
  }, [theme]);

  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => { if (!localStorage.getItem("theme")) setTheme(media.matches ? "dark" : "light"); };
    media.addEventListener("change", handler);
    return () => media.removeEventListener("change", handler);
  }, []);

  return (
    <button
      type="button"
      onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
      className="btn btn-ghost btn-sm rounded-xl"
      title={theme === "dark" ? "Light mode" : "Dark mode"}
    >
      {theme === "dark" ? <SunIcon className="h-5 w-5 text-yellow-300" /> : <MoonIcon className="h-5 w-5 text-indigo-300" />}
      <span className="ml-2 hidden sm:inline">{theme === "dark" ? "Light" : "Dark"}</span>
    </button>
  );
}
