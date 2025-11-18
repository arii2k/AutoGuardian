// src/pages/Settings.js — AutoGuardian AI (FINAL SYNCED VERSION)
import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Switch } from "@headlessui/react";
import Logo from "../logo.svg"; // <-- add at top of Settings.js
export default function Settings() {
  // -----------------------------------------------------
  // USER — loaded from backend /api/me
  // -----------------------------------------------------
  const [user, setUser] = useState({
    email: "",
    plan: "",
    joined: "",
    subscription_active: false,
  });

  const [loadingUser, setLoadingUser] = useState(true);

  const fetchUser = async () => {
    try {
      const res = await fetch("http://127.0.0.1:5000/api/me", {
        credentials: "include",
      });

      const json = await res.json();
      setUser({
        email: json.email || "",
        plan: (json.plan || "free").toLowerCase(),
        joined: json.joined || "",
        subscription_active: json.subscription_active || false,
      });
    } catch (err) {
      console.error("Failed to load user:", err);
    }
    setLoadingUser(false);
  };

  useEffect(() => {
    fetchUser();
  }, []);

  // -----------------------------------------------------
  // PLAN LIMITS (match backend EXACTLY)
  // -----------------------------------------------------
  const PLAN_LIMITS = {
    free: { allow_imap: false, max_inboxes: 0 },
    starter: { allow_imap: true, max_inboxes: 1 },
    pro: { allow_imap: true, max_inboxes: 2 },
    business: { allow_imap: true, max_inboxes: 5 },
    enterprise: { allow_imap: true, max_inboxes: 999 },
  };

  const currentPlan = PLAN_LIMITS[user.plan] || PLAN_LIMITS.free;

  // -----------------------------------------------------
  // Preferences (local only for now)
  // -----------------------------------------------------
  const [preferences, setPreferences] = useState({
    twoFactor: true,
    autoQuarantine: true,
    notifySuspicious: true,
    scanFrequency: "Daily",
  });

  const [saving, setSaving] = useState(false);
  const [downloading, setDownloading] = useState(false);

  // -----------------------------------------------------
  // Inbox + IMAP State
  // -----------------------------------------------------
  const [inboxLoading, setInboxLoading] = useState(true);
  const [inboxStatus, setInboxStatus] = useState({
    connected: false,
    provider: null,
    email_address: "",
    status: "disconnected",
    last_scan: null,
  });

  const [imapForm, setImapForm] = useState({
    host: "",
    username: "",
    password: "",
    port: 993,
    useSSL: true,
  });

  const [imapSaving, setImapSaving] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);

  const fetchInboxStatus = async () => {
    try {
      const res = await fetch("http://127.0.0.1:5000/api/inbox-status", {
        credentials: "include",
      });
      const json = await res.json();
      setInboxStatus(json);
    } catch (err) {
      console.error("Inbox load failed", err);
    }
    setInboxLoading(false);
  };

  useEffect(() => {
    fetchInboxStatus();
  }, []);

  // -----------------------------------------------------
  // IMAP CONNECT
  // -----------------------------------------------------
  const handleImapConnect = async () => {
    if (!currentPlan.allow_imap) {
      alert("❌ Your plan does NOT include IMAP inbox support. Upgrade to continue.");
      return;
    }

    setImapSaving(true);

    try {
      const res = await fetch("http://127.0.0.1:5000/api/link-imap", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          host: imapForm.host,
          username: imapForm.username,
          password: imapForm.password,
          port: imapForm.port,
          use_ssl: imapForm.useSSL,
        }),
      });

      const json = await res.json();
      if (!res.ok) {
        alert(json.error || "IMAP connection failed.");
        return;
      }

      await fetchInboxStatus();
      alert("📨 IMAP inbox connected!");
    } catch (err) {
      alert("Error connecting IMAP inbox.");
    }

    setImapSaving(false);
  };

  // -----------------------------------------------------
  // Disconnect IMAP
  // -----------------------------------------------------
  const handleDisconnectInbox = async () => {
    setDisconnecting(true);
    try {
      await fetch("http://127.0.0.1:5000/api/disconnect-inbox", {
        method: "POST",
        credentials: "include",
      });
      await fetchInboxStatus();
    } finally {
      setDisconnecting(false);
    }
  };

  // -----------------------------------------------------
  // PDF + CSV Exports
  // -----------------------------------------------------
  const exportPDF = async () => {
    setDownloading(true);
    try {
      const res = await fetch("http://127.0.0.1:5000/api/export-pdf", {
        method: "POST",
      });
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "AutoGuardian_Report.pdf";
      a.click();
    } catch (err) {
      alert("PDF export failed");
    }
    setDownloading(false);
  };

  const exportCSV = async () => {
    setDownloading(true);
    try {
      const res = await fetch("http://127.0.0.1:5000/api/export-csv");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "collective_report.csv";
      a.click();
    } catch {
      alert("CSV export failed");
    }
    setDownloading(false);
  };

  // -----------------------------------------------------
  // Save Settings
  // -----------------------------------------------------
  const saveSettings = () => {
    setSaving(true);
    setTimeout(() => {
      alert("Settings saved!");
      setSaving(false);
    }, 600);
  };

  const manageSubscription = () => {
    window.open("http://127.0.0.1:5000/auth/subscribe", "_blank");
  };

  // -----------------------------------------------------
  // UI
  // -----------------------------------------------------
  return (
    <div className="p-10 min-h-screen bg-gradient-to-br from-[#0a0f24] to-[#12224d] text-white">
     {/* HEADER */}
<motion.div
  initial={{ opacity: 0, y: 20 }}
  animate={{ opacity: 1, y: 0 }}
  className="flex items-center gap-4 mb-10"
>
  {/* SAME LOGO AS SIDEBAR */}
  <div className="relative h-12 w-12 flex items-center justify-center">
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 64 64"
      className="h-10 w-10"
    >
      {/* Shield background */}
      <path
        d="M32 4l22 8v14c0 14-9 26-22 34C19 52 10 40 10 26V12l22-8z"
        fill="url(#grad_settings)"
      />
      <defs>
        <linearGradient id="grad_settings" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#4f46e5" />
          <stop offset="100%" stopColor="#06b6d4" />
        </linearGradient>
      </defs>

      {/* Car silhouette */}
      <path
        d="M20 34h24l2 6H18l2-6zm4-8h16l4 8H20l4-8z"
        fill="rgba(255,255,255,0.9)"
      />
      <circle cx="24" cy="44" r="2.5" fill="#93c5fd" />
      <circle cx="40" cy="44" r="2.5" fill="#93c5fd" />
    </svg>

    {/* Soft glow */}
    <div className="absolute inset-0 rounded-full bg-blue-500/30 blur-xl" />
  </div>

  <div>
    <h1 className="text-3xl font-bold">Settings</h1>
    <p className="text-gray-400 text-sm">
      Manage account, inbox, and security preferences
    </p>
  </div>
</motion.div>


      <div className="space-y-8">

        {/* INBOX SECTION */}
        <motion.div className="rounded-3xl p-6 bg-[#0d1a2e] border border-blue-900/30">
          <h2 className="text-xl font-semibold mb-4 text-indigo-300">Inbox & Scanning</h2>

          {inboxLoading ? (
            <p className="text-gray-400">Loading inbox…</p>
          ) : (
            <>
              <div className="flex justify-between items-start mb-4 text-sm text-gray-300">
                <div>
                  <p><strong>Status:</strong> {inboxStatus.connected ? <span className="text-emerald-400">Connected</span> : <span className="text-red-400">Not Connected</span>}</p>
                  <p><strong>Provider:</strong> {inboxStatus.provider || "—"}</p>
                  <p><strong>Email:</strong> {inboxStatus.email_address || "—"}</p>
                  <p className="text-xs text-gray-400">
                    Last scan: {inboxStatus.last_scan ? new Date(inboxStatus.last_scan).toLocaleString() : "—"}
                  </p>
                </div>

                {inboxStatus.connected && (
                  <button onClick={handleDisconnectInbox} className="px-4 py-2 bg-red-600 hover:bg-red-500 rounded-lg text-sm">
                    {disconnecting ? "Disconnecting..." : "Disconnect"}
                  </button>
                )}
              </div>

              {!inboxStatus.connected && (
                <div className="border-t border-gray-700/40 pt-4 mt-4">
                  {!currentPlan.allow_imap && (
                    <p className="text-red-400 text-xs mb-3">
                      🚫 Your plan does not allow IMAP inboxes.
                    </p>
                  )}

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                    <input className="input" placeholder="IMAP host" value={imapForm.host} onChange={(e) => setImapForm({ ...imapForm, host: e.target.value })} />
                    <input className="input" placeholder="Username" value={imapForm.username} onChange={(e) => setImapForm({ ...imapForm, username: e.target.value })} />
                    <input type="password" className="input" placeholder="Password" value={imapForm.password} onChange={(e) => setImapForm({ ...imapForm, password: e.target.value })} />
                    <input type="number" className="input" value={imapForm.port} onChange={(e) => setImapForm({ ...imapForm, port: e.target.value })} />
                  </div>

                  <button disabled={imapSaving || !currentPlan.allow_imap} onClick={handleImapConnect} className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 rounded-lg text-sm">
                    {imapSaving ? "Connecting..." : "Connect Inbox"}
                  </button>
                </div>
              )}
            </>
          )}
        </motion.div>

        {/* ACCOUNT */}
        <motion.div className="rounded-3xl p-6 bg-[#0d1a2e] border border-blue-900/30">
          <h2 className="text-xl font-semibold mb-4 text-blue-300">Account</h2>

          {loadingUser ? (
            <p>Loading user…</p>
          ) : (
            <div className="text-sm space-y-2">
              <p><strong>Email:</strong> {user.email}</p>
              <p>
                <strong>Plan:</strong>{" "}
                <span className="text-emerald-400">{user.plan.charAt(0).toUpperCase() + user.plan.slice(1)}</span>
              </p>
              <p><strong>Joined:</strong> {user.joined}</p>

              {!user.subscription_active && (
                <p className="text-red-400 text-xs">⚠ No active subscription</p>
              )}
            </div>
          )}

          <button onClick={manageSubscription} className="mt-4 px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm">
            Manage Subscription
          </button>
        </motion.div>
        {/* --------------------- */}
{/* PLAN CARD (NEW) */}
{/* --------------------- */}
<motion.div
  initial={{ opacity: 0, y: 20 }}
  animate={{ opacity: 1, y: 0 }}
  className="rounded-3xl p-6 bg-[#0d1a2e] border border-blue-900/30"
>
  <h2 className="text-xl font-semibold mb-4 text-indigo-300">
    Your Plan
  </h2>

  {/* Card */}
  <div className="bg-[#0a1628] border border-blue-800/40 rounded-2xl p-5">
    <div className="flex items-center justify-between mb-4">
      <div>
        <h3 className="text-2xl font-bold text-white">
          {user.plan?.toUpperCase() || "FREE"}
        </h3>
        <p className="text-gray-400 text-sm mt-1">
          Manage or upgrade your AutoGuardian AI plan anytime.
        </p>
      </div>

      <span className="px-3 py-1 text-sm bg-blue-700/40 rounded-md border border-blue-500/40">
        Active
      </span>
    </div>

    {/* Feature list based on plan */}
    <ul className="text-gray-300 text-sm space-y-2 mb-6">
      {user.plan === "free" && (
        <>
          <li>• 1 Gmail inbox only</li>
          <li>• Basic threat detection</li>
          <li>• No IMAP support</li>
          <li>• Weekly scanning</li>
        </>
      )}

      {user.plan === "starter" && (
        <>
          <li>• 1 Gmail or IMAP inbox</li>
          <li>• AI detection</li>
          <li>• Daily scanning</li>
          <li>• Quarantine folder</li>
        </>
      )}

      {user.plan === "pro" && (
        <>
          <li>• 2 inboxes (Gmail or IMAP)</li>
          <li>• Real-time scanning</li>
          <li>• Advanced AI + memory alerts</li>
          <li>• Priority threat detection</li>
        </>
      )}

      {user.plan === "business" && (
        <>
          <li>• Up to 5 inboxes</li>
          <li>• Behavior AI & team dashboard</li>
          <li>• Priority support</li>
          <li>• Advanced inbox protection</li>
        </>
      )}

      {user.plan === "enterprise" && (
        <>
          <li>• Unlimited inboxes</li>
          <li>• SLA + security audits</li>
          <li>• Dedicated support line</li>
          <li>• Admin controls</li>
        </>
      )}
    </ul>

    {/* Button */}
    <button
      onClick={() => (window.location.href = "/pricing")}
      className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-semibold"
    >
      Manage / Upgrade Plan
    </button>
  </div>
</motion.div>


        {/* SECURITY */}
        <motion.div className="rounded-3xl p-6 bg-[#0d1a2e] border border-blue-900/30">
          <h2 className="text-xl font-semibold mb-4 text-emerald-400">Security</h2>

          {["twoFactor", "notifySuspicious"].map((key) => (
            <div key={key} className="flex justify-between items-center mb-4 text-sm">
              <span>{key === "twoFactor" ? "Enable 2FA" : "Suspicious Login Alerts"}</span>
              <Switch
                checked={preferences[key]}
                onChange={(val) => setPreferences({ ...preferences, [key]: val })}
                className={`${preferences[key] ? "bg-emerald-500" : "bg-gray-600"} relative inline-flex h-6 w-11 items-center rounded-full`}
              >
                <span className={`${preferences[key] ? "translate-x-6" : "translate-x-1"} inline-block h-4 w-4 bg-white rounded-full transform`} />
              </Switch>
            </div>
          ))}
        </motion.div>

        {/* EXPORT */}
        <motion.div className="rounded-3xl p-6 bg-[#0d1a2e] border border-blue-900/30">
          <h2 className="text-xl font-semibold mb-4 text-blue-400">Export & Reports</h2>
          <div className="flex gap-4 flex-wrap">
            <button className="btn" onClick={exportCSV}>Export CSV</button>
            <button className="btn" onClick={exportPDF}>Export PDF</button>
          </div>
        </motion.div>

        {/* SAVE */}
        <div className="flex justify-end">
          <button onClick={saveSettings} disabled={saving} className="px-6 py-3 bg-emerald-600 hover:bg-emerald-500 rounded-xl">
            {saving ? "Saving…" : "Save Changes"}
          </button>
        </div>
      </div>
    </div>
  );
}
