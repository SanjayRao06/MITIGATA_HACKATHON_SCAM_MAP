/*
  Scam Map website logic: one page, many screens.

  How it fits together:
  - The address after "#" picks the screen: #/ (home), #/check, #/report, #/map, #/dashboard,
    #/guide, #/how, #/dispute, #/more. router() draws it into <main id="view">.
  - api() talks to our own server (same address), e.g. GET /lookup, POST /reports. If the server
    says 403 LICENSE_EXPIRED, the full-screen "Licence expired" message appears and we keep
    checking every 20 s until it works again (no reload needed).
  - Every visible word comes from i18n.js through t("key"), so EN <-> हिंदी switches instantly.
  - Privacy: we never ask for a name or phone. A random anonymous id is kept in this browser
    only, "Use my location" is turned into the nearest AREA on the phone and the coordinates are
    thrown away, and all server text is escaped before it's shown.
*/
"use strict";

/* ================================================================ state + small helpers */
const S = {
  lang: storeGet("sm_lang") || "en",
  meta: null,               // areas, scam types, channels from GET /meta
  leafletLoading: null,     // promise while the map library downloads
};

function storeGet(key) { try { return localStorage.getItem(key); } catch { return null; } }
function storeSet(key, val) { try { localStorage.setItem(key, val); } catch { /* private mode: fine */ } }

/** Text in the current language, with {placeholders} filled in. */
function t(key, vars = {}) {
  const s = (STRINGS[S.lang] && STRINGS[S.lang][key]) ?? STRINGS.en[key] ?? key;
  return s.replace(/\{(\w+)\}/g, (_, k) => (vars[k] ?? ""));
}
/** Escape text from the server before putting it into HTML (stops injected markup). */
function esc(v) {
  return String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const view = () => $("#view");

function scamName(type) { return (SCAM_INFO[S.lang][type] || SCAM_INFO[S.lang].other)[0]; }
function scamHow(type) { return (SCAM_INFO[S.lang][type] || SCAM_INFO[S.lang].other)[1]; }
function scamAdvice(type) { return (SCAM_INFO[S.lang][type] || SCAM_INFO[S.lang].other)[2]; }
function channelName(ch) { return CHANNEL_LABELS[S.lang][ch] || ch; }
function fmtNum(n) { return Number(n || 0).toLocaleString(S.lang === "hi" ? "hi-IN" : "en-IN"); }
function fmtDate(iso) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString(S.lang === "hi" ? "hi-IN" : "en-IN",
    { day: "numeric", month: "short", hour: "numeric", minute: "2-digit", timeZone: "Asia/Kolkata" });
}
/** A Date in the PRD's time format, in India time: 2026-10-31T14:00:00+05:30. */
function toIstIso(date) {
  return new Date(date.getTime() + 5.5 * 3600e3).toISOString().slice(0, 19) + "+05:30";
}
/** A time `hoursAgo` hours before now, in the PRD's format. */
function istIso(hoursAgo = 0) { return toIstIso(new Date(Date.now() - hoursAgo * 3600e3)); }
/** A Date as the "YYYY-MM-DDTHH:MM" text a datetime-local box uses (in this device's time zone). */
function localInputValue(date) {
  const d = new Date(date.getTime() - date.getTimezoneOffset() * 60e3);
  return d.toISOString().slice(0, 16);
}
function randomId(prefix) {
  const r = (crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(16).slice(2) + Date.now().toString(16));
  return prefix + r.replace(/-/g, "").slice(0, 16);
}
/** Anonymous reporter id: random, kept only in this browser, never linked to a person. */
function reporterId() {
  let id = storeGet("sm_rid");
  if (!id) { id = randomId("w_"); storeSet("sm_rid", id); }
  return id;
}
function toast(msg) {
  const el = $("#toast"); el.textContent = msg; el.hidden = false;
  clearTimeout(toast._t); toast._t = setTimeout(() => (el.hidden = true), 2200);
}
function haversineKm(a, b) {
  const R = 6371, r = (x) => (x * Math.PI) / 180;
  const dLat = r(b.lat - a.lat), dLng = r(b.lng - a.lng);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(r(a.lat)) * Math.cos(r(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

/* ================================================================ talking to the server */
class ApiError extends Error {
  constructor(status, body) { super(body?.error || `HTTP ${status}`); this.status = status; this.body = body; }
}

/** GET/POST JSON to our server. Throws ApiError for non-2xx; shows the expired screen on 403. */
async function api(path, body) {
  let res;
  try {
    res = await fetch(path, body === undefined ? {} : {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, { error: "network" });
  }
  let data = null;
  try { data = await res.json(); } catch { /* empty body */ }
  if (res.status === 403 && data?.error === "LICENSE_EXPIRED") showExpired();
  if (!res.ok) throw new ApiError(res.status, data);
  return data;
}

/** Areas / scam types / channels, fetched once and kept. */
async function getMeta() {
  if (!S.meta) S.meta = await api("/meta");
  return S.meta;
}

/* ================================================================ licence expired screen */
function showExpired() {
  const box = $("#expired");
  if (!box.hidden) return;
  box.hidden = false;
  // Check every 20 s whether the service works again; then hide the screen and redraw.
  clearInterval(showExpired._poll);
  showExpired._poll = setInterval(async () => {
    try {
      const res = await fetch("/alerts?pincode=560102");
      if (res.ok) { clearInterval(showExpired._poll); box.hidden = true; router(); watchLicence(); }
    } catch { /* still offline */ }
  }, 20000);
}

/**
 * Licence watcher: lock the page the moment the licence ends, even if nobody clicks anything.
 * In: nothing. Out: nothing (it re-schedules itself).
 * Why: without it the expired screen only appears on the next request that gets a 403.
 * How: ask GET /license (always answers, never locked) every 15 s, and also set a timer for the
 * exact expiry second it reports, so the lock is on time and a newly uploaded licence (e.g. a
 * short demo one replacing the long one) is picked up within 15 s.
 */
async function watchLicence() {
  clearTimeout(watchLicence._next);
  clearTimeout(watchLicence._expiry);
  let wait = 15000;
  try {
    const res = await fetch("/license", { cache: "no-store" });
    const lic = res.ok ? await res.json() : null;
    if (lic && !lic.valid) { showExpired(); return; }        // expired: lock now (recovery is in showExpired)
    if (lic && lic.seconds_left != null) {
      // Timer for the exact end (+1 s so the server agrees it has passed).
      const ms = (lic.seconds_left + 1) * 1000;
      if (ms < 2 ** 31) watchLicence._expiry = setTimeout(watchLicence, ms);
    }
  } catch { /* offline: try again later */ }
  watchLicence._next = setTimeout(watchLicence, wait);
}

/* ================================================================ static text + icons */
function applyStatic() {
  document.documentElement.lang = S.lang;
  $$("[data-t]").forEach((el) => (el.textContent = t(el.dataset.t)));
  $$("[data-icon]").forEach((el) => { if (!el.dataset.done) { el.innerHTML = icon(el.dataset.icon); el.dataset.done = "1"; } });
  $$(".lang [data-lang]").forEach((el) => el.classList.toggle("on", el.dataset.lang === S.lang));
}
$("#langToggle").addEventListener("click", () => {
  S.lang = S.lang === "en" ? "hi" : "en";
  storeSet("sm_lang", S.lang);
  applyStatic();
  router();
});

/* ================================================================ router */
const ROUTES = {
  "": pageHome, check: pageCheck, report: pageReport, map: pageMap, dashboard: pageDashboard,
  guide: pageGuide, how: pageHow, dispute: pageDispute, more: pageMore,
};

/** Read "#/check?value=..." -> {name: "check", params: {value: "..."}} and draw that screen. */
function router() {
  const raw = location.hash.replace(/^#\/?/, "");
  const [name, query = ""] = raw.split("?");
  const params = Object.fromEntries(new URLSearchParams(query));
  // A link like "#/report?lang=hi" opens the site in Hindi (handy for demos and sharing).
  if ((params.lang === "hi" || params.lang === "en") && params.lang !== S.lang) {
    S.lang = params.lang; storeSet("sm_lang", S.lang); applyStatic();
  }
  const page = ROUTES[name] || pageHome;
  const navName = ROUTES[name] ? (name || "home") : "home";
  $$("[data-nav]").forEach((a) => a.classList.toggle("on", a.dataset.nav === navName));
  if (S.mapInstance && name !== "map") { S.mapInstance.remove(); S.mapInstance = null; }
  window.scrollTo(0, 0);
  page(params);
}
window.addEventListener("hashchange", router);

/* ================================================================ shared pieces */
function alertText(a) {
  const area = esc(a.locality || a.pincode);
  return a.type === "SPIKE" ? t("alert_spike", { area, n: a.count }) : t("alert_new", { area, type: esc(scamName(a.scam_type)) });
}
function alertBanners(alerts, max = 2) {
  return alerts.slice(0, max).map((a) => `
    <div class="banner">${icon("alert")}<div><strong>${t("alert_label")}</strong>${alertText(a)}</div></div>`).join("");
}
function errorBox(msg) { return `<p class="err">${icon("alertCircle")}<span>${esc(msg)}</span></p>`; }
function errMessage(e) {
  if (e.status === 0) return t("err_network");
  return t("err_generic");
}

/** Guess what someone pasted: link, UPI ID, SMS sender or phone number. */
function detectType(value) {
  const v = (value || "").trim();
  if (!v) return null;
  if (/^[a-z][a-z0-9+.-]*:\/\//i.test(v) || (/[a-z]/i.test(v) && /\.[a-z]{2,}/i.test(v) && !v.includes("@"))) return "url";
  if (v.includes("@")) return "upi";
  if (/[a-z]/i.test(v)) return "sender_id";
  return "phone";
}
const TYPES = ["phone", "upi", "url", "sender_id"];

/* How the input box looks for each identifier type: example text, phone keyboard, icon. */
const TYPE_INPUT = {
  phone: { ph: "+91 98765 43210", mode: "tel", icon: "phone" },
  upi: { ph: "name@okaxis", mode: "email", icon: "rupee" },
  url: { ph: "https://sbi-kyc.in/pay", mode: "url", icon: "link" },
  sender_id: { ph: "VM-HDFCBK", mode: "text", icon: "message" },
};

/** The four type tabs (Phone / UPI ID / Link / SMS sender) used on Check, Report and Dispute. */
function typeTabs(id, chosen) {
  return `<div class="segmented" id="${id}" role="radiogroup">${TYPES.map((k) => `
    <button type="button" role="radio" class="seg ${k === chosen ? "on" : ""}" data-v="${k}" aria-checked="${k === chosen}">
      ${icon(TYPE_INPUT[k].icon)}<span>${t("type_" + k)}</span></button>`).join("")}</div>`;
}

/**
 * Wire up type tabs + their input box. The user picks the type first; the box then shows the
 * right example and phone keyboard. If they paste something that is clearly another type
 * (e.g. an "@" UPI ID while "Phone" is picked) we switch the tab for them and say so.
 * Returns {type, touched, set(type)}: the current type, whether the user chose it themselves,
 * and a way for the page to change it (Report pre-picks the type from the channel).
 */
function bindTypeInput(tabsSel, inputSel, hintSel, startType, onChange = () => {}) {
  const st = { type: startType, touched: false };
  const input = $(inputSel);
  const apply = (type) => {
    st.type = type;
    $$(`${tabsSel} [data-v]`).forEach((b) => { b.classList.toggle("on", b.dataset.v === type); b.setAttribute("aria-checked", b.dataset.v === type); });
    input.placeholder = TYPE_INPUT[type].ph;
    input.inputMode = TYPE_INPUT[type].mode;
    $(`${inputSel}-label`) && ($(`${inputSel}-label`).textContent = t("enter_" + type));
    onChange(type);
  };
  $(tabsSel).addEventListener("click", (e) => {
    const b = e.target.closest("[data-v]"); if (!b) return;
    st.touched = true; apply(b.dataset.v); $(hintSel).textContent = ""; input.focus();
  });
  input.addEventListener("input", () => {
    st.touched = true;
    const d = detectType(input.value);
    // Only switch for clear cases: a phone tab with letters/@ in the box, or digits-only in another tab.
    if (d && d !== st.type && (d !== "sender_id" || st.type === "phone")) {
      apply(d); $(hintSel).textContent = t("switched", { type: t("type_" + d) });
    }
  });
  apply(startType);
  st.set = apply;
  return st;
}

/* ================================================================ HOME */
async function pageHome() {
  view().innerHTML = `
    <section class="hero">
      <span class="eyebrow">${icon("shieldCheck")} Scam Map</span>
      <h1>${t("home_title")}</h1>
      <p class="lead">${t("home_sub")}</p>
      <div class="btn-row" style="margin-top:16px">
        <a class="btn" href="#/check">${icon("search")} ${t("home_check")}</a>
        <a class="btn btn-outline" href="#/report">${icon("flag")} ${t("home_report")}</a>
      </div>
      <form class="field" id="quick" style="margin-top:12px" role="search">
        ${icon("copy")}
        <input name="v" autocomplete="off" placeholder="${t("paste_placeholder")}" aria-label="${t("paste_placeholder")}">
        <button class="btn btn-sm" type="submit">${t("check_btn")} ${icon("arrowRight")}</button>
      </form>
    </section>
    <div class="section" id="homeAlerts"></div>
    <div class="section grid3" id="homeStats">
      <div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div>
    </div>
    <div class="section split">
      <div class="card">
        <div class="section-head"><h2>${icon("mapPin")} ${t("home_map_title")}</h2></div>
        <p class="muted small">${t("home_map_sub")}</p>
        <ul class="mini-areas" id="homeAreas"><li class="skeleton"></li></ul>
        <a class="btn btn-quiet btn-block" style="margin-top:12px" href="#/map">${t("home_map_cta")} ${icon("arrowRight")}</a>
      </div>
      <div>
        <div class="section-head"><div><h2>${t("home_guide_title")}</h2><p class="muted small" style="margin:0">${t("home_guide_sub")}</p></div></div>
        <div class="grid2">${["digital-arrest", "fake-kyc-link", "upi-refund-qr", "job-offer"].map((k) => `
          <a class="scam-card" href="#/guide"><span class="ico-wrap">${icon(SCAM_TYPE_ICONS[k])}</span>
            <b>${esc(scamName(k))}</b><span>${esc(scamAdvice(k))}</span></a>`).join("")}
        </div>
        <a href="#/guide" class="small" style="display:inline-block;margin-top:10px">${t("home_guide_cta")} →</a>
      </div>
    </div>
    <a class="section dispute-card" href="#/dispute">
      <span class="ico-wrap">${icon("scale")}</span>
      <span><b>${t("home_dispute_title")}</b><span class="muted small">${t("home_dispute_sub")}</span></span>
      ${icon("chevronRight")}
    </a>`;
  $("#quick").addEventListener("submit", (e) => {
    e.preventDefault();
    const v = e.target.v.value.trim();
    location.hash = v ? `#/check?value=${encodeURIComponent(v)}` : "#/check";
  });

  // Live numbers: stats + alerts (all of India). Failures just leave the section quiet.
  try {
    const [stats, alerts] = await Promise.all([api("/stats"), api("/alerts")]);
    $("#homeAlerts").innerHTML = alertBanners(alerts.alerts, 1);
    $("#homeStats").innerHTML = `
      <div class="stat"><b>${fmtNum(stats.reports_this_week)}</b><span>${t("stat_reports")}</span></div>
      <div class="stat"><b>${fmtNum(stats.areas_affected)}</b><span>${t("stat_areas")}</span></div>
      <div class="stat"><b>${fmtNum(stats.alerts_now)}</b><span>${t("stat_alerts")}</span></div>`;
    $("#homeAreas").innerHTML = stats.top_areas.length ? stats.top_areas.slice(0, 4).map((a) => `
      <li><span><b>${esc(a.locality)}</b> <span class="muted small">${esc(a.city)}</span></span>
          <span class="pill sev-${esc(a.severity)}">${t("area_reports", { n: fmtNum(a.count) })}</span></li>`).join("")
      : `<li class="muted">${t("home_map_empty")}</li>`;
  } catch {
    $("#homeStats").innerHTML = "";
    $("#homeAreas").innerHTML = `<li class="muted">${t("home_map_empty")}</li>`;
  }
}

/* ================================================================ CHECK */
function pageCheck(params) {
  // Start on the type from the link, else guess it from a value passed in (home search box), else Phone.
  const start = TYPES.includes(params.type) ? params.type : (detectType(params.value) || "phone");
  view().innerHTML = `
    <div class="split">
      <section>
        <span class="eyebrow">${icon("search")} ${t("nav_check")}</span>
        <h1>${t("check_title")}</h1>
        <p class="lead">${t("check_sub")}</p>
        <form id="checkForm" class="card" style="margin-top:14px" novalidate>
          <label class="lbl">${t("q_kind")}</label>
          ${typeTabs("ctypes", start)}
          <label class="lbl" for="cv" id="cv-label" style="margin-top:14px"></label>
          <div class="field">${icon("search")}
            <input id="cv" name="v" autocomplete="off" value="${esc(params.value || "")}">
            <button type="button" class="clear" aria-label="Clear" id="cclear">${icon("x")}</button>
          </div>
          <p class="hint" id="cdetect"></p>
          <button class="btn btn-block" style="margin-top:12px" type="submit">${icon("search")} ${t("check_btn")}</button>
          <div id="cerr"></div>
        </form>
      </section>
      <section id="cresult" aria-live="polite"></section>
    </div>`;

  const input = $("#cv");
  const picked = bindTypeInput("#ctypes", "#cv", "#cdetect", start, () => { $("#cerr").innerHTML = ""; });
  $("#cclear").addEventListener("click", () => { input.value = ""; input.focus(); $("#cdetect").textContent = ""; $("#cresult").innerHTML = ""; });
  $("#checkForm").addEventListener("submit", (e) => { e.preventDefault(); runCheck(); });

  async function runCheck() {
    const value = input.value.trim();
    $("#cerr").innerHTML = "";
    if (!value) { $("#cerr").innerHTML = errorBox(t("required_" + picked.type)); return; }
    $("#cresult").innerHTML = `<div class="skeleton" style="min-height:220px"></div>`;
    try {
      const [r] = await Promise.all([api(`/lookup?type=${picked.type}&value=${encodeURIComponent(value)}`), safeMeta()]);
      $("#cresult").innerHTML = resultCard(r, value, picked.type);
      if (window.innerWidth < 900) $("#cresult").scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) {
      $("#cresult").innerHTML = "";
      $("#cerr").innerHTML = errorBox(err.status === 400 ? t("err_" + picked.type) : errMessage(err));
    }
  }
  if (params.value) runCheck();
}

/** The user's own area (saved on this device when they report or use "my location"), or null. */
function myArea() {
  const pin = storeGet("sm_area");
  return (pin && S.meta?.areas.find((a) => a.pincode === pin)) || null;
}

/**
 * "Why this result?": a fold-out list explaining the verdict in plain words (EN/HI).
 * In: the /lookup reply; its `why` list holds reason codes + counts (no ids, no notes) made by the
 * server's trust rules. Each code has a "why_<code>" text in i18n.js. Unknown codes are skipped,
 * so an older or newer server never breaks the page. Closed by default to keep the card short.
 */
function whyPanel(r) {
  const items = (r.why || []).filter((w) => STRINGS.en["why_" + w.code]);
  if (!items.length) return "";
  const num = (w) => Object.fromEntries(Object.entries(w).map(([k, v]) => [k, typeof v === "number" ? fmtNum(v) : v]));
  const okCodes = ["verified_list", "bar_met", "independent", "received", "no_reports"];
  return `
    <details class="more why">
      <summary>${icon("info")}<div><b>${t("why_title")}</b><br><span class="muted small">${t("why_sub")}</span></div>${icon("chevronDown")}</summary>
      <div class="more-body">
        <ol class="why-list">${items.map((w) => `
          <li class="${okCodes.includes(w.code) ? "" : "why-rule"}">${esc(t("why_" + w.code, num(w)))}</li>`).join("")}
        </ol>
        <p class="note">${icon("eyeOff")}<span>${t("why_privacy")}</span></p>
      </div>
    </details>`;
}

/** The coloured result card for one /lookup reply. */
function resultCard(r, typed, idType) {
  const cls = { KNOWN_SCAM: "known", SUSPICIOUS: "susp", NO_REPORTS: "none", VERIFIED_BUSINESS: "verified" }[r.verdict];
  const headIcon = { known: "alert", susp: "alertCircle", none: "info", verified: "shieldCheck" }[cls];
  // "Reported by 7 people" ([PRD §3] example). People = different people AFTER the trust rules.
  const people = r.distinct_reporters || 0;
  const reportedBy = t(people === 1 ? "v_by_one" : "v_by_many", { n: fmtNum(people) });

  // "Near you": areas in the evidence within 10 km of the user's own saved area (device only).
  const mine = myArea();
  const areaOf = (pin) => S.meta?.areas.find((a) => a.pincode === pin);
  const evAreas = [...new Set((r.evidence || []).map((ev) => ev.pincode))].map(areaOf).filter(Boolean);
  const near = mine ? evAreas.filter((a) => haversineKm(mine, a) <= 10) : [];

  let title, sub;
  if (r.verdict === "KNOWN_SCAM") { title = near.length ? t("v_known_near", { n: fmtNum(people) }) : reportedBy; sub = t("v_known_sub"); }
  else if (r.verdict === "SUSPICIOUS") { title = reportedBy + " " + t("v_susp_tail"); sub = r.masked ? t("v_susp_sub") : ""; }
  else if (r.verdict === "VERIFIED_BUSINESS") {
    title = t("v_verified");
    sub = (r.message || "").split(":").slice(1).join(":").trim();   // "Verified business: HDFC Bank ..."
  } else { title = t("v_none"); sub = t("v_none_sub"); }

  const facts = r.report_count ? `
    <dl class="facts">
      <dt>${t("r_last")}</dt><dd>${esc(fmtDate(r.last_seen))}</dd>
      <dt>${t("r_first")}</dt><dd>${esc(fmtDate(r.first_seen))}</dd>
      ${r.scam_type ? `<dt>${t("r_type")}</dt><dd>${esc(scamName(r.scam_type))}</dd>` : ""}
      <dt>${t("r_people")}</dt><dd>${fmtNum(people)}</dd>
      <dt>${t("r_reports")}</dt><dd>${fmtNum(r.report_count)}</dd>
      ${near.length ? `<dt>${t("r_near", { area: esc(mine.locality) })}</dt><dd>${esc(near.slice(0, 3).map((a) => a.locality).join(", "))}</dd>`
        : evAreas.length ? `<dt>${t("r_areas")}</dt><dd>${esc(evAreas.slice(0, 3).map((a) => a.locality).join(", "))}</dd>` : ""}
    </dl>` : "";
  const advice = r.verdict === "VERIFIED_BUSINESS" ? "" : `
    <div class="advice">${icon("shieldCheck")}<div><b>${t("advice_title")}</b>${esc(scamAdvice(r.scam_type || "otp-call"))}</div></div>`;
  const recent = (r.evidence || []).length ? `
    <div class="card" style="margin-top:12px">
      <div class="section-head"><h3 style="margin:0">${t("recent_title")}</h3><span class="pill sage">${fmtNum(r.report_count)}</span></div>
      <ul class="list">${r.evidence.slice(0, 5).map((ev) => `
        <li>${icon(CHANNEL_ICONS[ev.channel] || "dots")}
          <div><b>${esc(scamName(ev.scam_type))}</b><br><span class="muted small">${esc(channelName(ev.channel))} · ${esc(S.meta?.areas.find((a) => a.pincode === ev.pincode)?.locality || ev.pincode)}</span></div>
          <span class="meta">${esc(fmtDate(ev.occurred_at))}</span></li>`).join("")}
      </ul>
      <p class="note">${icon("eyeOff")}<span>${t("recent_note")}</span></p>
    </div>` : "";

  return `
    <div class="result ${cls}">
      <div class="result-head"><span class="badge-ico">${icon(headIcon)}</span>
        <div><span class="verdict-label">${t("verdict_" + r.verdict)}</span>
          <h2>${esc(title)}</h2>${sub ? `<p>${esc(sub)}</p>` : ""}</div></div>
      <div class="result-body">
        ${r.challenged ? `<div class="underreview">${icon("scale")} ${t("v_challenged")}</div>` : ""}
        <div class="value-box"><small>${t("r_value_" + idType)}</small><b>${esc(r.display_value)}</b>
          ${r.masked ? `<span class="small muted">${t(r.challenged ? "r_hidden_review" : "r_hidden")}</span>` : ""}</div>
        ${facts}${advice}${whyPanel(r)}
        <div class="btn-row">
          ${r.verdict === "VERIFIED_BUSINESS" ? "" : `<a class="btn btn-quiet btn-sm" href="#/report?value=${encodeURIComponent(typed)}&type=${idType}">${icon("flag")} ${t("report_this")}</a>`}
          <a class="btn btn-danger btn-sm" href="tel:1930">${icon("phone")} ${t("call_1930")}</a>
        </div>
        ${r.report_count && !r.challenged && r.verdict !== "VERIFIED_BUSINESS" ? `
          <a class="dispute-link" href="#/dispute?value=${encodeURIComponent(typed)}&type=${idType}">${icon("scale")} ${t("dispute_cta")}</a>` : ""}
      </div>
    </div>${recent}`;
}

/* ================================================================ REPORT */
/* Which identifier type each channel usually means, so step 3 starts on the right tab. */
const CHANNEL_TYPE = { "Phone call": "phone", "SMS or WhatsApp": "phone", "QR code": "upi",
  "Fake website": "url", "UPI request": "upi" };
const OTHER_CHANNEL = "Something else";
/* Short keys for the channel names, used to word step 3 ("q_what_call" = "Their phone number"). */
const CHANNEL_KEY = { "Phone call": "call", "SMS or WhatsApp": "sms", "QR code": "qr",
  "Fake website": "web", "UPI request": "upi", "Something else": "other" };
/* Pictures for the "when" chips, so they can be told apart without reading. */
const WHEN_ICONS = { now: "zap", today: "sun", yesterday: "moon", pick: "calendar" };
const EVIDENCE_KINDS = [["screenshot", "camera"], ["screen_rec", "smartphone"], ["call_rec", "headset"]];

async function pageReport(params) {
  const meta = await safeMeta();
  const savedPin = storeGet("sm_area");
  const form = {
    channel: "Phone call", when: "now",
    area: meta?.areas.find((a) => a.pincode === savedPin) || null,
    scamType: null, evidence: new Set(),
  };
  const whenHours = { now: 0, today: 3, yesterday: 24 };
  const startType = TYPES.includes(params.type) ? params.type : (detectType(params.value) || "phone");
  const openedAt = performance.now();   // rehearsal stopwatch: form opened -> report sent (PRD: < 60 s)
  const now = new Date();

  view().innerHTML = `
    <section class="report-page">
      <span class="eyebrow">${icon("flag")} ${t("nav_report")}</span>
      <h1>${t("report_title")}</h1>
      <p class="note">${icon("lock")}<span>${t("report_sub")}</span></p>
      <form id="rform" novalidate>
        <div class="step"><div class="step-title"><span class="step-num">1</span><span class="step-ico">${icon("message")}</span><h2>${t("q_channel")}</h2></div>
          <div class="tiles" id="rchan" role="radiogroup" aria-label="${t("q_channel")}">
            ${(meta?.channels || Object.keys(CHANNEL_ICONS)).map((c) => `
              <button type="button" role="radio" class="tile ${c === form.channel ? "on" : ""}" data-v="${esc(c)}" aria-checked="${c === form.channel}">
                ${icon(CHANNEL_ICONS[c] || "dots")}<span>${esc(channelName(c))}</span></button>`).join("")}
          </div>
          <input class="input" id="rchanother" maxlength="60" placeholder="${t("channel_other_ph")}" aria-label="${t("channel_other_ph")}" style="margin-top:8px" hidden></div>

        <div class="step"><div class="step-title"><span class="step-num">2</span><span class="step-ico">${icon("clock")}</span><h2>${t("q_when")}</h2></div>
          <div class="chips" id="rwhen">${[...Object.keys(whenHours), "pick"].map((k) => `
            <button type="button" class="chip ${k === form.when ? "on" : ""}" data-v="${k}">${icon(WHEN_ICONS[k])}${t("when_" + k)}</button>`).join("")}</div>
          <input class="input" type="datetime-local" id="rwhenat" style="margin-top:8px" hidden
            max="${localInputValue(now)}" min="${localInputValue(new Date(now - 365 * 864e5))}" value="${localInputValue(now)}" aria-label="${t("when_pick")}">
          <div id="rwhenerr"></div></div>

        <div class="step"><div class="step-title"><span class="step-num">3</span><span class="step-ico">${icon("clipboard")}</span><h2 id="rwhat"></h2></div>
          <p class="hint"><span id="rtypenow"></span> · <button type="button" class="linkbtn" id="rtypechange">${t("change")}</button></p>
          <div style="margin-top:8px" id="rtypewrap" hidden>${typeTabs("rtype", startType)}</div>
          <div class="field" style="margin-top:10px">${icon("copy")}
            <input id="rval" autocomplete="off" aria-labelledby="rwhat" value="${esc(params.value || "")}">
            <button type="button" class="paste-btn" id="rpaste" aria-label="${t("paste")}" hidden>${icon("clipboard")}<span>${t("paste")}</span></button></div>
          <p class="hint" id="rtypehint"></p>
          <div id="rvalerr"></div></div>

        <div class="step"><div class="step-title"><span class="step-num">4</span><span class="step-ico">${icon("mapPin")}</span><h2>${t("q_area")}</h2></div>
          <p class="hint">${t("q_area_sub")}</p>
          <div class="combo" style="margin-top:8px">
            <div class="field">${icon("search")}<input id="rarea" autocomplete="off" placeholder="${t("area_placeholder")}"
              value="${form.area ? esc(form.area.locality + ", " + form.area.city + " · " + form.area.pincode) : ""}" aria-label="${t("q_area")}"></div>
            <ul class="combo-list" id="rarealist" hidden></ul>
          </div>
          <button type="button" class="btn btn-quiet btn-sm" style="margin-top:8px" id="rloc">${icon("locate")} ${t("use_location")}</button>
          <p class="hint" id="rlocmsg"></p><div id="rareaerr"></div></div>

        <details class="more"><summary>${icon("sliders")}<div><b>${t("details_title")}</b><br><span class="muted small">${t("details_sub")}</span></div>${icon("chevronDown")}</summary>
          <div class="more-body">
            <label class="lbl">${t("q_type")}</label>
            <div class="tiles small" id="rscam">${Object.keys(SCAM_TYPE_ICONS).map((k) => `
              <button type="button" class="tile" data-v="${k}">${icon(SCAM_TYPE_ICONS[k])}<span>${esc(scamName(k))}</span></button>`).join("")}</div>
            <input class="input" id="rscamother" maxlength="60" placeholder="${t("scam_other_ph")}" aria-label="${t("scam_other_ph")}" style="margin-top:8px" hidden>
            <label class="lbl" for="rnote" style="margin-top:16px">${t("q_note")}</label>
            <textarea class="input" id="rnote" maxlength="2000" placeholder="${t("note_placeholder")}"></textarea>
            <label class="lbl" for="ramt" style="margin-top:16px">${t("q_amount")}</label>
            <input class="input" id="ramt" type="number" min="0" inputmode="numeric" placeholder="0">
            <label class="lbl" style="margin-top:16px">${t("q_evidence")}</label>
            <div class="chips" id="revid">${EVIDENCE_KINDS.map(([k, ic]) => `
              <button type="button" class="chip" data-v="${k}" aria-pressed="false">${icon(ic)} ${t("ev_" + k)}</button>`).join("")}</div>
            <p class="hint">${icon("lock")} ${t("evidence_note")}</p>
          </div></details>

        <button class="btn btn-block" style="margin-top:22px" type="submit" id="rsend">${icon("shieldCheck")} ${t("submit_report")}</button>
        <div id="rerr"></div>
      </form>
    </section>`;

  // ---- step 3: type tabs + box. Created first so step 1 can pre-pick the type.
  const val = $("#rval");
  // Step 1 already asked HOW they made contact, so step 3 only asks for the value, worded to match
  // ("Their phone number", "The website link" ...). The type is guessed from what's pasted; the
  // four type tabs stay hidden behind "Change" for the rare case the guess is wrong.
  const picked = bindTypeInput("#rtype", "#rval", "#rtypehint", startType, (type) => {
    $("#rvalerr").innerHTML = "";
    $("#rtypenow").textContent = t("type_is", { type: t("type_" + type) });
  });
  if (params.value || params.type) picked.touched = true;
  // Paste button: only shown where the browser lets a page read the clipboard (needs https).
  if (navigator.clipboard?.readText) {
    $("#rpaste").hidden = false;
    $("#rpaste").addEventListener("click", async () => {
      try {
        const text = (await navigator.clipboard.readText()).trim();
        if (text) { val.value = text.slice(0, 300); val.dispatchEvent(new Event("input", { bubbles: true })); }
      } catch { val.focus(); }      // permission refused: just put the cursor in the box
    });
  }
  $("#rtypechange").addEventListener("click", () => { $("#rtypewrap").hidden = !$("#rtypewrap").hidden; });
  const setWhatTitle = () => { $("#rwhat").textContent = t("q_what_" + (CHANNEL_KEY[form.channel] || "other")); };
  setWhatTitle();

  // ---- step 1: channel tiles. "Something else" opens a short "please say how" box.
  pickOne("#rchan", (v) => {
    form.channel = v;
    setWhatTitle();
    $("#rchanother").hidden = v !== OTHER_CHANNEL;
    if (v === OTHER_CHANNEL) $("#rchanother").focus();
    if (!picked.touched && CHANNEL_TYPE[v]) picked.set(CHANNEL_TYPE[v]);
  });

  // ---- step 2: quick chips, or "Pick date & time" for an exact time (shown on Check as "Last reported").
  pickOne("#rwhen", (v) => {
    form.when = v;
    $("#rwhenat").hidden = v !== "pick";
    $("#rwhenerr").innerHTML = "";
  });

  // ---- optional: scam type (tap again to unselect); "Something else" opens a box.
  $("#rscam").addEventListener("click", (e) => {
    const b = e.target.closest("[data-v]"); if (!b) return;
    form.scamType = form.scamType === b.dataset.v ? null : b.dataset.v;
    $$("#rscam .tile").forEach((x) => x.classList.toggle("on", x.dataset.v === form.scamType));
    $("#rscamother").hidden = form.scamType !== "other";
    if (form.scamType === "other") $("#rscamother").focus();
  });
  // ---- optional: which proof they have (several allowed). Files are NOT uploaded (privacy).
  $("#revid").addEventListener("click", (e) => {
    const b = e.target.closest("[data-v]"); if (!b) return;
    const k = b.dataset.v;
    form.evidence.has(k) ? form.evidence.delete(k) : form.evidence.add(k);
    b.classList.toggle("on", form.evidence.has(k)); b.setAttribute("aria-pressed", form.evidence.has(k));
  });

  // ---- step 4: searchable area list + "use my location"
  const areaInput = $("#rarea"), list = $("#rarealist");
  const drawList = () => {
    const q = areaInput.value.trim().toLowerCase();
    const hits = (meta?.areas || []).filter((a) => !q || `${a.locality} ${a.city} ${a.pincode}`.toLowerCase().includes(q)).slice(0, 8);
    list.innerHTML = hits.map((a) => `<li data-pin="${esc(a.pincode)}">${esc(a.locality)}, ${esc(a.city)} <span>${esc(a.pincode)}</span></li>`).join("");
    list.hidden = !hits.length;
  };
  areaInput.addEventListener("focus", drawList);
  areaInput.addEventListener("input", () => { form.area = null; drawList(); });
  areaInput.addEventListener("blur", () => setTimeout(() => (list.hidden = true), 150));
  list.addEventListener("mousedown", (e) => {
    const li = e.target.closest("[data-pin]"); if (!li) return;
    setArea(meta.areas.find((a) => a.pincode === li.dataset.pin));
  });
  function setArea(a) {
    form.area = a;
    areaInput.value = `${a.locality}, ${a.city} · ${a.pincode}`;
    list.hidden = true; $("#rareaerr").innerHTML = "";
    storeSet("sm_area", a.pincode);
  }
  $("#rloc").addEventListener("click", () => {
    if (!navigator.geolocation || !meta) { $("#rlocmsg").textContent = t("location_failed"); return; }
    $("#rlocmsg").textContent = t("locating");
    navigator.geolocation.getCurrentPosition((pos) => {
      // Turn the position into the nearest AREA right here on the phone; the coordinates are
      // never sent or stored ([PRD §5] rule 1).
      const here = { lat: pos.coords.latitude, lng: pos.coords.longitude };
      const nearest = meta.areas.reduce((best, a) => (haversineKm(here, a) < haversineKm(here, best) ? a : best));
      setArea(nearest);
      $("#rlocmsg").textContent = t("location_found", { area: nearest.locality });
    }, () => ($("#rlocmsg").textContent = t("location_failed")), { timeout: 8000, maximumAge: 600000 });
  });

  /** The report's occurred_at: from the quick chip, or the picked date & time (null if invalid). */
  function occurredAt() {
    if (form.when !== "pick") return istIso(whenHours[form.when]);
    const picked = new Date($("#rwhenat").value);
    if (isNaN(picked) || picked > new Date(Date.now() + 5 * 60e3)) return null;   // empty or in the future
    return toIstIso(picked);
  }

  // ---- submit
  $("#rform").addEventListener("submit", async (e) => {
    e.preventDefault();
    $("#rerr").innerHTML = $("#rvalerr").innerHTML = $("#rareaerr").innerHTML = $("#rwhenerr").innerHTML = "";
    const value = val.value.trim();
    const occurred = occurredAt();
    if (!occurred) { $("#rwhenerr").innerHTML = errorBox(t("err_when")); $("#rwhenat").focus(); return; }
    if (!value) { $("#rvalerr").innerHTML = errorBox(t("required_" + picked.type)); val.focus(); return; }
    if (!form.area) { $("#rareaerr").innerHTML = errorBox(t("required_area")); areaInput.focus(); return; }

    const body = {
      report_id: randomId("web_"),
      occurred_at: occurred,
      reported_at: istIso(0),
      reporter_id: reporterId(),
      ip_prefix: "web",                       // the server works out the network and hashes it
      channel: form.channel,
      identifier_type: picked.type,
      identifier_value: value,
      pincode: form.area.pincode, locality: form.area.locality, city: form.area.city,
      note: $("#rnote").value.trim(),
      has_screenshot: form.evidence.size > 0, // any proof (screenshot / recording) counts for the trust rules
      amount_lost_inr: Math.max(0, Number($("#ramt").value) || 0),
    };
    if (form.scamType) body.scam_type = form.scamType;
    if (form.channel === OTHER_CHANNEL && $("#rchanother").value.trim()) body.channel_other = $("#rchanother").value.trim();
    if (form.scamType === "other" && $("#rscamother").value.trim()) body.scam_type_other = $("#rscamother").value.trim();

    const btn = $("#rsend"); btn.disabled = true; btn.innerHTML = `<span class="spinner"></span> ${t("sending")}`;
    try {
      await api("/reports", body);
      console.info(`[stopwatch] report sent in ${((performance.now() - openedAt) / 1000).toFixed(1)} s`);
      reportSuccess(value, picked.type, form.scamType);
    } catch (err) {
      btn.disabled = false; btn.innerHTML = `${icon("shieldCheck")} ${t("submit_report")}`;
      const msg = err.body?.error || "";
      if (err.status === 400 && msg.includes("identifier")) $("#rvalerr").innerHTML = errorBox(t("err_" + picked.type));
      else if (err.status === 400 && msg.includes("pincode")) $("#rareaerr").innerHTML = errorBox(t("err_area"));
      else if (err.status === 400 && msg.includes("occurred_at")) $("#rwhenerr").innerHTML = errorBox(t("err_when"));
      else if (err.status === 429) $("#rerr").innerHTML = errorBox(t("err_rate"));
      else $("#rerr").innerHTML = errorBox(errMessage(err));
    }
  });
}

/** "Thanks" screen, with the safety advice for the scam type they picked (or general advice). */
function reportSuccess(value, idType, scamType) {
  const k = scamType && scamType !== "other" ? scamType : null;
  view().innerHTML = `
    <section class="success card narrow" style="margin:0 auto">
      <span class="big-ico">${icon("checkCircle")}</span>
      <h1>${t("ok_title")}</h1>
      <p class="lead" style="margin:0 auto 18px">${t("ok_sub")}</p>
      <div class="advice" style="text-align:left">${icon("shieldCheck")}<div><b>${t("advice_title")}</b>${esc(scamAdvice(k || "otp-call"))}</div></div>
      <div class="btn-row">
        <a class="btn" href="#/check?value=${encodeURIComponent(value)}&type=${idType}">${icon("search")} ${t("ok_check")}</a>
        <a class="btn btn-quiet" href="#/report">${icon("flag")} ${t("ok_another")}</a>
      </div>
      <a class="btn btn-danger btn-block" style="margin-top:10px" href="tel:1930">${icon("phone")} ${t("footer_lost")}</a>
    </section>`;
}

/** Make a group of buttons act like radio buttons; calls onPick(value). */
function pickOne(sel, onPick) {
  $(sel).addEventListener("click", (e) => {
    const b = e.target.closest("[data-v]"); if (!b) return;
    $$(`${sel} [data-v]`).forEach((x) => { x.classList.toggle("on", x === b); x.setAttribute("aria-checked", x === b); });
    onPick(b.dataset.v);
  });
}
async function safeMeta() { try { return await getMeta(); } catch { return null; } }

/* ================================================================ MAP */
function loadLeaflet() {
  if (window.L) return Promise.resolve();
  if (S.leafletLoading) return S.leafletLoading;
  S.leafletLoading = new Promise((resolve, reject) => {
    const css = document.createElement("link");
    css.rel = "stylesheet"; css.href = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css";
    document.head.appendChild(css);
    const js = document.createElement("script");
    js.src = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js";
    js.onload = resolve; js.onerror = reject;
    document.head.appendChild(js);
  });
  return S.leafletLoading;
}
const SEV_COLOR = { MED: "#C9A227", HIGH: "#D47A2A", CRIT: "#B5452F" };

async function pageMap() {
  const st = { days: 7, city: "Bengaluru", clusters: [] };
  view().innerHTML = `
    <span class="eyebrow">${icon("mapPin")} ${t("nav_map")}</span>
    <h1>${t("map_title")}</h1>
    <p class="note">${icon("shield")}<span>${t("map_sub")}</span></p>
    <p class="note">${icon("clock")}<span>${t("map_window")}</span></p>
    <div id="mapAlerts" style="margin-top:12px"></div>
    <div class="chips scroll" style="margin:12px 0" id="mrange">
      ${[7, 1].map((d) => `<button type="button" class="chip ${d === 7 ? "on" : ""}" data-v="${d}">${icon("clock")} ${t("range_" + d)}</button>`).join("")}
    </div>
    <div class="chips scroll" style="margin-bottom:12px" id="mcity"></div>
    <div class="split map">
      <div class="map-shell"><div id="mapbox" role="img" aria-label="${t("map_title")}"><p class="muted" style="padding:16px">${t("map_loading")}</p></div>
        <div class="map-legend"><b>${t("legend")}</b>
          ${["MED", "HIGH", "CRIT"].map((s) => `<div><span class="dot ${s}"></span>${t("sev_" + s)}</div>`).join("")}</div></div>
      <aside>
        <div class="field" style="margin-bottom:10px">${icon("search")}<input id="msearch" placeholder="${t("map_search")}" autocomplete="off"></div>
        <h2>${t("map_list_title")}</h2>
        <div id="mlist"><div class="skeleton"></div></div>
      </aside>
    </div>`;

  const meta = await safeMeta();
  const cityNames = meta?.cities || ["Bengaluru"];
  $("#mcity").innerHTML = [...cityNames, "__all"].map((c) => `
    <button type="button" class="chip ${c === st.city ? "on" : ""}" data-v="${esc(c)}">${c === "__all" ? t("all_cities") : esc(c)}</button>`).join("");

  try { await loadLeaflet(); } catch { $("#mapbox").innerHTML = errorBox(t("err_network")); }
  let map = null, layer = null;
  if (window.L) {
    $("#mapbox").innerHTML = "";
    map = L.map("mapbox", { zoomControl: true, attributionControl: true });
    S.mapInstance = map;
    // OpenStreetMap tiles: free, no key, no card. app.css softens their colours to match the cream palette.
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);
    layer = L.layerGroup().addTo(map);
  }

  const focusCity = () => {
    if (!map || !meta) return;
    const pts = meta.areas.filter((a) => st.city === "__all" || a.city === st.city).map((a) => [a.lat, a.lng]);
    if (pts.length === 1) map.setView(pts[0], 12);
    else if (pts.length) map.fitBounds(pts, { padding: [40, 40], maxZoom: 12 });
  };

  async function load() {
    try {
      const [m, al] = await Promise.all([api(`/map?days=${st.days}`), api("/alerts")]);
      st.clusters = m.clusters;
      $("#mapAlerts").innerHTML = alertBanners(al.alerts, 3);
      draw();
    } catch (err) {
      $("#mlist").innerHTML = errorBox(errMessage(err));
    }
  }

  function draw() {
    const q = ($("#msearch").value || "").trim().toLowerCase();
    const inCity = st.clusters.filter((c) => st.city === "__all" || c.city === st.city);
    const shown = inCity.filter((c) => !q || `${c.locality} ${c.pincode}`.toLowerCase().includes(q));
    // map circles: area points only (from the brief), sized by count, coloured by severity
    if (layer) {
      layer.clearLayers();
      st.clusters.forEach((c) => {
        const r = Math.min(46, 12 + Math.sqrt(c.count) * 7);
        const col = SEV_COLOR[c.severity] || SEV_COLOR.MED;
        L.circleMarker([c.lat, c.lng], { radius: r, color: col, weight: 2, fillColor: col, fillOpacity: 0.32 })
          .bindPopup(areaPopup(c)).addTo(layer);
        L.marker([c.lat, c.lng], { interactive: false, icon: L.divIcon({ className: "map-count", html: `<span>${c.count}</span>`, iconSize: [30, 30] }) }).addTo(layer);
      });
    }
    $("#mlist").innerHTML = shown.length ? shown.map((c) => `
      <button type="button" class="area-row" data-pin="${esc(c.pincode)}">
        <span class="dot ${esc(c.severity)}"></span>
        <span><b>${esc(c.locality)}</b> <span class="muted small">${t("area_reports", { n: fmtNum(c.count) })}</span>
          <span class="sub">${t("area_mostly", { type: esc(scamName(c.top_scam_type)) })} · ${esc(c.pincode)}</span></span>
        <span class="pill sev-${esc(c.severity)}">${t("sev_" + c.severity)}</span></button>`).join("")
      : `<p class="muted">${t("map_empty")}</p>`;
  }

  function areaPopup(c) {
    return `<b style="font-family:var(--serif);font-size:16px">${esc(c.locality)}</b><br>
      <span>${t("area_reports", { n: fmtNum(c.count) })} · ${t("sev_" + c.severity)}</span><br>
      <span>${t("area_mostly", { type: esc(scamName(c.top_scam_type)) })}</span><br>
      <a href="#/report" style="display:inline-block;margin-top:6px">${t("report_here")}</a>`;
  }

  pickOne("#mrange", (v) => { st.days = Number(v); load(); });
  pickOne("#mcity", (v) => { st.city = v; focusCity(); draw(); });
  $("#msearch").addEventListener("input", draw);
  $("#mlist").addEventListener("click", (e) => {
    const b = e.target.closest("[data-pin]"); if (!b || !map) return;
    const c = st.clusters.find((x) => x.pincode === b.dataset.pin);
    map.setView([c.lat, c.lng], 13);
    L.popup().setLatLng([c.lat, c.lng]).setContent(areaPopup(c)).openOn(map);
    if (window.innerWidth < 900) $("#mapbox").scrollIntoView({ behavior: "smooth" });
  });
  focusCity();
  load();
}

/* ================================================================ DASHBOARD */
async function pageDashboard(params) {
  const meta = await safeMeta();
  const city = params.city || "Bengaluru";
  view().innerHTML = `
    <span class="eyebrow">${icon("barChart")} ${t("nav_dashboard")}</span>
    <h1>${t("dash_title")}</h1>
    <p class="note">${icon("shieldCheck")}<span>${t("dash_sub")}</span></p>
    <div class="chips scroll" style="margin:14px 0" id="dcity">
      ${[...(meta?.cities || ["Bengaluru"]), "__all"].map((c) => `
        <a class="chip ${c === city ? "on" : ""}" href="#/dashboard?city=${encodeURIComponent(c)}">${c === "__all" ? t("all_cities") : esc(c)}</a>`).join("")}
    </div>
    <div id="dbody"><div class="grid4"><div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div></div></div>`;
  let s;
  try { s = await api(city === "__all" ? "/stats" : `/stats?city=${encodeURIComponent(city)}`); }
  catch (err) { $("#dbody").innerHTML = errorBox(errMessage(err)); return; }

  const change = s.reports_last_week ? Math.round(((s.reports_this_week - s.reports_last_week) / s.reports_last_week) * 100) : null;
  const max = Math.max(1, ...s.per_day.map((d) => d.count));
  const peak = s.per_day.reduce((a, b) => (b.count > a.count ? b : a), s.per_day[0]);
  const dayName = (iso) => new Date(iso + "T12:00:00+05:30").toLocaleDateString(S.lang === "hi" ? "hi-IN" : "en-IN", { weekday: "short", timeZone: "Asia/Kolkata" });

  $("#dbody").innerHTML = `
    <div class="grid4">
      <div class="stat"><b>${fmtNum(s.reports_this_week)}</b><span>${t("d_reports")}</span>
        ${change !== null ? `<br><span class="${change > 0 ? "up" : "down"} small">${t("d_vs_last", { sign: change > 0 ? "+" : "", n: change })}</span>` : ""}</div>
      <div class="stat"><b>${fmtNum(s.areas_affected)}</b><span>${t("d_areas")}</span></div>
      <div class="stat"><b>${fmtNum(s.alerts_now)}</b><span>${t("d_alerts")}</span></div>
      <div class="stat"><b style="font-size:18px">${s.most_reported_type ? esc(scamName(s.most_reported_type)) : "-"}</b><span>${t("d_top")}</span></div>
    </div>
    ${s.reports_this_week ? "" : `<p class="muted" style="margin-top:14px">${t("d_empty")}</p>`}
    <div class="split section">
      <div class="card"><div class="section-head"><h2>${t("d_per_day")}</h2><span class="pill sage">${t("d_last7")}</span></div>
        <div class="bars">${s.per_day.map((d) => `
          <div class="bar ${d === peak && d.count ? "peak" : ""}"><b>${d.count}</b><i style="height:${(d.count / max) * 100}%"></i><span>${esc(dayName(d.date))}</span></div>`).join("")}</div></div>
      <div class="card"><h2>${t("d_types")}</h2>
        ${s.top_types.length ? s.top_types.map((x) => `
          <div class="hbar"><div class="hbar-top"><span>${icon(SCAM_TYPE_ICONS[x.scam_type] || "dots")} ${esc(scamName(x.scam_type))}</span>
            <b>${x.count} (${Math.round(x.share * 100)}%)</b></div><div class="hbar-track"><i style="width:${x.share * 100}%"></i></div></div>`).join("")
          : `<p class="muted">${t("d_empty")}</p>`}</div>
    </div>
    <div class="split section">
      <div class="card"><h2>${t("d_areas_title")}</h2>
        ${s.top_areas.length ? `<table class="tbl"><thead><tr><th>${t("d_area")}</th><th style="text-align:right">${t("d_count")}</th><th>${t("d_trend")}</th><th>${t("d_risk")}</th></tr></thead><tbody>
          ${s.top_areas.map((a) => {
            const diff = a.count - a.last_week;
            return `<tr><td><b>${esc(a.locality)}</b></td><td class="num">${a.count}</td>
              <td class="${diff > 0 ? "up" : diff < 0 ? "down" : "muted"}">${diff > 0 ? "▲ +" + diff : diff < 0 ? "▼ " + diff : "–"}</td>
              <td><span class="pill sev-${esc(a.severity)}">${t("sev_" + a.severity)}</span></td></tr>`;
          }).join("")}</tbody></table>` : `<p class="muted">${t("d_empty")}</p>`}</div>
      <div class="card"><h2>${t("d_alerts_title")}</h2>
        ${s.alerts.length ? alertBanners(s.alerts, 6) : `<p class="muted">${t("d_no_alerts")}</p>`}</div>
    </div>`;
}

/* ================================================================ SAFETY GUIDE */
function pageGuide() {
  const types = Object.keys(SCAM_TYPE_ICONS).filter((k) => k !== "other");
  view().innerHTML = `
    <span class="eyebrow">${icon("book")} ${t("nav_guide")}</span>
    <h1>${t("guide_title")}</h1>
    <p class="lead">${t("guide_sub")}</p>
    <div class="banner" style="margin:14px 0;background:var(--red-tint);border-color:#EBC9BF;border-left-color:var(--red)">
      ${icon("phone")}<div>${t("guide_urgent")} <a href="tel:1930"><b>${t("call_1930")}</b></a></div></div>
    <div class="guide-grid">${types.map((k) => `
      <details class="scam"><summary><span class="ico-wrap">${icon(SCAM_TYPE_ICONS[k])}</span>
        <div><b>${esc(scamName(k))}</b><br><span class="small muted">${esc(scamHow(k))}</span></div>
        <span class="chev">${icon("chevronDown")}</span></summary>
        <div class="body"><div class="advice">${icon("shieldCheck")}<div><b>${t("what_to_do")}</b>${esc(scamAdvice(k))}</div></div>
          <a class="btn btn-quiet btn-sm" href="#/report">${icon("flag")} ${t("home_report")}</a></div></details>`).join("")}
    </div>`;
}

/* ================================================================ HOW IT WORKS */
function pageHow() {
  view().innerHTML = `
    <span class="eyebrow">${icon("info")} ${t("nav_how")}</span>
    <h1>${t("how_title")}</h1>
    <div class="steps3" style="margin-top:14px">
      ${[1, 2, 3].map((n) => `<div class="step-card"><span class="n">${n}</span><h3>${t("how_s" + n)}</h3><p class="muted" style="margin:0">${t("how_s" + n + "_d")}</p></div>`).join("")}
    </div>
    <div class="section"><h2>${t("how_fake_title")}</h2>
      <ul class="points">${[["users", 1], ["wifi", 2], ["copy", 3], ["layers", 4]].map(([ic, n]) => `
        <li>${icon(ic)}<div><b>${t("how_f" + n)}</b><br><span class="muted small">${t("how_f" + n + "_d")}</span></div></li>`).join("")}</ul></div>
    <div class="section"><h2>${t("how_privacy_title")}</h2>
      <ul class="points">${[["lock", 1], ["mapPin", 2], ["eyeOff", 3], ["message", 4]].map(([ic, n]) => `
        <li>${icon(ic)}<div><b>${t("how_p" + n)}</b></div></li>`).join("")}</ul>
      <p class="note" style="margin-top:12px">${icon("shieldCheck")}<span>${t("how_verified")}</span></p></div>`;
}

/* ================================================================ BUSINESS DISPUTE */
function pageDispute(params) {
  const start = TYPES.includes(params.type) ? params.type : (detectType(params.value) || "phone");
  view().innerHTML = `
    <div class="split">
      <section class="narrow">
        <span class="eyebrow">${icon("scale")} ${t("nav_dispute")}</span>
        <h1>${t("dispute_title")}</h1>
        <p class="lead">${t("dispute_sub")}</p>
        <form id="dform" class="card" style="margin-top:14px" novalidate>
          <label class="lbl">${t("q_kind")}</label>
          ${typeTabs("dtype", start)}
          <label class="lbl" for="dval" id="dval-label" style="margin-top:12px"></label>
          <div class="field">${icon("copy")}<input id="dval" autocomplete="off" value="${esc(params.value || "")}"></div>
          <p class="hint" id="dtypehint"></p>
          <label class="lbl" for="dname" style="margin-top:12px">${t("f_name")}</label>
          <input class="input" id="dname" autocomplete="organization">
          <label class="lbl" for="demail" style="margin-top:12px">${t("f_email")}</label>
          <input class="input" id="demail" type="email" autocomplete="email" placeholder="owner@example.com">
          <label class="lbl" for="dproof" style="margin-top:12px">${t("f_proof")}</label>
          <textarea class="input" id="dproof" maxlength="2000" placeholder="${t("f_proof_ph")}"></textarea>
          <button class="btn btn-block" style="margin-top:16px" type="submit" id="dsend">${icon("scale")} ${t("dispute_submit")}</button>
          <div id="derr"></div>
          <p class="note" style="margin-top:12px">${icon("lock")}<span>${t("dispute_note")}</span></p>
        </form>
      </section>
      <aside class="card flat">
        <h3>${t("dispute_how_title")}</h3>
        <ul class="points">${[["scale", 1], ["eyeOff", 2], ["shieldCheck", 3]].map(([ic, n]) => `
          <li>${icon(ic)}<div>${t("dispute_how_" + n)}</div></li>`).join("")}</ul>
      </aside>
    </div>`;
  const picked = bindTypeInput("#dtype", "#dval", "#dtypehint", start);
  $("#dform").addEventListener("submit", async (e) => {
    e.preventDefault();
    const body = {
      identifier_type: picked.type, identifier_value: $("#dval").value.trim(),
      claimant_name: $("#dname").value.trim(), contact_email: $("#demail").value.trim(), proof_note: $("#dproof").value.trim(),
    };
    $("#derr").innerHTML = "";
    if (!body.identifier_value) { $("#derr").innerHTML = errorBox(t("required_value")); return; }
    if (!body.claimant_name) { $("#derr").innerHTML = errorBox(t("err_dispute_name")); return; }
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(body.contact_email)) { $("#derr").innerHTML = errorBox(t("err_dispute_email")); return; }
    const btn = $("#dsend"); btn.disabled = true;
    try {
      await api("/challenges", body);
      view().innerHTML = `<section class="success card narrow" style="margin:0 auto"><span class="big-ico">${icon("checkCircle")}</span>
        <h1>${t("dispute_ok")}</h1><p class="muted">${t("dispute_note")}</p>
        <a class="btn" href="#/check?value=${encodeURIComponent(body.identifier_value)}&type=${body.identifier_type}">${icon("search")} ${t("ok_check")}</a></section>`;
    } catch (err) {
      btn.disabled = false;
      const msg = err.body?.error || "";
      $("#derr").innerHTML = errorBox(err.status === 400 && msg.includes("identifier") ? t("err_identifier")
        : err.status === 400 && msg.includes("email") ? t("err_dispute_email") : errMessage(err));
    }
  });
}

/* ================================================================ MORE (phone menu) */
function pageMore() {
  view().innerHTML = `
    <h1>${t("more_title")}</h1>
    <nav class="menu" style="margin-top:12px">
      ${[["dispute", "scale"], ["dashboard", "barChart"], ["guide", "book"], ["how", "info"]].map(([r, ic]) => `
        <a href="#/${r}">${icon(ic)}<span class="menu-text"><b>${t("nav_" + r)}</b><span class="small muted">${t("more_" + r)}</span></span>${icon("chevronRight")}</a>`).join("")}
      <a href="https://cybercrime.gov.in" target="_blank" rel="noopener">${icon("external")} cybercrime.gov.in ${icon("chevronRight")}</a>
    </nav>`;
}

/* ================================================================ start */
applyStatic();
getMeta().catch(() => {});   // warm the area list in the background
router();
watchLicence();              // lock the page by itself when the licence ends
