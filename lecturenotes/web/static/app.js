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

// --- 5: review ---------------------------------------------------------------------
// mdToHtml parses exactly the closed construct set our own MarkdownRenderer emits
// (pinned by tests/fixtures/notes/week01.md) — it is not a general markdown parser.

function escapeHtml(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function inline(text) {
  let html = escapeHtml(text);
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  return html;
}

function mdToHtml(markdown, assetSrc) {
  const lines = markdown.split("\n");
  const out = [];
  let i = 0;
  const paragraph = [];
  const flush = () => {
    if (paragraph.length) {
      out.push(`<p>${inline(paragraph.join(" "))}</p>`);
      paragraph.length = 0;
    }
  };
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { flush(); i += 1; continue; }
    if (line.startsWith("```")) {
      flush();
      const code = [];
      i += 1;
      while (i < lines.length && !lines[i].startsWith("```")) { code.push(lines[i]); i += 1; }
      i += 1;
      out.push(`<pre><code>${escapeHtml(code.join("\n"))}</code></pre>`);
      continue;
    }
    if (line.trim() === "$$") {
      flush();
      const math = [];
      i += 1;
      while (i < lines.length && lines[i].trim() !== "$$") { math.push(lines[i]); i += 1; }
      i += 1;
      out.push(`<pre class="math">${escapeHtml(math.join("\n"))}</pre>`);
      continue;
    }
    const heading = /^(#{1,3}) (.*)$/.exec(line);
    if (heading) {
      flush();
      const level = heading[1].length + 1; // page h1 is the site header
      out.push(`<h${level}>${inline(heading[2])}</h${level}>`);
      i += 1;
      continue;
    }
    if (/^\[\d+:\d\d/.test(line.trim())) { // the SourceAnchor citation line
      flush();
      out.push(`<p class="anchor">${escapeHtml(line.trim())}</p>`);
      i += 1;
      continue;
    }
    if (line.startsWith("> ")) {
      flush();
      const quoted = [];
      while (i < lines.length && lines[i].startsWith(">")) {
        quoted.push(lines[i].replace(/^> ?/, ""));
        i += 1;
      }
      const kind = /^\*\*(EXAM|PITFALL|UNCERTAIN|ASIDE)\*\*/.exec(quoted[0]);
      const cls = kind ? ` class="callout callout-${kind[1].toLowerCase()}"` : "";
      out.push(`<blockquote${cls}>${quoted.map(inline).join("<br>")}</blockquote>`);
      continue;
    }
    if (line.startsWith("|")) {
      flush();
      const rows = [];
      while (i < lines.length && lines[i].startsWith("|")) { rows.push(lines[i]); i += 1; }
      const cells = (row) => row.replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
      let html = "<table><thead><tr>";
      html += cells(rows[0]).map((c) => `<th>${inline(c)}</th>`).join("");
      html += "</tr></thead><tbody>";
      for (const row of rows.slice(2)) { // row 1 is the |---| separator
        html += `<tr>${cells(row).map((c) => `<td>${inline(c)}</td>`).join("")}</tr>`;
      }
      out.push(html + "</tbody></table>");
      continue;
    }
    if (/^\s*- /.test(line)) {
      flush();
      let html = "";
      let depth = -1;
      while (i < lines.length && /^\s*- /.test(lines[i])) {
        const item = /^(\s*)- (.*)$/.exec(lines[i]);
        const level = Math.floor(item[1].length / 2);
        while (depth < level) { html += "<ul><li>"; depth += 1; }
        while (depth > level) { html += "</li></ul>"; depth -= 1; }
        if (!html.endsWith("<li>")) html += `</li><li>`;
        html += inline(item[2]);
        i += 1;
      }
      while (depth >= 0) { html += "</li></ul>"; depth -= 1; }
      out.push(html);
      continue;
    }
    const figure = /^!\[(.*)\]\((.*)\)$/.exec(line.trim());
    if (figure) {
      flush();
      let caption = "";
      if (i + 1 < lines.length && /^\*[^*].*\*$/.test(lines[i + 1].trim())) {
        caption = `<figcaption>${inline(lines[i + 1].trim().slice(1, -1))}</figcaption>`;
        i += 1;
      }
      const src = assetSrc(figure[2]);
      out.push(
        `<figure><img src="${escapeHtml(src)}" alt="${escapeHtml(figure[1])}">${caption}</figure>`
      );
      i += 1;
      continue;
    }
    paragraph.push(line);
    i += 1;
  }
  flush();
  return out.join("\n");
}

function renderMarkdownPreview(container, result) {
  const bySuffix = {};
  for (const asset of result.assets) bySuffix[asset.id] = asset.source;
  const assetSrc = (src) => {
    // The page links asset_target ("assets/<id>.<ext>"); the bytes live at the
    // manifest's source path, served under /ws/ when workspace-relative.
    const id = src.replace(/^assets\//, "").replace(/\.[a-z]+$/, "");
    const source = bySuffix[id];
    if (!source) return src;
    return /^([a-zA-Z]:|\/)/.test(source) ? source : `/ws/${source}`;
  };
  const page = document.createElement("article");
  page.className = "md";
  page.innerHTML = result.documents.map((doc) => mdToHtml(doc.text, assetSrc)).join("<hr>");
  container.appendChild(page);
}

function renderAnkiPreview(container, result) {
  for (const doc of result.documents) {
    const rows = doc.text.split("\n").filter((l) => l && !l.startsWith("#"));
    const table = document.createElement("table");
    table.innerHTML =
      "<thead><tr><th>front</th><th>back</th><th>tags</th><th>guid</th></tr></thead>";
    const body = document.createElement("tbody");
    for (const row of rows) {
      const [guid, front, back, tags] = row.split("\t");
      const tr = document.createElement("tr");
      for (const value of [front, back, tags, guid]) {
        const td = document.createElement("td");
        td.textContent = (value || "").replace(/""/g, '"').replace(/^"|"$/g, "");
        tr.appendChild(td);
      }
      body.appendChild(tr);
    }
    table.appendChild(body);
    const count = document.createElement("p");
    count.className = "hint";
    count.textContent = `${rows.length} card(s) — File > Import in Anki updates in place`;
    container.appendChild(count);
    container.appendChild(table);
  }
}

function renderNotionPreview(container, result) {
  for (const doc of result.documents) {
    const payload = JSON.parse(doc.text);
    const histogram = {};
    const walk = (blocks) => {
      for (const block of blocks) {
        histogram[block.type] = (histogram[block.type] || 0) + 1;
        const children = block[block.type] && block[block.type].children;
        if (children) walk(children);
      }
    };
    for (const blocks of payload.payloads) walk(blocks);
    const summary = document.createElement("p");
    summary.textContent =
      `page "${payload.page.title}" - ${payload.payloads.length} payload(s), ` +
      Object.entries(histogram).map(([type, n]) => `${type}: ${n}`).join(", ");
    container.appendChild(summary);
    const details = document.createElement("details");
    const label = document.createElement("summary");
    label.textContent = "raw payload JSON";
    const pre = document.createElement("pre");
    pre.textContent = JSON.stringify(payload, null, 2);
    details.appendChild(label);
    details.appendChild(pre);
    container.appendChild(details);
  }
}

async function refreshWeeks(selectedId) {
  const select = $("week-select");
  const data = await api("GET", "/api/state");
  select.textContent = "";
  for (const week of data.weeks.filter((w) => w.valid)) {
    const option = document.createElement("option");
    option.value = week.id;
    option.textContent = `${week.file} (${week.lectures} lecture(s), ${week.topics} topic(s))`;
    select.appendChild(option);
  }
  if (selectedId) select.value = selectedId;
  await renderPreview();
}

// The last successful /api/render, so the download button can save exactly the
// bytes previewed. The doc text is \n-joined UTF-8 — the cmd_build file convention.
let lastRender = null;

const _DOWNLOAD_TYPES = {
  markdown: "text/markdown;charset=utf-8",
  anki: "text/plain;charset=utf-8",
};

function downloadRendered() {
  if (!lastRender) return;
  for (const doc of lastRender.result.documents) {
    const blob = new Blob([doc.text], { type: _DOWNLOAD_TYPES[lastRender.format] });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = doc.name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }
}

async function renderPreview() {
  const container = $("preview");
  container.textContent = "";
  setError("review-error", "");
  const download = $("download-rendered");
  download.hidden = true;
  lastRender = null;
  const week = $("week-select").value;
  if (!week) return;
  const format = document.querySelector("#format-tabs .active").dataset.format;
  try {
    const result = await api("GET", `/api/render?week=${encodeURIComponent(week)}&format=${format}`);
    if (format === "markdown") renderMarkdownPreview(container, result);
    else if (format === "anki") renderAnkiPreview(container, result);
    else renderNotionPreview(container, result);
    // Markdown and anki are file targets — offer the previewed file itself.
    // Notion's artifact is the push, not a download.
    if (format in _DOWNLOAD_TYPES) {
      lastRender = { format, result };
      download.textContent = `Download ${result.documents.map((d) => d.name).join(", ")}`;
      download.hidden = false;
    }
  } catch (error) {
    setError("review-error", error.message);
  }
  document.dispatchEvent(new CustomEvent("week-selected"));
}

function wireReview() {
  $("week-select").addEventListener("change", renderPreview);
  $("download-rendered").addEventListener("click", downloadRendered);
  for (const tab of document.querySelectorAll("#format-tabs .tab")) {
    tab.addEventListener("click", () => {
      document.querySelectorAll("#format-tabs .tab").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      renderPreview();
    });
  }
  document.addEventListener("week-written", () => {
    // After a build, jump the review panel to the freshly written week.
    api("GET", "/api/job")
      .then((job) => refreshWeeks(job.result && job.result.week_id))
      .catch(() => refreshWeeks());
  });
  refreshWeeks().catch((error) => setError("review-error", error.message));
}

// --- 6: push -----------------------------------------------------------------------

async function runPush() {
  setError("push-error", "");
  $("push-result").hidden = true;
  const parent = $("parent-page").value.trim();
  if (!parent) {
    setError("push-error", "a parent page id is required");
    return;
  }
  $("push-spinner").hidden = false;
  $("run-push").disabled = true;
  try {
    const data = await api("POST", "/api/push", {
      week_id: $("week-select").value,
      parent_page_id: parent,
    });
    const result = $("push-result");
    result.textContent =
      `pushed "${data.title}": ${data.payloads} payload(s), ${data.assets} asset(s)`;
    result.hidden = false;
  } catch (error) {
    setError("push-error", error.message);
  }
  $("push-spinner").hidden = true;
  updatePushGate();
}

function updatePushGate() {
  $("run-push").disabled = !$("week-select").value;
}

function wirePush() {
  $("run-push").addEventListener("click", runPush);
  document.addEventListener("week-selected", updatePushGate);
}

wireFilesAndPairing();
wireChunks();
wireBuild();
wireReview();
wirePush();
