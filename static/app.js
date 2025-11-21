let chart;
let poseModel, webcam, ctx, labelContainer, maxPredictions;
let isRunning = false;

const MODEL_URL = "/static/my-pose-model/";

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

async function sendPrediction(slouchProb) {
    try {
        await fetch("/api/dev/ingest-sample", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ slouch_prob: slouchProb })
        });
    } catch (err) {
        console.error("Failed to send prediction:", err);
    }
}

async function initPoseModel() {
    const statusEl = document.getElementById("modelStatus");
    const startBtn = document.getElementById("startButton");
    const stopBtn = document.getElementById("stopButton");
    
    try {
        statusEl.textContent = "Loading model...";
        startBtn.disabled = true;
        
        const modelURL = MODEL_URL + "model.json";
        const metadataURL = MODEL_URL + "metadata.json";
        
        poseModel = await tmPose.load(modelURL, metadataURL);
        maxPredictions = poseModel.getTotalClasses();
        
        statusEl.textContent = "Starting webcam...";
        
        const size = 400;
        const flip = true;
        webcam = new tmPose.Webcam(size, size, flip);
        await webcam.setup();
        await webcam.play();
        
        const canvas = document.getElementById("canvas");
        canvas.width = size;
        canvas.height = size;
        ctx = canvas.getContext("2d");
        
        labelContainer = document.getElementById("label-container");
        labelContainer.innerHTML = "";
        for (let i = 0; i < maxPredictions; i++) {
            labelContainer.appendChild(document.createElement("div"));
        }
        
        isRunning = true;
        startBtn.style.display = "none";
        stopBtn.style.display = "inline-block";
        statusEl.textContent = "✓ Model running";
        
        window.requestAnimationFrame(poseLoop);
        
    } catch (err) {
        statusEl.textContent = "Error: " + err.message;
        console.error(err);
        startBtn.disabled = false;
    }
}

async function poseLoop(timestamp) {
    if (!isRunning) return;
    
    webcam.update();
    await predictPose();
    window.requestAnimationFrame(poseLoop);
}

async function predictPose() {
    const { pose, posenetOutput } = await poseModel.estimatePose(webcam.canvas);

    const prediction = await poseModel.predict(posenetOutput);

    let slouchProb = 0;
    let slouchProbFromClass = null;
    let notSlouchProbFromClass = null;

    for (let i = 0; i < maxPredictions; i++) {
        const className = prediction[i].className;
        const probability = prediction[i].probability;
        const name = className.toLowerCase();

        const isNotSlouch =
            name.includes("not") ||
            name.includes("good") ||
            name.includes("upright");
        const isSlouch = name.includes("slouch");

        if (isNotSlouch) {
            notSlouchProbFromClass = probability;
        } else if (isSlouch) {
            slouchProbFromClass = probability;
        }

        const classPrediction = className + ": " + probability.toFixed(2);
        labelContainer.childNodes[i].innerHTML = classPrediction;
    }

    if (slouchProbFromClass !== null) {
        slouchProb = slouchProbFromClass;
    } else if (notSlouchProbFromClass !== null) {
        slouchProb = 1 - notSlouchProbFromClass;
    }

    slouchProb = Math.max(0, Math.min(1, slouchProb));

    await sendPrediction(slouchProb);
    
    drawPose(pose);
}

function drawPose(pose) {
    if (webcam.canvas) {
        ctx.drawImage(webcam.canvas, 0, 0);
        if (pose) {
            const minPartConfidence = 0.5;
            tmPose.drawKeypoints(pose.keypoints, minPartConfidence, ctx);
            tmPose.drawSkeleton(pose.keypoints, minPartConfidence, ctx);
        }
    }
}

function stopPoseModel() {
    isRunning = false;
    if (webcam) {
        webcam.stop();
    }
    document.getElementById("startButton").style.display = "inline-block";
    document.getElementById("stopButton").style.display = "none";
    document.getElementById("modelStatus").textContent = "Model stopped";
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
    const threshold = Number.isFinite(window.SLOUCH_THRESHOLD) ? window.SLOUCH_THRESHOLD : 0.6;

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

    // Compute simple posture splits for the displayed window.
    const total = vals.length;
    const slouchCount = vals.filter(v => v >= threshold).length;
    const slouchPct = total ? (slouchCount / total) * 100 : 0;
    const goodPct = total ? 100 - slouchPct : 0;

    const slouchEl = document.getElementById("metricSlouch");
    const goodEl = document.getElementById("metricGood");
    if (slouchEl) slouchEl.textContent = `Slouching: ${slouchPct.toFixed(1)}%`;
    if (goodEl) goodEl.textContent = `Good posture: ${goodPct.toFixed(1)}%`;
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
