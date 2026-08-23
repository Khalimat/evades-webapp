const API_BASE = "/api";

// --- tabs ---
document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(btn.dataset.tab).classList.add("active");
  });
});

function setStatus(msg) {
  document.getElementById("status").textContent = msg;
}

let lastResult = null;

// Raw JSON key -> display label for the results table. Keys not
// listed here just show as-is.
const COLUMN_LABELS = {
  query_name: "Query",
  query: "Query",
  adp: "ADP",
  defence: "Inhibited Defence",
  evalue: "E-value",
  score: "Score",
  hmm_from: "HMM From",
  hmm_to: "HMM To",
  ali_from: "Ali From",
  ali_to: "Ali To",
  seq_identity: "Seq Identity",
  aln_len: "Alignment Length",
  prob: "Probability",
  tm_score: "TM-score",
};

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderCell(col, value) {
  if (col === "adp" && value) {
    const safeId = encodeURIComponent(value);
    return `<a href="/explore/details/${safeId}/" target="_blank" rel="noopener noreferrer">${escapeHtml(value)}</a>`;
  }
  return escapeHtml(value);
}

function renderResults(job) {
  const el = document.getElementById("results");
  const downloadBtn = document.getElementById("downloadResultsBtn");

  lastResult = job.result;

  if (!job.result || !job.result.hits || job.result.hits.length === 0) {
    el.innerHTML = job.result ? "<p>No hits found.</p>" : "";
    downloadBtn.style.display = "none";
    return;
  }
  const hits = job.result.hits;
  const cols = Object.keys(hits[0]);
  let html = "<table><thead><tr>" + cols.map(c => `<th>${COLUMN_LABELS[c] || c}</th>`).join("") + "</tr></thead><tbody>";
  for (const hit of hits) {
    html += "<tr>" + cols.map(c => `<td>${renderCell(c, hit[c])}</td>`).join("") + "</tr>";
  }
  html += "</tbody></table>";
  el.innerHTML = html;
  downloadBtn.style.display = "inline-block";
}

function downloadResultsCsv() {
  if (!lastResult || !lastResult.hits || lastResult.hits.length === 0) return;

  const hits = lastResult.hits;
  const cols = Object.keys(hits[0]);

  const escapeCell = (val) => {
    const str = String(val);
    if (/[",\n]/.test(str)) {
      return `"${str.replace(/"/g, '""')}"`;
    }
    return str;
  };

  const lines = [
    cols.map(c => escapeCell(COLUMN_LABELS[c] || c)).join(","),
    ...hits.map(hit => cols.map(c => escapeCell(hit[c])).join(","))
  ];
  const csvContent = lines.join("\n");

  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${lastResult.tool || "search"}_results.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

async function pollJob(jobId) {
  setStatus("Queued...");
  while (true) {
    const res = await fetch(`${API_BASE}/jobs/${jobId}`);
    const job = await res.json();

    if (job.status === "finished") {
      setStatus(`Done — ${job.result.n_hits} hit(s) found.`);
      renderResults(job);
      return;
    }
    if (job.status === "failed") {
      setStatus(`Failed: ${job.error || "unknown error"}`);
      return;
    }
    setStatus(`Status: ${job.status}...`);
    await new Promise(r => setTimeout(r, 2000));
  }
}

async function submitHmm() {
  const input = document.getElementById("fastaInput");
  if (!input.files.length) { alert("Choose a FASTA file first"); return; }

  const formData = new FormData();
  formData.append("fasta", input.files[0]);

  setStatus("Uploading...");
  const res = await fetch(`${API_BASE}/search/hmm`, { method: "POST", body: formData });
  if (!res.ok) { setStatus("Upload failed"); return; }
  const job = await res.json();
  pollJob(job.id);
}

async function submitStructure() {
  const input = document.getElementById("pdbInput");
  if (!input.files.length) { alert("Choose a PDB file first"); return; }

  const formData = new FormData();
  formData.append("pdb", input.files[0]);

  setStatus("Uploading...");
  const res = await fetch(`${API_BASE}/search/structure`, { method: "POST", body: formData });
  if (!res.ok) { setStatus("Upload failed"); return; }
  const job = await res.json();
  pollJob(job.id);
}
