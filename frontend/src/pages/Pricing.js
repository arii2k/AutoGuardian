// src/pages/Pricing.js — AutoGuardian AI (final synced version)
import { useState, useEffect } from "react";
import { motion } from "framer-motion";

export default function Pricing() {
  const [loadingPlan, setLoadingPlan] = useState("");
  const [currentPlan, setCurrentPlan] = useState("");
  const [subscriptionActive, setSubscriptionActive] = useState(false);

  // Load current plan from backend
  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch("http://127.0.0.1:5000/api/me", {
          credentials: "include",
        });
        const json = await res.json();
        setCurrentPlan(json.plan || "free");
        setSubscriptionActive(json.subscription_active || false);
      } catch (err) {
        console.error("Failed to load current plan", err);
      }
    };
    load();
  }, []);

  // -------------------------
  // HANDLE SUBSCRIBE
  // -------------------------
  const handleSubscribe = async (plan) => {
    try {
      setLoadingPlan(plan);

      const res = await fetch("http://127.0.0.1:5000/auth/subscribe", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan }),
      });

      // Paddle redirect (mock)
      if (res.redirected) {
        window.location.href = res.url;
        return;
      }

      const data = await res.json();
      if (!res.ok) {
        alert(data.error || "Subscription error");
        return;
      }

      alert("🎉 Your subscription plan has been updated!");
      window.location.href = "/settings";
    } catch (err) {
      console.error(err);
      alert("❌ Subscription failed");
    } finally {
      setLoadingPlan("");
    }
  };

  // -------------------------
  // PLAN TIERS (backend synced)
  // -------------------------
  const tiers = [
    {
      name: "Free",
      plan: "free",
      price: "$0/mo",
      features: [
        "1 Gmail inbox",
        "Basic threat detection",
        "No IMAP Support",
        "Weekly scans",
      ],
    },
    {
      name: "Starter",
      plan: "starter",
      price: "$5/mo",
      features: [
        "1 inbox (Gmail or IMAP)",
        "AI threat model",
        "Daily scans",
        "Quarantine folder",
      ],
    },
    {
      name: "Pro",
      plan: "pro",
      price: "$15/mo",
      features: [
        "2 inboxes",
        "Real-time scanning",
        "Gmail + IMAP",
        "Advanced AI & memory alerts",
      ],
    },
    {
      name: "Business",
      plan: "business",
      price: "$49/mo",
      features: [
        "5 inboxes",
        "Team dashboard",
        "Behavior AI",
        "Priority support",
      ],
    },
    {
      name: "Enterprise",
      plan: "enterprise",
      price: "Custom",
      features: [
        "Unlimited inboxes",
        "SLA + security audits",
        "Admin controls",
        "Dedicated support line",
      ],
    },
  ];

  return (
    <div className="min-h-screen p-12 bg-gradient-to-br from-[#0a0f24] to-[#12224d] text-white">
      <motion.h1
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-4xl font-bold text-center mb-12"
      >
        Choose Your Plan
      </motion.h1>

      {/* Current Plan Indicator */}
      <div className="text-center mb-10 text-lg text-blue-300">
        <p>
          Current Plan:{" "}
          <span className="font-semibold text-emerald-400">
            {currentPlan.charAt(0).toUpperCase() + currentPlan.slice(1)}
          </span>
        </p>
        {!subscriptionActive && (
          <p className="text-red-400 text-sm mt-1">
            ⚠ No active subscription – please choose a plan
          </p>
        )}
      </div>

      {/* Pricing Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-8">
        {tiers.map((tier, i) => {
          const isCurrent = tier.plan === currentPlan;

          return (
            <motion.div
              key={tier.plan}
              initial={{ opacity: 0, y: 25 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1 }}
              className={`rounded-3xl p-6 border shadow-xl flex flex-col
                ${
                  isCurrent
                    ? "bg-[#102040] border-emerald-500/60 shadow-emerald-500/40"
                    : "bg-[#0d1a2e] border-[#1e3a8a]/30"
                }
              `}
            >
              <h2 className="text-xl font-bold mb-2">{tier.name}</h2>

              <p
                className={`text-3xl font-semibold ${
                  isCurrent ? "text-emerald-300" : "text-blue-300"
                }`}
              >
                {tier.price}
              </p>

              {/* Features */}
              <ul className="mt-4 text-sm text-gray-300 space-y-2 flex-1">
                {tier.features.map((f, idx) => (
                  <li key={idx}>• {f}</li>
                ))}
              </ul>

              {/* Button */}
              <button
                disabled={loadingPlan === tier.plan || isCurrent}
                onClick={() => handleSubscribe(tier.plan)}
                className={`mt-6 px-4 py-2 rounded-xl font-medium transition ${
                  isCurrent
                    ? "bg-gray-700 cursor-default"
                    : loadingPlan === tier.plan
                    ? "bg-gray-600 cursor-not-allowed"
                    : "bg-blue-600 hover:bg-blue-500"
                }`}
              >
                {isCurrent
                  ? "Current Plan"
                  : loadingPlan === tier.plan
                  ? "Processing…"
                  : "Subscribe"}
              </button>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
