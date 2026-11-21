"use strict";
const $ = (s, el = document) => el.querySelector(s);
const I18N = {
  en: { search: "Search", filters: "Filters", country: "Country", category: "Category", color: "Colour",
        size: "Size (cm)", width: "Width", depth: "Depth", height: "Height", seats: "Seats",
        hasdims: "Only items with known size", price: "Price", instock: "In stock", material: "Material",
        retailer: "Retailer", clear: "Clear all filters", s_rel: "Best match", s_pa: "Price: low to high",
        s_pd: "Price: high to low", s_w: "Width: narrow first", s_new: "Newest",
        results: n => `${n.toLocaleString()} products`, understood: "Understood:",
        asFilter: "use as filter", none: "Nothing found. Try fewer words or loosen the filters.",
        view: "View at retailer", variants: "Variants", others: "Same product at other retailers",
        history: "Price history", from: "from", colors: "colours", dims: "Dimensions", DK: "Denmark", DE: "Germany",
        unknown: "size unknown" },
  da: { search: "Søg", filters: "Filtre", country: "Land", category: "Kategori", color: "Farve",
        size: "Mål (cm)", width: "Bredde", depth: "Dybde", height: "Højde", seats: "Pladser",
        hasdims: "Kun varer med kendte mål", price: "Pris", instock: "På lager", material: "Materiale",
        retailer: "Forhandler", clear: "Nulstil filtre", s_rel: "Bedste match", s_pa: "Pris: lav til høj",
        s_pd: "Pris: høj til lav", s_w: "Bredde: smallest først", s_new: "Nyeste",
        results: n => `${n.toLocaleString("da-DK")} produkter`, understood: "Forstået:",
        asFilter: "brug som filter", none: "Intet fundet. Prøv færre ord eller løsn filtrene.",
        view: "Se hos forhandler", variants: "Varianter", others: "Samme produkt hos andre forhandlere",
        history: "Prishistorik", from: "fra", colors: "farver", dims: "Mål", DK: "Danmark", DE: "Tyskland",
        unknown: "mål ukendte" },
};
I18N.da.s_w = "Bredde: smalleste først";

const MULTI = ["country", "retailer", "category", "color", "material"];
const NUMS = ["wmin", "wmax", "dmin", "dmax", "hmin", "hmax", "pmin", "pmax", "seats_min", "seats_max"];
const BOOLS = ["in_stock", "has_dimensions"];
let META = null;
let state = readState();
const t = k => I18N[state.lang][k] ?? I18N.en[k] ?? k;

function store(key, val) { try { localStorage.setItem(key, val); } catch (_) {} }
function load(key) { try { return localStorage.getItem(key); } catch (_) { return null; } }

function readState() {
  const p = new URLSearchParams(location.search);
  const s = { q: p.get("q") || "", sort: p.get("sort") || "relevance", page: +(p.get("page") || 1),
              lang: p.get("lang") || load("fb.lang") || (navigator.language.startsWith("da") ? "da" : "en"),
              currency: p.get("currency") || load("fb.currency") || "DKK" };
  MULTI.forEach(k => s[k] = p.getAll(k));
  NUMS.forEach(k => s[k] = p.get(k) || "");
  BOOLS.forEach(k => s[k] = p.get(k) === "true");
  return s;
}

function params(extra = {}) {
  const s = { ...state, ...extra };
  const p = new URLSearchParams();
  if (s.q) p.set("q", s.q);
  MULTI.forEach(k => s[k].forEach(v => p.append(k, v)));
  NUMS.forEach(k => s[k] !== "" && p.set(k, s[k]));
  BOOLS.forEach(k => s[k] && p.set(k, "true"));
  if (s.sort !== "relevance") p.set("sort", s.sort);
  if (s.page > 1) p.set("page", s.page);
  p.set("currency", s.currency);
  return p;
}

function label(group, id) {
  const list = META && META[group];
  const c = list && list.find(x => x.id === id);
  return c ? c[state.lang] : id.replace(/_/g, " ");
}

const fmtMoney = (v, cur) => v == null ? "–" : new Intl.NumberFormat(state.lang === "da" ? "da-DK" : "en-GB",
  { style: "currency", currency: cur, maximumFractionDigits: cur === "DKK" ? 0 : 2 }).format(v);

function dimsText(p) {
  const parts = [];
  if (p.diameter_cm) parts.push(`Ø${p.diameter_cm}`);
  else {
    if (p.width_cm) parts.push(`${state.lang === "da" ? "B" : "W"}${p.width_cm}`);
    if (p.depth_cm) parts.push(`${state.lang === "da" ? "D" : "D"}${p.depth_cm}`);
  }
  if (p.height_cm) parts.push(`${state.lang === "da" ? "H" : "H"}${p.height_cm}`);
  return parts.length ? parts.join(" × ") + " cm" : t("unknown");
}

function colorHex(id) { const c = META.colors.find(x => x.id === id); return c ? c.hex : null; }

const TABLES = new Set(["table", "dining_table", "coffee_table", "side_table", "desk", "nightstand"]);
function placeholder(p) {
  const hex = colorHex(p.colors[0]) || "#c9c2b6";
  const st = 'stroke="rgba(0,0,0,.2)"';
  if (TABLES.has(p.category))
    return `<svg viewBox="0 0 100 70" aria-hidden="true"><rect x="6" y="18" width="88" height="8" rx="2" fill="${hex}" ${st}/>
      <rect x="14" y="26" width="5" height="36" fill="${hex}" ${st}/><rect x="81" y="26" width="5" height="36" fill="${hex}" ${st}/></svg>`;
  return `<svg viewBox="0 0 100 70" aria-hidden="true"><rect x="8" y="22" width="84" height="30" rx="8" fill="${hex}" ${st}/>
    <rect x="14" y="10" width="72" height="18" rx="6" fill="${hex}" ${st}/>
    <rect x="16" y="52" width="5" height="12" fill="#7a6a58"/><rect x="79" y="52" width="5" height="12" fill="#7a6a58"/></svg>`;
}

function esc(s) { return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }

function renderFacets(f) {
  const opts = (el, group, values, labelFn) => {
    const sel = new Set(state[group]);
    const entries = Object.entries(values).sort((a, b) => b[1] - a[1]);
    state[group].forEach(v => { if (!(v in values)) entries.push([v, 0]); });
    $(el).innerHTML = entries.map(([v, n]) => `<label><input type="checkbox" data-group="${group}" value="${esc(v)}"
      ${sel.has(v) ? "checked" : ""}> ${esc(labelFn(v))}<span class="n">${n}</span></label>`).join("") || "<span class='meta'>–</span>";
  };
  opts("#f-country", "country", f.country, v => t(v));
  opts("#f-category", "category", f.category, v => label("categories", v));
  opts("#f-material", "material", f.material, v => label("materials", v));
  const rname = id => (META.retailers.find(r => r.id === id) || { name: id }).name;
  opts("#f-retailer", "retailer", f.retailer_id, rname);
  const sel = new Set(state.color);
  $("#f-color").innerHTML = META.colors.map(c => {
    const n = f.color[c.id] || 0;
    const style = c.hex ? `style="background:${c.hex}"` : "";
    return `<button type="button" class="sw ${c.id === "multi" ? "multi" : ""}" ${style} data-color="${c.id}"
      aria-pressed="${sel.has(c.id)}" title="${esc(c[state.lang])} (${n})" aria-label="${esc(c[state.lang])}"
      ${n === 0 && !sel.has(c.id) ? "disabled" : ""}></button>`;
  }).join("");
}

function renderUnderstood(rec) {
  const map = { category: ["category", "categories"], color: ["color", "colors"], material: ["material", "materials"] };
  const chips = [];
  for (const [group, ids] of Object.entries(rec || {})) {
    for (const id of ids) {
      const m = map[group];
      const name = label(m ? m[1] : "attributes", id);
      if (m && !state[m[0]].includes(id))
        chips.push(`<button class="chip" data-add="${m[0]}" data-id="${id}" title="${t("asFilter")}">${esc(name)} +</button>`);
      else chips.push(`<span class="chip">${esc(name)}</span>`);
    }
  }
  $("#understood").innerHTML = chips.length ? `<span class="chip muted">${t("understood")}</span>` + chips.join("") : "";
}

function renderResults(data) {
  $("#summary").textContent = t("results")(data.total);
  if (!data.items.length) { $("#results").innerHTML = `<div class="empty">${t("none")}</div>`; return; }
  $("#results").innerHTML = data.items.map(p => {
    const cur = p.display_currency;
    const price = p.n_variants > 1 && p.display_min !== p.display_max
      ? `${t("from")} ${fmtMoney(p.display_min, cur)}` : fmtMoney(p.display_price, cur);
    const dots = (p.group_colors || p.colors).map(c => `<span class="dot" style="background:${colorHex(c) || "conic-gradient(red,yellow,green,blue)"}" title="${esc(label("colors", c))}"></span>`).join("");
    const retailer = (META.retailers.find(r => r.id === p.retailer_id) || { name: p.retailer_id }).name;
    const img = p.image_url ? `<img loading="lazy" src="${esc(p.image_url)}" alt="" referrerpolicy="no-referrer"
         onerror="this.replaceWith(document.createRange().createContextualFragment(this.dataset.ph))" data-ph='${placeholder(p)}'>` : placeholder(p);
    return `<button class="card" data-id="${p.id}">
      <div class="thumb">${img}</div>
      <div class="body">
        <div class="meta"><span class="badge">${p.country}</span> ${esc(retailer)}</div>
        <div class="title">${esc(p.title)}</div>
        <div class="meta">${esc(p.category ? label("categories", p.category) : "")} · ${dimsText(p)}</div>
        <div class="dots">${dots}</div>
        <div class="price">${price}</div>
      </div></button>`;
  }).join("");
}

function renderPager(data) {
  const pages = Math.ceil(data.total / data.per_page);
  if (pages <= 1) { $("#pager").innerHTML = ""; return; }
  const cur = data.page, out = [];
  for (let i = 1; i <= pages; i++) {
    if (i === 1 || i === pages || Math.abs(i - cur) <= 2)
      out.push(`<button data-page="${i}" ${i === cur ? 'aria-current="page"' : ""}>${i}</button>`);
    else if (out[out.length - 1] !== "…") out.push("…");
  }
  $("#pager").innerHTML = out.map(x => x === "…" ? "<span>…</span>" : x).join("");
}

let inflight;
async function run(push = true) {
  const p = params();
  if (push) history.replaceState(null, "", "?" + p.toString());
  inflight?.abort(); inflight = new AbortController();
  try {
    const data = await (await fetch("/api/search?" + p, { signal: inflight.signal })).json();
    renderFacets(data.facets); renderUnderstood(data.recognised); renderResults(data); renderPager(data);
  } catch (e) { if (e.name !== "AbortError") $("#results").innerHTML = `<div class="empty">Error: ${esc(e.message)}</div>`; }
}

async function openDetail(id) {
  const p = await (await fetch(`/api/product/${id}?currency=${state.currency}`)).json();
  const cur = p.display_currency;
  const rname = rid => (META.retailers.find(r => r.id === rid) || { name: rid }).name;
  const row = v => `<tr><td>${esc(v.title)}</td><td>${(v.colors || []).map(c => esc(label("colors", c))).join(", ")}</td>
     <td>${fmtMoney(v.display_price, cur)}</td><td><a href="${esc(v.url)}" target="_blank" rel="noopener nofollow">↗</a></td></tr>`;
  const others = p.other_offers.map(v => `<tr><td>${esc(rname(v.retailer_id))} <span class="badge">${v.country}</span></td>
     <td>${esc(v.title)}</td><td>${fmtMoney(v.display_price, cur)}</td><td><a href="${esc(v.url)}" target="_blank" rel="noopener nofollow">↗</a></td></tr>`).join("");
  const hist = p.price_history.length > 1 ? `<h3>${t("history")}</h3><table>${p.price_history.map(h =>
     `<tr><td>${new Date(h.ts * 1000).toLocaleDateString()}</td><td>${fmtMoney(h.price, h.currency)}</td></tr>`).join("")}</table>` : "";
  $("#detailBody").innerHTML = `<div class="inner">
    <button class="close" aria-label="Close" onclick="this.closest('dialog').close()">×</button>
    <div class="meta"><span class="badge">${p.country}</span> ${esc(rname(p.retailer_id))}${p.brand ? " · " + esc(p.brand) : ""}</div>
    <h2>${esc(p.title)}</h2>
    <p><strong>${fmtMoney(p.display_price, cur)}</strong>${p.currency !== cur && p.price != null ? ` <span class="meta">(${fmtMoney(p.price, p.currency)})</span>` : ""}</p>
    <table>
      <tr><th>${t("category")}</th><td>${esc(p.category ? label("categories", p.category) : "–")}</td></tr>
      <tr><th>${t("dims")}</th><td>${dimsText(p)}${p.seats ? ` · ${p.seats} ${t("seats").toLowerCase()}` : ""}</td></tr>
      <tr><th>${t("color")}</th><td>${p.colors.map(c => esc(label("colors", c))).join(", ") || "–"}${p.color_raw ? ` <span class="meta">(“${esc(p.color_raw)}”)</span>` : ""}</td></tr>
      <tr><th>${t("material")}</th><td>${p.materials.map(m => esc(label("materials", m))).join(", ") || "–"}</td></tr>
    </table>
    <a class="cta" href="${esc(p.url)}" target="_blank" rel="noopener nofollow">${t("view")} ↗</a>
    ${p.variants.length > 1 ? `<h3>${t("variants")}</h3><table>${p.variants.map(row).join("")}</table>` : ""}
    ${others ? `<h3>${t("others")}</h3><table>${others}</table>` : ""}
    ${hist}
    ${p.description ? `<p class="desc">${esc(p.description)}</p>` : ""}
  </div>`;
  $("#detail").showModal();
}

function applyLang() {
  document.documentElement.lang = state.lang;
  document.querySelectorAll("[data-i18n]").forEach(el => el.textContent = t(el.dataset.i18n));
  $("#q").placeholder = $("#q").dataset["ph" + state.lang[0].toUpperCase() + state.lang.slice(1)];
  $("#curLabel").textContent = state.currency;
}

function syncInputs() {
  $("#q").value = state.q; $("#sort").value = state.sort; $("#lang").value = state.lang; $("#currency").value = state.currency;
  NUMS.forEach(k => $("#" + k).value = state[k]);
  BOOLS.forEach(k => $("#" + k).checked = state[k]);
}

let debounce;
function bind() {
  $("#search").addEventListener("submit", e => { e.preventDefault(); state.q = $("#q").value.trim(); state.page = 1; run(); });
  $("#sort").addEventListener("change", e => { state.sort = e.target.value; state.page = 1; run(); });
  $("#lang").addEventListener("change", e => { state.lang = e.target.value; store("fb.lang", state.lang); applyLang(); run(); });
  $("#currency").addEventListener("change", e => { state.currency = e.target.value; store("fb.currency", state.currency); state.pmin = state.pmax = ""; syncInputs(); applyLang(); run(); });
  $("#filters").addEventListener("change", e => {
    const el = e.target;
    if (el.dataset.group) {
      const g = el.dataset.group;
      state[g] = el.checked ? [...state[g], el.value] : state[g].filter(v => v !== el.value);
    } else if (NUMS.includes(el.id)) state[el.id] = el.value;
    else if (BOOLS.includes(el.id)) state[el.id] = el.checked;
    state.page = 1; clearTimeout(debounce); debounce = setTimeout(run, 150);
  });
  $("#filters").addEventListener("click", e => {
    const sw = e.target.closest(".sw");
    if (sw) { const c = sw.dataset.color;
      state.color = state.color.includes(c) ? state.color.filter(x => x !== c) : [...state.color, c]; state.page = 1; run(); }
  });
  $("#filtersToggle").addEventListener("click", () => $("#filters").classList.toggle("open"));
  $("#clear").addEventListener("click", () => {
    MULTI.forEach(k => state[k] = []); NUMS.forEach(k => state[k] = ""); BOOLS.forEach(k => state[k] = false);
    state.page = 1; syncInputs(); run();
  });
  $("#understood").addEventListener("click", e => {
    const b = e.target.closest("[data-add]");
    if (b) { state[b.dataset.add] = [...state[b.dataset.add], b.dataset.id]; state.page = 1; run(); }
  });
  $("#results").addEventListener("click", e => { const c = e.target.closest(".card"); if (c) openDetail(c.dataset.id); });
  $("#pager").addEventListener("click", e => { const b = e.target.closest("[data-page]");
    if (b) { state.page = +b.dataset.page; run(); scrollTo({ top: 0, behavior: "smooth" }); } });
  $("#detail").addEventListener("click", e => { if (e.target.id === "detail") e.target.close(); });
}

(async function init() {
  META = await (await fetch("/api/meta")).json();
  syncInputs(); applyLang(); bind(); run(false);
})();
