const state = {
  catalog: null,
  wikiLinks: {},
  groups: [],
  query: "",
  source: "All",
  platform: "All",
  format: "All",
  sort: "popularity",
  onlyBoth: false,
  onlyLanguage: false,
  onlyMetadata: false,
  visibleCount: 150,
};

const PAGE_SIZE = 150;

const elements = {
  stats: document.querySelector("#stats"),
  games: document.querySelector("#games"),
  resultTitle: document.querySelector("#resultTitle"),
  resultMeta: document.querySelector("#resultMeta"),
  search: document.querySelector("#searchInput"),
  source: document.querySelector("#sourceSelect"),
  platform: document.querySelector("#platformSelect"),
  format: document.querySelector("#collectionSelect"),
  sort: document.querySelector("#sortSelect"),
  both: document.querySelector("#bothToggle"),
  language: document.querySelector("#languageToggle"),
  metadata: document.querySelector("#metadataToggle"),
  reset: document.querySelector("#resetButton"),
  loadMore: document.querySelector("#loadMoreButton"),
  statTemplate: document.querySelector("#statTemplate"),
  gameTemplate: document.querySelector("#gameTemplate"),
};

const collator = new Intl.Collator(undefined, { sensitivity: "base", numeric: true });

const POPULAR_TITLE_HINTS = [
  "bubble bobble",
  "civilization",
  "defender of the crown",
  "doom",
  "elite",
  "gauntlet",
  "giana sisters",
  "lemmings",
  "maniac mansion",
  "monkey island",
  "pac man",
  "ports of call",
  "prince of persia",
  "rtype",
  "secret of monkey island",
  "sensible soccer",
  "speedball",
  "stunt car racer",
  "turrican",
  "zak mckracken",
];

function formatNumber(value) {
  return new Intl.NumberFormat().format(value || 0);
}

function cleanTitle(value) {
  return (value || "")
    .replace(/[_]+/g, " ")
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/\s+/g, " ")
    .trim();
}

function displayBaseTitle(title) {
  return cleanTitle(title)
    .replace(/\s+(De|Ger|German|Deutsch|Fr|Fre|French|Francais|It|Ita|Italian|Es|Spa|Spanish)$/i, "")
    .trim();
}

function groupKey(title) {
  return displayBaseTitle(title)
    .toLowerCase()
    .replace(/\[[^\]]*\]|\([^)]*\)/g, " ")
    .replace(/\b(disk|disc|side|part|cd)\s*\d+\b/g, " ")
    .replace(/\b(ntsc|pal|aga|ocs|ecs|cd32|whdload)\b/g, " ")
    .replace(/[^a-z0-9]+/g, "");
}

function hasMetadata(entry) {
  return Boolean(entry.genre || entry.developer || entry.publisher || entry.rating || entry.description);
}

function formatLabel(entry) {
  if (entry.collection === "WHDLoad") return "WHDLoad";
  if (entry.collection === "Installed") return "Installed";
  if (entry.platform === "scummvm") return "ScummVM";
  if (entry.source === "Batocera") return "ROM file";
  return "File";
}

function variantLabel(entry) {
  return [entry.language, entry.category, formatLabel(entry)].filter(Boolean).join(" / ") || formatLabel(entry);
}

function uniqueSorted(values) {
  return [...new Set(values.filter(Boolean))].sort(collator.compare);
}

function popularityScore(group) {
  const title = group.title.toLowerCase();
  const hintScore = POPULAR_TITLE_HINTS.some((hint) => title.includes(hint)) ? 100 : 0;
  const bothScore = group.libraries.length > 1 ? 35 : 0;
  const metadataScore = group.hasMetadata ? 12 : 0;
  const variantScore = Math.min(group.variants.length, 15) * 2;
  const ratingValues = group.variants
    .map((entry) => Number.parseFloat(entry.rating))
    .filter((value) => Number.isFinite(value));
  const ratingScore = ratingValues.length
    ? (ratingValues.reduce((sum, value) => sum + value, 0) / ratingValues.length) * 20
    : 0;
  return Math.round(hintScore + bothScore + metadataScore + variantScore + ratingScore);
}

function buildGroups(entries) {
  const map = new Map();
  for (const entry of entries) {
    const key = groupKey(entry.title) || entry.normalizedTitle || entry.id;
    if (!map.has(key)) {
      map.set(key, {
        key,
        title: displayBaseTitle(entry.title) || entry.title,
        variants: [],
      });
    }
    map.get(key).variants.push(entry);
  }

  const groups = [...map.values()].map((group) => {
    group.variants.sort((a, b) =>
      collator.compare(`${a.source} ${variantLabel(a)} ${a.path}`, `${b.source} ${variantLabel(b)} ${b.path}`),
    );
    group.libraries = uniqueSorted(group.variants.map((entry) => entry.source));
    group.systems = uniqueSorted(group.variants.map((entry) => entry.platform));
    group.formats = uniqueSorted(group.variants.map(formatLabel));
    group.languages = uniqueSorted(group.variants.map((entry) => entry.language));
    group.categories = uniqueSorted(group.variants.map((entry) => entry.category));
    group.hasMetadata = group.variants.some(hasMetadata);
    group.metadataBits = uniqueSorted(
      group.variants.flatMap((entry) => [entry.genre, entry.developer, entry.publisher]).filter(Boolean),
    ).slice(0, 3);
    group.descriptions = uniqueSorted(group.variants.map((entry) => entry.description).filter(Boolean));
    group.wiki = state.wikiLinks[group.key] || null;
    group.popularity = popularityScore(group);
    group.searchText = [
      group.title,
      group.libraries.join(" "),
      group.systems.join(" "),
      group.formats.join(" "),
      group.languages.join(" "),
      group.categories.join(" "),
      group.metadataBits.join(" "),
      group.descriptions.join(" "),
      group.wiki?.article,
      ...group.variants.flatMap((entry) => [entry.title, entry.path, entry.genre, entry.developer, entry.publisher]),
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return group;
  });

  return groups.sort((a, b) => b.popularity - a.popularity || collator.compare(a.title, b.title));
}

function fillSelect(select, values, current, allLabel = "All") {
  select.replaceChildren();
  for (const value of [allLabel, ...values]) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    option.selected = value === current;
    select.append(option);
  }
}

function renderStats() {
  const groups = state.groups;
  const stats = [
    ["Games", groups.length],
    ["Variants", state.catalog.summary.total],
    ["Batocera entries", state.catalog.summary.bySource.Batocera || 0],
    ["PiMiga entries", state.catalog.summary.bySource.PiMiga || 0],
    ["In both libraries", groups.filter((group) => group.libraries.length > 1).length],
  ];

  elements.stats.replaceChildren();
  for (const [label, value] of stats) {
    const node = elements.statTemplate.content.cloneNode(true);
    node.querySelector("span").textContent = label;
    node.querySelector("strong").textContent = formatNumber(value);
    elements.stats.append(node);
  }
}

function initControls() {
  fillSelect(elements.source, ["Batocera", "PiMiga", "Both"], state.source);
  fillSelect(elements.platform, uniqueSorted(state.groups.flatMap((group) => group.systems)), state.platform);
  fillSelect(elements.format, uniqueSorted(state.groups.flatMap((group) => group.formats)), state.format);
}

function matchesFilters(group) {
  if (state.source === "Both" && group.libraries.length < 2) return false;
  if (state.source !== "All" && state.source !== "Both" && !group.libraries.includes(state.source)) return false;
  if (state.platform !== "All" && !group.systems.includes(state.platform)) return false;
  if (state.format !== "All" && !group.formats.includes(state.format)) return false;
  if (state.onlyBoth && group.libraries.length < 2) return false;
  if (state.onlyLanguage && !group.languages.length) return false;
  if (state.onlyMetadata && !group.hasMetadata) return false;
  if (state.query && !group.searchText.includes(state.query)) return false;
  return true;
}

function filteredGroups() {
  const groups = state.groups.filter(matchesFilters);
  return groups.sort((a, b) => {
    if (state.sort === "popularity") return b.popularity - a.popularity || collator.compare(a.title, b.title);
    if (state.sort === "libraries") {
      return b.libraries.length - a.libraries.length || collator.compare(a.title, b.title);
    }
    if (state.sort === "platform") {
      return collator.compare(a.systems[0] || "", b.systems[0] || "") || collator.compare(a.title, b.title);
    }
    if (state.sort === "variants") {
      return b.variants.length - a.variants.length || collator.compare(a.title, b.title);
    }
    if (state.sort === "metadata") {
      return Number(b.hasMetadata) - Number(a.hasMetadata) || collator.compare(a.title, b.title);
    }
    return collator.compare(a.title, b.title);
  });
}

function resetVisibleCount() {
  state.visibleCount = PAGE_SIZE;
}

function badge(text, className = "") {
  const span = document.createElement("span");
  span.className = `badge ${className}`.trim();
  span.textContent = text;
  return span;
}

function sourceClass(source) {
  return source === "Batocera" ? "source-batocera" : "source-pimiga";
}

function renderVariant(entry) {
  const row = document.createElement("div");
  row.className = "variant-row";

  const title = document.createElement("strong");
  title.textContent = entry.title;
  row.append(title);

  const meta = document.createElement("span");
  meta.textContent = [entry.source, entry.platform, variantLabel(entry)].filter(Boolean).join(" · ");
  row.append(meta);

  const path = document.createElement("code");
  path.textContent = entry.path;
  row.append(path);

  return row;
}

function paragraphsFromDescription(description) {
  return description
    .split(/\n\s*\n|\r\n\s*\r\n/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean);
}

function renderDescription(description) {
  const section = document.createElement("section");
  section.className = "description-block";
  const heading = document.createElement("h4");
  heading.textContent = "Description";
  section.append(heading);
  for (const paragraph of paragraphsFromDescription(description)) {
    const p = document.createElement("p");
    p.textContent = paragraph;
    section.append(p);
  }
  return section;
}

function renderBadgeList(target, values, classForValue = () => "") {
  target.replaceChildren();
  for (const value of values) {
    target.append(badge(value, classForValue(value)));
  }
}

function renderGroups() {
  const groups = filteredGroups();
  const visibleGroups = groups.slice(0, state.visibleCount);
  elements.games.replaceChildren();

  elements.resultTitle.textContent = "Games";
  elements.resultMeta.textContent = `${formatNumber(visibleGroups.length)} shown from ${formatNumber(
    groups.length,
  )} matching games`;
  elements.loadMore.hidden = state.visibleCount >= groups.length;

  if (!groups.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.className = "empty";
    cell.colSpan = 6;
    cell.textContent = "No games match the current filters.";
    row.append(cell);
    elements.games.append(row);
    elements.loadMore.hidden = true;
    return;
  }

  const fragment = document.createDocumentFragment();
  for (const group of visibleGroups) {
    const node = elements.gameTemplate.content.cloneNode(true);
    node.querySelector("summary strong").textContent = group.title;
    node.querySelector(".game-note").textContent = `${group.variants.length} variant${
      group.variants.length === 1 ? "" : "s"
    }`;

    const variantList = node.querySelector(".variant-list");
    if (group.wiki || group.descriptions.length) {
      const info = document.createElement("div");
      info.className = "game-info";
      if (group.wiki) {
        const link = document.createElement("a");
        link.className = "external-link";
        link.href = group.wiki.url;
        link.target = "_blank";
        link.rel = "noreferrer";
        link.textContent = `Wikipedia: ${group.wiki.article}`;
        info.append(link);
      }
      for (const description of group.descriptions.slice(0, 2)) {
        info.append(renderDescription(description));
      }
      variantList.append(info);
    }
    for (const variant of group.variants) {
      variantList.append(renderVariant(variant));
    }

    renderBadgeList(node.querySelector(".library-cell"), group.libraries, sourceClass);
    renderBadgeList(node.querySelector(".system-cell"), group.systems.slice(0, 4));
    renderBadgeList(node.querySelector(".variant-cell"), [
      ...group.formats.slice(0, 2),
      ...group.languages,
      ...group.categories.slice(0, 2),
    ]);

    const metadataCell = node.querySelector(".metadata-cell");
    if (group.hasMetadata) {
      renderBadgeList(metadataCell, group.metadataBits.length ? group.metadataBits : ["metadata"]);
    } else {
      metadataCell.textContent = "file names only";
    }
    if (group.wiki) {
      metadataCell.append(badge("Wikipedia", "external"));
    }

    node.querySelector(".popularity-cell").textContent = group.popularity ? String(group.popularity) : "-";
    fragment.append(node);
  }
  elements.games.append(fragment);
}

function bindEvents() {
  elements.search.addEventListener("input", (event) => {
    state.query = event.target.value.trim().toLowerCase();
    resetVisibleCount();
    renderGroups();
  });

  elements.source.addEventListener("change", (event) => {
    state.source = event.target.value;
    resetVisibleCount();
    renderGroups();
  });

  elements.platform.addEventListener("change", (event) => {
    state.platform = event.target.value;
    resetVisibleCount();
    renderGroups();
  });

  elements.format.addEventListener("change", (event) => {
    state.format = event.target.value;
    resetVisibleCount();
    renderGroups();
  });

  elements.sort.addEventListener("change", (event) => {
    state.sort = event.target.value;
    resetVisibleCount();
    renderGroups();
  });

  elements.both.addEventListener("change", (event) => {
    state.onlyBoth = event.target.checked;
    resetVisibleCount();
    renderGroups();
  });

  elements.language.addEventListener("change", (event) => {
    state.onlyLanguage = event.target.checked;
    resetVisibleCount();
    renderGroups();
  });

  elements.metadata.addEventListener("change", (event) => {
    state.onlyMetadata = event.target.checked;
    resetVisibleCount();
    renderGroups();
  });

  elements.loadMore.addEventListener("click", () => {
    state.visibleCount += PAGE_SIZE;
    renderGroups();
  });

  elements.reset.addEventListener("click", () => {
    state.query = "";
    state.source = "All";
    state.platform = "All";
    state.format = "All";
    state.sort = "popularity";
    state.onlyBoth = false;
    state.onlyLanguage = false;
    state.onlyMetadata = false;
    resetVisibleCount();
    elements.search.value = "";
    elements.sort.value = "popularity";
    elements.both.checked = false;
    elements.language.checked = false;
    elements.metadata.checked = false;
    initControls();
    renderGroups();
  });
}

async function loadCatalog() {
  const response = await fetch("./public/catalog.json", { cache: "no-store" });
  if (!response.ok) throw new Error(`Unable to load catalog: ${response.status}`);
  state.catalog = await response.json();
  try {
    const linksResponse = await fetch("./public/wiki-links.json", { cache: "no-store" });
    if (linksResponse.ok) {
      state.wikiLinks = (await linksResponse.json()).links || {};
    }
  } catch {
    state.wikiLinks = {};
  }
  state.groups = buildGroups(state.catalog.games);
}

async function start() {
  try {
    await loadCatalog();
    renderStats();
    initControls();
    bindEvents();
    renderGroups();
  } catch (error) {
    elements.resultTitle.textContent = "Catalog unavailable";
    elements.resultMeta.textContent = error.message;
  }
}

start();
