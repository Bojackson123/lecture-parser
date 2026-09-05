// The lecturenotes GUI. No framework, no build step: fetch + DOM.
// State flows top to bottom like the pipeline: files -> pairing -> (later panels).
"use strict";

const state = {
  paths: [],      // strings the server understands (workspace-relative or absolute)
  pairs: null,    // last /api/pair result, or null
  confirmed: false,
};

const $ = (id) => document.getElementById(id);

async function api(method, url, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers["content-type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const response = await fetch(url, opts);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `${method} ${url}: HTTP ${response.status}`);
  return data;
}

function setError(id, message) {
  const el = $(id);
  el.textContent = message || "";
  el.hidden = !message;
}

// --- 1: files ----------------------------------------------------------------------

function weekSlug() {
  const raw = $("week-slug").value.trim() || "week";
  return raw.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "week";
}

function renderFileList() {
  const list = $("file-list");
  list.textContent = "";
  for (const path of state.paths) {
    const item = document.createElement("li");
    item.textContent = path;
    list.appendChild(item);
  }
}

async function addUploads(fileList) {
  setError("files-error", "");
  const form = new FormData();
  for (const file of fileList) form.append("files", file);
  try {
    const data = await fetch(`/api/upload?week=${encodeURIComponent(weekSlug())}`, {
      method: "POST",
      body: form,
    }).then(async (response) => {
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.error || `upload: HTTP ${response.status}`);
      return body;
    });
    for (const path of data.paths) {
      if (!state.paths.includes(path)) state.paths.push(path);
    }
    renderFileList();
    await refreshPairing();
  } catch (error) {
    setError("files-error", error.message);
  }
}

function addFolder() {
  const folder = $("folder-path").value.trim();
  if (!folder) return;
  if (!state.paths.includes(folder)) state.paths.push(folder);
  $("folder-path").value = "";
  renderFileList();
  refreshPairing();
}

// --- 2: pairing --------------------------------------------------------------------

function setConfirmed(value) {
  state.confirmed = value;
  $("confirm-pairing").checked = value;
  document.dispatchEvent(new CustomEvent("pairing-changed"));
}

async function refreshPairing() {
  setConfirmed(false);
  state.pairs = null;
  const table = $("pairing-table");
  const confirmRow = $("confirm-row");
  setError("pairing-error", "");
  table.hidden = true;
  confirmRow.hidden = true;
  if (!state.paths.length) return;
  try {
    const data = await api("POST", "/api/pair", { paths: state.paths });
    state.pairs = data.pairs;
    const body = table.querySelector("tbody");
    body.textContent = "";
    for (const pair of data.pairs) {
      const row = document.createElement("tr");
      for (const value of [pair.lecture_id, pair.deck, pair.captions]) {
        const cell = document.createElement("td");
        cell.textContent = value;
        row.appendChild(cell);
      }
      body.appendChild(row);
    }
    table.hidden = false;
    confirmRow.hidden = false;
  } catch (error) {
    setError("pairing-error", error.message);
  }
  document.dispatchEvent(new CustomEvent("pairing-changed"));
}

function wireFilesAndPairing() {
  const zone = $("dropzone");
  zone.addEventListener("dragover", (event) => {
    event.preventDefault();
    zone.classList.add("drag");
  });
  zone.addEventListener("dragleave", () => zone.classList.remove("drag"));
  zone.addEventListener("drop", (event) => {
    event.preventDefault();
    zone.classList.remove("drag");
    if (event.dataTransfer.files.length) addUploads(event.dataTransfer.files);
  });
  $("filepick").addEventListener("change", (event) => {
    if (event.target.files.length) addUploads(event.target.files);
    event.target.value = "";
  });
  $("add-folder").addEventListener("click", addFolder);
  $("folder-path").addEventListener("keydown", (event) => {
    if (event.key === "Enter") addFolder();
  });
  $("confirm-pairing").addEventListener("change", (event) => {
    state.confirmed = event.target.checked;
    document.dispatchEvent(new CustomEvent("pairing-changed"));
  });
}

// --- 3: chunk preview (dry-run) ----------------------------------------------------

function formatClock(seconds) {
  const total = Math.floor(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = String(total % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${s}` : `${m}:${s}`;
}

function chunkTable(lecture) {
  const wrap = document.createElement("div");
  const heading = document.createElement("h3");
  heading.textContent = `${lecture.lecture_id}: ${lecture.deck} + ${lecture.captions}`;
  wrap.appendChild(heading);
  const table = document.createElement("table");
  table.innerHTML =
    "<thead><tr><th>slides</th><th>span</th><th>words</th><th>title</th></tr></thead>";
  const body = document.createElement("tbody");
  for (const chunk of lecture.chunks) {
    const row = document.createElement("tr");
    const slides = document.createElement("td");
    if (chunk.gap) {
      const badge = document.createElement("span");
      badge.className = "gap-badge";
      badge.textContent = "gap - board work";
      slides.appendChild(badge);
    } else {
      slides.textContent =
        chunk.slides.start === chunk.slides.end
          ? `slide ${chunk.slides.start}`
          : `slides ${chunk.slides.start}-${chunk.slides.end}`;
    }
    row.appendChild(slides);
    for (const value of [
      `${formatClock(chunk.start_s)}–${formatClock(chunk.end_s)}`,
      String(chunk.words),
      chunk.title || "",
    ]) {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.appendChild(cell);
    }
    body.appendChild(row);
  }
  table.appendChild(body);
  wrap.appendChild(table);
  return wrap;
}

async function runDryRun() {
  setError("chunks-error", "");
  $("request-count").textContent = "";
  const tables = $("chunk-tables");
  tables.textContent = "";
  state.dryRun = null;
  try {
    const data = await api("POST", "/api/dry-run", {
      paths: state.paths,
      min_words: Number($("min-words").value) || 100,
    });
    state.dryRun = data;
    for (const lecture of data.lectures) tables.appendChild(chunkTable(lecture));
    $("request-count").textContent =
      `${data.total_requests} API request(s) when built (responses are cached)`;
  } catch (error) {
    setError("chunks-error", error.message);
  }
  document.dispatchEvent(new CustomEvent("dry-run-changed"));
}

function wireChunks() {
  $("run-dry-run").addEventListener("click", runDryRun);
  document.addEventListener("pairing-changed", () => {
    $("run-dry-run").disabled = !state.pairs;
    // A changed pairing invalidates any preview on screen.
    if (state.dryRun) {
      state.dryRun = null;
      $("chunk-tables").textContent = "";
      $("request-count").textContent = "";
      document.dispatchEvent(new CustomEvent("dry-run-changed"));
    }
  });
}

// --- 4: build ----------------------------------------------------------------------

function updateBuildGate() {
  const ready = Boolean(state.pairs && state.confirmed && state.dryRun);
  $("run-build").disabled = !ready;
  $("build-gate-hint").hidden = ready;
}

function showJob(job) {
  const progress = $("build-progress");
  const result = $("build-result");
  if (!job) return;
  if (job.state === "running") {
    progress.hidden = false;
    $("progress-bar").max = job.total || 1;
    $("progress-bar").value = job.total ? job.done : 0;
    $("progress-text").textContent = job.total
      ? `${job.done}/${job.total} requests (${job.phase})`
      : job.phase;
    $("progress-current").textContent = job.current || "";
  } else {
    progress.hidden = true;
    if (job.state === "done") {
      const r = job.result;
      result.textContent =
        `wrote ${r.file}: ${r.lectures} lecture(s), ${r.topics} topic(s), ${r.assets} asset(s)`;
      result.hidden = false;
      document.dispatchEvent(new CustomEvent("week-written"));
    } else {
      setError("build-error", job.error || "build failed");
    }
  }
}

async function pollJob() {
  try {
    const job = await api("GET", "/api/job");
    showJob(job);
    if (job.state === "running") setTimeout(pollJob, 500);
  } catch (error) {
    setError("build-error", error.message);
  }
}

async function runBuild() {
  setError("build-error", "");
  $("build-result").hidden = true;
  const course = $("course").value.trim();
  if (!course) {
    setError("build-error", "course is required (e.g. CS-RL-101)");
    return;
  }
  try {
    await api("POST", "/api/build", {
      paths: state.paths,
      course,
      week: Number($("week-number").value) || 1,
      min_words: Number($("min-words").value) || 100,
      pairs: state.pairs,
    });
    pollJob();
  } catch (error) {
    setError("build-error", error.message);
  }
}

function wireBuild() {
  $("run-build").addEventListener("click", runBuild);
  document.addEventListener("pairing-changed", updateBuildGate);
  document.addEventListener("dry-run-changed", updateBuildGate);
  // A build that was running when the page loaded keeps reporting.
  api("GET", "/api/state")
    .then((data) => {
      if (data.job) {
        showJob(data.job);
        if (data.job.state === "running") pollJob();
      }
    })
    .catch(() => {});
}

wireFilesAndPairing();
wireChunks();
wireBuild();
