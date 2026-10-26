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
  const genreCounts = new Map();
  const durations = new Map();
  const durationCounts = new Map();
  const yearCounts = new Map();
  for (const item of catalog) {
    const itemGenreKeys = new Set();
    for (const genre of item.genres) {
      const key = genre.toLowerCase();
      if (itemGenreKeys.has(key)) continue;
      itemGenreKeys.add(key);
      if (!genres.has(key)) genres.set(key, genre);
      genreCounts.set(key, (genreCounts.get(key) || 0) + 1);
    }
    const duration = typeof item.duration_approx === "string" ? item.duration_approx.trim().replace(/\s+/g, " ") : "";
    const durationKey = normalizeApproxDuration(duration);
    if (durationKey) {
      if (!durations.has(durationKey)) durations.set(durationKey, duration);
      durationCounts.set(durationKey, (durationCounts.get(durationKey) || 0) + 1);
    }
    yearCounts.set(item.year, (yearCounts.get(item.year) || 0) + 1);
  }
  const sortedGenres = [...genres.keys()].sort((a, b) =>
    genreCounts.get(b) - genreCounts.get(a) || genres.get(a).localeCompare(genres.get(b), "it"));
  const sortedDurations = [...durations.values()].sort((a, b) =>
    approximateMinutes(a) - approximateMinutes(b) || a.localeCompare(b, "it", { sensitivity: "base" }));
  const options = {
    genres: sortedGenres.map(key => genres.get(key)),
    durations: sortedDurations,
    years: [...new Set(catalog.map(item => item.year))].sort((a, b) => b - a),
  };
  Object.defineProperties(options, {
    genreCounts: { value: genreCounts },
    durationCounts: { value: durationCounts },
    yearCounts: { value: yearCounts },
  });
  return options;
}

export function formatDuration(minutes) {
  const seconds = Math.round(minutes * 60);
  const hours = Math.floor(seconds / 3600);
  const remainingMinutes = Math.floor((seconds % 3600) / 60);
  const remainingSeconds = seconds % 60;
  return [hours ? `${hours} h` : "", remainingMinutes ? `${remainingMinutes} min` : "", remainingSeconds ? `${remainingSeconds} s` : ""].filter(Boolean).join(" ") || "< 1 s";
}
