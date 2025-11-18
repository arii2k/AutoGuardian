/* static/js/dashboard.js — AutoGuardian Dashboard (Enhanced Data + Full Visualization) */
(() => {
  const blob = document.getElementById('dataBlobs');
  let scanHistory = JSON.parse(blob?.dataset?.scanHistory || '[]');
  let collective = JSON.parse(blob?.dataset?.collective || '[]');

  const by = (sel, ctx = document) => ctx.querySelector(sel);
  const aiOverallScoreEl = by('#aiOverallScore');
  const aiRiskLabelEl = by('#aiRiskLabel');
  const threatIndexEl = by('#threatIndex');
  const totalScansEl = by('#totalScans');
  const highRiskPctEl = by('#highRiskPct');
  const quarantineCountEl = by('#quarantineCount');
  const refreshBtn = by('#refreshBtn');
  const lastRefEl = by('#lastRefreshed');

  let charts = {};
  const avg = arr => arr.length ? arr.reduce((a,b)=>a+b,0)/arr.length : 0;
  const fmt = n => isNaN(n) ? 0 : Math.round(n * 100) / 100;

  // === METRIC COMPUTATION ===
  function computeMetrics() {
    const scores = scanHistory.map(e => e.score || 0);
    const high = scores.filter(s => s >= 7).length;
    const med = scores.filter(s => s >= 4 && s < 7).length;
    const low = scores.filter(s => s < 4).length;
    const total = scores.length;

    const perDay = {};
    scanHistory.forEach(e => {
      const date = (e.timestamp || '').split('T')[0];
      if (!date) return;
      perDay[date] = (perDay[date] || 0) + 1;
    });

    const bySender = {};
    scanHistory.forEach(e => {
      const sender = e.sender || e.email_from || '';
      if (!sender) return;
      bySender[sender] = (bySender[sender] || 0) + 1;
    });

    const byRule = {};
    scanHistory.forEach(e => {
      const rules = (e.matched_rules || '').split(',').map(r => r.trim()).filter(Boolean);
      for (const r of rules) byRule[r] = (byRule[r] || 0) + 1;
    });

    const quarantine = scanHistory.filter(e => e.quarantine).length;
    const highPct = total ? fmt((high / total) * 100) : 0;

    return { high, med, low, perDay, bySender, byRule, quarantine, total, highPct };
  }

  // === RENDER CHARTS ===
  function renderCharts() {
    const { high, med, low, perDay, bySender, byRule } = computeMetrics();
    const destroy = id => charts[id]?.destroy();

    destroy('risk'); destroy('scans'); destroy('threats');
    destroy('senders'); destroy('rules'); destroy('trend');

    // Risk Distribution
    charts.risk = new Chart(by('#riskDonut').getContext('2d'), {
      type: 'doughnut',
      data: {
        labels: ['High', 'Medium', 'Low'],
        datasets: [{ data: [high, med, low],
          backgroundColor: ['#ef4444', '#eab308', '#22c55e'] }]
      },
      options: {
        cutout: '70%',
        plugins: {
          legend: { labels: { color: '#cbd5e1' } },
        }
      }
    });

    // Scans Over Time
    charts.scans = new Chart(by('#scansLine').getContext('2d'), {
      type: 'line',
      data: {
        labels: Object.keys(perDay),
        datasets: [{
          label: 'Emails Scanned',
          data: Object.values(perDay),
          borderColor: '#3b82f6',
          fill: true,
          backgroundColor: 'rgba(59,130,246,0.25)',
          tension: 0.3
        }]
      },
      options: {
        scales: {
          x: { ticks: { color:'#cbd5e1' } },
          y: { ticks: { color:'#cbd5e1' } }
        },
        plugins:{ legend:{ labels:{color:'#e2e8f0'} } }
      }
    });

    // Top Threat Senders (from scan history)
    const risky = Object.entries(bySender).sort((a,b)=>b[1]-a[1]).slice(0,7);
    charts.threats = new Chart(by('#topThreatsBar').getContext('2d'), {
      type: 'bar',
      data: {
        labels: risky.map(r=>r[0]),
        datasets: [{
          label:'Top Threat Senders',
          data: risky.map(r=>r[1]),
          backgroundColor:'#f87171'
        }]
      },
      options: {
        plugins:{ legend:{display:false}},
        scales:{x:{ticks:{color:'#cbd5e1'}},y:{ticks:{color:'#cbd5e1'}}}
      }
    });

    // Top Risky Senders (collective)
    const collSenders = {};
    collective.forEach(r => {
      if (r.sender) collSenders[r.sender] = (collSenders[r.sender] || 0) + 1;
    });
    const topSenders = Object.entries(collSenders).sort((a,b)=>b[1]-a[1]).slice(0,7);
    charts.senders = new Chart(by('#collectiveTopSenders').getContext('2d'), {
      type: 'bar',
      data: {
        labels: topSenders.map(s=>s[0]),
        datasets: [{
          label:'Top Risky Senders (Community)',
          data: topSenders.map(s=>s[1]),
          backgroundColor:'#facc15'
        }]
      },
      options:{ plugins:{legend:{display:false}},
        scales:{x:{ticks:{color:'#cbd5e1'}},y:{ticks:{color:'#cbd5e1'}}} }
    });

    // Top Matched Rules
    const topRules = Object.entries(byRule).sort((a,b)=>b[1]-a[1]).slice(0,7);
    charts.rules = new Chart(by('#collectiveTopRules').getContext('2d'), {
      type: 'bar',
      data: {
        labels: topRules.map(r=>r[0]),
        datasets: [{
          label:'Matched Rules',
          data: topRules.map(r=>r[1]),
          backgroundColor:'#60a5fa'
        }]
      },
      options:{ plugins:{legend:{display:false}},
        scales:{x:{ticks:{color:'#cbd5e1'}},y:{ticks:{color:'#cbd5e1'}}} }
    });

    // High-Risk Trend (collective)
    const riskOverTime = {};
    collective.forEach(r => {
      if (!r.timestamp) return;
      const day = r.timestamp.split('T')[0];
      if (r.risk_level === 'High' || r.risk_level === 'Suspicious')
        riskOverTime[day] = (riskOverTime[day] || 0) + 1;
    });
    charts.trend = new Chart(by('#collectiveHighRiskTrend').getContext('2d'), {
      type: 'line',
      data: {
        labels: Object.keys(riskOverTime),
        datasets: [{
          label:'High-Risk Trend Over Time',
          data:Object.values(riskOverTime),
          borderColor:'#f43f5e',
          backgroundColor:'rgba(244,63,94,0.25)',
          fill:true,
          tension:0.35
        }]
      },
      options: {
        scales:{x:{ticks:{color:'#cbd5e1'}},y:{ticks:{color:'#cbd5e1'}}},
        plugins:{legend:{labels:{color:'#cbd5e1'}}}
      }
    });
  }

  // === AI METRICS ===
  function updateAIMetrics() {
    const zs = scanHistory.map(e => e.ai_details?.zero_shot || e.score || 0);
    const tr = scanHistory.map(e => e.ai_details?.transformer || e.score || 0);
    const hy = scanHistory.map(e => e.ai_details?.hybrid_score || e.score || 0);

    const zsAvg = fmt(avg(zs)), trAvg = fmt(avg(tr)), hyAvg = fmt(avg(hy));
    const overall = Math.round(hyAvg);

    if (by('#aiZSAvg')) by('#aiZSAvg').textContent = zsAvg;
    if (by('#aiTRAvg')) by('#aiTRAvg').textContent = trAvg;
    if (by('#aiHYAvg')) by('#aiHYAvg').textContent = hyAvg;

    aiOverallScoreEl.textContent = overall;
    let trend = 'Stable';
    const sorted = hy.slice(-5);
    if (sorted.length >= 2) {
      const diff = sorted[sorted.length-1] - sorted[0];
      if (diff > 1) trend = 'Rising';
      else if (diff < -1) trend = 'Falling';
    }
    if (by('#aiTrend')) by('#aiTrend').textContent = trend;

    if (overall < 4) {
      aiRiskLabelEl.textContent = 'Safe';
      aiRiskLabelEl.className = 'low';
    } else if (overall < 7) {
      aiRiskLabelEl.textContent = 'Medium';
      aiRiskLabelEl.className = 'medium';
    } else {
      aiRiskLabelEl.textContent = 'High Risk';
      aiRiskLabelEl.className = 'high';
    }
  }

  // === DASHBOARD UPDATE ===
  function updateDashboard() {
    const { quarantine, total, highPct } = computeMetrics();
    totalScansEl.textContent = total;
    highRiskPctEl.textContent = `${highPct}%`;
    quarantineCountEl.textContent = quarantine;
    if (threatIndexEl) {
      const avgScore = avg(scanHistory.map(e => e.score || 0));
      threatIndexEl.textContent = fmt(avgScore * 3.1); // Weighted index
    }
    updateAIMetrics();
    renderCharts();
  }

  // === MANUAL RESCAN ===
  refreshBtn?.addEventListener('click', async () => {
    try {
      refreshBtn.textContent = 'Scanning...';
      const r = await fetch('/rescan', { method: 'POST' });
      if (!r.ok) throw new Error('Rescan failed');
      await r.json();
      location.reload();
    } catch (err) {
      alert(err.message);
    } finally {
      refreshBtn.textContent = 'Rescan now';
    }
  });

  // === AUTO REFRESH ===
  setInterval(async () => {
    try {
      const r = await fetch('/dashboard?json=1');
      if (!r.ok) return;
      const d = await r.json();
      scanHistory = d.scan_history || [];
      collective = d.collective_stats || [];
      updateDashboard();
      if (lastRefEl) lastRefEl.textContent = 'Last refreshed: ' + new Date().toLocaleString();
    } catch (e) {
      console.warn('Auto-refresh failed', e);
    }
  }, 180000);

  updateDashboard();
})();
