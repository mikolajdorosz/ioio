const MAX_FILES = 2;
const MAX_BYTES = 250 * 1024 * 1024;
const labels = { flac: "FLAC", mp3: "MP3", wav: "WAV", jpg: "JPG", png: "PNG", heic: "HEIC", gif: "GIF", mp4: "MP4", mov: "MOV" };
const targets = {
  flac: ["mp3", "wav"], mp3: ["flac", "wav"], wav: ["flac", "mp3"],
  jpg: ["png", "heic"], png: ["jpg", "heic"], heic: ["jpg", "png"],
  gif: ["mp4", "mov"], mp4: ["gif", "mov"], mov: ["gif", "mp4"],
};
const warnings = {
  mp3: "MP3 jest formatem stratnym. Konwersja do formatu bezstratnego nie odzyska utraconej jakości.",
  jpg: "JPG jest formatem stratnym. Przezroczystość zostanie zastąpiona białym tłem.",
  heic: "HEIC jest formatem stratnym. Wynik może mieć niższą jakość niż źródło.",
  gif: "GIF obsługuje do 256 kolorów i nie zawiera dźwięku.",
  mp4: "MP4 jest formatem stratnym. Wynik może mieć niższą jakość niż źródło.",
  mov: "MOV może wymagać ponownego kodowania, gdy kodeki źródła nie pasują do kontenera.",
};

const state = { selected: [], tasks: [], poller: null, email: "", user: null };
const el = (id) => document.getElementById(id);
const loginView = el("login-view");
const appView = el("app-view");
const notice = el("notice");

function showNotice(message, type = "") {
  notice.textContent = message;
  notice.className = `notice ${type}`;
  window.clearTimeout(showNotice.timeout);
  showNotice.timeout = window.setTimeout(() => notice.classList.add("hidden"), 6500);
}

async function api(path, options = {}) {
  const response = await fetch(path, { credentials: "same-origin", ...options });
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : null;
  if (!response.ok) throw new Error(payload?.detail || "Wystąpił nieoczekiwany błąd.");
  return payload;
}

function formBody(values) {
  const body = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => body.set(key, value));
  return body;
}

function extension(file) {
  const raw = file.name.split(".").pop()?.toLowerCase() || "";
  return raw === "jpeg" ? "jpg" : raw;
}

function formatSize(bytes) {
  if (bytes < 1024 * 1024) return `${Math.ceil(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1).replace(".", ",")} MB`;
}

function targetWarning(source, target) {
  if (source === "mp3" && ["flac", "wav"].includes(target)) return warnings.mp3;
  return warnings[target] || "";
}

function renderSelection() {
  const panel = el("selected-panel");
  const container = el("selected-files");
  const warningBox = el("warnings");
  container.replaceChildren();
  warningBox.replaceChildren();
  panel.classList.toggle("hidden", !state.selected.length);
  state.selected.forEach((entry, index) => {
    const row = document.createElement("div");
    row.className = "file-row";
    const info = document.createElement("div");
    const name = document.createElement("span");
    name.className = "file-name";
    name.textContent = entry.file.name;
    const details = document.createElement("div");
    details.className = "file-details";
    details.textContent = `${labels[entry.source] || "nierozpoznane rozszerzenie"} • ${formatSize(entry.file.size)}`;
    info.append(name, details);
    const select = document.createElement("select");
    select.setAttribute("aria-label", `Format docelowy dla ${entry.file.name}`);
    const options = targets[entry.source] || [];
    if (!options.length) {
      const option = new Option("Nierozpoznany format", "");
      select.add(option);
      select.disabled = true;
    } else {
      options.forEach((format) => select.add(new Option(`Zamień na ${labels[format]}`, format)));
      select.value = entry.target;
      select.addEventListener("change", () => { entry.target = select.value; renderSelection(); });
    }
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "text-button remove-file";
    remove.textContent = "Usuń";
    remove.addEventListener("click", () => {
      state.selected.splice(index, 1);
      renderSelection();
    });
    row.append(info, select, remove);
    container.append(row);
    const warning = targetWarning(entry.source, entry.target);
    if (warning) {
      const warningEl = document.createElement("div");
      warningEl.className = "warning";
      warningEl.textContent = `${entry.file.name}: ${warning}`;
      warningBox.append(warningEl);
    }
  });
}

function addFiles(list) {
  const incoming = Array.from(list);
  if (state.selected.length + incoming.length > MAX_FILES) {
    showNotice("Jedno zadanie może zawierać najwyżej dwa pliki.", "error");
    return;
  }
  for (const file of incoming) {
    if (file.size > MAX_BYTES) {
      showNotice(`${file.name} przekracza limit 250 MB.`, "error");
      continue;
    }
    const source = extension(file);
    if (!targets[source]) {
      showNotice(`${file.name} ma nieobsługiwane rozszerzenie.`, "error");
      continue;
    }
    state.selected.push({ file, source, target: targets[source][0] });
  }
  renderSelection();
}

async function submitEmail(event) {
  event.preventDefault();
  const button = event.submitter;
  const email = el("email").value.trim();
  button.disabled = true;
  try {
    const payload = await api("/api/auth/request-code", { method: "POST", body: formBody({ email }) });
    state.email = email;
    el("email-form").classList.add("hidden");
    el("code-form").classList.remove("hidden");
    const preview = el("development-code");
    preview.classList.toggle("hidden", !payload.development_code);
    preview.textContent = payload.development_code ? `Tryb programisty — kod: ${payload.development_code}` : "";
    el("otp-code").focus();
    showNotice(payload.message, "success");
  } catch (error) { showNotice(error.message, "error"); }
  finally { button.disabled = false; }
}

async function submitCode(event) {
  event.preventDefault();
  const button = event.submitter;
  button.disabled = true;
  try {
    const payload = await api("/api/auth/verify", { method: "POST", body: formBody({ email: state.email, code: el("otp-code").value.trim() }) });
    state.user = payload.user;
    enterApp();
    showNotice("Zalogowano. Możesz dodać pliki do konwersji.", "success");
  } catch (error) { showNotice(error.message, "error"); }
  finally { button.disabled = false; }
}

function enterApp() {
  loginView.classList.add("hidden");
  appView.classList.remove("hidden");
  el("account").classList.remove("hidden");
  el("user-email").textContent = state.user.email;
  el("admin-button").classList.toggle("hidden", !state.user.is_admin);
  loadTasks();
}

function leaveApp() {
  state.user = null;
  state.selected = [];
  state.tasks = [];
  window.clearInterval(state.poller);
  state.poller = null;
  renderSelection();
  loginView.classList.remove("hidden");
  appView.classList.add("hidden");
  el("account").classList.add("hidden");
  el("code-form").classList.add("hidden");
  el("email-form").classList.remove("hidden");
  el("otp-code").value = "";
}

async function convertFiles() {
  if (!state.selected.length) return;
  const button = el("convert-button");
  button.disabled = true;
  const body = new FormData();
  state.selected.forEach((entry) => {
    body.append("files", entry.file, entry.file.name);
    body.append("target_formats", entry.target);
  });
  try {
    await api("/api/tasks", { method: "POST", body });
    state.selected = [];
    el("file-input").value = "";
    renderSelection();
    showNotice("Pliki przyjęto do kolejki konwersji.", "success");
    await loadTasks();
  } catch (error) { showNotice(error.message, "error"); }
  finally { button.disabled = false; }
}

function statusClass(value) { return value.replaceAll(" ", "-"); }
function dateLabel(value) { return value ? new Intl.DateTimeFormat("pl-PL", { dateStyle: "short", timeStyle: "short" }).format(new Date(value)) : ""; }

function renderTasks() {
  const root = el("tasks");
  root.replaceChildren();
  if (!state.tasks.length) {
    const empty = document.createElement("p"); empty.className = "empty"; empty.textContent = "Nie masz jeszcze żadnych zadań."; root.append(empty); return;
  }
  state.tasks.forEach((task) => {
    const card = document.createElement("article"); card.className = "card task";
    const top = document.createElement("div"); top.className = "task-top";
    const title = document.createElement("div"); title.className = "task-title"; title.textContent = `Zadanie z ${dateLabel(task.created_at)}`;
    const taskPill = document.createElement("span"); taskPill.className = `pill ${statusClass(task.status)}`; taskPill.textContent = task.status;
    top.append(title, taskPill); card.append(top);
    const files = document.createElement("div"); files.className = "task-files";
    task.files.forEach((file) => {
      const row = document.createElement("div"); row.className = "task-file";
      const info = document.createElement("div");
      const name = document.createElement("strong"); name.textContent = `${file.original_name} → ${labels[file.target_format]}`;
      info.append(name);
      if (file.error) { const error = document.createElement("p"); error.className = "file-error"; error.textContent = file.error; info.append(error); }
      const pill = document.createElement("span"); pill.className = `pill ${statusClass(file.status)}`; pill.textContent = file.status;
      const actions = document.createElement("div"); actions.className = "task-actions";
      if (file.can_download) { const download = document.createElement("a"); download.className = "download-link"; download.href = `/api/files/${file.id}/download`; download.textContent = "Pobierz"; actions.append(download); }
      if (file.can_retry) { const retry = document.createElement("button"); retry.className = "text-button"; retry.type = "button"; retry.textContent = "Ponów"; retry.addEventListener("click", () => retryFile(file.id)); actions.append(retry); }
      if (file.delete_at) { const expires = document.createElement("span"); expires.className = "file-details"; expires.textContent = `Usunięcie: ${dateLabel(file.delete_at)}`; actions.append(expires); }
      row.append(info, pill, actions); files.append(row);
    });
    card.append(files); root.append(card);
  });
}

async function loadTasks() {
  try {
    const payload = await api("/api/tasks");
    state.tasks = payload.tasks;
    renderTasks();
    const active = state.tasks.some((task) => task.files.some((file) => ["oczekuje", "w toku"].includes(file.status)));
    window.clearInterval(state.poller);
    state.poller = active ? window.setInterval(loadTasks, 3000) : null;
  } catch (error) {
    if (/Zaloguj|Sesja/.test(error.message)) leaveApp(); else showNotice(error.message, "error");
  }
}

async function retryFile(id) {
  try { await api(`/api/files/${id}/retry`, { method: "POST" }); showNotice("Plik ponownie dodano do kolejki.", "success"); await loadTasks(); }
  catch (error) { showNotice(error.message, "error"); }
}

async function showLogs() {
  try { const payload = await api("/api/admin/logs"); el("logs-content").textContent = payload.logs || "Dziennik jest pusty."; el("logs-dialog").showModal(); }
  catch (error) { showNotice(error.message, "error"); }
}

function bindEvents() {
  el("email-form").addEventListener("submit", submitEmail);
  el("code-form").addEventListener("submit", submitCode);
  el("back-to-email").addEventListener("click", () => { el("code-form").classList.add("hidden"); el("email-form").classList.remove("hidden"); });
  el("choose-files").addEventListener("click", () => el("file-input").click());
  el("file-input").addEventListener("change", (event) => addFiles(event.target.files));
  el("clear-files").addEventListener("click", () => { state.selected = []; renderSelection(); });
  el("convert-button").addEventListener("click", convertFiles);
  el("refresh-tasks").addEventListener("click", loadTasks);
  el("logout-button").addEventListener("click", async () => { await api("/api/auth/logout", { method: "POST" }); leaveApp(); showNotice("Wylogowano."); });
  el("admin-button").addEventListener("click", showLogs);
  const drop = el("drop-zone");
  ["dragenter", "dragover"].forEach((type) => drop.addEventListener(type, (event) => { event.preventDefault(); drop.classList.add("active"); }));
  ["dragleave", "drop"].forEach((type) => drop.addEventListener(type, (event) => { event.preventDefault(); drop.classList.remove("active"); }));
  drop.addEventListener("drop", (event) => addFiles(event.dataTransfer.files));
  drop.addEventListener("keydown", (event) => { if (["Enter", " "].includes(event.key)) { event.preventDefault(); el("file-input").click(); } });
}

async function bootstrap() {
  bindEvents();
  try { const payload = await api("/api/me"); state.user = payload.user; enterApp(); } catch (_) { /* login is the expected initial state */ }
}

bootstrap();
