export const DEFAULT_FILTERS = Object.freeze({ genre: null, duration: "all", year: null });
export const DURATIONS = ["all", "lt60", "60to120", "gte120"];

export function matchesAllFilters(item, filters) {
  return (!filters.genre || item.genres.includes(filters.genre)) &&
    (filters.year === null || item.year === filters.year) &&
    (filters.duration === "all" ||
      (filters.duration === "lt60" && item.duration_minutes < 60) ||
      (filters.duration === "60to120" && item.duration_minutes >= 60 && item.duration_minutes < 120) ||
      (filters.duration === "gte120" && item.duration_minutes >= 120));
}

export function selectSet(catalog, filters, currentVideoId, rng = Math.random) {
  const candidates = catalog.filter(item => matchesAllFilters(item, filters));
  const alternatives = candidates.filter(item => item.youtube_id !== currentVideoId);
  const pool = alternatives.length ? alternatives : candidates;
  return { count: candidates.length, item: pool.length ? pool[Math.floor(rng() * pool.length)] : null };
}

export function catalogOptions(catalog) {
  return {
    genres: [...new Set(catalog.flatMap(item => item.genres))].sort((a, b) => a.localeCompare(b, "it")),
    years: [...new Set(catalog.map(item => item.year))].sort((a, b) => b - a),
  };
}

export function formatDuration(minutes) {
  const seconds = Math.round(minutes * 60);
  const hours = Math.floor(seconds / 3600);
  const remainingMinutes = Math.floor((seconds % 3600) / 60);
  const remainingSeconds = seconds % 60;
  return [hours ? `${hours} h` : "", remainingMinutes ? `${remainingMinutes} min` : "", remainingSeconds ? `${remainingSeconds} s` : ""].filter(Boolean).join(" ") || "< 1 s";
}
