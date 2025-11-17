let chart;

async function fetchJSON(url) {
    const res = await fetch(url);
    return res.json();
}

function setStatus(isSlouch) {
    const el = document.getElementById("statusBadge");
    el.textContent = isSlouch ? "SLOUCHING" : "GOOD POSTURE";
    el.classList.remove("ok", "bad");
    el.classList.add(isSlouch ? "bad" : "ok");
}

function setGauge(prob) {
    const pct = Math.max(0, Math.min(1, prob)) * 100;
    document.getElementById("gaugeFill").style.width = pct.toFixed(1) + "%";
    document.getElementById("slouchProb").textContent = prob.toFixed(2);
}

async function refreshLatest() {
    const data = await fetchJSON("/api/latest");
    if (!data.ok || !data.latest) return;
    setStatus(data.latest.is_slouch);
    setGauge(data.latest.slouch_prob);
    document.getElementById("lastTs").textContent = data.latest.ts;
}

async function refreshSeries() {
    const data = await fetchJSON("/api/metrics?minutes=30");
    if (!data.ok) return;
    const labels = data.series.map(p => p.ts);
    const vals = data.series.map(p => p.slouch_prob);

    if (!chart) {
        const ctx = document.getElementById("tsChart");
        chart = new Chart(ctx, {
            type: "line",
            data: {
                labels,
                datasets: [{
                    label: "Slouch probability",
                    data: vals,
                    tension: 0.2,
                    fill: false,
                    pointRadius: 0,
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: { suggestedMin: 0, suggestedMax: 1 },
                    x: { ticks: { maxTicksLimit: 6 } }
                },
                plugins: { legend: { display: false } }
            }
        });
    } else {
        chart.data.labels = labels;
        chart.data.datasets[0].data = vals;
        chart.update();
    }
}

async function refreshEvents() {
    const data = await fetchJSON("/api/events?limit=20");
    const body = document.getElementById("eventsBody");
    body.innerHTML = "";
    (data.events || []).forEach(e => {
        const tr = document.createElement("tr");
        tr.innerHTML = `<td>${e.ts}</td><td>${e.type}</td><td>${e.prob.toFixed(2)}</td>`;
        body.appendChild(tr);
    });
}

async function tick() {
    await Promise.all([refreshLatest(), refreshSeries(), refreshEvents()]);
}

window.addEventListener("load", () => {
    tick();
    setInterval(refreshLatest, 1500);
    setInterval(refreshSeries, 5000);
    setInterval(refreshEvents, 5000);
});