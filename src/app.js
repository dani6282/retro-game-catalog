const state = {
  catalog: null,
  groups: [],
  detailCache: new Map(),
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

function formatNumber(value) {
  return new Intl.NumberFormat().format(value || 0);
}

function uniqueSorted(values) {
  return [...new Set(values.filter(Boolean))].sort(collator.compare);
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
  const summary = state.catalog.summary;
  const stats = [
    ["Games", summary.games],
    ["Variants", summary.variants],
    ["Batocera entries", summary.bySource.Batocera || 0],
    ["PiMiga entries", summary.bySource.PiMiga || 0],
    ["With info", summary.withMetadata],
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
  fillSelect(elements.platform, uniqueSorted(state.groups.flatMap((group) => group.platforms)), state.platform);
  fillSelect(elements.format, uniqueSorted(state.groups.flatMap((group) => group.formats)), state.format);
}

function matchesFilters(group) {
  if (state.source === "Both" && group.libraries.length < 2) return false;
  if (state.source !== "All" && state.source !== "Both" && !group.libraries.includes(state.source)) return false;
  if (state.platform !== "All" && !group.platforms.includes(state.platform)) return false;
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
    if (state.sort === "libraries") return b.libraries.length - a.libraries.length || collator.compare(a.title, b.title);
    if (state.sort === "platform") {
      return collator.compare(a.platforms[0] || "", b.platforms[0] || "") || collator.compare(a.title, b.title);
    }
    if (state.sort === "variants") return b.variantCount - a.variantCount || collator.compare(a.title, b.title);
    if (state.sort === "metadata") return Number(b.hasMetadata) - Number(a.hasMetadata) || collator.compare(a.title, b.title);
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

function renderBadgeList(target, values, classForValue = () => "") {
  target.replaceChildren();
  for (const value of values) {
    target.append(badge(value, classForValue(value)));
  }
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

function renderVariant(variant) {
  const row = document.createElement("div");
  row.className = "variant-row";

  const title = document.createElement("strong");
  title.textContent = variant.title;
  row.append(title);

  const meta = document.createElement("span");
  meta.textContent = [variant.library, variant.platform, variant.format, variant.language, variant.category]
    .filter(Boolean)
    .join(" · ");
  row.append(meta);

  const path = document.createElement("code");
  path.textContent = variant.path;
  row.append(path);

  return row;
}

async function loadDetail(group) {
  if (!state.detailCache.has(group.detailFile)) {
    const response = await fetch(`./public/${group.detailFile}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`Unable to load details: ${response.status}`);
    state.detailCache.set(group.detailFile, await response.json());
  }
  return state.detailCache.get(group.detailFile)[group.key] || { descriptions: [], variants: [] };
}

async function fillDetail(group, variantList) {
  variantList.replaceChildren();
  variantList.append(Object.assign(document.createElement("p"), { className: "detail-loading", textContent: "Loading details..." }));
  const detail = await loadDetail(group);
  variantList.replaceChildren();

  if (group.wiki || detail.descriptions.length) {
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
    for (const description of detail.descriptions) {
      info.append(renderDescription(description));
    }
    variantList.append(info);
  }

  for (const variant of detail.variants) {
    variantList.append(renderVariant(variant));
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
    cell.colSpan = 5;
    cell.textContent = "No games match the current filters.";
    row.append(cell);
    elements.games.append(row);
    elements.loadMore.hidden = true;
    return;
  }

  const fragment = document.createDocumentFragment();
  for (const group of visibleGroups) {
    const node = elements.gameTemplate.content.cloneNode(true);
    const details = node.querySelector("details");
    const variantList = node.querySelector(".variant-list");
    node.querySelector("summary strong").textContent = group.title;
    node.querySelector(".game-note").textContent = `${group.variantCount} variant${group.variantCount === 1 ? "" : "s"}`;

    details.addEventListener(
      "toggle",
      () => {
        if (details.open && !details.dataset.loaded) {
          details.dataset.loaded = "true";
          fillDetail(group, variantList).catch((error) => {
            variantList.replaceChildren(Object.assign(document.createElement("p"), { className: "empty", textContent: error.message }));
          });
        }
      },
      { once: true },
    );

    renderBadgeList(node.querySelector(".library-cell"), group.libraries, sourceClass);
    renderBadgeList(node.querySelector(".platform-format-cell"), [...group.platforms.slice(0, 3), ...group.formats.slice(0, 2)]);
    renderBadgeList(node.querySelector(".variant-cell"), [
      `${group.variantCount} total`,
      ...group.languages,
      ...group.categories.slice(0, 2),
    ]);

    const infoCell = node.querySelector(".info-cell");
    if (group.hasMetadata) infoCell.append(badge("metadata"));
    if (group.hasDescription) infoCell.append(badge("description"));
    if (group.wiki) infoCell.append(badge("Wikipedia", "external"));
    for (const bit of group.metadataBits.slice(0, 2)) infoCell.append(badge(bit));
    if (!infoCell.children.length) infoCell.textContent = "file names only";

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

  for (const [element, key] of [
    [elements.source, "source"],
    [elements.platform, "platform"],
    [elements.format, "format"],
    [elements.sort, "sort"],
  ]) {
    element.addEventListener("change", (event) => {
      state[key] = event.target.value;
      resetVisibleCount();
      renderGroups();
    });
  }

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
  const response = await fetch("./public/game-index.json", { cache: "no-store" });
  if (!response.ok) throw new Error(`Unable to load catalog: ${response.status}`);
  state.catalog = await response.json();
  state.groups = state.catalog.groups;
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
