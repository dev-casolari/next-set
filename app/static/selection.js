export const DEFAULT_FILTERS = Object.freeze({ genre: null, duration: "all", year: null });

export function normalizeApproxDuration(value) {
  return typeof value === "string" ? value.trim().replace(/\s+/g, " ").toLocaleLowerCase("en") : "";
}

function approximateMinutes(value) {
  const hoursAndMinutes = /^(\d+)\s*h(?:\s*(\d+)\s*(?:min)?)?$/i.exec(value);
  if (hoursAndMinutes) return Number(hoursAndMinutes[1]) * 60 + Number(hoursAndMinutes[2] || 0);
  const minutes = /^(\d+)\s*min$/i.exec(value);
  return minutes ? Number(minutes[1]) : Number.POSITIVE_INFINITY;
}

export function matchesAllFilters(item, filters) {
  const selectedGenre = filters.genre?.toLowerCase();
  return (!selectedGenre || item.genres.some(genre => genre.toLowerCase() === selectedGenre)) &&
    (filters.year === null || item.year === filters.year) &&
    (filters.duration === "all" || normalizeApproxDuration(item.duration_approx) === normalizeApproxDuration(filters.duration));
}

export function selectSet(catalog, filters, currentVideoId, rng = Math.random) {
  const candidates = catalog.filter(item => matchesAllFilters(item, filters));
  const alternatives = candidates.filter(item => item.youtube_id !== currentVideoId);
  const pool = alternatives.length ? alternatives : candidates;
  return { count: candidates.length, item: pool.length ? pool[Math.floor(rng() * pool.length)] : null };
}

export function catalogOptions(catalog) {
  const genres = new Map();
  const durations = new Map();
  for (const item of catalog) {
    for (const genre of item.genres) {
      const key = genre.toLowerCase();
      if (!genres.has(key)) genres.set(key, genre);
    }
    const duration = typeof item.duration_approx === "string" ? item.duration_approx.trim().replace(/\s+/g, " ") : "";
    const durationKey = normalizeApproxDuration(duration);
    if (durationKey && !durations.has(durationKey)) durations.set(durationKey, duration);
  }
  const sortedDurations = [...durations.values()].sort((a, b) =>
    approximateMinutes(a) - approximateMinutes(b) || a.localeCompare(b, "it", { sensitivity: "base" }));
  return {
    genres: [...genres.values()].sort((a, b) => a.localeCompare(b, "it")),
    durations: sortedDurations,
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
