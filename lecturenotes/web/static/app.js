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

wireFilesAndPairing();
