import { DEFAULT_FILTERS, DURATIONS, catalogOptions, formatDuration, selectSet } from "./selection.js";
import { SetPlayer } from "./player.js";

const $ = id => document.getElementById(id);
const ui = Object.fromEntries(["genre", "duration", "year", "reset", "next", "reload", "frame-message", "frame-message-title", "frame-message-detail", "loader", "player-frame", "player-error", "set-title", "metadata", "genres", "set-duration", "set-year", "catalog-total", "selection-note", "announcement", "play-hint", "set-eyebrow"].map(id => [id, $(id)]));
const state = { catalog: [], filters: { ...DEFAULT_FILTERS }, currentVideoId: null, catalogStatus: "loading", playerStatus: "idle", selectionVersion: 0, candidates: 0, item: null };
let catalogController;
let catalogVersion = 0;
const preview = document.body.dataset.preview === "true";
$("demo-notice").hidden = !preview;

function announce(message) { ui.announcement.textContent = message; }
function controls() {
  const disabled = state.catalogStatus !== "ready";
  for (const key of ["genre", "duration", "year", "reset"]) ui[key].disabled = disabled;
  ui.next.disabled = disabled || state.candidates < 2 || state.playerStatus === "loading";
}
function frame(title, detail, loading = false, reload = false) {
  ui["frame-message"].hidden = false;
  ui["frame-message-title"].textContent = title;
  ui["frame-message-detail"].textContent = detail;
  ui.loader.hidden = !loading;
  ui.reload.hidden = !reload;
  ui["player-frame"].setAttribute("aria-busy", String(loading));
}

const player = new SetPlayer($("youtube-player"), ({ status, message, version }) => {
  if (version !== state.selectionVersion) return;
  state.playerStatus = status;
  ui["player-frame"].setAttribute("aria-busy", String(status === "loading"));
  ui["player-error"].hidden = status !== "error";
  ui["player-error"].textContent = status === "error" ? message : "";
  if (status === "loading") frame("Loading player", "The video will only start when you press Play.", true);
  else if (status === "error" && !$("youtube-player").querySelector("iframe")) frame("Player unavailable", "You can choose another set or change the filters.");
  else ui["frame-message"].hidden = true;
  if (status === "error") announce(message);
  else if (status === "ready") announce(`${state.item.title}. ${state.candidates} sets available. Press Play to listen.`);
  controls();
});

function renderItem(item) {
  ui.metadata.hidden = !item;
  ui["play-hint"].hidden = !item;
  ui["set-eyebrow"].hidden = !item;
  if (!item) return;
  ui["set-title"].textContent = item.title;
  ui.genres.replaceChildren(...item.genres.map(genre => {
    const tag = document.createElement("span");
    tag.className = "genre-tag";
    tag.textContent = genre;
    return tag;
  }));
  ui["set-duration"].textContent = formatDuration(item.duration_minutes);
  ui["set-year"].textContent = String(item.year);
}

async function select() {
  if (state.catalogStatus !== "ready") return;
  const version = ++state.selectionVersion;
  const result = selectSet(state.catalog, state.filters, state.currentVideoId);
  state.candidates = result.count;
  state.item = result.item;
  state.currentVideoId = result.item?.youtube_id ?? null;
  state.playerStatus = result.item ? "loading" : "idle";
  ui["selection-note"].textContent = result.count === 1 ? "Only one DJ set available with these filters" : "";
  ui["player-error"].hidden = true;
  renderItem(result.item);
  controls();
  if (!result.item) {
    player.clear(version);
    ui["set-title"].textContent = "Try another combination.";
    frame("No DJ set matches the selected filters", "Modify the filters or reset them to start over.");
    announce("No DJ set matches the selected filters");
    return;
  }
  announce(`Loading ${result.item.title}. ${result.count === 1 ? "Only one DJ set available with these filters." : ""}`);
  await player.replace(result.item.youtube_id, version);
}

function updateFilters() {
  state.filters = { genre: ui.genre.value || null, duration: ui.duration.value, year: ui.year.value ? Number(ui.year.value) : null };
  return select();
}
function reset() {
  ui.genre.value = ""; ui.duration.value = "all"; ui.year.value = "";
  return updateFilters();
}
function fillOptions() {
  const options = catalogOptions(state.catalog);
  ui.genre.replaceChildren(new Option("All genres", ""), ...options.genres.map(g => new Option(g[0].toUpperCase() + g.slice(1), g)));
  ui.year.replaceChildren(new Option("All years", ""), ...options.years.map(y => new Option(String(y), String(y))));
}

function validCatalog(data) {
  return data && typeof data.fetched_at === "string" && Array.isArray(data.items) && data.items.every(item =>
    /^[A-Za-z0-9_-]{11}$/.test(item.youtube_id) && typeof item.title === "string" && item.title.trim() &&
    Array.isArray(item.genres) && item.genres.length && item.genres.every(g => typeof g === "string" && g.trim()) &&
    Number.isFinite(item.duration_minutes) && item.duration_minutes > 0 && Number.isInteger(item.year) && item.year >= 1000 && item.year <= 9999);
}

async function initialize() {
  const version = ++catalogVersion;
  catalogController?.abort();
  catalogController = new AbortController();
  const controller = catalogController;
  player.clear(++state.selectionVersion);
  Object.assign(state, { catalog: [], filters: { ...DEFAULT_FILTERS }, currentVideoId: null, catalogStatus: "loading", playerStatus: "idle", candidates: 0, item: null });
  ui.genre.value = ""; ui.duration.value = "all"; ui.year.value = "";
  ui["catalog-total"].textContent = "—";
  ui["selection-note"].textContent = "";
  ui["player-error"].hidden = true;
  renderItem(null); controls();
  frame("Loading catalog", "One moment, choosing your next set.", true);
  announce("Loading catalog");
  const timeout = setTimeout(() => controller.abort(), 12000);
  try {
    const response = await fetch(preview ? "/preview-catalog.json" : "/api/catalog", { cache: "no-store", signal: controller.signal });
    if (!response.ok) {
      const problem = await response.json().catch(() => ({}));
      throw new Error(problem.error?.code || "unavailable");
    }
    const data = await response.json();
    if (!validCatalog(data)) throw new Error("invalid");
    if (version !== catalogVersion) return;
    state.catalog = data.items;
    ui["catalog-total"].textContent = String(data.items.length);
    if (!data.items.length) {
      state.catalogStatus = "empty";
      ui["set-title"].textContent = "The catalog is currently empty.";
      frame("Catalog empty", "There are no DJ sets available. Reload the page to try again.", false, true);
      announce("Catalog empty. Reload the page to try again.");
      controls(); return;
    }
    fillOptions();
    state.catalogStatus = "ready";
    void select();
  } catch (error) {
    if (version !== catalogVersion) return;
    state.catalogStatus = "error";
    ui["set-title"].textContent = "Let's try again in a moment.";
    const reasons = {
      CATALOG_TIMEOUT: "The catalog is taking too long to load.",
      CATALOG_RATE_LIMITED: "The catalog is temporarily busy.",
      CATALOG_SCHEMA_INVALID: "The catalog format is invalid.",
    };
    const message = controller.signal.aborted ? reasons.CATALOG_TIMEOUT : reasons[error.message] || "Unable to load the catalog.";
    frame(message, "Reload the page to try again.", false, true);
    announce(`${message} Reload the page to try again.`);
    controls();
  } finally { clearTimeout(timeout); }
}

for (const key of ["genre", "duration", "year"]) ui[key].addEventListener("change", updateFilters);
ui.reset.addEventListener("click", reset);
ui.next.addEventListener("click", select);
ui.reload.addEventListener("click", () => window.location.reload());
$("filters-form").addEventListener("submit", event => event.preventDefault());
window.addEventListener("pageshow", event => { if (event.persisted) void initialize(); });
window.addEventListener("pagehide", () => { ++catalogVersion; catalogController?.abort(); player.clear(++state.selectionVersion); });

// Progressive enhancement: all tools act on the same state as the visible controls.
if (document.modelContext?.registerTool) {
  const lifecycle = new AbortController();
  const snapshot = () => ({ filters: state.filters, current: state.item, candidates: state.candidates, playerStatus: state.playerStatus });
  const register = tool => {
    try { Promise.resolve(document.modelContext.registerTool(tool, { signal: lifecycle.signal })).catch(() => {}); } catch { /* Unsupported experimental API. */ }
  };
  register({ name: "nextset_get_selection", description: "Read the selected DJ set and active filters.", inputSchema: { type: "object", properties: {}, additionalProperties: false }, annotations: { readOnlyHint: true, untrustedContentHint: true }, execute: snapshot });
  register({ name: "nextset_select_set", description: "Select another DJ set with the specified filters; stops the current video without starting audio.", inputSchema: { type: "object", properties: { genre: { type: ["string", "null"] }, duration: { enum: DURATIONS }, year: { type: ["integer", "null"] } }, additionalProperties: false }, annotations: { readOnlyHint: false, untrustedContentHint: true }, execute: async input => {
    if (state.catalogStatus !== "ready") throw new Error("Catalog unavailable");
    if (!input || typeof input !== "object" || Array.isArray(input) || Object.keys(input).some(key => !["genre", "duration", "year"].includes(key))) throw new Error("Invalid filters");
    const filters = { ...state.filters, ...input };
    const options = catalogOptions(state.catalog);
    if ((filters.genre !== null && !options.genres.includes(filters.genre)) || !DURATIONS.includes(filters.duration) || (filters.year !== null && !options.years.includes(filters.year))) throw new Error("Invalid filters");
    ui.genre.value = filters.genre ?? ""; ui.duration.value = filters.duration; ui.year.value = filters.year ?? "";
    await updateFilters(); return snapshot();
  }});
  // Preserve registrations across bfcache restoration.
  window.addEventListener("pagehide", event => { if (!event.persisted) lifecycle.abort(); });
}
void initialize();