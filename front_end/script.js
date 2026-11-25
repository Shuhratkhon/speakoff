/* Speakoff website: one page, screens switched by the address (#/home, #/record, ...).
   Talks to the Flask server (server/app.py) through /api/... */

"use strict";

// ------------------------------------------------------------------ state
const S = {
  me: null,          // signed-in user (or null)
  usage: null,       // limits for today
  lang: "en",
  text: {},          // texts of the current language
  langs: {},
  signup: {},        // contact / method during sign-up
};
const app = document.getElementById("app");
const tabbar = document.getElementById("tabbar");
const SECTIONS = ["fluency", "grammar", "vocabulary", "pronunciation"];
const SEC_COLORS = { fluency: "#3574F0", grammar: "#5FB865", vocabulary: "#E5A750", pronunciation: "#C77DFF" };
const RANKS = [
  ["copper", "#B87333"], ["bronze", "#8C5A2B"], ["silver", "#9EA7B3"], ["gold", "#D4A72C"],
  ["platinum", "#3FB8AF"], ["diamond", "#4C8DF6"], ["master", "#9B59F5"],
];

// ------------------------------------------------------------------ icons
const ICONS = {
  home: '<path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z"/>',
  progress: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
  mic: '<rect x="9" y="2.5" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3.5"/>',
  trophy: '<path d="M7 4h10v5a5 5 0 0 1-10 0zM7 6H4v2a3 3 0 0 0 3 3M17 6h3v2a3 3 0 0 1-3 3M12 14v4M8 21h8M9 18h6"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
  video: '<rect x="2.5" y="6" width="13" height="12" rx="2.5"/><path d="m15.5 10 6-3.5v11l-6-3.5"/>',
  back: '<path d="m15 18-6-6 6-6"/>',
  play: '<path d="M7 4.5v15l13-7.5z"/>',
  stop: '<rect x="6" y="6" width="12" height="12" rx="2"/>',
  upload: '<path d="M12 16V4M7 9l5-5 5 5M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/>',
  lock: '<rect x="5" y="11" width="14" height="10" rx="2.5"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
  check: '<path d="m5 12.5 4.5 4.5L19 7"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path d="M20 14.5A8.5 8.5 0 1 1 9.5 4a7 7 0 0 0 10.5 10.5z"/>',
  calendar: '<rect x="3" y="5" width="18" height="16" rx="2.5"/><path d="M3 10h18M8 3v4M16 3v4"/>',
  spark: '<path d="M12 3l2.2 5.8L20 11l-5.8 2.2L12 19l-2.2-5.8L4 11l5.8-2.2z"/>',
  podium: '<path d="M9 21V9h6v12M3 21v-7h6M15 21v-5h6v5M2 21h20M12 3l.9 1.8 2 .3-1.45 1.4.35 2-1.8-.95-1.8.95.35-2L9.1 5.1l2-.3z"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 4.6a3.5 3.5 0 0 1 0 6.8M18 14.3a6.5 6.5 0 0 1 3.5 5.7"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
  edit: '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="m13.5 6.5 4 4"/>',
  shield: '<path d="M12 3 4.5 6v5.5c0 4.6 3.2 8.4 7.5 9.5 4.3-1.1 7.5-4.9 7.5-9.5V6z"/><path d="m8.8 12 2.2 2.2 4.4-4.4"/>',
  doc: '<path d="M6 2.5h8l4 4V21a.5.5 0 0 1-.5.5h-11A.5.5 0 0 1 6 21z"/><path d="M14 2.5V7h4M9 12h6M9 16h6"/>',
  bag: '<path d="M5 8h14l-1 12.5a1 1 0 0 1-1 .9H7a1 1 0 0 1-1-.9z"/><path d="M9 10V6.5a3 3 0 0 1 6 0V10"/>',
  bookmark: '<path d="M6.5 3h11v18l-5.5-4-5.5 4z"/>',
  camera: '<path d="M4 8h3l2-3h6l2 3h3a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z"/><circle cx="12" cy="13.5" r="3.5"/>',
};
function icon(name, fill) {
  const f = fill || name === "play" || name === "stop";
  return `<svg viewBox="0 0 24 24" fill="${f ? "currentColor" : "none"}" stroke="currentColor" stroke-width="${f ? 0 : 1.9}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ""}</svg>`;
}
function fillIcons(root) {
  root.querySelectorAll("[data-icon]").forEach((el) => { el.innerHTML = icon(el.dataset.icon); });
}

// ------------------------------------------------------------------ countries (names come from the browser, in the UI language)
const COUNTRIES = "AF AL DZ AD AO AG AR AM AU AT AZ BS BH BD BB BY BE BZ BJ BT BO BA BW BR BN BG BF BI KH CM CA CV CF TD CL CN CO KM CG CD CR CI HR CU CY CZ DK DJ DM DO EC EG SV GQ ER EE SZ ET FJ FI FR GA GM GE DE GH GR GD GT GN GW GY HT HN HK HU IS IN ID IR IQ IE IL IT JM JP JO KZ KE KI KW KG LA LV LB LS LR LY LI LT LU MO MG MW MY MV ML MT MH MR MU MX FM MD MC MN ME MA MZ MM NA NR NP NL NZ NI NE NG KP MK NO OM PK PW PS PA PG PY PE PH PL PT PR QA RO RU RW KN LC VC WS SM ST SA SN RS SC SL SG SK SI SB SO ZA KR SS ES LK SD SR SE CH SY TW TJ TZ TH TL TG TO TT TN TR TM TV UG UA AE GB US UY UZ VU VA VE VN YE ZM ZW".split(" ");
function flag(code) { return code ? String.fromCodePoint(...[...code].map((c) => 0x1F1A5 + c.charCodeAt(0))) : ""; }
function countryName(code) {
  try { return new Intl.DisplayNames([S.lang === "zh" ? "zh-CN" : S.lang], { type: "region" }).of(code); } catch (e) { return code; }
}
function guessCountry() {
  for (const l of navigator.languages || [navigator.language || ""]) { const m = /-([A-Z]{2})$/i.exec(l); if (m && COUNTRIES.includes(m[1].toUpperCase())) return m[1].toUpperCase(); }
  return { ko: "KR", ja: "JP", zh: "CN", ru: "RU", de: "DE", id: "ID", uz: "UZ", vi: "VN", hi: "IN" }[S.lang] || null;
}
function countrySelect(id, cur) {
  const list = COUNTRIES.map((c) => [c, countryName(c)]).sort((a, b) => a[1].localeCompare(b[1]));
  return `<select class="input" id="${id}">${cur ? "" : `<option value="">–</option>`}${list.map(([c, n]) => `<option value="${c}" ${c === cur ? "selected" : ""}>${flag(c)} ${esc(n)}</option>`).join("")}</select>`;
}

// ------------------------------------------------------------------ helpers
function t(key, params) {
  let s = S.text[key] ?? key;
  if (params) for (const [k, v] of Object.entries(params)) s = s.split(`{${k}}`).join(v);
  return s;
}
function esc(v) {
  return String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function mmss(s) { s = Math.max(0, Math.round(s)); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; }
function cls(score) { return score >= 80 ? "good" : score >= 60 ? "mid" : "bad"; }
function fmtDate(iso, withTime) {
  const d = new Date(iso);
  const opt = withTime ? { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" } : { year: "numeric", month: "long", day: "numeric" };
  try { return d.toLocaleString(S.lang === "zh" ? "zh-CN" : S.lang, opt); } catch (e) { return d.toLocaleString(undefined, opt); }
}
function store(key, val) { try { if (val === undefined) return localStorage.getItem(key); localStorage.setItem(key, val); } catch (e) { return null; } }
function toast(msg, ms = 2600) {
  const el = document.getElementById("toast");
  el.textContent = msg; el.hidden = false;
  clearTimeout(toast._t); toast._t = setTimeout(() => { el.hidden = true; }, ms);
}
function errText(res) { return res && res.error ? t(res.error, res.params) : t("err_network"); }

async function api(path, body, method) {
  const opts = { method: method || (body ? "POST" : "GET"), headers: { "X-SC": "1", "X-Act": S.view || "" }, credentials: "same-origin" };
  if (body) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
  try {
    const r = await fetch(path, opts);
    const data = await r.json().catch(() => ({}));
    if (r.status === 401 && path !== "/api/me") { S.me = null; go("#/welcome"); }
    return data;
  } catch (e) { return { ok: false, error: "err_network" }; }
}

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  store("sc-theme", theme);
  document.querySelector('meta[name="theme-color"]').content = theme === "light" ? "#F7F8FA" : "#1E1F22";
}
async function setLang(lang) {
  const data = await api(`/api/i18n/${lang}`);
  if (!data.text) return;
  S.lang = lang; S.text = data.text; S.langs = data.langs;
  store("sc-lang", lang);
  document.documentElement.lang = lang;
  document.querySelectorAll("[data-t]").forEach((el) => { el.textContent = t(el.dataset.t); });
}
function guessLang() {
  const saved = store("sc-lang");
  if (saved) return saved;
  const nav = (navigator.language || "en").slice(0, 2).toLowerCase();
  return ["en", "ko", "ru", "de", "id", "uz", "zh", "vi", "hi", "ja"].includes(nav) ? nav : "en";
}
function go(hash) { if (location.hash !== hash) location.hash = hash; else route(); }

// ------------------------------------------------------------------ sounds
// Small sounds made in code (Web Audio): nothing to download, no licences. Never while a microphone is recording.
const SFX = { ctx: null, on: store("sc-sound") !== "off" };
function sfxRecording() {
  return (typeof rec !== "undefined" && rec.recorder && rec.recorder.state === "recording")
    || (typeof rk !== "undefined" && rk.recorder && rk.recorder.state === "recording")
    || (typeof mk !== "undefined" && mk.rec && mk.rec.state === "recording");
}
function sfxTone(ctx, t0, freq, dur, { type = "sine", vol = .18, slide = 0 } = {}) {
  const o = ctx.createOscillator(), g = ctx.createGain();
  o.type = type; o.frequency.setValueAtTime(freq, t0);
  if (slide) o.frequency.exponentialRampToValueAtTime(freq * slide, t0 + dur);
  g.gain.setValueAtTime(0.0001, t0);
  g.gain.exponentialRampToValueAtTime(vol, t0 + .012);
  g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
  o.connect(g).connect(ctx.destination);
  o.start(t0); o.stop(t0 + dur + .02);
}
const SOUNDS = {
  click: (c, t) => sfxTone(c, t, 520, .05, { type: "triangle", vol: .06 }),
  pop: (c, t) => sfxTone(c, t, 380, .12, { vol: .16, slide: 2.2 }),
  tick: (c, t) => sfxTone(c, t, 880, .07, { type: "square", vol: .05 }),
  found: (c, t) => { sfxTone(c, t, 660, .16, { vol: .16 }); sfxTone(c, t + .12, 990, .28, { vol: .16 }); },
  coin: (c, t) => { sfxTone(c, t, 988, .08, { type: "square", vol: .06 }); sfxTone(c, t + .07, 1319, .25, { type: "square", vol: .06 }); },
  sparkle: (c, t) => [1047, 1319, 1568, 2093].forEach((f, i) => sfxTone(c, t + i * .06, f, .22, { vol: .09 })),
  win: (c, t) => [523, 659, 784, 1047].forEach((f, i) => sfxTone(c, t + i * .1, f, i === 3 ? .5 : .16, { type: "triangle", vol: .16 })),
  loss: (c, t) => [392, 330, 262].forEach((f, i) => sfxTone(c, t + i * .14, f, i === 2 ? .45 : .18, { type: "triangle", vol: .13 })),
  draw: (c, t) => { sfxTone(c, t, 523, .18, { type: "triangle", vol: .13 }); sfxTone(c, t + .15, 523, .3, { type: "triangle", vol: .13 }); },
  rankup: (c, t) => [523, 659, 784, 1047, 1319].forEach((f, i) => sfxTone(c, t + i * .08, f, i === 4 ? .6 : .14, { type: "sawtooth", vol: .07 })),
};
function sfx(name) {
  if (!SFX.on || !SOUNDS[name] || sfxRecording()) return;
  try {
    SFX.ctx = SFX.ctx || new (window.AudioContext || window.webkitAudioContext)();
    if (SFX.ctx.state === "suspended") SFX.ctx.resume();
    SOUNDS[name](SFX.ctx, SFX.ctx.currentTime + .01);
  } catch (e) { /* no audio: stay silent */ }
}
// a light click only on the main menu (the tab bar at the bottom)
document.addEventListener("click", (e) => {
  if (e.target.closest("#tabbar .tab, #tabbar .tabround")) sfx("click");
}, true);

// ------------------------------------------------------------------ router
const ROUTES = {
  welcome: viewWelcome, signup: viewSignup, verify: viewVerify, create: viewCreate, signin: viewSignin, forgot: viewForgot,
  home: viewHome, progress: viewProgress, record: viewRecord, ranked: viewRanked, profile: viewProfile,
  result: viewResult, plans: viewPlans, match: viewMatch, u: viewUser, friends: viewFriends, challenge: viewChallenge, leaderboard: viewLeaderboard, shop: viewShop, mock: viewMock, setup: viewSetup,
};
const PUBLIC = new Set(["welcome", "signup", "verify", "create", "signin", "forgot"]);
let leaveHooks = [];

async function route() {
  leaveHooks.forEach((f) => f()); leaveHooks = [];
  const [name, arg] = (location.hash.replace(/^#\/?/, "") || "home").split("/");
  const view = ROUTES[name] ? name : "home";
  if (!PUBLIC.has(view) && !S.me) return go("#/welcome");
  if (PUBLIC.has(view) && S.me) return go("#/home");
  const authScreen = PUBLIC.has(view);
  tabbar.hidden = authScreen;
  app.className = authScreen ? "auth" : "";
  const tab = { result: "progress", plans: "profile", match: "ranked", u: "ranked", friends: "profile", challenge: "profile", leaderboard: "ranked", shop: "home", mock: "record" }[view] || view;
  tabbar.querySelectorAll("[data-tab]").forEach((a) => a.classList.toggle("on", a.dataset.tab === tab));
  window.scrollTo(0, 0);
  S.view = view;
  await ROUTES[view](arg);
  fillIcons(app);
  if (Q.on) queueDraw();
}
window.addEventListener("hashchange", route);

function render(html) { app.innerHTML = `<div class="fade-in">${html}</div>`; fillIcons(app); addCreditsPill(); }
function $(sel) { return app.querySelector(sel); }
function $$(sel) { return [...app.querySelectorAll(sel)]; }

async function refreshMe() {
  const data = await api("/api/me");
  S.me = data.user || null;
  S.usage = data.usage || null;
  if (S.me) {
    setTheme(S.me.theme);
    if (S.me.lang !== S.lang) await setLang(S.me.lang);
    if (!S.me.country) {                     // first visit: guess the country once (changeable in Settings)
      const c = guessCountry();
      if (c) { const r = await api("/api/settings", { country: c }); if (r.ok) S.me = r.user; }
    }
  }
}

// ------------------------------------------------------------------ sign up / sign in
const LANG_FLAG = { en: "GB", ko: "KR", ja: "JP", zh: "CN", ru: "RU", de: "DE", uz: "UZ", id: "ID", vi: "VN", hi: "IN" };
function langSelect(id) {
  return `<select class="input" id="${id}" aria-label="${esc(t("app_language"))}">${Object.entries(S.langs)
    .map(([c, n]) => `<option value="${c}" ${c === S.lang ? "selected" : ""}>${flag(LANG_FLAG[c])} ${esc(n)}</option>`).join("")}</select>`;
}
function themeToggle() {
  const dark = document.documentElement.dataset.theme !== "light";
  return `<button class="iconbtn" id="themeBtn" aria-label="${esc(t("theme"))}">${icon(dark ? "sun" : "moon")}</button>`;
}
function bindAuthTop() {
  const sel = $("#langSel");
  if (sel) sel.onchange = async () => { await setLang(sel.value); route(); };
  const tb = $("#themeBtn");
  if (tb) tb.onclick = () => { setTheme(document.documentElement.dataset.theme === "light" ? "dark" : "light"); route(); };
}
function backBtn(hash) { return `<button class="back" onclick="location.hash='${hash}'">${icon("back")}${esc(t("back"))}</button>`; }

function viewWelcome() {
  render(`
    <div class="auth-top">${langSelect("langSel")}${themeToggle()}</div>
    <div class="auth-hero">
      <img class="logo" src="icon.svg" alt="">
      <h1>${esc(t("app_name"))}</h1>
      <p>${esc(t("tagline"))}</p>
    </div>
    <div class="auth-actions stack">
      ${socialButtons()}
      <div class="or-line"><span>${esc(t("or_divider"))}</span></div>
      <a class="btn block" href="#/signup/email">${esc(t("signup_email"))}</a>
      <p class="center muted" style="margin-top:22px">${esc(t("have_account"))} <a href="#/signin"><b>${esc(t("sign_in"))}</b></a></p>
    </div>`);
  bindAuthTop();
  bindSocial();
}

// ------------------------------------------------------------------ Sign in with Google / Apple
const GOOGLE_G = '<svg viewBox="0 0 48 48" aria-hidden="true"><path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9 3.5l6.7-6.7C35.6 2.4 30.2 0 24 0 14.6 0 6.6 5.4 2.7 13.2l7.8 6.1C12.4 13.6 17.7 9.5 24 9.5z"/><path fill="#4285F4" d="M46.1 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.4c-.5 2.9-2.2 5.3-4.6 6.9l7.4 5.8c4.3-4 6.9-9.9 6.9-17.2z"/><path fill="#FBBC05" d="M10.5 28.7c-.5-1.4-.8-3-.8-4.7s.3-3.2.8-4.7l-7.8-6.1C1 16.6 0 20.2 0 24s1 7.4 2.7 10.8l7.8-6.1z"/><path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.4-5.8c-2.1 1.4-4.8 2.3-8.5 2.3-6.3 0-11.6-4.1-13.5-9.8l-7.8 6.1C6.6 42.6 14.6 48 24 48z"/></svg>';
const APPLE_LOGO = '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M16.4 12.6c0-2.6 2.1-3.8 2.2-3.9-1.2-1.8-3.1-2-3.7-2-1.6-.2-3.1.9-3.9.9-.8 0-2-.9-3.3-.9-1.7 0-3.3 1-4.2 2.5-1.8 3.1-.5 7.7 1.3 10.2.8 1.2 1.8 2.6 3.1 2.5 1.2 0 1.7-.8 3.2-.8s1.9.8 3.2.8c1.3 0 2.2-1.2 3-2.4.9-1.4 1.3-2.7 1.3-2.8 0 0-2.5-1-2.5-4.1zM13.9 5c.7-.8 1.1-1.9 1-3-1 0-2.1.6-2.8 1.4-.6.7-1.2 1.8-1 2.9 1.1.1 2.1-.5 2.8-1.3z"/></svg>';
function socialButtons() {
  return `<button class="btn block social google" data-social="google">${GOOGLE_G}${esc(t("continue_google"))}</button>
    <button class="btn block social apple" data-social="apple">${APPLE_LOGO}${esc(t("continue_apple"))}</button>`;
}
function loadScript(src) {
  return new Promise((ok, no) => {
    if (document.querySelector(`script[src="${src}"]`)) return ok();
    const s = document.createElement("script"); s.src = src; s.async = true; s.onload = ok; s.onerror = no;
    document.head.appendChild(s);
  });
}
async function socialToken(provider) {
  // returns {token, kind} from Google / Apple, or null if the user closed the window
  S.providers = S.providers || await api("/api/auth/providers");
  const cfg = S.providers[provider];
  if (!cfg) { toast(t("oauth_not_set", { name: provider === "google" ? "Google" : "Apple" })); return null; }
  if (provider === "google") {
    await loadScript("https://accounts.google.com/gsi/client");
    return new Promise((ok) => {
      const client = google.accounts.oauth2.initTokenClient({ client_id: cfg, scope: "openid email profile",
        callback: (r) => ok(r && r.access_token ? { token: r.access_token, kind: "access_token" } : null),
        error_callback: () => ok(null) });
      client.requestAccessToken();
    });
  }
  await loadScript("https://appleid.cdn-apple.com/appleauth/static/jsapi/appleid/1/en_US/appleid.auth.js");
  AppleID.auth.init({ clientId: cfg.client_id, scope: "name email", redirectURI: cfg.redirect_uri, usePopup: true });
  try { const r = await AppleID.auth.signIn(); return { token: r.authorization.id_token, kind: "id_token" }; }
  catch (e) { return null; }
}
function bindSocial() {
  $$("[data-social]").forEach((b) => b.onclick = async () => {
    const provider = b.dataset.social;
    b.disabled = true;
    try {
      const got = await socialToken(provider);
      if (!got) return;
      const res = await api("/api/auth/oauth", { provider, token: got.token, kind: got.kind });
      if (!res.ok) { toast(errText(res)); return; }
      if (res.new) { S.signup = { social: provider, contact: res.email }; go("#/create"); return; }
      await refreshMe();
      go("#/home");
    } catch (e) { toast(t("oauth_failed", { name: provider === "google" ? "Google" : "Apple" })); }
    finally { b.disabled = false; }
  });
}

function viewSignup(method) {
  method = "email";                          // phone sign-up removed (2026-11-23)
  render(`
    <div class="auth-top">${backBtn("#/welcome")}${langSelect("langSel")}</div>
    <div class="stack-lg" style="margin-top:28px">
      <h1>${esc(t(method === "email" ? "signup_email" : "signup_phone"))}</h1>
      <form id="f" class="stack" novalidate>
        <label class="field"><span>${esc(t(method))}</span>
          <input class="input" id="contact" ${method === "email" ? 'type="email" autocomplete="email" inputmode="email"' : 'type="tel" autocomplete="tel" inputmode="tel" placeholder="+82 10 1234 5678"'} required>
          <div class="hint">${esc(t(method === "email" ? "email_hint" : "phone_hint"))}</div>
        </label>
        <div class="error" id="err"></div>
        <button class="btn block" id="go">${esc(t("send_code"))}</button>
      </form>
    </div>`);
  bindAuthTop();
  $("#contact").focus();
  $("#f").onsubmit = async (e) => {
    e.preventDefault();
    $("#go").disabled = true;
    const res = await api("/api/auth/start", { method, contact: $("#contact").value });
    $("#go").disabled = false;
    if (!res.ok) { $("#err").textContent = errText(res); return; }
    S.signup = { method, contact: res.contact, dev_code: res.dev_code, sentAt: Date.now(), resend: res.resend_in };
    go("#/verify");
  };
}

function viewVerify() {
  if (!S.signup.contact) return go("#/welcome");
  render(`
    <div class="auth-top">${backBtn(`#/signup/${S.signup.method}`)}</div>
    <div class="stack-lg" style="margin-top:28px">
      <h1>${esc(t("enter_code"))}</h1>
      <p class="muted">${esc(t("code_sent_to", { to: S.signup.contact }))}</p>
      ${S.signup.dev_code ? `<div class="notice">${esc(t("dev_code", { code: S.signup.dev_code }))}</div>` : ""}
      <form id="f" class="stack" novalidate>
        <input class="input code" id="code" inputmode="numeric" autocomplete="one-time-code" maxlength="6" required>
        <div class="error" id="err"></div>
        <button class="btn block" id="go">${esc(t("verify"))}</button>
        <button type="button" class="linkbtn" id="resend">${esc(t("resend_code"))}</button>
      </form>
    </div>`);
  $("#code").focus();
  $("#code").oninput = (e) => { e.target.value = e.target.value.replace(/\D/g, "").slice(0, 6); if (e.target.value.length === 6) $("#f").requestSubmit(); };
  $("#f").onsubmit = async (e) => {
    e.preventDefault();
    $("#go").disabled = true;
    const res = await api("/api/auth/verify", { code: $("#code").value });
    $("#go").disabled = false;
    if (!res.ok) { $("#err").textContent = errText(res); $("#code").select(); return; }
    go("#/create");
  };
  $("#resend").onclick = async () => {
    const res = await api("/api/auth/start", { method: S.signup.method, contact: S.signup.contact });
    if (!res.ok) { $("#err").textContent = errText(res); return; }
    S.signup.dev_code = res.dev_code;
    viewVerify(); fillIcons(app);
    toast(t("code_sent_to", { to: res.contact }));
  };
}

function viewCreate() {
  render(`
    <div class="stack-lg" style="margin-top:36px">
      <h1>${esc(t("create_account"))}</h1>
      <form id="f" class="stack" novalidate>
        <label class="field"><span>${esc(t("username"))}</span>
          <input class="input" id="u" autocomplete="username" autocapitalize="off" spellcheck="false" maxlength="20" required>
          <div class="hint">${esc(t("username_hint"))}</div></label>
        ${S.signup.social ? "" : `<label class="field"><span>${esc(t("password"))}</span>
          <input class="input" id="p" type="password" autocomplete="new-password" required>
          <div class="hint">${esc(t("password_hint"))}</div></label>
        <label class="field"><span>${esc(t("password_again"))}</span>
          <input class="input" id="p2" type="password" autocomplete="new-password" required></label>`}
        <div class="error" id="err"></div>
        <button class="btn block" id="go">${esc(t("continue"))}</button>
      </form>
    </div>`);
  $("#u").focus();
  $("#f").onsubmit = async (e) => {
    e.preventDefault();
    $("#go").disabled = true;
    const res = await api("/api/auth/create", { username: $("#u").value, password: $("#p") ? $("#p").value : "", password2: $("#p2") ? $("#p2").value : "",
      lang: S.lang, theme: document.documentElement.dataset.theme });
    $("#go").disabled = false;
    if (!res.ok) { $("#err").textContent = errText(res); return; }
    S.signup = {};
    await refreshMe();
    go("#/setup");
  };
}

function viewSignin() {
  render(`
    <div class="auth-top">${backBtn("#/welcome")}${langSelect("langSel")}</div>
    <div class="stack-lg" style="margin-top:28px">
      <h1>${esc(t("sign_in"))}</h1>
      <div class="stack">${socialButtons()}</div>
      <div class="or-line"><span>${esc(t("or_divider"))}</span></div>
      <form id="f" class="stack" novalidate>
        <label class="field"><span>${esc(t("username"))}</span>
          <input class="input" id="u" autocomplete="username" autocapitalize="off" spellcheck="false" required></label>
        <label class="field"><span>${esc(t("password"))}</span>
          <input class="input" id="p" type="password" autocomplete="current-password" required></label>
        <div class="error" id="err"></div>
        <button class="btn block" id="go">${esc(t("sign_in"))}</button>
        <a class="linkbtn center" href="#/forgot">${esc(t("forgot_password"))}</a>
      </form>
    </div>`);
  bindAuthTop();
  bindSocial();
  $("#u").focus();
  $("#f").onsubmit = async (e) => {
    e.preventDefault();
    $("#go").disabled = true;
    const res = await api("/api/auth/signin", { username: $("#u").value, password: $("#p").value });
    $("#go").disabled = false;
    if (!res.ok) { $("#err").textContent = errText(res); return; }
    await refreshMe();
    go("#/home");
  };
}

function viewForgot() {
  // step 1: username or email -> a code by email; step 2: code + new password
  const step1 = () => {
    render(`
      <div class="auth-top">${backBtn("#/signin")}</div>
      <div class="stack-lg" style="margin-top:28px">
        <div><h1>${esc(t("forgot_password"))}</h1><p class="muted">${esc(t("forgot_sub"))}</p></div>
        <form id="f" class="stack" novalidate>
          <input class="input" id="login" autocomplete="username" autocapitalize="off" spellcheck="false" placeholder="${esc(t("username_or_email"))}" required>
          <div class="error" id="err"></div>
          <button class="btn block" id="go">${esc(t("send_code"))}</button>
        </form>
      </div>`);
    $("#login").focus();
    $("#f").onsubmit = async (e) => {
      e.preventDefault();
      $("#go").disabled = true;
      const r = await api("/api/auth/forgot", { login: $("#login").value });
      $("#go").disabled = false;
      if (!r.ok) { $("#err").textContent = errText(r); return; }
      step2(r);
    };
  };
  const step2 = (info) => {
    render(`
      <div class="auth-top">${backBtn("#/signin")}</div>
      <div class="stack-lg" style="margin-top:28px">
        <div><h1>${esc(t("new_password"))}</h1><p class="muted">${esc(t("code_sent_to", { to: info.to }))}</p></div>
        ${info.dev_code ? `<div class="notice">${esc(t("dev_code", { code: info.dev_code }))}</div>` : ""}
        <form id="f" class="stack" novalidate>
          <input class="input code" id="code" inputmode="numeric" autocomplete="one-time-code" maxlength="6" placeholder="000000" required>
          <input class="input" id="p" type="password" autocomplete="new-password" placeholder="${esc(t("new_password"))}">
          <input class="input" id="p2" type="password" autocomplete="new-password" placeholder="${esc(t("password_again"))}">
          <div class="error" id="err"></div>
          <button class="btn block" id="go">${esc(t("save"))}</button>
        </form>
      </div>`);
    $("#code").focus();
    $("#f").onsubmit = async (e) => {
      e.preventDefault();
      $("#go").disabled = true;
      const r = await api("/api/auth/reset", { code: $("#code").value, password: $("#p").value, password2: $("#p2").value });
      $("#go").disabled = false;
      if (!r.ok) { $("#err").textContent = errText(r); return; }
      toast(t("password_reset_done"));
      await refreshMe();
      go("#/home");
    };
  };
  step1();
}

// ------------------------------------------------------------------ shared pieces
function ring(score, size = 132, label) {
  const r = 52, c = 2 * Math.PI * r, pct = Math.max(0, Math.min(100, score || 0)) / 100;
  return `<div class="ring ${size < 100 ? "sm" : ""}" style="width:${size}px;height:${size}px">
    <svg class="track" viewBox="0 0 120 120"><circle cx="60" cy="60" r="${r}" fill="none" stroke="var(--surface-2)" stroke-width="10"/></svg>
    <svg class="arc ${cls(score)}" viewBox="0 0 120 120"><circle cx="60" cy="60" r="${r}" fill="none" stroke="currentColor" stroke-width="10" stroke-linecap="round"
      stroke-dasharray="${c}" stroke-dashoffset="${c * (1 - pct)}"/></svg>
    <div class="num"><div><b class="${cls(score)}">${score ?? "–"}</b>${label ? `<span>${esc(label)}</span>` : ""}</div></div></div>`;
}
function planName(p) { return t(`plan_${p}`); }
function levelParts(cefr) {
  // "B2 (borderline B1)" -> ["B2", "B1"];  "below A1" -> translated
  const m = /^(.+?) \(borderline (.+)\)$/.exec(cefr || "");
  const fix = (x) => x === "below A1" ? t("below_a1") : x;
  return m ? [fix(m[1]), fix(m[2])] : [fix(cefr || "–"), null];
}
function levelHtml(cefr, size) {
  const [main, near] = levelParts(cefr);
  return `<div class="level-big" ${size ? `style="font-size:${size}px"` : ""}>${esc(main)}</div>${near ? `<div class="muted small">${esc(t("close_to", { b: near }))}</div>` : ""}`;
}
function usageLine(u) {
  if (!u) return "";
  if (u.unlimited) return `${esc(t("left_today"))}: <b>${esc(t("unlimited"))}</b>`;
  const parts = [`${esc(t("left_today"))}: <b>${u.left_today}</b>`];
  if (u.bonus_left > 0) parts.push(`${esc(t("welcome_left"))}: <b>${u.bonus_left}</b>`);
  return parts.join(" · ");
}

// ------------------------------------------------------------------ home (like the App Store's "Today")
async function viewHome() {
  render(`<div class="splash"><div class="spinner"></div></div>`);
  const data = await api("/api/home");
  if (!data.usage) return;
  S.usage = data.usage;
  if (data.calendar) S.me.credits = data.calendar.credits;
  const u = data.usage, last = data.last;
  const today = new Date().toLocaleDateString(S.lang === "zh" ? "zh-CN" : S.lang, { weekday: "long", month: "long", day: "numeric" });
  render(`
    <div class="page-head"><div><div class="date">${esc(today)}</div><h1>${esc(t("hello", { name: S.me.username }))}</h1></div>
      <a href="#/profile">${avatarHtml(S.me.card, 48)}</a></div>
    <div class="stack">
      <div class="hero cal" id="cal">${calendarHtml(data.calendar)}</div>
      <a class="card tap row dq" href="${u.daily_answered ? `#/result/${u.daily_answered}` : "#/record/daily"}" style="color:inherit">
        <span class="iconbtn" style="width:52px;height:52px;border-radius:16px;background:var(--accent-soft);color:var(--accent-2);border:0">${icon(u.daily_answered ? "check" : "calendar")}</span>
        <div style="flex:1;min-width:0"><div class="card-title" style="margin:0 0 2px">${esc(t("daily_question"))}</div>
          <div class="dq-text">${esc(data.daily_question)}</div></div>
      </a>
      <a class="card tap row" href="#/record" style="color:inherit">
        <span class="iconbtn" style="width:52px;height:52px;border-radius:16px;background:var(--accent-soft);color:var(--accent-2);border:0">${icon("mic")}</span>
        <div style="flex:1"><h3>${esc(t("start_speaking"))}</h3><p class="muted small">${esc(t("start_sub"))}</p></div>
      </a>
      <div class="card">
        <div class="row between"><div class="card-title" style="margin:0">${esc(t("your_plan"))}</div>
          <span class="tag accent">${esc(planName(u.plan))}</span></div>
        <p style="margin-top:10px">${usageLine(u)}</p>
        ${u.plan === "free" ? `<a class="btn small" href="#/plans" style="margin-top:12px">${icon("spark")} ${esc(t("upgrade"))}</a>` : ""}
      </div>
      <div class="card ${last ? "tap" : ""}" ${last ? `onclick="location.hash='#/result/${last.id}'"` : ""}>
        <div class="card-title">${esc(t("last_result"))}</div>
        ${last ? `<div class="row">${ring(last.overall, 64)}<div>${levelHtml(last.cefr, 26)}
          <div class="muted small">IELTS ${esc(last.ielts)} · ${esc(fmtDate(last.created, true))}</div></div></div>`
          : `<p class="muted">${esc(t("no_results"))}</p>`}
      </div>
    </div>`);
  centreToday();
}

function calendarHtml(c) {
  const box = (d) => {
    const special = d.kind === "frame" ? "frame" : d.amount >= 100 ? "big" : "";
    const pic = d.state === "claimed" ? icon("check") : d.state === "missed" ? "–" : d.kind === "frame" ? streakFrame(30) : coin();
    return `<div class="cal-day ${d.state} ${special}">
        <span class="cal-n">${esc(t("day_n", { n: d.n }))}</span>
        <span class="cal-coin">${pic}</span>
        <b>${d.kind === "frame" ? esc(t("cal_frame")) : d.amount}</b></div>`;
  };
  return `<div class="cal-head"><div class="eyebrow">${esc(t("daily_rewards"))}</div></div>
    <div class="cal-days" id="calDays">${c.days.map(box).join("")}
      <div class="cal-day future ${c.future.state}"><span class="future-t">${esc(t("future_rewards"))}</span><span class="future-arrow">→</span></div></div>
    ${c.can_claim ? `<button class="btn" id="claimBtn">${c.next_kind === "frame" ? `${streakFrame(22)} ${esc(t("collect_frame"))}` : `${coin()} ${esc(t("collect_n", { n: c.next_amount }))}`}</button>`
      : `<div class="cal-done">${icon("check")} ${esc(t("come_back_tomorrow"))}</div>`}`;
}
function streakFrame(size) {
  // the real "Streak" frame (the same one as in Frames), drawn on the player's own avatar
  return `<span class="cal-frame">${avatarHtml({ ...(S.me && S.me.card || {}), username: S.me ? S.me.username : "?", frame: "streak" }, size)}</span>`;
}
function centreToday() {
  const strip = document.getElementById("calDays");
  const today = strip && (strip.querySelector(".cal-day.today") || [...strip.querySelectorAll(".cal-day.claimed, .cal-day.missed")].pop());
  if (today) strip.scrollLeft = today.offsetLeft - (strip.clientWidth - today.offsetWidth) / 2;
}
function coin() {
  // a medium-blue ticket (Speakoff credits)
  return `<svg class="coin" viewBox="0 0 32 22" aria-hidden="true"><path d="M3 1h26a2 2 0 0 1 2 2v5a3 3 0 0 0 0 6v5a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2v-5a3 3 0 0 0 0-6V3a2 2 0 0 1 2-2z" fill="#3B82F6"/><path d="M3 1h26a2 2 0 0 1 2 2v5a3 3 0 0 0 0 6v5a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2v-5a3 3 0 0 0 0-6V3a2 2 0 0 1 2-2z" fill="none" stroke="#93C5FD" stroke-width="1.2"/><path d="M22 3.5v15" stroke="#DBEAFE" stroke-width="1.3" stroke-dasharray="2 2"/><path d="M11.5 6.5l1.4 2.9 3.2.5-2.3 2.2.5 3.2-2.8-1.5-2.8 1.5.5-3.2-2.3-2.2 3.2-.5z" fill="#FFFFFF"/></svg>`;
}
function creditsPill() {
  return `<a class="credits-pill" href="#/shop" title="${esc(t("credits"))}">${coin()}<b>${(S.me && S.me.credits || 0).toLocaleString()}</b></a>`;
}
const MAIN_VIEWS = new Set(["home", "progress", "record", "ranked", "profile"]);
function addCreditsPill() {
  // every main tab: the credits balance at the top right of the page head
  if (!S.me || !MAIN_VIEWS.has(S.view)) return;
  const head = app.querySelector(".page-head");
  if (!head || head.querySelector(".credits-pill")) return;
  const kids = [...head.children];
  if (kids.length >= 2) {
    const right = kids[kids.length - 1];
    const box = document.createElement("div");
    box.className = "head-right";
    head.replaceChild(box, right);
    box.appendChild(right);
    box.insertAdjacentHTML("beforeend", creditsPill());
  } else {
    head.insertAdjacentHTML("beforeend", `<div class="head-right">${creditsPill()}</div>`);
  }
}
document.addEventListener("click", async (e) => {
  const b = e.target.closest("#claimBtn");
  if (!b) return;
  b.disabled = true;
  const r = await api("/api/daily/claim", {});
  if (!r.ok) { toast(errText(r)); b.disabled = false; return; }
  const box = document.getElementById("cal");
  if (box) { box.innerHTML = calendarHtml(r.calendar); fillIcons(box); box.classList.add("collected"); centreToday(); }
  if (S.me) S.me.credits = r.calendar.credits;
  app.querySelectorAll(".credits-pill b").forEach((el) => { el.textContent = r.calendar.credits.toLocaleString(); });
  sfx(r.reward.kind === "frame" || r.reward.sticker ? "sparkle" : "coin");
  toast(r.reward.kind === "frame" ? `🖼️ ${t("new_frame", { name: t("frame_streak") })}`
    : `+${r.reward.amount} ${t("credits")}${r.reward.sticker ? " · " + STICKERS[r.reward.sticker.replace("sticker_", "")] : ""}`);
});

// ------------------------------------------------------------------ record
const rec = { stream: null, recorder: null, chunks: [], timer: null, start: 0, blob: null, mime: "", mode: "audio", sections: new Set(SECTIONS) };

function stopStream() {
  if (rec.timer) clearInterval(rec.timer);
  rec.timer = null;
  if (rec.recorder && rec.recorder.state !== "inactive") { rec.recorder.onstop = null; rec.recorder.stop(); }
  if (rec.stream) rec.stream.getTracks().forEach((tr) => tr.stop());
  rec.stream = null; rec.recorder = null;
}
function pickMime(video) {
  const list = video
    ? ["video/webm;codecs=vp8,opus", "video/webm", "video/mp4"]
    : ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg"];
  return list.find((m) => window.MediaRecorder && MediaRecorder.isTypeSupported(m)) || "";
}
function extFor(mime) { return mime.includes("mp4") ? "mp4" : mime.includes("ogg") ? "ogg" : "webm"; }

async function viewRecord(arg) {
  const daily = arg === "daily";
  await refreshMe();
  const u = S.usage;
  const max = daily ? 70 : u.max_s;
  let question = null;
  if (daily) {
    const h = await api("/api/home");
    question = h.daily_question;
    if (h.usage.daily_answered) { render(`<div class="card empty">${esc(t("daily_done"))}</div>`); return; }
  }
  rec.blob = null;
  leaveHooks.push(stopStream);

  if (!daily && !u.can_record) {
    render(`
      <div class="page-head"><h1>${esc(t("tab_record"))}</h1></div>
      <div class="card stack center" style="padding:28px">
        <h2>${esc(t("no_left"))}</h2><p class="muted">${esc(t("no_left_sub"))}</p>
        <a class="btn block" href="#/plans">${icon("spark")} ${esc(t("upgrade"))}</a>
        ${u.daily_answered ? "" : `<a class="btn block ghost" href="#/record/daily">${esc(t("daily_question"))}</a>`}
      </div>`);
    return;
  }

  render(`
    <div class="page-head"><h1>${esc(daily ? t("daily_question") : t("tab_record"))}</h1>
      ${daily ? "" : `<span class="tag accent">${esc(planName(u.plan))}</span>`}</div>
    <div class="stack">
      ${daily ? "" : langSwitch()}
      ${daily ? `<div class="hero"><div class="eyebrow">${esc(t("question"))}</div><div class="q" style="margin-bottom:0">${esc(question)}</div></div>`
        : `<a class="card row between mock-entry" href="#/mock"><div class="row">${icon("doc")}<b>${esc(t(S.me.learn_lang === "ko" ? "mock_title_ko" : "mock_title"))}</b></div>${icon("back")}</a>`}
      <div class="seg" id="modeSeg">
        <button data-mode="audio" class="${rec.mode === "audio" ? "on" : ""}">${icon("mic")} ${esc(t("mode_audio"))}</button>
        <button data-mode="video" class="${rec.mode === "video" ? "on" : ""}">${icon("video")} ${esc(t("mode_video"))}</button>
      </div>
      ${daily ? "" : `
      <div class="card">
        <div class="card-title">${esc(t("sections_title"))}</div>
        <div class="chips" id="chips">${SECTIONS.map((s) => `<button class="chip ${rec.sections.has(s) ? "on" : ""}" data-sec="${s}">${icon("check")}${esc(t("sec_" + s))}</button>`).join("")}</div>
        <p class="hint">${esc(t("overall_always"))}</p>
      </div>`}
      <div class="card recorder" id="recCard">
        <video class="rec-preview" id="preview" muted playsinline hidden></video>
        <div class="timer" id="timer">0:00 <small>/ 1:00</small></div>
        <button class="rec-btn" id="recBtn" aria-label="${esc(t("rec_start"))}">
          <svg class="track" viewBox="0 0 120 120"><circle cx="60" cy="60" r="56" fill="none" stroke="var(--surface-2)" stroke-width="6"/>
            <circle id="minArc" cx="60" cy="60" r="56" fill="none" stroke="var(--border)" stroke-width="6" stroke-dasharray="${2 * Math.PI * 56 * 60 / max} 999"/>
            <circle id="arc" cx="60" cy="60" r="56" fill="none" stroke="var(--bad)" stroke-width="6" stroke-linecap="round" stroke-dasharray="0 999"/></svg>
          <span class="core">${icon("mic")}</span>
        </button>
        <p class="muted small center" id="recHint">${esc(t("rec_plan_max", { max: mmss(max) }))}</p>
        <button class="btn small ghost" id="recCancel" hidden>${esc(t("cancel"))}</button>
        <div id="after" class="stack" style="width:100%" hidden></div>
      </div>
      <label class="drop" id="drop">${icon("upload")} <b>${esc(t("or_upload"))}</b><div class="hint">${esc(t("upload_hint", { max: mmss(max) }))}</div>
        <input type="file" id="file" accept="audio/*,video/*" hidden></label>
      <div id="sendBox" class="stack" hidden><div class="progress-line"><i id="upBar"></i></div><p class="muted small center" id="upText"></p></div>
      <div class="error center" id="err"></div>
    </div>`);
  bindLangSwitch(() => viewRecord(arg));
  $$("#modeSeg button").forEach((b) => b.onclick = () => {
    if (rec.recorder) return;
    rec.mode = b.dataset.mode;
    $$("#modeSeg button").forEach((x) => x.classList.toggle("on", x === b));
  });
  $$("#chips .chip").forEach((c) => c.onclick = () => {
    const s = c.dataset.sec;
    rec.sections.has(s) ? rec.sections.delete(s) : rec.sections.add(s);
    c.classList.toggle("on", rec.sections.has(s));
  });

  const C = 2 * Math.PI * 56;
  const recBtn = $("#recBtn");
  recBtn.onclick = async () => {
    $("#err").textContent = "";
    if (rec.recorder) {                       // stop (allowed after 1:00)
      if ((Date.now() - rec.start) / 1000 >= 60) rec.recorder.stop();
      return;
    }
    if (!daily && rec.sections.size === 0) { $("#err").textContent = t("choose_section"); return; }
    const video = rec.mode === "video";
    try {
      rec.stream = await navigator.mediaDevices.getUserMedia(video
        ? { audio: { echoCancellation: true, noiseSuppression: true }, video: { width: { ideal: 640 }, height: { ideal: 480 }, frameRate: { ideal: 24 } } }
        : { audio: { echoCancellation: true, noiseSuppression: true } });
    } catch (e) { $("#err").textContent = t("mic_denied"); return; }
    if (video) { const pv = $("#preview"); pv.srcObject = rec.stream; pv.hidden = false; pv.play().catch(() => {}); }
    rec.mime = pickMime(video);
    rec.recorder = new MediaRecorder(rec.stream, rec.mime ? { mimeType: rec.mime, audioBitsPerSecond: 64000, videoBitsPerSecond: 900000 } : undefined);
    rec.chunks = [];
    rec.recorder.ondataavailable = (e) => { if (e.data.size) rec.chunks.push(e.data); };
    rec.recorder.onstop = () => finishRecording();
    rec.recorder.start(1000);
    rec.start = Date.now();
    recBtn.classList.add("live");
    recBtn.disabled = true;
    $("#recCancel").hidden = false;
    $("#recCancel").onclick = () => { stopStream(); route(); };     // throw this recording away and start over
    $("#modeSeg").style.opacity = .5;
    $("#drop").hidden = true;
    rec.timer = setInterval(() => {
      const s = (Date.now() - rec.start) / 1000;
      $("#timer").innerHTML = `<span class="pulse"></span>${mmss(s)} <small>${s < 60 ? "/ 1:00" : esc(t("max_time", { t: mmss(max) }))}</small>`;
      $("#arc").setAttribute("stroke-dasharray", `${C * Math.min(s / max, 1)} 999`);
      if (s < 60) $("#recHint").textContent = t("rec_min_left", { s: Math.ceil(60 - s) });
      else { recBtn.disabled = false; $("#recHint").textContent = t("rec_auto_stop", { max: mmss(max) }); }
      if (s >= max) rec.recorder && rec.recorder.state === "recording" && rec.recorder.stop();
    }, 200);
  };

  function finishRecording() {
    clearInterval(rec.timer); rec.timer = null;
    const type = rec.recorder.mimeType || rec.mime || (rec.mode === "video" ? "video/webm" : "audio/webm");
    rec.blob = new Blob(rec.chunks, { type });
    rec.stream.getTracks().forEach((tr) => tr.stop());
    rec.stream = null; rec.recorder = null;
    recBtn.hidden = true;
    $("#recCancel").hidden = true;
    $("#preview").hidden = true;
    $("#recHint").hidden = true;
    const url = URL.createObjectURL(rec.blob);
    const after = $("#after");
    after.hidden = false;
    after.innerHTML = `${rec.mode === "video" ? `<video class="player" src="${url}" controls playsinline></video>` : `<audio src="${url}" controls></audio>`}
      <button class="btn block" id="send">${icon("spark")} ${esc(t("analyse"))}</button>
      <button class="btn block ghost" id="again">${esc(t("rec_again"))}</button>`;
    fillIcons(after);
    $("#send").onclick = () => send(rec.blob, `recording.${extFor(type)}`);
    $("#again").onclick = () => route();
  }

  $("#file").onchange = (e) => {
    const f = e.target.files[0];
    if (!f) return;
    if (!daily && rec.sections.size === 0) { $("#err").textContent = t("choose_section"); return; }
    rec.mode = f.type.startsWith("video") ? "video" : rec.mode === "video" && !f.type ? "video" : "audio";
    send(f, f.name);
  };

  function send(blob, name) {
    $("#err").textContent = "";
    const fd = new FormData();
    fd.append("file", blob, name);
    fd.append("mode", rec.mode);
    fd.append("sections", [...rec.sections].join(","));
    if (daily) fd.append("daily", "1");
    $("#sendBox").hidden = false;
    $$("#send, #again").forEach((b) => b.disabled = true);
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/recordings");
    xhr.setRequestHeader("X-SC", "1");
    xhr.upload.onprogress = (e) => {
      if (!e.lengthComputable) return;
      const pct = Math.round(100 * e.loaded / e.total);
      $("#upBar").style.width = pct + "%";
      $("#upText").textContent = t("uploading", { pct });
    };
    xhr.onload = () => {
      let res = {};
      try { res = JSON.parse(xhr.responseText); } catch (e) { /* not JSON */ }
      if (res.ok) { go(`#/result/${res.id}`); return; }
      $("#sendBox").hidden = true;
      $$("#send, #again").forEach((b) => b.disabled = false);
      $("#err").textContent = errText(res);
    };
    xhr.onerror = () => { $("#sendBox").hidden = true; $$("#send, #again").forEach((b) => b.disabled = false); $("#err").textContent = t("err_network"); };
    xhr.send(fd);
  }
}

// ------------------------------------------------------------------ result
async function viewResult(id) {
  let r = await api(`/api/recordings/${id}`);
  if (!r.id) { render(`<div class="card empty">404</div>`); return; }
  if (r.status === "queued" || r.status === "running") {
    render(`
      <div class="card analysing">
        <div class="spinner"></div>
        <h2>${esc(r.status === "queued" && r.ahead ? t("queued") : t("analysing"))}</h2>
        <p class="muted" style="margin-top:8px">${esc(t("analysing_sub"))}</p>
        <p class="muted small" style="margin-top:14px" id="elapsed"></p>
      </div>`);
    const started = Date.now();
    const tick = setInterval(() => { const el = document.getElementById("elapsed"); if (el) el.textContent = mmss((Date.now() - started) / 1000); }, 1000);
    const poll = setInterval(async () => {
      const x = await api(`/api/recordings/${id}`);
      if (x.status && x.status !== r.status && !(x.status === "running" && r.status === "queued")) { clearInterval(poll); clearInterval(tick); route(); }
      r.status = x.status;
    }, 3000);
    leaveHooks.push(() => { clearInterval(poll); clearInterval(tick); });
    return;
  }
  if (r.status === "failed") {
    render(`<div class="card center stack" style="padding:28px"><h2>${esc(t("failed"))}</h2><p class="muted">${esc(t(r.error || "failed_sub", r.params))}</p>
      <a class="btn" href="#/record">${esc(t("tab_record"))}</a></div>`);
    return;
  }
  const lv = r.level;
  const secCard = (s) => {
    if ((r.coming || []).includes(s)) return `<div class="sec off"><div class="name">${esc(t("sec_" + s))}</div>
      <div class="val"><small>${esc(t("coming_soon"))}</small></div><div class="bar"><i style="width:0%"></i></div></div>`;
    const on = r.chosen.includes(s), v = r.scores[s];
    return `<div class="sec ${on ? "" : "off"}"><div class="name">${esc(t("sec_" + s))}</div>
      <div class="val ${on ? cls(v) : ""}">${on ? v : "0"}${on ? "" : ` <small>${esc(t("not_chosen"))}</small>`}</div>
      <div class="bar ${on ? cls(v) : ""}"><i style="width:${on ? v : 0}%"></i></div></div>`;
  };
  const g = r.grammar, f = r.fluency, v = r.vocabulary, p = r.pronunciation, cam = r.camera;
  render(`
    <div class="page-head"><div><div class="date">${esc(fmtDate(r.created, true))} · ${esc(t(r.mode === "video" ? "mode_video" : "mode_audio"))}</div>
      <h1>${esc(t("overall"))}</h1></div>${r.is_daily ? `<span class="tag accent">${esc(t("daily_badge"))}</span>` : r.is_mock ? `<span class="tag accent">${esc(t("mock_short"))}</span>` : ""}</div>
    <div class="stack">
      ${r.question ? `<div class="card"><div class="card-title">${esc(t("question"))}</div><p>${esc(r.question)}</p></div>` : ""}
      <div class="card row" style="gap:18px">
        ${ring(r.overall, 132, "/ 100")}
        <div class="levels">
          <div>${levelHtml(lv.cefr)}</div>
          ${lv.exam === "topik" ? `<div class="level-row"><span class="muted">${esc(t("topik_speaking"))}</span><b>${lv.topik ? esc(t("topik_level", { n: lv.topik })) : "–"}</b></div>
            <div class="level-row"><span class="muted"></span><span class="tag">${esc(t("beta"))}</span></div>`
          : `<div class="level-row"><span class="muted">${esc(t("ielts"))}</span><b>${esc(lv.ielts)}</b></div>
          <div class="level-row"><span class="muted">${esc(t("toefl"))}</span><b>${esc(lv.toefl)}/6 · ${esc(lv.toefl_old)}/30</b></div>`}
        </div>
      </div>
      ${r.is_mock && lv.ielts_parts ? `<div class="card"><div class="card-title">${esc(t("ielts"))}</div><div class="ielts-parts">
        ${SECTIONS.map((s) => `<div><b>${esc(lv.ielts_parts[s])}</b><span>${esc(t("sec_" + s))}</span></div>`).join("")}</div></div>` : ""}
      ${r.profanity ? `<div class="notice bad">${esc(t("profanity_note"))}</div>` : ""}
      ${r.integrity === "cheat" ? `<div class="notice bad">${esc(t("cheat_note"))}</div>`
        : r.integrity === "tip" ? `<div class="notice warn">${esc(t("cheat_tip"))}</div>` : ""}
      ${r.topic === "repeated" ? `<div class="notice bad">${esc(t("repeated_note"))}</div>`
        : r.off_topic ? `<div class="notice bad">${esc(t("off_topic_note"))}</div>`
        : r.topic === "partial" ? `<div class="notice warn">${esc(t("partial_note"))}</div>` : ""}
      ${lv.too_short ? `<div class="notice">${esc(t("estimate_note"))}</div>` : ""}
      ${r.trimmed ? `<div class="notice warn">${esc(t("trimmed", { max: mmss(r.max_s) }))}</div>` : ""}
      ${r.repetition ? `<div class="notice bad">${esc(t("repetition_warn", { pct: r.repetition.pct, cap: r.repetition.cap }))}</div>` : ""}
      <div class="grid2">${SECTIONS.map(secCard).join("")}</div>
      ${cam ? `<div class="card row between"><div><h3>${esc(t("sec_on_camera"))}</h3><p class="muted small">${esc(t("on_camera_note"))}</p></div>
        <div class="val ${cls(cam.score)}" style="font-size:28px;font-weight:800">${cam.score}</div></div>` : ""}

      ${r.feedback ? `<div class="card">
        <div class="row between" style="margin-bottom:12px"><h2>${esc(t("feedback"))}</h2>
          <button class="btn small" id="play">${icon("play")} ${esc(t("play_feedback"))}</button></div>
        <audio id="voice" hidden controls></audio>
        <div class="feedback-text">${r.feedback.split("\n").map((x) => `<p>${esc(x)}</p>`).join("")}</div>
      </div>` : ""}

      ${r.chosen.includes("grammar") ? `<details class="acc" open><summary>${esc(t("sec_grammar"))} · ${r.scores.grammar}</summary><div class="acc-body stack">
        <dl class="kv"><dt>${esc(t("accuracy"))}</dt><dd>${g.accuracy} · ${esc(t("mistakes_per_100", { n: g.per100 }))}</dd>
          <dt>${esc(t("range"))}</dt><dd>${g.range} · ${esc(t("complex_pct", { n: g.complex }))}</dd></dl>
        <div>${g.sentences.length ? g.sentences.map((s) => `<div class="sent">
          <div class="lbl">${esc(t("you_said"))}</div><div class="said">${esc(s.original)}</div>
          <div class="lbl">${esc(t("better"))}</div><div class="fixed">${esc(s.corrected)}</div>
          ${s.mistakes.map((m) => `<div class="fix"><span class="tag">${esc(m.category)}</span> ${m.wrong ? `<s>${esc(m.wrong)}</s>` : ""} → <ins>${esc(m.right || "∅")}</ins></div>`).join("")}
        </div>`).join("") : `<p class="muted">${esc(t("no_grammar_mistakes"))}</p>`}</div></div></details>` : ""}

      ${r.chosen.includes("fluency") ? `<details class="acc"><summary>${esc(t("sec_fluency"))} · ${r.scores.fluency}</summary><div class="acc-body">
        <dl class="kv"><dt>${esc(t("speed"))}</dt><dd>${esc(t("syll_per_sec", { n: f.sps }))}</dd>
          <dt>${esc(t("pauses"))}</dt><dd>${f.pauses}%</dd><dt>${esc(t("avg_run"))}</dt><dd>${f.mlr}</dd>
          <dt>${esc(t("fillers"))}</dt><dd>${f.fillers}</dd><dt>${esc(t("repairs"))}</dt><dd>${f.repairs}</dd></dl></div></details>` : ""}

      ${r.chosen.includes("vocabulary") ? `<details class="acc"><summary>${esc(t("sec_vocabulary"))} · ${r.scores.vocabulary}</summary><div class="acc-body stack">
        <dl class="kv"><dt>${esc(t(r.learn_lang === "ko" ? "ko_mid_words" : "b1_words"))}</dt><dd>${v.b1}%</dd><dt>${esc(t(r.learn_lang === "ko" ? "ko_adv_words" : "b2_words"))}</dt><dd>${v.b2}%</dd>
          <dt>${esc(t("variety"))}</dt><dd>${v.variety}</dd></dl>
        ${v.words.length ? `<div><div class="card-title">${esc(t("good_words"))}</div>${v.words.map((w) => `<span class="word">${esc(w)}</span>`).join("")}</div>` : ""}
      </div></details>` : ""}

      ${r.chosen.includes("pronunciation") ? `<details class="acc"><summary>${esc(t("sec_pronunciation"))} · ${r.scores.pronunciation}</summary><div class="acc-body stack">
        <p>${esc(t("sounds_right", { n: p.right }))}</p>
        ${p.mouth ? `<div class="notice">${esc(p.mouth)}</div>` : ""}
        ${p.mistakes.map((m) => `<div class="sent"><b>${esc(t("practise_sound", { e: m.e }))}</b>
          <span class="muted small">(${esc(m.h === "?" ? t("unclear") : t("heard_as", { h: m.h }))}) ×${m.n}</span>
          <div style="margin-top:6px">${m.words.map((w) => `<span class="word">${esc(w)}</span>`).join("")}</div></div>`).join("")}
      </div></details>` : ""}

      ${cam ? `<details class="acc"><summary>${esc(t("sec_on_camera"))} · ${cam.score}</summary><div class="acc-body stack">
        <dl class="kv"><dt>${esc(t("eye_contact"))}</dt><dd>${cam.stats.eye_contact ?? "–"}%</dd>
          <dt>${esc(t("smiling"))}</dt><dd>${cam.stats.smile ?? "–"}%</dd>
          <dt>${esc(t("head_movement"))}</dt><dd>${cam.stats.head_motion ?? "–"}°</dd>
          <dt>${esc(t("face_visible"))}</dt><dd>${cam.stats.face_visible ?? "–"}%</dd></dl>
        ${cam.tips.map((x) => `<p>• ${esc(x)}</p>`).join("")}
      </div></details>` : ""}

      <details class="acc"><summary>${esc(t("transcript"))}</summary><div class="acc-body"><p>${esc(r.transcript)}</p></div></details>
      <div class="card"><div class="row between"><div class="card-title" style="margin:0">${esc(t("your_recording"))}</div>
          ${r.keep_forever ? `<span class="tag accent">${icon("bookmark")} ${esc(t("kept_forever"))}</span>`
            : r.audio ? `<button class="btn small outline" id="keepBtn">${icon("bookmark")} ${esc(t("keep_forever"))} · ${coin()} 40</button>` : ""}</div>
        ${r.audio ? `<audio src="/api/recordings/${r.id}/audio" controls preload="none" style="margin-top:10px"></audio>` : `<p class="muted">${esc(t("recording_deleted", { n: r.keep }))}</p>`}</div>
    </div>`);

  const keepBtn = $("#keepBtn");
  if (keepBtn) keepBtn.onclick = async () => {
    keepBtn.disabled = true;
    const res = await api("/api/shop/buy", { item: "keep_audio", ref: r.id });
    if (!res.ok) { keepBtn.disabled = false; toast(errText(res)); return; }
    S.me = res.user; sfx("sparkle"); toast(t("kept_forever")); viewResult(r.id);
  };
  if ($("#play")) $("#play").onclick = async () => {
    // the server makes the voice only now (first press), which takes a few seconds; then it is kept
    const a = $("#voice"), b = $("#play");
    b.disabled = true;
    b.innerHTML = `<span class="spinner sm"></span> ${esc(t("preparing_voice"))}`;
    try {
      const res = await fetch(`/api/recordings/${r.id}/voice`, { credentials: "same-origin" });
      if (!res.ok || !(res.headers.get("content-type") || "").startsWith("audio")) throw new Error("voice");
      a.src = URL.createObjectURL(await res.blob());
      a.hidden = false;
      b.hidden = true;
      a.play().catch(() => {});                // the browser may want a second tap; the controls are shown
    } catch (e) {
      b.disabled = false;
      b.innerHTML = `${icon("play")} ${esc(t("play_feedback"))}`;
      toast(t("voice_failed"));
    }
  };
}

// ------------------------------------------------------------------ progress (+ history)
function lineChart(points, series, height = 150) {
  // points: [{date, values: {key: number}}]; series: [{key, color}]
  const W = 320, H = height, L = 26, R = 8, T = 10, B = 22;
  const n = points.length;
  const x = (i) => n <= 1 ? (L + W - R) / 2 : L + (W - L - R) * i / (n - 1);
  const y = (v) => T + (H - T - B) * (1 - v / 100);
  let svg = `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img"><g class="grid">`;
  for (const v of [0, 25, 50, 75, 100]) svg += `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}"/><text x="0" y="${y(v) + 3}">${v}</text>`;
  svg += "</g>";
  for (const s of series) {
    const pts = points.map((p, i) => [x(i), p.values[s.key]]).filter((p) => p[1] != null);
    if (!pts.length) continue;
    svg += `<polyline fill="none" stroke="${s.color}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" points="${pts.map(([a, b]) => `${a},${y(b)}`).join(" ")}"/>`;
    svg += pts.map(([a, b]) => `<circle cx="${a}" cy="${y(b)}" r="3.2" fill="${s.color}"/>`).join("");
  }
  if (n) {
    svg += `<text x="${L}" y="${H - 5}">${esc(points[0].date.slice(5))}</text>`;
    if (n > 1) svg += `<text x="${W - R}" y="${H - 5}" text-anchor="end">${esc(points[n - 1].date.slice(5))}</text>`;
  }
  return svg + "</svg>";
}

async function viewProgress() {
  render(`<div class="splash"><div class="spinner"></div></div>`);
  const d = await api("/api/progress");
  if (!d.history) return;
  const overallPts = d.trend.map((p) => ({ date: p.date, values: { overall: p.overall } }));
  const secPts = d.trend.map((p) => ({ date: p.date, values: Object.fromEntries(SECTIONS.map((s) => [s, p.chosen.includes(s) ? p.scores[s] : null])) }));
  const fullBlock = d.full ? `
      <div class="card"><div class="card-title">${esc(t("by_section"))}</div>
        ${d.trend.length ? lineChart(secPts, SECTIONS.map((s) => ({ key: s, color: SEC_COLORS[s] }))) : `<p class="muted">${esc(t("no_history"))}</p>`}
        <div class="legend">${SECTIONS.map((s) => `<span><i style="background:${SEC_COLORS[s]}"></i>${esc(t("sec_" + s))}</span>`).join("")}</div></div>
      <div class="grid2">
        <div class="card"><div class="card-title">${esc(t("level_history"))}</div>
          ${(d.levels || []).length ? d.levels.map((l) => `<div class="level-row"><span class="muted">${esc(l.date.slice(5))}</span><b>${esc(levelParts(l.cefr)[0])}</b></div>`).join("") : "–"}</div>
        <div class="card"><div class="card-title">${esc(t("common_sounds"))}</div>
          ${(d.sounds || []).length ? d.sounds.map((s) => `<span class="word ipa">/${esc(s.e)}/ ×${s.n}</span>`).join("") : "–"}</div>
      </div>
      <div class="card"><div class="card-title">${esc(t("common_mistakes"))}</div>
        ${(d.mistakes || []).length ? (() => { const top = d.mistakes[0].n; return d.mistakes.map((m) => `<div class="hbar" style="margin-bottom:10px"><span>${esc(m.category)}</span><b>${m.n}</b>
          <div class="bar"><i style="width:${100 * m.n / top}%"></i></div></div>`).join(""); })() : "–"}</div>`
    : `
      <div class="card locked">
        <div class="blur">
          <div class="card-title">${esc(t("by_section"))}</div>
          ${lineChart([{ date: "01-01", values: { a: 55, b: 62, c: 48, d: 70 } }, { date: "01-08", values: { a: 63, b: 66, c: 57, d: 72 } }, { date: "01-15", values: { a: 70, b: 71, c: 64, d: 78 } }],
            ["a", "b", "c", "d"].map((k, i) => ({ key: k, color: Object.values(SEC_COLORS)[i] })))}
          <div class="hbar"><span>${esc(t("common_mistakes"))}</span><b>7</b><div class="bar"><i style="width:70%"></i></div></div>
        </div>
        <div class="lock"><div class="lock-inner">${icon("lock")}<b>${esc(t("unlock_plus"))}</b><a class="btn small" href="#/plans">${esc(t("upgrade"))}</a></div></div>
      </div>`;
  render(`
    <div class="page-head"><h1>${esc(t("progress_title"))}</h1></div>
    <div class="stack">
      <div class="stats4">
        <div class="stat"><b>${d.count}</b><span>${esc(t("recordings_count"))}</span></div>
        <div class="stat"><b class="${d.average != null ? cls(d.average) : ""}">${d.average ?? "–"}</b><span>${esc(t("average"))}</span></div>
        <div class="stat"><b class="${d.best != null ? cls(d.best) : ""}">${d.best ?? "–"}</b><span>${esc(t("best_score"))}</span></div>
        <div class="stat"><b>${esc(levelParts(d.level)[0])}</b><span>${esc(t("level"))}</span></div>
      </div>
      <div class="card"><div class="row between"><div class="card-title" style="margin:0">${esc(t("overall_trend"))}</div>
        <span class="tag">${esc(t(d.full ? "all_time" : "last_14_days"))}</span></div>
        <div style="margin-top:10px">${d.trend.length ? lineChart(overallPts, [{ key: "overall", color: "#3574F0" }]) : `<p class="muted">${esc(t("no_history"))}</p>`}</div></div>
      ${fullBlock}
      <div class="card"><div class="card-title">${esc(t("history"))}</div>
        ${d.full ? "" : `<p class="hint" style="margin:-4px 0 8px">${esc(t("history_free_note"))}</p>`}
        ${d.history.length ? d.history.map((h) => `
          <div class="hist" onclick="location.hash='#/result/${h.id}'">
            <div class="score ${h.status === "done" ? cls(h.overall) : ""}">${h.status === "done" ? h.overall : `<span class="spinner sm"></span>`}</div>
            <div class="meta"><div class="t">${esc(h.is_mock ? t(h.learn_lang === "ko" ? "mock_history_ko" : "mock_history") : h.question || (h.status === "done" ? `${t("level")} ${levelParts(h.cefr)[0]}` : t("analysing")))}</div>
              <div class="s">${icon(h.mode === "video" ? "video" : "mic")} ${esc(fmtDate(h.created, true))}${h.is_daily ? ` · ${esc(t("daily_badge"))}` : ""}</div></div>
          </div>`).join("") : `<p class="empty">${esc(t("no_history"))}</p>`}
      </div>
    </div>`);
}

// ------------------------------------------------------------------ ranks, avatars, frames
const RANK_COLOR = Object.fromEntries(RANKS);
const ROMAN = ["", "I", "II", "III"];
function rankLabel(r) { return r ? `${t("rank_" + r.rank)}${r.div ? " " + ROMAN[r.div] : r.wins != null ? " " + r.wins : ""}` : ""; }
function shade(hex, amt) {
  // amt > 0 mixes with white, amt < 0 with black
  const n = parseInt(hex.slice(1), 16), to = amt > 0 ? 255 : 0, a = Math.abs(amt);
  const ch = (v) => Math.round(v + (to - v) * a).toString(16).padStart(2, "0");
  return `#${ch(n >> 16)}${ch((n >> 8) & 255)}${ch(n & 255)}`;
}
// rank emblem (chosen by the user 2026-11-24): a detailed hexagon with nothing inside (faceted bevel, enamel, engraving);
// the plate grows with the rank: studs (Bronze), green laurel (Silver), gold rim + ball (Gold),
// wings + glow (Platinum), gem on top (Diamond), jewelled crown (Master). The stage / Master wins sit on a ribbon.
const EM_GOLD = "#E9B949", EM_LEAF = "#3DBE6B", EM_LEAF_DK = "#2A9653";
let embN = 0;
const emRad = (d) => d * Math.PI / 180;
const emPts = (p) => p.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
const emHex = (R) => emPts(Array.from({ length: 6 }, (_, i) => [60 + R * Math.cos(emRad(-90 + i * 60)), 54 + R * Math.sin(emRad(-90 + i * 60))]));
function emSparkle(x, y, s, op = 1) {
  return `<path opacity="${op}" d="M${x} ${y - s} Q${x + s * .14} ${y - s * .14} ${x + s} ${y} Q${x + s * .14} ${y + s * .14} ${x} ${y + s} Q${x - s * .14} ${y + s * .14} ${x - s} ${y} Q${x - s * .14} ${y - s * .14} ${x} ${y - s} Z" fill="#FFFFFF"/>`;
}
function emGem(id, cx, cy, R, c, sides = 6) {
  const O = Array.from({ length: sides }, (_, i) => [cx + R * Math.cos(emRad(-90 + i * 360 / sides)), cy + R * Math.sin(emRad(-90 + i * 360 / sides))]);
  const I = O.map(([x, y]) => [cx + (x - cx) * .48, cy + (y - cy) * .48]);
  const tones = [.55, .3, -.05, -.35, -.5, -.3, .05, .35];
  const f = O.map((o, i) => `<polygon points="${emPts([o, O[(i + 1) % sides], I[(i + 1) % sides], I[i]])}" fill="${shade(c, tones[i % 8])}"/>`).join("");
  return `<polygon points="${emPts(O)}" fill="${shade(c, -.55)}" stroke="${shade(c, -.75)}" stroke-width="1.2" stroke-linejoin="round"/>${f}
    <polygon points="${emPts(I)}" fill="url(#${id}e)"/>${emSparkle(cx - R * .3, cy - R * .35, R * .32)}`;
}
function emDefs(id, c, lvl) {
  const rim = lvl >= 3 ? EM_GOLD : c;
  const metal = (nm, b) => `<linearGradient id="${id}${nm}" x1="0" y1="0" x2=".25" y2="1">
      <stop offset="0" stop-color="${shade(b, .75)}"/><stop offset=".22" stop-color="${shade(b, .2)}"/><stop offset=".48" stop-color="${shade(b, -.4)}"/>
      <stop offset=".6" stop-color="${shade(b, .05)}"/><stop offset=".85" stop-color="${shade(b, .45)}"/><stop offset="1" stop-color="${shade(b, -.2)}"/></linearGradient>`;
  return `<defs>${metal("r", rim)}${metal("g", EM_GOLD)}
    <radialGradient id="${id}e" cx=".5" cy=".32" r=".75"><stop offset="0" stop-color="${shade(c, .45)}"/><stop offset=".55" stop-color="${c}"/><stop offset="1" stop-color="${shade(c, -.6)}"/></radialGradient>
    <radialGradient id="${id}d" cx=".5" cy=".4" r=".7"><stop offset="0" stop-color="${shade(c, -.2)}"/><stop offset="1" stop-color="${shade(c, -.72)}"/></radialGradient>
    <linearGradient id="${id}w" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FFFFFF"/><stop offset=".6" stop-color="${shade(c, .6)}"/><stop offset="1" stop-color="${shade(c, .1)}"/></linearGradient>
    <linearGradient id="${id}b" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${shade(c, .25)}"/><stop offset=".5" stop-color="${shade(c, -.2)}"/><stop offset="1" stop-color="${shade(c, -.5)}"/></linearGradient>
    <filter id="${id}f" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="6"/></filter>
    <clipPath id="${id}c"><polygon points="${emHex(46)}"/></clipPath></defs>`;
}
function emFace(id, c, lvl) {
  // the hexagon's own detail, no picture inside: a faceted bevel ring, an enamel face with engraved lines
  const V = (R) => Array.from({ length: 6 }, (_, i) => [60 + R * Math.cos(emRad(-90 + i * 60)), 54 + R * Math.sin(emRad(-90 + i * 60))]);
  const O = V(38), I = V(27), C = V(14);
  const tones = [.5, .25, -.2, -.45, -.25, .2];
  const bevel = O.map((o, i) => `<polygon points="${emPts([o, O[(i + 1) % 6], I[(i + 1) % 6], I[i]])}" fill="${shade(c, tones[i])}"/>`).join("");
  const inner = I.map((o, i) => `<polygon points="${emPts([o, I[(i + 1) % 6], C[(i + 1) % 6], C[i]])}" fill="${shade(c, -tones[i] * .5 - .15)}" opacity=".9"/>`).join("");
  const spokes = I.map(([x, y], i) => `<line x1="${x.toFixed(1)}" y1="${y.toFixed(1)}" x2="${O[i][0].toFixed(1)}" y2="${O[i][1].toFixed(1)}"/>`).join("");
  const corners = lvl >= 3 ? V(42).map(([x, y]) => `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3.4" fill="url(#${id}e)" stroke="#8A5A0B" stroke-width=".8"/><circle cx="${(x - 1).toFixed(1)}" cy="${(y - 1).toFixed(1)}" r="1" fill="#FFFFFF"/>`).join("") : "";
  return `${bevel}${inner}<polygon points="${emPts(C)}" fill="url(#${id}e)" stroke="${shade(c, .5)}" stroke-width="1"/>
    <polygon points="${emPts(C)}" fill="#FFFFFF" opacity=".18"/>
    <g stroke="#FFFFFF" stroke-width=".6" opacity=".4">${spokes}</g>
    <polygon points="${emPts(I)}" fill="none" stroke="${shade(c, .55)}" stroke-width="1" opacity=".7"/>
    ${lvl >= 2 ? `<polygon points="${emPts(V(20))}" fill="none" stroke="${lvl >= 3 ? EM_GOLD : shade(c, .6)}" stroke-width="1.2" stroke-dasharray="2 2.5" opacity=".85"/>` : ""}
    <g class="em-twinkle">${emSparkle(52, 44, 4.5)}</g>${lvl >= 5 ? emSparkle(70, 66, 2.6, .8) : ""}${corners}`;
}
function emLaurel(cy = 58, R = 54) {
  const leaf = "M0 0 C5 -4 5 -10 0 -15 C-5 -10 -5 -4 0 0Z";
  const side = [118, 140, 162, 184].map((d, i) => {
    const x = 60 + R * Math.cos(emRad(d)), y = cy + R * Math.sin(emRad(d));
    return `<path d="${leaf}" transform="translate(${x.toFixed(1)} ${y.toFixed(1)}) rotate(${d + 148}) scale(${1 - i * .06})" fill="${i % 2 ? EM_LEAF_DK : EM_LEAF}"/>`;
  }).join("");
  const a = [60 + R * Math.cos(emRad(108)), cy + R * Math.sin(emRad(108))], b = [60 + R * Math.cos(emRad(194)), cy + R * Math.sin(emRad(194))];
  const g = `<path d="M${a[0].toFixed(1)} ${a[1].toFixed(1)} A${R} ${R} 0 0 1 ${b[0].toFixed(1)} ${b[1].toFixed(1)}" fill="none" stroke="${EM_LEAF_DK}" stroke-width="2" stroke-linecap="round"/>${side}`;
  return `${g}<g transform="translate(120 0) scale(-1 1)">${g}</g>`;
}
function emWings(id, c, lvl) {
  const n = lvl === 4 ? 3 : lvl === 5 ? 4 : 5, k = .9 * (.85 + (lvl - 4) * .12);
  const feather = (i) => { const a = -62 + i * 22, L = (34 - i * 3) * k;
    return `<path d="M0 0 C${-L * .18} ${-L * .3} ${-L * .25} ${-L * .75} ${-L * .05} ${-L} C${L * .12} ${-L * .7} ${L * .12} ${-L * .3} 0 0Z" transform="rotate(${a})" fill="url(#${id}w)" stroke="${shade(c, -.55)}" stroke-width="1"/>`; };
  const one = Array.from({ length: n }, (_, i) => feather(n - 1 - i)).join("");
  return `<g transform="translate(34 50)">${one}</g><g transform="translate(86 50) scale(-1 1)">${one}</g>`;
}
function emPips(id, c, n) {
  // the stage as turned squares (diamonds) just above the hexagon, in the rank's colour: I = 1, II = 2, III = 3
  const rim = n && c, edge = shade(c, -.7);
  const pip = (cx, cy, R) => {
    const T = [cx, cy - R], Rt = [cx + R, cy], B = [cx, cy + R], L = [cx - R, cy], k = .45;
    const t = [cx, cy - R * k], r = [cx + R * k, cy], b = [cx, cy + R * k], l = [cx - R * k, cy];
    return `<polygon points="${emPts([T, Rt, B, L])}" fill="url(#${id}r)" stroke="${edge}" stroke-width="1.2" stroke-linejoin="round"/>
      <polygon points="${emPts([T, Rt, r, t])}" fill="${shade(c, .45)}"/><polygon points="${emPts([Rt, B, b, r])}" fill="${shade(c, -.35)}"/>
      <polygon points="${emPts([B, L, l, b])}" fill="${shade(c, -.5)}"/><polygon points="${emPts([L, T, t, l])}" fill="${shade(c, .2)}"/>
      <polygon points="${emPts([t, r, b, l])}" fill="url(#${id}e)" stroke="${shade(c, .55)}" stroke-width=".6"/>
      ${emSparkle(cx - R * .18, cy - R * .2, R * .22, .9)}`;
  };
  return Array.from({ length: n }, (_, i) => pip(60 + (i - (n - 1) / 2) * 21, -6, 9)).join("");
}
function emTop(id, lvl) {
  if (lvl !== 6) return "";
  return `<g transform="translate(0 4)">
    <path d="M40 4 L37 -16 L49 -6 L60 -22 L71 -6 L83 -16 L80 4 Z" fill="url(#${id}g)" stroke="#8A5A0B" stroke-width="1.4" stroke-linejoin="round"/>
    <rect x="40" y="0" width="40" height="7" rx="2" fill="url(#${id}g)" stroke="#8A5A0B" stroke-width="1.2"/>
    <circle cx="60" cy="-22" r="3.4" fill="#C084FC" stroke="#8A5A0B" stroke-width=".8"/><circle cx="37" cy="-16" r="2.6" fill="#93C5FD"/><circle cx="83" cy="-16" r="2.6" fill="#93C5FD"/>
    <circle cx="60" cy="3.5" r="2.4" fill="#F472B6"/>${emSparkle(54, -10, 4, .9)}</g>`;
}
function emBanner(id, c, text) {
  const y = 100, w = 36, big = text.length > 2;
  return `<path d="M${60 - w} ${y - 4} L${60 - w - 14} ${y - 4} L${60 - w - 8} ${y + 4} L${60 - w - 14} ${y + 12} L${60 - w + 6} ${y + 12} Z" fill="${shade(c, -.6)}"/>
    <path d="M${60 + w} ${y - 4} L${60 + w + 14} ${y - 4} L${60 + w + 8} ${y + 4} L${60 + w + 14} ${y + 12} L${60 + w - 6} ${y + 12} Z" fill="${shade(c, -.6)}"/>
    <path d="M${60 - w} ${y - 9} Q60 ${y - 15} ${60 + w} ${y - 9} L${60 + w} ${y + 9} Q60 ${y + 3} ${60 - w} ${y + 9} Z" fill="url(#${id}b)" stroke="${shade(c, -.75)}" stroke-width="1.3"/>
    <path d="M${60 - w + 2} ${y - 7} Q60 ${y - 13} ${60 + w - 2} ${y - 7}" fill="none" stroke="#FFFFFF" stroke-width="1.2" opacity=".5"/>
    <text x="60" y="${y + 3.5}" text-anchor="middle" font-size="${big ? 14 : 16}" font-weight="800" font-family="'Segoe UI', system-ui, -apple-system, Roboto, sans-serif"
      fill="#FFFFFF" stroke="${shade(c, -.8)}" stroke-width="2" paint-order="stroke">${text}</text>`;
}
function emblem(r, size = 52, bare = false) {
  const rank = r.rank, c = RANK_COLOR[rank], lvl = RANKS.findIndex((x) => x[0] === rank);
  const id = `em${++embN}`, small = size < 30;
  const text = r.div ? ROMAN[r.div] : r.wins ? String(r.wins) : "★";
  const rimDk = shade(lvl >= 3 ? EM_GOLD : c, -.7);
  const studs = lvl >= 1 ? Array.from({ length: 6 }, (_, i) => { const a = emRad(-90 + i * 60);
    return `<circle cx="${(60 + 41 * Math.cos(a)).toFixed(1)}" cy="${(54 + 41 * Math.sin(a)).toFixed(1)}" r="2.4" fill="url(#${id}r)" stroke="${shade(c, -.7)}" stroke-width=".6"/>`; }).join("") : "";
  const plate = `<polygon points="${emHex(46)}" fill="url(#${id}r)" stroke="${rimDk}" stroke-width="2" stroke-linejoin="round"/>
    <polygon points="${emHex(38)}" fill="url(#${id}d)" stroke="${shade(c, -.8)}" stroke-width="1.5" stroke-linejoin="round"/>
    ${small ? "" : studs}<polygon points="${emHex(35)}" fill="none" stroke="${shade(c, .45)}" stroke-width="1" opacity=".45" stroke-linejoin="round"/>`;
  const shine = `<g clip-path="url(#${id}c)"><path d="M14 30 L60 8 L106 30 V40 Q60 26 14 46 Z" fill="#FFFFFF" opacity=".16"/>
    <rect class="em-sweep" x="-60" y="-10" width="22" height="140" fill="#FFFFFF" opacity=".35" transform="skewX(-20)"/></g>`;
  if (small) {
    // in lists: just the plate and the swords, so it stays readable
    return `<svg class="emblem rk-${rank}" style="width:${size}px;height:${size}px" viewBox="10 4 100 100" aria-hidden="true">${emDefs(id, c, lvl)}${plate}${emFace(id, c, lvl)}${shine}</svg>`;
  }
  const glow = lvl >= 4 ? `<polygon points="${emHex(46)}" fill="${shade(c, .2)}" filter="url(#${id}f)" opacity="${lvl === 6 ? .95 : .6}"/>` : "";
  return `<svg class="emblem rk-${rank}" style="width:${size}px;height:${Math.round(size * .94)}px" viewBox="-20 -30 160 150" aria-hidden="true">
    ${emDefs(id, c, lvl)}${glow}${lvl >= 4 ? emWings(id, c, lvl) : ""}${lvl >= 2 ? emLaurel() : ""}
    ${plate}${emFace(id, c, lvl)}${shine}${emTop(id, lvl)}${bare ? (lvl < 6 ? emPips(id, c, 3) : "") : r.div ? emPips(id, c, r.div) : emBanner(id, c, text)}</svg>`;
}
function avatarHtml(c, size = 72) {
  const initial = esc((c.username || "?")[0].toUpperCase());
  const inner = c.bot ? `<span class="bot-face">🤖</span>` : c.photo ? `<img src="${esc(c.photo)}" alt="">` : initial;
  return `<div class="ava f-${esc(c.frame || "none")}" style="--s:${size}px"><div class="in" style="font-size:${Math.round(size * .42)}px">${inner}</div></div>`;
}
// cosmetics (server/cosmetics.py): name styles, entrance effects, victory stickers
const STICKERS = { gg: "GG", fire: "🔥", cool: "😎", crown: "👑", rocket: "🚀", target: "🎯", trophy: "🏆",
  clap: "👏", hundred: "💯", diamond: "💎", mic: "🎤", goat: "🐐", wave: "👋", thumbs: "👍", native: `<span class="st-emo">😌</span><span class="st-word">Native</span>`, shush: "🤫" };
function nameHtml(c, name) {
  const st = (c && c.name_style || "").replace("name_", "");
  return `<span class="uname ${st ? "nm-" + esc(st) : ""}">${esc(name ?? c.username)}</span>`;
}
function stickerHtml(id, cls = "") {
  const k = (id || "").replace("sticker_", "");
  return k ? `<span class="sticker st-${esc(k)} ${cls}">${STICKERS[k] || ""}</span>` : "";
}
function entranceFx(id) {
  const k = (id || "").replace("enter_", "");
  return k ? { cls: `en-${k}`, fx: `<i class="fx fx1"></i><i class="fx fx2"></i><i class="fx fx3"></i>` } : { cls: "", fx: "" };
}
function skillChips(skills) {
  return (skills || []).map((s) => `<span class="skill-chip r-${s.rarity}">${s.icon} ${esc(t("sk_" + s.id))} <b>x${s.count}</b></span>`).join("");
}
function awardName(a) {
  return a.kind === "skill" ? `${t("sk_" + a.id)} x${a.count}` : `${t("ac_" + a.id)} ${achTierLabel(a.id, a.target)}`;
}
function achTierLabel(id, target) {
  if (id === "best_rank") return rankLabel({ rank: RANKS[Math.min(6, Math.floor(target / 300))][0], div: target >= 1800 ? null : 1 });
  return `x${target >= 1000 ? target.toLocaleString() : target}`;
}
function awardToast(list) {
  if ((list || []).length) sfx("sparkle");
  (list || []).forEach((a, i) => setTimeout(() => toast(`${a.icon} ${t(a.kind === "skill" ? "new_skill" : "new_ach", { name: awardName(a) })}`, 3200), i * 3400));
}

// ------------------------------------------------------------------ ranked
async function viewRanked() {
  render(`<div class="splash"><div class="spinner"></div></div>`);
  const d = await api("/api/ranked");
  if (!d.me) return;
  const r = d.me.rank, lim = d.limits;
  const pct = r.next ? Math.round(100 * (r.rp - r.floor) / (r.next - r.floor)) : 100;
  const nextName = r.next ? rankLabel(nextDivision(r)) : null;
  render(`
    <div class="page-head"><h1>${esc(t("ranked_title"))}</h1><span class="tag accent">${esc(t("season_label", { s: d.season_no }))}</span></div>
    <div class="stack">
      <div class="rank-hero" style="--c:${RANK_COLOR[r.rank]}">
        <a class="iconbtn round lb-btn" href="#/leaderboard" aria-label="${esc(t("leaderboard"))}" title="${esc(t("leaderboard"))}">${icon("podium")}</a>
        <div class="row" style="gap:16px"><button class="emb-btn" id="allRanks" aria-label="${esc(t("all_ranks"))}">${emblem(r, 66)}</button>
          <div style="flex:1;min-width:0"><div class="eyebrow">${esc(t("your_rank"))}</div>
            <div class="rank-name">${esc(rankLabel(r))}</div>
            <div class="muted small"><b style="color:var(--text)">${r.rp}</b> ${esc(t("rp"))} · ${esc(r.next ? t("next_div", { n: r.next - r.rp, rank: nextName }) : t("top_rank"))}</div></div></div>
        <div class="bar" style="margin-top:14px;color:${RANK_COLOR[r.rank]}"><i style="width:${pct}%"></i></div>
        <div class="row between hero-foot"><div class="muted small">${esc(t("season_ends", { date: fmtDate(d.season_end) }))}</div>
          ${d.max_rank ? `<div class="max-inline">${emblem(d.max_rank, 30)}<div><span>${esc(t("max_rank"))}</span><b>${esc(rankLabel(d.max_rank))}</b></div></div>` : ""}</div>
      </div>
      ${d.ban_until ? `<div class="card center stack"><h3>${esc(t("ranked_banned"))}</h3><p class="muted small">${esc(t("ranked_banned_sub", { date: fmtDate(d.ban_until * 1000, true) }))}</p></div>`
        : d.live ? `<a class="btn block" href="#/match/${d.live}">${icon("trophy")} ${esc(t("back_to_match"))}</a>`
        : Q.on ? `<a class="btn block big" href="#/match/search"><span class="q-dot"></span> ${esc(t("searching_short"))}</a>`
        : lim.left > 0 && langSwitch() ? `<div class="stack" style="gap:8px">${langSwitch()}<a class="btn block big" href="#/match/search">${icon("trophy")} ${esc(t("find_match"))}</a></div>`
        : lim.left > 0 ? `<a class="btn block big" href="#/match/search">${icon("trophy")} ${esc(t("find_match"))}</a>`
        : `<div class="card center stack"><h3>${esc(t("no_matches_left"))}</h3><p class="muted small">${esc(t("no_matches_left_sub"))}</p>
            ${S.me.plan !== "pro" ? `<a class="btn small" href="#/plans">${icon("spark")} ${esc(t("upgrade"))}</a>` : ""}</div>`}
      <p class="muted center small">${esc(t("matches_left", { n: lim.left, total: lim.per_day }))}</p>
      <details class="acc"><summary>${esc(t("how_it_works"))}</summary><div class="acc-body">
        <ol class="rules">${[1, 2, 3, 4, 5].map((i) => `<li>${esc(t("rule_" + i))}</li>`).join("")}<li>${esc(t("ranked_limits"))}</li></ol></div></details>
      <div class="card"><div class="card-title">${esc(t("recent_matches"))}</div>
        ${d.history.length ? d.history.map((h) => `
          <div class="hist" onclick="location.hash='#/match/${h.id}'">
            <div class="score res-${h.result}" title="${esc(t("res_" + h.result))}">${{ win: "✓", loss: "✕", draw: "=" }[h.result] || "–"}</div>
            <div class="meta"><div class="t">${esc(h.opp_name)}${h.kind === "friendly" ? ` <span class="tag accent">${esc(t("friendly_tag"))}</span>` : ""}</div>
              <div class="s">${h.me ?? "–"} : ${h.opp ?? "–"} · ${esc(fmtDate(h.created * 1000, true))}</div></div>
            <b class="${(h.rp_delta || 0) >= 0 ? "good" : "bad"}">${h.rp_delta == null ? "" : (h.rp_delta > 0 ? "+" : "") + h.rp_delta}</b>
          </div>`).join("") : `<p class="empty">${esc(t("no_matches"))}</p>`}
      </div>
    </div>`);
  $("#allRanks").onclick = () => openRanks(r.rank);
  bindLangSwitch(viewRanked);
}

function maxRankBox(mr) {
  // the highest rank ever reached, as a smaller emblem beside the current one
  return mr ? `<div class="max-rank" title="${esc(t("max_rank"))}: ${esc(rankLabel(mr))}">${emblem(mr, 40)}
    <span>${esc(t("max_rank"))}</span><b>${esc(rankLabel(mr))}</b></div>` : "";
}
function openRanks(mine) {
  // every rank with its main emblem (no stage marks) and RP range; the player's own rank is highlighted
  const sheet = document.createElement("div");
  sheet.className = "sheet-wrap";
  const rows = RANKS.map(([k], i) => {
    const from = i * 300, range = k === "master" ? `${from}+ ${t("rp")}` : `${from}–${from + 299} ${t("rp")}`;
    return `<div class="rank-row ${mine === k ? "on" : ""}" style="--c:${RANK_COLOR[k]}">${emblem({ rank: k }, 64, true)}
      <div class="grow"><b>${esc(t("rank_" + k))}</b><div class="muted small">${range}</div></div>
      ${mine === k ? `<span class="tag accent">${esc(t("your_rank"))}</span>` : ""}</div>`;
  }).reverse().join("");
  sheet.innerHTML = `<div class="sheet" role="dialog" aria-modal="true">
    <div class="row between" style="margin-bottom:12px"><h2>${esc(t("all_ranks"))}</h2><button class="iconbtn" id="closeSheet" aria-label="${esc(t("back"))}">✕</button></div>
    <div class="stack">${rows}</div></div>`;
  document.body.appendChild(sheet);
  const close = () => sheet.remove();
  sheet.onclick = (e) => { if (e.target === sheet) close(); };
  sheet.querySelector("#closeSheet").onclick = close;
  leaveHooks.push(close);
}
let lbScope = store("sc-lb") || "national";
async function viewLeaderboard() {
  render(`<div class="splash"><div class="spinner"></div></div>`);
  const d = await api(`/api/ranked/leaderboard?scope=${lbScope}`);
  if (!d.board) return;
  const meRow = d.me_place ? `<div class="board-row me"><span class="pos">${d.me_place}</span>${avatarHtml(d.me, 40)}
    <span class="nm">${d.country ? flag(d.country) + " " : ""}${nameHtml(d.me, S.me.username)}</span>${emblem(d.me.rank, 22)}<span class="muted small">${d.me.rank.rp}</span></div>` : "";
  render(`
    <div class="page-head">${backBtn("#/ranked")}<span class="tag accent">${esc(t("season_label", { s: d.season_no }))}</span></div>
    <h1 style="margin-bottom:16px">${esc(t("leaderboard"))}</h1>
    <div class="stack">
      <div class="seg" id="lbSeg"><button data-v="national" class="${lbScope === "national" ? "on" : ""}">${d.country ? flag(d.country) : "🏳️"} ${esc(d.country ? countryName(d.country) : t("lb_national"))}</button>
        <button data-v="global" class="${lbScope === "global" ? "on" : ""}">🌍 ${esc(t("lb_global"))}</button></div>
      ${meRow ? `<div class="card"><div class="card-title">${esc(t("your_place"))}</div>${meRow}</div>` : ""}
      <div class="card">
        ${lbScope === "national" && !d.country ? `<p class="empty"><a href="#/profile">${esc(t("set_country"))}</a></p>`
          : d.board.length ? d.board.map((b, i) => `
          <a class="board-row ${b.me ? "me" : ""}" href="#/u/${encodeURIComponent(b.username)}">
            <span class="pos ${i < 3 ? "top" + (i + 1) : ""}">${i + 1}</span>${avatarHtml(b, 40)}
            <span class="nm">${b.country ? flag(b.country) + " " : ""}${nameHtml(b)}</span>${emblem(b.rank, 22)}<span class="muted small">${b.rank.rp}</span></a>`).join("")
          : `<p class="empty">${esc(t("no_matches"))}</p>`}
      </div>
    </div>`);
  $$("#lbSeg button").forEach((b) => b.onclick = () => { lbScope = b.dataset.v; store("sc-lb", lbScope); viewLeaderboard(); });
}
function nextDivision(r) {
  const rp = r.next;
  if (rp >= 1800) return { rank: "master", div: null };
  const index = Math.floor(rp / 300), step = Math.floor((rp % 300) / 100);
  return { rank: RANKS[index][0], div: step + 1 };
}

// ------------------------------------------------------------------ ranked match
const rk = { stream: null, recorder: null, chunks: [], loop: null, poll: null, keep: false, sent: false, offset: 0 };
function rkStop(all) {
  clearInterval(rk.loop); clearInterval(rk.poll); rk.loop = rk.poll = null;
  if (rk.recorder && rk.recorder.state !== "inactive") { rk.recorder.onstop = null; rk.recorder.stop(); }
  rk.recorder = null;
  if (all && rk.stream) { rk.stream.getTracks().forEach((x) => x.stop()); rk.stream = null; }
}
async function rkMic() {
  if (rk.stream && rk.stream.getTracks().some((x) => x.readyState === "live")) return true;
  try {
    rk.stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
    return true;
  } catch (e) { return false; }
}
function viewMatch(arg) {
  leaveHooks.push(() => { rkStop(!(rk.keep || Q.on)); rk.keep = false; });
  return arg === "search" ? matchSearch() : matchPlay(arg);
}

// ranked queue: keeps searching while the player uses the rest of the app
const Q = { on: false, started: 0, poll: null, tick: null };
function queueStop() {
  Q.on = false; clearInterval(Q.poll); clearInterval(Q.tick); Q.poll = Q.tick = null;
  document.getElementById("qPill")?.remove();
}
async function queueLeave() {
  queueStop();
  await api("/api/ranked/leave", {});
  if (S.view !== "match") rkStop(true);
}
function queueRun(waited = 0) {
  Q.on = true; Q.started = Date.now() - waited * 1000;
  clearInterval(Q.poll); clearInterval(Q.tick);
  Q.tick = setInterval(queueDraw, 500);
  Q.poll = setInterval(async () => {
    const st = await api("/api/ranked/queue");
    if (!Q.on) return;
    if (st.state === "found") {
      queueStop(); rk.keep = true; sfx("found");
      if (navigator.vibrate) navigator.vibrate([120, 60, 120]);
      if (S.view !== "match") toast(t("match_found"));
      go(`#/match/${st.match}`);
    } else if (st.state === "idle" || st.state === "limit") {
      queueStop();
      if (S.view === "match") go("#/ranked");
    }
  }, 1500);
  queueDraw();
}
function queueDraw() {
  const time = mmss((Date.now() - Q.started) / 1000);
  const w = document.getElementById("waited");
  if (w) w.textContent = time;
  let pill = document.getElementById("qPill");
  const show = Q.on && S.view !== "match";
  if (!show) { pill?.remove(); return; }
  if (!pill) {
    pill = document.createElement("div");
    pill.id = "qPill"; pill.className = "q-pill";
    pill.innerHTML = `<button class="q-main" id="qOpen"><span class="q-dot"></span><span>${esc(t("searching_short"))}</span><b id="qTime"></b></button>
      <button class="iconbtn" id="qX" aria-label="${esc(t("cancel"))}">✕</button>`;
    document.body.appendChild(pill);
    pill.querySelector("#qOpen").onclick = () => go("#/match/search");
    pill.querySelector("#qX").onclick = () => queueLeave();
  }
  pill.querySelector("#qTime").textContent = time;
}

async function matchSearch() {
  const page = () => {
    render(`
      <div class="card analysing search">
        <div class="radar-ping"><span></span><span></span>${avatarHtml(S.me.card, 72)}</div>
        <h2>${esc(t("searching"))}</h2>
        <p class="timer" id="waited" style="margin-top:14px">0:00</p>
        <div class="row center" style="gap:10px;margin-top:8px">
          <a class="btn" href="#/home">${esc(t("search_in_bg"))}</a>
          <button class="btn outline" id="cancel">${esc(t("cancel"))}</button></div>
      </div>`);
    $("#cancel").onclick = async () => { await queueLeave(); go("#/ranked"); };
    queueDraw();
  };
  if (Q.on) return page();
  render(`<div class="card analysing"><div class="spinner"></div><h2>${esc(t("mic_check"))}</h2></div>`);
  if (!(await rkMic())) {
    render(`<div class="card center stack" style="padding:28px"><h2>${esc(t("mic_denied"))}</h2>
      <a class="btn" href="#/ranked">${esc(t("back_ranked"))}</a></div>`);
    return;
  }
  const first = await api("/api/ranked/queue", {});
  if (first.state === "found") { rk.keep = true; return go(`#/match/${first.match}`); }
  if (first.state !== "searching") { go("#/ranked"); return; }
  queueRun(first.waited || 0);
  page();
}
async function queueRestore() {
  const st = await api("/api/ranked/queue");
  if (st.state === "searching") queueRun(st.waited || 0);
  else if (st.state === "found" && S.view !== "match") { toast(t("match_found")); go(`#/match/${st.match}`); }
}

function playerCol(p, big, win) {
  const tags = [p.bot ? t("bot_tag") : ""].filter(Boolean);
  const link = !p.bot && !p.me && p.username !== "—" ? `href="#/u/${encodeURIComponent(p.username)}"` : "";
  const en = big ? entranceFx(p.entrance) : { cls: "", fx: "" };
  return `<a class="pcol ${p.me ? "me" : ""} ${en.cls}" data-slot="${p.slot}" ${link}>
    <div class="pava">${en.fx}${avatarHtml(p, big ? 84 : 64)}${win && p.result === "win" ? stickerHtml(p.sticker, "pop") : ""}</div>
    <div class="pname">${p.country ? flag(p.country) + " " : ""}${nameHtml(p, p.me ? S.me.username : p.username)}</div>
    <div class="prank">${emblem(p.rank, 18)}<span>${esc(rankLabel(p.rank))}</span></div>
    ${tags.length ? `<div>${tags.map((x) => `<span class="tag">${esc(x)}</span>`).join(" ")}</div>` : ""}
    ${p.skills && p.skills.length ? `<div class="pskills">${p.skills.map((s) => `<span class="r-${s.rarity}" title="${esc(t("sk_" + s.id))} x${s.count}">${s.icon}<b>${s.count}</b></span>`).join("")}</div>` : ""}
  </a>`;
}

async function matchPlay(id) {
  let m = await api(`/api/ranked/match/${id}`);
  if (!m.id) { render(`<div class="card empty">404</div>`); return; }
  if (m.status === "done") return matchResult(m);
  rk.offset = m.now * 1000 - Date.now();
  const now = () => (Date.now() + rk.offset) / 1000;
  if (m.my_state !== "waiting") return matchWaiting(id);
  const tooLate = now() > m.speak_at + m.max_s - m.min_s;
  if (tooLate) return matchWaiting(id);
  if (!(await rkMic())) {
    render(`<div class="card center stack" style="padding:28px"><h2>${esc(t("mic_denied"))}</h2><p class="muted">${esc(t("leave_warning"))}</p></div>`);
    return;
  }
  const me = m.players.find((p) => p.me), opp = m.players.find((p) => !p.me);
  let phase = "";
  rk.sent = false;

  function drawVs() {
    render(`<div class="match">
      <div class="vs-row">${playerCol(me, true)}<div class="vs">${esc(t("vs"))}</div>${playerCol(opp, true)}</div>
      <h2 class="center" style="margin-top:22px">${esc(t("opponent_found"))}</h2>
      <div class="count" id="count"></div>
      <p class="muted center small">${esc(t("dont_leave"))}</p></div>`);
  }
  async function drawQuestion() {
    if (!m.question) m = await api(`/api/ranked/match/${id}`);
    render(`<div class="match">
      <div class="mini-vs">${avatarHtml(me, 34)}<span class="muted small">${esc(t("vs"))}</span>${avatarHtml(opp, 34)}</div>
      <div class="hero"><div class="eyebrow">${esc(t("read_question"))}</div><div class="q" style="margin-bottom:0">${esc(m.question || "…")}</div></div>
      <div class="count" id="count"></div><p class="center muted">${esc(t("get_ready"))}</p></div>`);
  }
  function drawSpeak() {
    render(`<div class="match">
      <div class="mini-vs">${avatarHtml(me, 34)}<span class="muted small">${esc(t("vs"))}</span>${avatarHtml(opp, 34)}
        <span class="muted small" style="margin-left:auto">${esc(opp.bot || opp.ghost ? "" : t("opp_speaking"))}</span></div>
      <div class="card"><div class="card-title">${esc(t("question"))}</div><p style="font-weight:650">${esc(m.question || "")}</p></div>
      <div class="card recorder">
        <div class="timer" id="timer"><span class="pulse"></span>0:00 <small>/ ${mmss(m.max_s)}</small></div>
        <div class="progress-line" style="width:100%"><i id="spBar"></i></div>
        <p class="muted small center" id="spHint"></p>
        <button class="btn block" id="stopBtn" disabled>${icon("stop")} ${esc(t("stop_send"))}</button>
      </div>
      <p class="muted center small">${esc(t("dont_leave"))}</p></div>`);
    $("#stopBtn").onclick = () => { if (rk.recorder && rk.recorder.state === "recording") rk.recorder.stop(); };
  }
  function startRecording() {
    const mime = pickMime(false);
    rk.recorder = new MediaRecorder(rk.stream, mime ? { mimeType: mime, audioBitsPerSecond: 64000 } : undefined);
    rk.chunks = [];
    rk.recStart = Date.now();
    rk.recorder.ondataavailable = (e) => { if (e.data.size) rk.chunks.push(e.data); };
    rk.recorder.onstop = () => {
      const type = (rk.recorder && rk.recorder.mimeType) || mime || "audio/webm";
      sendAnswer(new Blob(rk.chunks, { type }), `answer.${extFor(type)}`);
    };
    rk.recorder.start(1000);
  }
  async function sendAnswer(blob, name) {
    if (rk.sent) return;
    rk.sent = true;
    clearInterval(rk.loop);
    rk.recorder = null;
    render(`<div class="card analysing"><div class="spinner"></div><h2>${esc(t("sending"))}</h2></div>`);
    const fd = new FormData();
    fd.append("file", blob, name);
    let res = {};
    try {
      const r = await fetch(`/api/ranked/match/${id}/answer`, { method: "POST", body: fd, headers: { "X-SC": "1" }, credentials: "same-origin" });
      res = await r.json().catch(() => ({}));
    } catch (e) { res = { error: "err_network" }; }
    if (res.error) toast(errText(res));
    matchWaiting(id);
  }

  rk.loop = setInterval(() => {
    const n = now();
    if (n < m.reveal_at) {
      if (phase !== "vs") {
        phase = "vs"; drawVs(); rk.mySlot = me.slot; rk.lastTick = null; sfx("found");
        emoteBar(id).then((bar) => { if (phase === "vs") app.querySelector(".match").appendChild(bar); });
        const ep = setInterval(async () => {
          if (phase !== "vs") { clearInterval(ep); return; }
          const mm = await api(`/api/ranked/match/${id}`);
          if (mm.id && phase === "vs") emotesFrom(mm);
        }, 1200);
      }
      const el = document.getElementById("count"); if (el) el.textContent = Math.ceil(m.reveal_at - n);
    } else if (n < m.speak_at) {
      if (phase !== "q") { phase = "q"; drawQuestion(); }
      const left = Math.ceil(m.speak_at - n);
      if (left <= 3 && left !== rk.lastTick) { rk.lastTick = left; sfx("tick"); }   // 3-2-1 before speaking
      const el = document.getElementById("count"); if (el) el.textContent = left;
    } else {
      if (phase !== "speak") { phase = "speak"; drawSpeak(); startRecording(); }
      const s = (Date.now() - rk.recStart) / 1000;
      const left = m.speak_at + m.max_s - n;               // the match clock, not the button
      const el = document.getElementById("timer");
      if (el) el.innerHTML = `<span class="pulse"></span>${mmss(s)} <small>/ ${mmss(m.max_s)}</small>`;
      const bar = document.getElementById("spBar"); if (bar) bar.style.width = `${Math.min(100, 100 * s / m.max_s)}%`;
      const hint = document.getElementById("spHint"), btn = document.getElementById("stopBtn");
      if (s < m.min_s) { if (hint) hint.textContent = t("speak_min", { s: Math.ceil(m.min_s - s) }); }
      else { if (btn) btn.disabled = false; if (hint) hint.textContent = t("speak_can_stop", { max: mmss(m.max_s) }); }
      if ((s >= m.max_s || left <= 0) && rk.recorder && rk.recorder.state === "recording") rk.recorder.stop();
    }
  }, 200);
}

// stickers during a match: a bar of the player's stickers; sent ones pop over the sender's picture for both players
let myEmotes = null;
async function emoteList() {
  if (!myEmotes) {
    const d = await api("/api/cosmetics");
    myEmotes = ["sticker_wave", "sticker_thumbs", ...(d.items || []).filter((i) => i.kind === "sticker" && i.owned).map((i) => i.id)];
  }
  return myEmotes;
}
async function emoteBar(matchId) {
  const list = await emoteList();
  const bar = document.createElement("div");
  bar.className = "emote-bar";
  bar.innerHTML = list.map((s) => `<button data-emote="${s}" aria-label="${s}">${stickerHtml(s)}</button>`).join("");
  bar.querySelectorAll("[data-emote]").forEach((b) => b.onclick = async () => {
    bar.classList.add("cool");
    setTimeout(() => bar.classList.remove("cool"), 2500);
    const r = await api(`/api/ranked/match/${matchId}/emote`, { sticker: b.dataset.emote });
    if (r.ok) emoteShow(rk.mySlot, b.dataset.emote);
  });
  return bar;
}
const seenEmotes = new Set();
function emoteShow(slot, sticker) {
  const host = app.querySelector(`[data-slot="${slot}"] .pava, [data-slot="${slot}"].mini-ava`);
  if (!host) return;
  const el = document.createElement("span");
  el.className = "emote-pop"; sfx("pop");
  el.innerHTML = stickerHtml(sticker);
  host.appendChild(el);
  setTimeout(() => el.remove(), 2600);
}
function emotesFrom(m) {
  (m.emotes || []).forEach((e) => {
    const key = `${m.id}:${e.slot}:${e.at}`;
    if (seenEmotes.has(key)) return;
    seenEmotes.add(key);
    if (e.slot !== rk.mySlot) emoteShow(e.slot, e.sticker);
  });
}
async function matchWaiting(id) {
  rkStop(true);
  const oppText = (m) => { const opp = m.players.find((p) => !p.me);
    return `${opp.username}: ${t("opp_" + (opp.state === "speaking" ? "speaking" : opp.state === "scoring" ? "scoring" : "ready"))}`; };
  let m = await api(`/api/ranked/match/${id}`);
  if (m.status === "done") return matchResult(m);
  const me = m.players.find((p) => p.me), opp = m.players.find((p) => !p.me);
  rk.mySlot = me.slot;
  render(`<div class="card analysing">
      <div class="row center" style="gap:28px;margin-bottom:14px">
        <div class="mini-ava" data-slot="${me.slot}">${avatarHtml(me, 52)}</div><span class="muted small">${esc(t("vs"))}</span>
        <div class="mini-ava" data-slot="${opp.slot}">${avatarHtml(opp, 52)}</div></div>
      <div class="spinner"></div><h2>${esc(t("scoring"))}</h2>
      <p class="muted" style="margin-top:8px">${esc(t("scoring_sub"))}</p>
      <p class="muted small" id="oppState" style="margin-top:14px">${esc(oppText(m))}</p>
    </div>`);
  app.querySelector(".analysing").appendChild(await emoteBar(id));
  emotesFrom(m);
  rk.poll = setInterval(async () => {
    m = await api(`/api/ranked/match/${id}`);
    if (!m.id) return;
    if (m.status === "done") { clearInterval(rk.poll); matchResult(m); fillIcons(app); return; }
    const st = document.getElementById("oppState");
    if (st) st.textContent = oppText(m);
    emotesFrom(m);
  }, 1500);
}

function matchResult(m) {
  const me = m.players.find((p) => p.me), opp = m.players.find((p) => !p.me);
  const res = me.result || "none";
  const scoreCell = (p) => p.overall != null ? `<b class="big-score ${cls(p.overall)}">${p.overall}</b>${p.integrity === "cheat" ? `<div><span class="tag bad-tag">${esc(t("not_own_words"))}</span></div>`
      : p.off_topic ? `<div><span class="tag bad-tag">${esc(t(p.topic === "repeated" ? "repeated" : "off_topic"))}</span></div>` : ""}`
    : `<b class="big-score muted">–</b><div class="muted small">${esc(t(p.error || "ranked_missed", { n: p.error_n }))}</div>`;
  const bars = SECTIONS.map((s) => {
    const a = me.scores ? me.scores[s] : 0, b = opp.scores ? opp.scores[s] : 0;
    return `<div class="cmp"><span class="${a >= b ? "lead" : ""}">${me.scores ? a : "–"}</span>
      <div class="cmp-bars"><i class="l" style="width:${a / 2}%"></i><i class="r" style="width:${b / 2}%"></i></div>
      <span class="${b > a ? "lead" : ""}">${opp.scores ? b : "–"}</span><div class="cmp-name">${esc(t("sec_" + s))}</div></div>`;
  }).join("");
  const delta = me.rp_delta;
  if (!m._sounded) {
    m._sounded = true;
    const up = me.rank_after && RANKS.findIndex((x) => x[0] === me.rank_after.rank) > RANKS.findIndex((x) => x[0] === me.rank.rank);
    sfx(up ? "rankup" : res === "win" ? "win" : res === "loss" ? "loss" : "draw");
  }
  render(`<div class="match stack">
    <div class="result-banner res-${res}">${esc(t(res === "none" ? "no_contest" : "result_" + res))}</div>
    ${m.kind === "friendly" ? `<div class="notice small">${esc(t("friendly_note"))}</div>` : m.kind === "bot" ? `<div class="notice small">${esc(t("match_note_bot"))}</div>` : ""}
    <div class="vs-row">
      <div class="stack center">${playerCol(me, false, true)}${scoreCell(me)}</div>
      <div class="vs">${esc(t("vs"))}</div>
      <div class="stack center">${playerCol(opp, false, true)}${scoreCell(opp)}
        ${opp.audio ? `<audio class="opp-audio" src="/api/ranked/match/${m.id}/audio?slot=${opp.slot}" controls preload="none"></audio>` : ""}</div>
    </div>
    <div class="card"><div class="card-title">${esc(t("question"))}</div><p>${esc(m.question || "")}</p>
      ${me.audio ? `<audio src="/api/ranked/match/${m.id}/audio" controls preload="none"></audio>` : ""}</div>
    ${me.scores || opp.scores ? `<div class="card">${bars}</div>` : ""}
    ${delta != null ? `<div class="card row between">
        <div class="row">${emblem(me.rank_after, 40)}<div><div class="lab" style="font-weight:700">${esc(rankLabel(me.rank_after))}</div>
          <div class="muted small">${me.rp_after} ${esc(t("rp"))}</div></div></div>
        <div class="stack center" style="gap:4px"><b class="${delta >= 0 ? "good" : "bad"}" style="font-size:24px">${delta > 0 ? "+" : ""}${delta} ${esc(t("rp"))}</b>
          ${me.shield ? `<span class="tag accent">${icon("shield")} ${esc(t("shield_used"))}</span>` : ""}</div></div>` : ""}
    ${me.profanity_warn ? `<div class="notice warn">${esc(t("profanity_warn"))}</div>` : ""}
    ${opp.can_report ? `<div class="card row between" style="gap:10px"><span class="small">${esc(t("report_ask", { name: opp.username }))}</span>
      <button class="btn small danger" id="reportBtn">${esc(t("report"))}</button></div>` : ""}
    ${(me.new_awards || []).length ? `<div class="card"><div class="card-title">${esc(t("unlocked"))}</div>
      ${me.new_awards.map((a) => `<div class="award-new"><span class="hexicon sm r-${a.rarity}">${a.icon}</span> <b>${esc(awardName(a))}</b> <span class="tag">${esc(t(a.kind === "skill" ? "tab_skills" : "tab_achievements"))}</span></div>`).join("")}</div>` : ""}
    <a class="btn block" href="#/match/search">${icon("trophy")} ${esc(t("play_again"))}</a>
    <a class="btn block ghost" href="#/ranked">${esc(t("back_ranked"))}</a>
  </div>`);
  if (!m._toasted) { m._toasted = true; awardToast(me.new_awards); }
  const rb = document.getElementById("reportBtn");
  if (rb) rb.onclick = async () => {
    rb.disabled = true;
    const r = await api(`/api/ranked/match/${m.id}/report`, {});
    toast(r.ok ? t("reported") : errText(r));
    rb.closest(".card").remove();
  };
}

// ------------------------------------------------------------------ statistics (profile)
function radarChart(v) {
  const keys = ["fluency", "grammar", "vocabulary", "pronunciation", "consistency"];
  const labels = [t("sec_fluency"), t("sec_grammar"), t("sec_vocabulary"), t("sec_pronunciation"), t("ax_consistency")];
  const W = 360, H = 300, cx = 180, cy = 156, R = 112;
  const pt = (i, f) => { const a = -Math.PI / 2 + i * 2 * Math.PI / keys.length; return [cx + R * f * Math.cos(a), cy + R * f * Math.sin(a)]; };
  let svg = `<svg class="radar" viewBox="-95 -6 ${W + 190} ${H + 12}" role="img"><defs><radialGradient id="radarFill"><stop offset="0" stop-color="#8A5CF6" stop-opacity=".75"/><stop offset="1" stop-color="#3574F0" stop-opacity=".45"/></radialGradient></defs>`;
  for (const f of [1, 2 / 3, 1 / 3]) svg += `<polygon class="rgrid" points="${keys.map((_, i) => pt(i, f).join(",")).join(" ")}"/>`;
  keys.forEach((_, i) => { const [x, y] = pt(i, 1); svg += `<line class="rgrid" x1="${cx}" y1="${cy}" x2="${x}" y2="${y}"/>`; });
  const poly = keys.map((k, i) => pt(i, Math.max(0.04, (v[k] || 0) / 100)).join(",")).join(" ");
  svg += `<polygon class="rarea" points="${poly}"/>`;
  keys.forEach((k, i) => { const [x, y] = pt(i, Math.max(0.04, (v[k] || 0) / 100)); svg += `<circle cx="${x}" cy="${y}" r="3.5" class="rdot"/>`; });
  keys.forEach((k, i) => {
    // the number sits right next to its corner of the web, the name a little further out
    const [nx, ny] = pt(i, 1.12), [lx, ly] = pt(i, 1.36);
    const anchor = Math.abs(lx - cx) < 8 ? "middle" : lx > cx ? "start" : "end";
    svg += `<text x="${nx}" y="${ny + 4}" text-anchor="middle" class="rval">${v[k] || 0}</text><text x="${lx}" y="${ly + 4}" text-anchor="${anchor}">${esc(labels[i])}</text>`;
  });
  return svg + "</svg>";
}
function circleStat(value, label, color) {
  return `<div class="cstat" style="--c:${color}"><b>${esc(value)}</b><span>${esc(label)}</span></div>`;
}
function statsBlock(s) {
  if (!s.matches) return `<p class="empty">${esc(t("stats_empty"))}</p>`;
  const rows = [
    ["st_wins", s.wins], ["st_losses", s.losses], ["st_draws", s.draws], ["st_longest_streak", s.longest_streak],
    ["st_current_streak", s.current_streak > 0 ? `${s.current_streak} ${t("res_win")}` : s.current_streak < 0 ? `${-s.current_streak} ${t("res_loss")}` : "0"],
    ["st_average", s.average], ["st_perfect", s.perfect], ["st_top_score", s.top_score],
  ];
  const pair = s.max_rank ? `<div class="rank-pair">
      <div class="rp-cur">${emblem(s.cur_rank, 54)}<span>${esc(t("your_rank"))}</span><b>${esc(rankLabel(s.cur_rank))}</b></div>
      ${maxRankBox(s.max_rank)}</div>` : "";
  return `${pair}
    <div class="cstats">${circleStat(s.matches, t("st_matches"), "#D65DB1")}${circleStat(`${s.win_rate}%`, t("st_win_rate"), "#E5B84C")}${circleStat(mmss(s.talk_time || 0), t("st_talk_time"), "#5FB865")}</div>
    <div class="stat-list">${rows.map(([k, v]) => `<div><span>${esc(t(k))}</span><b>${esc(v)}</b></div>`).join("")}</div>
    ${radarChart(s.radar)}`;
}

// ------------------------------------------------------------------ public profile
async function viewUser(name) {
  render(`<div class="splash"><div class="spinner"></div></div>`);
  const d = await api(`/api/users/${encodeURIComponent(decodeURIComponent(name || ""))}`);
  if (!d.card) { render(`<div class="card empty">404</div>`); return; }
  const c = d.card;
  render(`
    <div class="page-head">${backBtn("#/ranked")}</div>
    <div class="stack-lg">
      <div class="player-card" style="--c:${RANK_COLOR[c.rank.rank]}">
        ${avatarHtml(c, 92)}
        <div style="min-width:0;flex:1"><h2>${c.country ? `<span class="flag">${flag(c.country)}</span>` : ""}${nameHtml(c)}</h2>
          ${c.display_name ? `<div class="muted small real-name">${esc(c.display_name)}</div>` : ""}
          <div class="prank">${emblem(c.rank, 20)}<span>${esc(rankLabel(c.rank))} · ${c.rank.rp} ${esc(t("rp"))}</span></div>
          <div class="muted small">${esc(t("best_rank"))}: ${esc(rankLabel(d.best_rank))}</div>
          <div class="skills-row">${skillChips(c.skills)}</div></div>
      </div>
      ${d.me ? "" : `<div class="row" id="relBtns">${relationButtons(c.username, d.relation)}</div>`}
      <div class="grid2"><div class="stat"><b>${d.skills_earned}</b><span>${esc(t("tab_skills"))}</span></div>
        <div class="stat"><b>${d.achs_earned}</b><span>${esc(t("tab_achievements"))}</span></div></div>
      <div class="card"><div class="card-title">${esc(t("current_season"))}</div>${statsBlock(d.stats)}</div>
    </div>`);
  bindFriendButtons(app, () => viewUser(name));
}

// ------------------------------------------------------------------ friends
function relationButtons(name, rel) {
  const n = esc(name);
  if (rel === "friend") return `<button class="btn small" data-challenge="${n}">${icon("trophy")} ${esc(t("challenge"))}</button>
    <button class="btn small ghost" data-remove="${n}">${esc(t("remove_friend"))}</button>`;
  if (rel === "received") return `<button class="btn small" data-accept="${n}">${esc(t("accept"))}</button>
    <button class="btn small ghost" data-decline="${n}">${esc(t("decline"))}</button>`;
  if (rel === "sent") return `<button class="btn small ghost" data-remove="${n}">${esc(t("request_sent"))} ✕</button>`;
  return `<button class="btn small" data-add="${n}">${icon("users")} ${esc(t("add_friend"))}</button>`;
}
function bindFriendButtons(root, redraw) {
  const act = async (path, body) => { const r = await api(path, body); if (!r.ok) toast(errText(r)); return r; };
  root.querySelectorAll("[data-add]").forEach((b) => b.onclick = async () => { b.disabled = true; if ((await act("/api/friends/request", { username: b.dataset.add })).ok) toast(t("request_sent")); redraw(); });
  root.querySelectorAll("[data-accept]").forEach((b) => b.onclick = async () => { b.disabled = true; await act("/api/friends/respond", { username: b.dataset.accept, accept: true }); redraw(); });
  root.querySelectorAll("[data-decline]").forEach((b) => b.onclick = async () => { b.disabled = true; await act("/api/friends/respond", { username: b.dataset.decline, accept: false }); redraw(); });
  root.querySelectorAll("[data-remove]").forEach((b) => b.onclick = async () => {
    if (b.dataset.confirm !== "1" && !b.textContent.includes("✕")) { b.dataset.confirm = "1"; b.textContent = t("remove_confirm"); return; }
    await act("/api/friends/remove", { username: b.dataset.remove }); redraw();
  });
  root.querySelectorAll("[data-challenge]").forEach((b) => b.onclick = async () => {
    b.disabled = true;
    const r = await act("/api/friends/challenge", { username: b.dataset.challenge });
    if (r.ok) go(`#/challenge/${r.challenge}`); else b.disabled = false;
  });
}
function friendStatus(act) {
  const shown = ["match", "mock", "record", "queue"].includes(act) ? act : "online";
  const busy = shown === "record" || shown === "queue";            // yellow: can't play right now
  return `<span class="fr-act ${busy ? "busy" : ""}">● ${esc(t("act_" + shown))}</span>`;
}
function friendRow(c, buttons) {
  return `<div class="friend-row">
    <a href="#/u/${encodeURIComponent(c.username)}" class="fr-ava">${avatarHtml(c, 46)}${c.online ? `<i class="dot-online" title="${esc(t("online"))}"></i>` : ""}</a>
    <a href="#/u/${encodeURIComponent(c.username)}" class="fr-main"><b>${c.country ? flag(c.country) + " " : ""}${nameHtml(c)}</b>
      <span class="prank">${emblem(c.rank, 16)}<span>${esc(rankLabel(c.rank))} · ${c.rank.rp}</span></span>
      ${c.online && c.activity ? friendStatus(c.activity) : ""}</a>
    <div class="fr-btns">${buttons}</div></div>`;
}
async function viewFriends() {
  render(`<div class="splash"><div class="spinner"></div></div>`);
  const d = await api("/api/friends");
  if (!d.friends) return;
  render(`
    <div class="page-head"><h1>${esc(t("friends"))}</h1><span class="tag accent">${d.friends.length}</span></div>
    <div class="stack">
      <div class="search-box">${icon("search")}<input class="input" id="q" placeholder="${esc(t("search_players"))}" autocomplete="off" autocapitalize="off" spellcheck="false"></div>
      <div id="results"></div>
      ${d.challenges.length ? `<div class="card"><div class="card-title">${esc(t("challenges_in"))}</div>
        ${d.challenges.map((ch) => friendRow(ch.from, `<button class="btn small" data-chacc="${ch.id}">${esc(t("accept"))}</button><button class="btn small ghost" data-chdec="${ch.id}">✕</button>`)).join("")}</div>` : ""}
      ${d.incoming.length ? `<div class="card"><div class="card-title">${esc(t("friend_requests"))}</div>
        ${d.incoming.map((c) => friendRow(c, relationButtons(c.username, "received"))).join("")}</div>` : ""}
      <div class="card"><div class="card-title">${esc(t("your_friends"))}</div>
        ${d.friends.length ? d.friends.map((c) => friendRow(c, c.online && !["match", "mock", "record", "queue"].includes(c.activity)
            ? `<button class="btn small" data-challenge="${esc(c.username)}">${icon("trophy")}</button>` : "")).join("")
          : `<p class="empty">${esc(t("no_friends"))}</p>`}</div>
      ${d.outgoing.length ? `<div class="card"><div class="card-title">${esc(t("requests_sent"))}</div>
        ${d.outgoing.map((c) => friendRow(c, relationButtons(c.username, "sent"))).join("")}</div>` : ""}
    </div>`);
  bindFriendButtons(app, viewFriends);
  $$("[data-chacc]").forEach((b) => b.onclick = () => answerChallenge(b.dataset.chacc, true));
  $$("[data-chdec]").forEach((b) => b.onclick = async () => { await answerChallenge(b.dataset.chdec, false); viewFriends(); });
  let timer;
  $("#q").oninput = (e) => {
    clearTimeout(timer);
    const q = e.target.value.trim();
    timer = setTimeout(async () => {
      const box = $("#results");
      if (!box) return;
      if (q.length < 2) { box.innerHTML = ""; return; }
      const r = await api(`/api/friends/search?q=${encodeURIComponent(q)}`);
      box.innerHTML = (r.users || []).length ? `<div class="card">${r.users.map((u) => friendRow(u, relationButtons(u.username, u.relation))).join("")}</div>`
        : `<p class="empty">${esc(t("no_players_found"))}</p>`;
      fillIcons(box);
      bindFriendButtons(box, viewFriends);
    }, 300);
  };
}
async function answerChallenge(id, accept) {
  document.getElementById("chBanner")?.remove();
  const r = await api(`/api/challenges/${id}/${accept ? "accept" : "decline"}`, {});
  if (!r.ok) { toast(errText(r)); return; }
  if (accept && r.match) { if (Q.on) await queueLeave(); go(`#/match/${r.match}`); }
}
const seenChallenges = new Set();
// ------------------------------------------------------------------ notifications
// Website version: the browser's notifications (they show while Speakoff is open in a background tab).
// The phone apps will send the same two through push notifications (Firebase / Apple) when they are built.
function notifyOn() { return store("sc-notify") === "on" && "Notification" in window && Notification.permission === "granted"; }
function notify(title, body, hash) {
  if (!notifyOn() || (!document.hidden && document.hasFocus())) return;      // the app is in front: the banner is enough
  try {
    const n = new Notification(title, { body, icon: "/icon.svg", tag: hash || title });
    n.onclick = () => { window.focus(); if (hash) go(hash); n.close(); };
  } catch (e) { /* not supported */ }
}
async function checkDailyReward() {
  if (!S.me || !notifyOn()) return;
  const today = new Date().toDateString();
  if (store("sc-daily-notified") === today) return;
  const h = await api("/api/home");
  if (h.calendar && h.calendar.can_claim) {
    store("sc-daily-notified", today);
    notify("Speakoff", t("notif_daily"), "#/home");
  }
}
async function checkChallenges() {
  if (!S.me || /^#\/(match|challenge)/.test(location.hash) || document.getElementById("chBanner")) return;
  const r = await api("/api/challenges/pending");
  const ch = (r.challenges || []).find((c) => !seenChallenges.has(c.id));
  if (!ch) return;
  seenChallenges.add(ch.id);
  const el = document.createElement("div");
  el.id = "chBanner";
  el.className = "ch-banner";
  el.innerHTML = `${avatarHtml(ch.from, 40)}<div class="ch-text"><b>${esc(ch.from.username)}</b><span>${esc(t("challenges_you"))}</span></div>
    <button class="btn small" id="chYes">${esc(t("accept"))}</button><button class="iconbtn" id="chNo" aria-label="${esc(t("decline"))}">✕</button>`;
  document.body.appendChild(el);
  notify("Speakoff", `${ch.from.username} ${t("challenges_you")}`, "#/friends");
  el.querySelector("#chYes").onclick = () => answerChallenge(ch.id, true);
  el.querySelector("#chNo").onclick = () => answerChallenge(ch.id, false);
  setTimeout(() => el.remove(), Math.max(5, ch.expires_in) * 1000);
}
async function viewChallenge(id) {
  const draw = (st) => render(`
    <div class="card analysing search">
      ${st.status === "pending" ? `<div class="radar-ping"><span></span><span></span>${avatarHtml(st.to, 72)}</div>` : avatarHtml(st.to, 72)}
      <h2 style="margin-top:14px">${esc(t(st.status === "pending" ? "waiting_for" : "challenge_" + st.status, { name: st.to.username }))}</h2>
      ${st.status === "pending" ? `<p class="timer" style="margin-top:10px">${mmss(st.expires_in)}</p>
        <button class="btn outline" id="cancel" style="margin-top:8px">${esc(t("cancel"))}</button>`
        : `<a class="btn" href="#/friends" style="margin-top:16px">${esc(t("friends"))}</a>`}
    </div>`);
  let st = await api(`/api/challenges/${id}`);
  if (!st.id) { go("#/friends"); return; }
  if (st.status === "accepted" && st.match) return go(`#/match/${st.match}`);
  draw(st);
  const bindCancel = () => { const c = document.getElementById("cancel"); if (c) c.onclick = async () => { await api(`/api/challenges/${id}/cancel`, {}); go("#/friends"); }; };
  bindCancel();
  if (st.status !== "pending") return;
  const poll = setInterval(async () => {
    st = await api(`/api/challenges/${id}`);
    if (!st.id) return;
    if (st.status === "accepted" && st.match) { clearInterval(poll); go(`#/match/${st.match}`); return; }
    draw(st); fillIcons(app); bindCancel();
    if (st.status !== "pending") clearInterval(poll);
  }, 2000);
  leaveHooks.push(() => clearInterval(poll));
}

// ------------------------------------------------------------------ profile
let profileTab = store("sc-ptab") || "stats";
async function viewProfile() {
  await refreshMe();
  const m = S.me, c = m.card;
  const tabs = [["stats", "tab_stats"], ["skills", "tab_skills"], ["achs", "tab_achievements"], ["settings", "tab_settings"]];
  render(`
    <div class="page-head"><h1>${esc(t("profile"))}</h1></div>
    <div class="stack-lg">
      <div class="player-card" style="--c:${RANK_COLOR[c.rank.rank]}">
        <button class="ava-btn" id="editLook" aria-label="${esc(t("edit_look"))}">${avatarHtml(c, 92)}<span class="ava-edit">${icon("camera")}</span></button>
        <div style="min-width:0;flex:1"><h2>${m.country ? `<span class="flag">${flag(m.country)}</span>` : ""}${nameHtml(c, m.username)}</h2>
          ${m.display_name ? `<div class="muted small real-name">${esc(m.display_name)}</div>` : ""}
          <div class="prank">${emblem(c.rank, 20)}<span>${esc(rankLabel(c.rank))} · ${c.rank.rp} ${esc(t("rp"))}</span></div>
          <div class="skills-row">${skillChips(c.skills)}</div>
          <a class="btn small ghost" href="#/friends" style="margin-top:10px">${icon("users")} ${esc(t("friends"))}</a></div>
      </div>
      <div class="seg" id="ptabs">${tabs.map(([k, l]) => `<button data-v="${k}" class="${k === profileTab ? "on" : ""}">${esc(t(l))}</button>`).join("")}</div>
      <div id="ptab"><div class="splash" style="min-height:200px"><div class="spinner"></div></div></div>
    </div>`);
  $("#editLook").onclick = () => openLook();
  $$("#ptabs button").forEach((b) => b.onclick = () => { profileTab = b.dataset.v; store("sc-ptab", profileTab); $$("#ptabs button").forEach((x) => x.classList.toggle("on", x === b)); drawTab(); });
  drawTab();
}

async function drawTab() {
  const box = $("#ptab");
  if (!box) return;
  if (profileTab === "settings") { box.innerHTML = settingsHtml(); fillIcons(box); bindSettings(); return; }
  if (profileTab === "stats") {
    let season = store("sc-pseason") || "current";
    const draw = async () => {
      const d = await api(`/api/profile/stats?season=${season}`);
      if (!d.stats || profileTab !== "stats") return;
      box.innerHTML = `<div class="card">
        <div class="seg small-seg" id="seasonSeg"><button data-v="current" class="${season === "current" ? "on" : ""}">${esc(t("current_season"))}</button>
          <button data-v="all" class="${season === "all" ? "on" : ""}">${esc(t("all_seasons"))}</button></div>
        <div style="margin-top:16px">${statsBlock(d.stats)}</div></div>`;
      box.querySelectorAll("#seasonSeg button").forEach((b) => b.onclick = () => { season = b.dataset.v; store("sc-pseason", season); draw(); });
    };
    return draw();
  }
  const d = await api("/api/profile/awards");
  if (!d.skills) return;
  awardToast(d.new);
  if (profileTab === "skills") {
    const owned = d.skills.filter((s) => s.count);
    const shown = new Set(d.shown);
    const done = d.block - d.next_skill_in;
    box.innerHTML = `
      <div class="card next-skill"><div class="row between"><b>${esc(t("next_skill", { n: d.next_skill_in }))}</b><span class="muted small">${done} / ${d.block}</span></div>
        <div class="bar shine-bar"><i style="width:${100 * done / d.block}%"></i></div>
        <div class="rarity-key"><span class="r-blue">x1</span><span class="r-green">x5</span><span class="r-purple">x15</span></div></div>
      <div class="awards">${[...owned, ...d.skills.filter((s) => !s.count)].map((s) => `
        <div class="award ${s.count ? "on r-" + s.rarity : ""}">
          <div class="hexicon ${s.count ? "r-" + s.rarity : ""}">${s.icon}${s.count ? `<b class="stack">x${s.count}</b>` : ""}</div>
          <div class="aw-body"><div class="aw-name">${esc(t("sk_" + s.id))}</div><div class="aw-desc">${esc(t("skd_" + s.id))}</div>
            ${s.count ? `<div class="aw-foot"><span></span>
                <button class="chip ${shown.has(s.id) ? "on" : ""}" data-show="${s.id}">${icon("check")}${esc(t(shown.has(s.id) ? "shown" : "show_on_profile"))}</button></div>` : ""}
          </div></div>`).join("")}</div>`;
    fillIcons(box);
    box.querySelectorAll("[data-show]").forEach((b) => b.onclick = async () => {
      const id = b.dataset.show;
      if (shown.has(id)) shown.delete(id);
      else { if (shown.size >= 2) { toast(t("max_two")); return; } shown.add(id); }
      const res = await api("/api/profile/look", { skills: [...shown] });
      if (res.ok) { S.me = res.user; viewProfile(); }
    });
  } else {
    const earned = d.achs.reduce((n, a) => n + a.tier, 0);
    box.innerHTML = `<p class="muted small" style="margin-bottom:12px">${esc(t("n_of_total", { n: earned, total: d.achs.length * 3 }))}</p>
      <div class="awards ach">${d.achs.map((a) => `
        <div class="award ${a.tier ? "on r-" + a.rarity : ""}">
          <div class="hexicon ${a.tier ? "r-" + a.rarity : ""}">${a.icon}</div>
          <div class="aw-body"><div class="aw-name">${esc(t("ac_" + a.id))}</div>
            <div class="tiers">${a.tiers.map((x, i) => `<span class="tier ${i < a.tier ? "r-" + ["blue", "green", "purple"][i] : ""}">${esc(achTierLabel(a.id, x))}</span>`).join("")}</div>
            ${a.next != null ? `<div class="bar"><i style="width:${Math.min(100, 100 * a.value / a.next)}%"></i></div>
              <div class="muted small">${esc(t("ach_goal_" + a.id, { n: a.id === "best_rank" ? achTierLabel(a.id, a.next) : a.next.toLocaleString() }))} · ${a.id === "best_rank" ? "" : `${a.value.toLocaleString()} / ${a.next.toLocaleString()}`}</div>`
              : `<div class="muted small">${esc(t("ach_maxed"))}</div>`}
          </div></div>`).join("")}</div>`;
  }
}

// photo + frame editor (a sheet over the page)
async function openLook() {
  const d = await api("/api/profile/awards");
  if (!d.frames) return;
  const sheet = document.createElement("div");
  sheet.className = "sheet-wrap";
  const frameName = (f) => f.id === "none" ? t("frame_none") : RANK_COLOR[f.id] ? t("rank_" + f.id) : t("frame_" + f.id);
  const frameNeed = (f) => !f.need ? "" : f.need[0] === "daily" ? t("frame_need_streak", { n: f.need[1] }) : f.need[0] === "rank" ? t("goal_reach", { rank: t("rank_" + f.need[1]) })
    : `${t("ac_" + f.need[1])} ${achTierLabel(f.need[1], (d.achs.find((a) => a.id === f.need[1]) || { tiers: [0, 0, 0] }).tiers[f.need[2] - 1])}`;
  const draw = () => {
    const c = S.me.card;
    sheet.innerHTML = `<div class="sheet" role="dialog" aria-modal="true">
      <div class="row between"><h2>${esc(t("edit_look"))}</h2><button class="iconbtn" id="closeSheet" aria-label="${esc(t("back"))}">✕</button></div>
      <div class="row" style="margin:16px 0">${avatarHtml(c, 84)}
        <div class="stack" style="flex:1"><label class="btn small block">${icon("camera")} ${esc(t("change_photo"))}<input type="file" id="photoIn" accept="image/*" hidden></label>
          ${c.photo ? `<button class="btn small block ghost" id="rmPhoto">${esc(t("remove_photo"))}</button>` : ""}</div></div>
      <div class="error" id="lookErr"></div>
      <div class="card-title">${esc(t("frames"))}</div>
      <div class="frames">${d.frames.map((f) => `
        <button class="frame-opt ${f.unlocked ? "" : "locked"} ${c.frame === f.id ? "on" : ""}" data-frame="${f.id}" ${f.unlocked ? "" : "disabled"}>
          ${avatarHtml({ ...c, frame: f.id }, 56)}<span>${esc(frameName(f))}</span>${f.unlocked ? "" : `<small>${icon("lock")} ${esc(frameNeed(f))}</small>`}
        </button>`).join("")}</div>
    </div>`;
    fillIcons(sheet);
    sheet.querySelector("#closeSheet").onclick = close;
    sheet.querySelector("#photoIn").onchange = async (e) => {
      const f = e.target.files[0];
      if (!f) return;
      try {
        const blob = await squarePhoto(f, 256);
        const fd = new FormData(); fd.append("photo", blob, "photo.jpg");
        const r = await fetch("/api/profile/photo", { method: "POST", body: fd, headers: { "X-SC": "1" }, credentials: "same-origin" });
        const res = await r.json().catch(() => ({}));
        if (!res.ok) { sheet.querySelector("#lookErr").textContent = errText(res); return; }
        S.me = res.user; draw(); toast(t("saved"));
      } catch (err) { sheet.querySelector("#lookErr").textContent = t("bad_photo"); }
    };
    const rm = sheet.querySelector("#rmPhoto");
    if (rm) rm.onclick = async () => { const res = await api("/api/profile/photo/remove", {}); if (res.ok) { S.me = res.user; draw(); } };
    sheet.querySelectorAll("[data-frame]").forEach((b) => b.onclick = async () => {
      const res = await api("/api/profile/look", { frame: b.dataset.frame });
      if (res.ok) { S.me = res.user; draw(); }
    });
  };
  function close() { sheet.remove(); viewProfile(); }
  sheet.onclick = (e) => { if (e.target === sheet) close(); };
  document.body.appendChild(sheet);
  draw();
  leaveHooks.push(() => sheet.remove());
}
function squarePhoto(file, size) {
  // centre-crop to a square and shrink in the browser: the server only stores a small JPEG
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      const s = Math.min(img.naturalWidth, img.naturalHeight);
      const cv = document.createElement("canvas");
      cv.width = cv.height = size;
      cv.getContext("2d").drawImage(img, (img.naturalWidth - s) / 2, (img.naturalHeight - s) / 2, s, s, 0, 0, size, size);
      URL.revokeObjectURL(img.src);
      cv.toBlob((b) => b ? resolve(b) : reject(new Error("photo")), "image/jpeg", 0.86);
    };
    img.onerror = () => reject(new Error("photo"));
    img.src = URL.createObjectURL(file);
  });
}

// settings (the old profile page)
function settingsHtml() {
  const m = S.me;
  const seg = (id, opts, cur) => `<div class="seg" id="${id}">${opts.map(([v, label, ic]) => `<button data-v="${v}" class="${v === cur ? "on" : ""}">${ic ? icon(ic) : ""}${esc(label)}</button>`).join("")}</div>`;
  return `<div class="stack-lg">
      <div class="muted small">${esc(m.contact)} · ${esc(t("member_since", { date: fmtDate(m.created) }))}</div>
      <div><div class="card-title">${esc(t("plan_label"))}</div><div class="list">
        <div class="li"><div><div class="lab">${esc(planName(m.plan))}</div>
          ${m.plan_renews ? `<div class="muted small">${esc(t("renews", { date: fmtDate(m.plan_renews) }))}</div>` : ""}</div>
          <a class="btn small ${m.plan === "free" ? "" : "ghost"}" href="#/plans">${esc(m.plan === "free" ? t("upgrade") : t("manage_plan"))}</a></div>
      </div></div>

      <div><div class="card-title">${esc(t("appearance"))}</div><div class="list">
        <div class="li"><span class="lab">${esc(t("notifications"))}</span>${seg("notifySeg", [["on", t("sound_on")], ["off", t("sound_off")]], notifyOn() ? "on" : "off")}</div>
        <div class="li"><span class="lab">${esc(t("sounds"))}</span>${seg("soundSeg", [["on", t("sound_on")], ["off", t("sound_off")]], SFX.on ? "on" : "off")}</div>
        <div class="li"><span class="lab">${esc(t("theme"))}</span>${seg("themeSeg", [["dark", t("theme_dark"), "moon"], ["light", t("theme_light"), "sun"]], m.theme)}</div>
        <div class="li"><span class="lab">${esc(t("ai_voice"))}</span>${seg("voiceSeg", [["female", t("voice_female")], ["male", t("voice_male")]], m.voice)}</div>
        <div class="li"><div><div class="lab">${esc(t("app_language"))}</div><div class="muted small">${esc(t("language_note"))}</div></div>${langSelect("langSel")}</div>
      </div></div>

      <div><div class="card-title">${esc(t("account"))}</div><div class="list">
        ${m.contact.includes(":") ? "" : `<div class="li"><span class="lab">${esc(t(m.contact_type))}</span><span class="val acct">${esc(m.contact)}</span></div>`}
        ${m.google || m.apple ? `<div class="li"><span class="lab">${esc(t("signed_in_with"))}</span><span class="val">${[m.google ? "Google" : "", m.apple ? "Apple" : ""].filter(Boolean).join(", ")}</span></div>` : ""}
        <div class="li"><span class="lab">${esc(t("username"))}</span>
          <button class="val un-name" id="unEdit" aria-label="${esc(t("change_username"))}">${esc(m.username)} ${icon("edit")}</button></div>
        <form id="unForm" class="li un-form" novalidate hidden>
          <div class="stack" style="flex:1;gap:6px">
            <div class="row" style="gap:8px"><input class="input" id="unNew" autocomplete="off" maxlength="20" value="${esc(m.username)}" placeholder="${esc(t("username"))}">
              <button class="btn small" id="unSave" disabled>${esc(t("save"))}</button></div>
            <div class="small" id="unHint"></div></div></form>
        <div class="li"><div><div class="lab">${esc(t("share_answers"))}</div><div class="muted small">${esc(t("share_answers_sub"))}</div></div>
          ${seg("shareSeg", [["on", t("sound_on")], ["off", t("sound_off")]], m.share_answers ? "on" : "off")}</div>
        <div class="li" style="flex-wrap:wrap;gap:10px"><div><div class="lab">${esc(t("learning_languages"))}</div>
            <div class="muted small">${esc(m.lang_cap ? t("langs_of", { n: (m.learn_langs || []).length, cap: m.lang_cap }) : t("langs_all"))}</div></div>
          <div class="learn-chips" id="learnChips">${LEARN.map(([c, f, n, ok]) =>
            `<button class="learn-chip ${(m.learn_langs || []).includes(c) ? "on" : ""}" data-l="${c}" ${ok ? "" : "disabled"}>${f} ${esc(n)}${ok ? "" : ` <span class="soon">${esc(t("soon"))}</span>`}</button>`).join("")}</div></div>
        <div class="li"><div><div class="lab">${esc(t("country"))}</div>${m.country_change && !m.country_change.first ? `<div class="muted small">${esc(m.country_change.ok
          ? t("country_open", { to: fmtDate(m.country_change.until) }) : t("country_locked", { from: fmtDate(m.country_change.from), to: fmtDate(m.country_change.to) }))}</div>` : ""}</div>
          ${countrySelect("countrySel", m.country)}</div>
      </div></div>

      <details class="acc"><summary>${esc(t(m.has_password ? "change_password" : "set_password"))}</summary><div class="acc-body">
        <form id="pwForm" class="stack" novalidate>
          ${m.has_password ? `<input class="input" id="pwCur" type="password" autocomplete="current-password" placeholder="${esc(t("current_password"))}">` : ""}
          <input class="input" id="pwNew" type="password" autocomplete="new-password" placeholder="${esc(t("new_password"))}">
          <input class="input" id="pwNew2" type="password" autocomplete="new-password" placeholder="${esc(t("password_again"))}">
          <div class="error" id="pwErr"></div>
          <button class="btn">${esc(t("save"))}</button>
        </form></div></details>

      <div class="stack">
        <button class="btn block outline" id="signOut">${esc(t("sign_out"))}</button>
        <details class="acc"><summary style="color:var(--bad)">${esc(t("delete_account"))}</summary><div class="acc-body stack">
          <p class="muted small">${esc(t("delete_confirm"))}</p>
          <input class="input" id="delPw" ${m.has_password ? `type="password" autocomplete="current-password" placeholder="${esc(t("password"))}"` : `autocomplete="off" placeholder="${esc(t("type_username"))}"`}>
          <div class="error" id="delErr"></div>
          <button class="btn danger block" id="delBtn">${esc(t("delete_account"))}</button>
        </div></details>
      </div>
    </div>`;
}
function bindSettings() {
  const unIn = $("#unNew"), unHint = $("#unHint"), unSave = $("#unSave");
  $("#unEdit").onclick = () => { $("#unEdit").closest(".li").hidden = true; $("#unForm").hidden = false; unIn.focus(); unIn.select(); };
  let unTimer = null;
  unIn.oninput = () => {
    clearTimeout(unTimer);
    const name = unIn.value.trim();
    unSave.disabled = true; unHint.className = "small"; unHint.textContent = "";
    if (!name || name === S.me.username) return;
    unTimer = setTimeout(async () => {
      const r = await api(`/api/username/check?name=${encodeURIComponent(name)}`);
      if (unIn.value.trim() !== name) return;
      unHint.className = `small ${r.ok ? "good" : "bad"}`;
      unHint.textContent = r.ok ? `✓ ${t("username_free")}` : t(r.error || "err_username");
      unSave.disabled = !r.ok;
    }, 350);
  };
  $("#unForm").onsubmit = async (e) => {
    e.preventDefault();
    unSave.disabled = true;
    const r = await api("/api/username", { username: unIn.value.trim() });
    if (!r.ok) { unHint.className = "small bad"; unHint.textContent = errText(r); return; }
    S.me = r.user; toast(t("saved")); viewProfile();
  };
  async function save(change) {
    const res = await api("/api/settings", change);
    if (res.ok) S.me = res.user;
    return res.ok;
  }
  $$("#themeSeg button").forEach((b) => b.onclick = async () => { setTheme(b.dataset.v); if (await save({ theme: b.dataset.v })) toast(t("saved")); viewProfile(); });
  $$("#shareSeg button").forEach((b) => b.onclick = async () => { if (await save({ share_answers: b.dataset.v === "on" })) toast(t("saved")); viewProfile(); });
  $$("#learnChips .learn-chip").forEach((b) => b.onclick = async () => {
    const now = S.me.learn_langs || [];
    const want = now.includes(b.dataset.l) ? now.filter((x) => x !== b.dataset.l) : [...now, b.dataset.l];
    const res = await api("/api/settings", { learn_langs: want });
    if (!res.ok) { toast(errText(res)); if (res.error === "lang_limit") go("#/plans"); return; }
    S.me = res.user;
    toast(t("saved"));
    viewProfile();
  });
  $$("#notifySeg button").forEach((b) => b.onclick = async () => {
    if (b.dataset.v === "on") {
      if (!("Notification" in window)) { toast(t("notif_unsupported")); return; }
      const p = Notification.permission === "default" ? await Notification.requestPermission() : Notification.permission;
      if (p !== "granted") { toast(t("notif_blocked")); viewProfile(); return; }
    }
    store("sc-notify", b.dataset.v); toast(t("saved")); viewProfile();
  });
  $$("#soundSeg button").forEach((b) => b.onclick = () => { SFX.on = b.dataset.v === "on"; store("sc-sound", b.dataset.v); if (SFX.on) sfx("coin"); viewProfile(); });
  $$("#voiceSeg button").forEach((b) => b.onclick = async () => { if (await save({ voice: b.dataset.v })) toast(t("saved")); viewProfile(); });
  $("#langSel").onchange = async (e) => { const ok = await save({ lang: e.target.value }); await setLang(e.target.value); viewProfile(); if (ok) toast(t("saved")); };
  if (S.me.country_change && !S.me.country_change.ok) $("#countrySel").disabled = true;
  $("#countrySel").onchange = async (e) => {
    const c = S.me.country_change || {};
    if (!c.first && !confirm(t("country_confirm"))) { e.target.value = S.me.country || ""; return; }
    const res = await api("/api/settings", { country: e.target.value });
    if (!res.ok) { toast(errText(res)); e.target.value = S.me.country || ""; return; }
    S.me = res.user;
    toast(t("saved"));
    viewProfile();
  };
  $("#pwForm").onsubmit = async (e) => {
    e.preventDefault();
    const res = await api("/api/password", { current: $("#pwCur") ? $("#pwCur").value : "", new: $("#pwNew").value, new2: $("#pwNew2").value });
    if (!res.ok) { $("#pwErr").textContent = errText(res); return; }
    $("#pwErr").textContent = ""; e.target.reset(); toast(t("saved"));
  };
  $("#signOut").onclick = async () => { await api("/api/auth/signout", {}); S.me = null; go("#/welcome"); };
  $("#delBtn").onclick = async () => {
    if (!confirm(t("delete_confirm"))) return;
    const res = await api("/api/account/delete", { password: $("#delPw").value });
    if (!res.ok) { $("#delErr").textContent = errText(res); return; }
    S.me = null; go("#/welcome");
  };
}

// ------------------------------------------------------------------ plans (test mode)
async function viewPlans() {
  const data = await api("/api/plans");
  let period = "monthly";
  const draw = () => {
    const cur = S.me.plan;
    const card = (p) => {
      const price = period === "yearly" ? p.price_y : p.price_m;
      const feats = p.id === "free"
        ? [t("feat_welcome"), t("feat_length", { max: mmss(p.max_s) }), t("feat_daily_q"), t("feat_progress_simple"), t("feat_ranked", { n: p.ranked }), t("feat_langs", { n: p.langs }), t("feat_mock_month")]
        : [p.id === "pro" ? t("feat_unlimited") : t("feat_per_day", { n: p.per_day }), t("feat_length", { max: mmss(p.max_s) }), t(period === "yearly" ? "feat_credits" : "feat_credits_once", { n: p.credits_month }),
           t("feat_daily_q"), t("feat_progress_full"), t("feat_ranked", { n: p.ranked }), p.langs ? t("feat_langs", { n: p.langs }) : t("feat_langs_all"), t(p.id === "pro" ? "feat_mock_day" : "feat_mock_week"), ...(p.id === "pro" ? [t("feat_trial")] : [])];
      return `<div class="plan ${p.id === "pro" ? "best" : ""}">
        ${cur === p.id ? `<span class="tag accent badge">${esc(t("current_plan"))}</span>` : period === "yearly" && p.price_m ? `<span class="tag accent badge">${esc(t("bonus_months", { n: 2 }))}</span>` : ""}
        <h2>${esc(planName(p.id))}</h2>
        <div class="price">${price ? `$${price.toFixed(2)}` : "$0"} <small>${price ? esc(t(period === "yearly" ? "per_year" : "per_month")) : ""}</small></div>
        <ul>${feats.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
        ${cur === p.id ? `<button class="btn block ghost" disabled>${esc(t("current_plan"))}</button>`
          : `<button class="btn block ${p.id === "free" ? "outline" : ""}" data-plan="${p.id}">${esc(p.id === "free" ? t("switch_free") : t("choose"))}</button>`}
      </div>`;
    };
    render(`
      <div class="page-head">${backBtn("#/profile")}</div>
      <h1 style="margin-bottom:16px">${esc(t("plans_title"))}</h1>
      <div class="stack">
        <div class="seg" id="periodSeg"><button data-v="monthly" class="${period === "monthly" ? "on" : ""}">${esc(t("monthly"))}</button>
          <button data-v="yearly" class="${period === "yearly" ? "on" : ""}">${esc(t("yearly"))}</button></div>
        ${data.plans.slice().reverse().map(card).join("")}
        <div class="notice small">${esc(t("test_mode_note"))}</div>
        <div class="cards-logos">${["Visa", "Mastercard", "JCB", "UnionPay", "Amex"].map((c) => `<span class="tag">${c}</span>`).join("")}</div>
      </div>`);
    $$("#periodSeg button").forEach((b) => b.onclick = () => { period = b.dataset.v; draw(); });
    $$("[data-plan]").forEach((b) => b.onclick = async () => {
      b.disabled = true;
      const res = await api("/api/plans/choose", { plan: b.dataset.plan, period });
      if (res.ok) { S.me = res.user; S.usage = res.usage; toast(t("plan_changed", { plan: planName(res.user.plan) })); draw(); }
      else b.disabled = false;
    });
  };
  draw();
}

// ------------------------------------------------------------------ setup after sign-up
function langSwitch() {
  const mine = (S.me.learn_langs || [S.me.learn_lang || "en"]);
  if (mine.length < 2) return "";
  return `<div class="seg small lang-sw" id="langSw">${mine.map((c) => { const l = LEARN.find((x) => x[0] === c) || [c, "", c];
    return `<button data-l="${c}" class="${c === (S.me.learn_lang || "en") ? "on" : ""}">${l[1]} ${esc(l[2])}</button>`; }).join("")}</div>`;
}
function bindLangSwitch(after) {
  app.querySelectorAll("#langSw button").forEach((b) => b.onclick = async () => {
    if (b.classList.contains("on")) return;
    const r = await api("/api/settings", { learn_lang: b.dataset.l });
    if (!r.ok) { toast(errText(r)); return; }
    S.me = { ...S.me, ...r.user };
    after();
  });
}
const LEARN = [["en", "🇬🇧", "English", true], ["ko", "🇰🇷", "한국어", true], ["es", "🇪🇸", "Español", false],
  ["de", "🇩🇪", "Deutsch", false], ["ja", "🇯🇵", "日本語", false]];
async function viewSetup() {
  tabbar.hidden = true;
  const me = S.me;
  let share = true;                                    // suggested: on
  let learn = me.learn_lang || "en";
  render(`
    <div class="setup stack-lg">
      <div><h1>${esc(t("setup_title"))}</h1><p class="muted">${esc(t("setup_sub"))}</p></div>
      <label class="field"><span>${esc(t("your_name"))}</span>
        <input class="input" id="suName" maxlength="30" autocomplete="name" value="${esc(me.display_name || "")}" placeholder="${esc(t("your_name_ph"))}"></label>
      <label class="field"><span>${esc(t("app_language"))}</span>${langSelect("suLang")}</label>
      <div class="field"><span>${esc(t("learning_language"))}</span>
        <div class="learn-list">${LEARN.map(([c, f, n, ok]) => `<button class="learn ${c === learn ? "on" : ""}" data-learn="${c}" ${ok ? "" : "disabled"}>
          <span class="lf">${f}</span><b>${esc(n)}</b>${ok ? "" : `<span class="tag">${esc(t("soon"))}</span>`}</button>`).join("")}</div></div>
      <label class="field"><span>${esc(t("country"))}</span>${countrySelect("suCountry", me.country || guessCountry())}</label>
      <div class="share-card">
        <div class="row between" style="gap:12px"><div><b>🎧 ${esc(t("share_answers"))}</b>
          <p class="muted small" style="margin-top:4px">${esc(t("share_pitch"))}</p></div>
          <button class="switch on" id="suShare" role="switch" aria-checked="true"><i></i></button></div></div>
      <div class="error" id="suErr"></div>
      <button class="btn block big" id="suGo">${esc(t("setup_go"))}</button>
    </div>`);
  $("#suLang").onchange = async (e) => { await setLang(e.target.value); viewSetup(); };
  $$("[data-learn]").forEach((b) => b.onclick = () => { learn = b.dataset.learn; $$("[data-learn]").forEach((x) => x.classList.toggle("on", x === b)); });
  $("#suShare").onclick = () => { share = !share; $("#suShare").classList.toggle("on", share); $("#suShare").setAttribute("aria-checked", share); };
  $("#suGo").onclick = async () => {
    const name = $("#suName").value.trim();
    if (!name) { $("#suErr").textContent = t("err_your_name"); $("#suName").focus(); return; }
    $("#suGo").disabled = true;
    const res = await api("/api/settings", { display_name: name, lang: S.lang, learn_lang: learn, country: $("#suCountry").value, share_answers: share });
    if (!res.ok) { $("#suGo").disabled = false; $("#suErr").textContent = errText(res); return; }
    S.me = res.user;
    go("#/home");
  };
}

// ------------------------------------------------------------------ credits shop
const SHOP = [
  ["ranked", "trophy", (it) => t("n_left_today", { n: it.left_today })],
  ["shield", "shield", (it) => `${t("shop_shield_sub")} · ${it.have}/3`],
  ["recording", "mic", (it) => S.me.plan === "free" ? t("n_left_today", { n: it.left_today }) : t("free_only")],
  ["plus_day", "spark", (it) => it.until ? t("plus_until", { date: fmtDate(it.until, true) }) : t("free_only")],
  ["keep_audio", "bookmark", (it) => `${t("shop_keep_sub")} · ${it.have}/5`],
];
let shopTab = store("sc-shop") || "boosts", cosKind = store("sc-cos") || "name";
function shopHead(credits) {
  return `<div class="page-head">${backBtn("#/home")}<div class="credits-pill big">${coin()}<b>${credits.toLocaleString()}</b></div></div>
    <h1 style="margin-bottom:16px">${esc(t("shop"))}</h1>
    <div class="seg" id="shopSeg" style="margin-bottom:12px"><button data-v="boosts" class="${shopTab === "boosts" ? "on" : ""}">${icon("spark")} ${esc(t("shop_boosts"))}</button>
      <button data-v="cosmetics" class="${shopTab === "cosmetics" ? "on" : ""}">${icon("bag")} ${esc(t("shop_cosmetics"))}</button></div>`;
}
function bindShopSeg() {
  $$("#shopSeg button").forEach((b) => b.onclick = () => { shopTab = b.dataset.v; store("sc-shop", shopTab); viewShop(); });
}
async function viewShop() {
  if (shopTab === "cosmetics") return viewCosmetics();
  const d = await api("/api/shop");
  if (!d.items) return;
  render(`
    ${shopHead(d.credits)}
    <div class="stack">
      ${SHOP.map(([id, ic, sub]) => { const it = d.items[id]; return `
        <div class="card shop-row">
          <span class="shop-ic">${icon(ic)}</span>
          <div class="grow"><b>${esc(t("shop_" + id))}</b><div class="muted small">${esc(sub(it))}</div></div>
          ${id === "keep_audio" ? "" : `<button class="btn small" data-buy="${id}" ${it.ok && d.credits >= it.price ? "" : "disabled"}>${coin()} ${it.price}</button>`}
        </div>`; }).join("")}
    </div>`);
  $$("[data-buy]").forEach((b) => b.onclick = async () => {
    b.disabled = true;
    const res = await api("/api/shop/buy", { item: b.dataset.buy });
    if (!res.ok) { toast(errText(res)); b.disabled = false; return; }
    S.me = res.user; S.usage = res.usage;
    sfx("coin"); toast(t("bought"));
    viewShop();
  });
  bindShopSeg();
}
async function viewCosmetics() {
  const d = await api("/api/cosmetics");
  if (!d.items) return;
  const me = S.me.card;
  const preview = (it) => {
    const k = it.id.split("_")[1];
    if (it.kind === "name") return `<div class="cos-prev">${nameHtml({ name_style: it.id }, S.me.username)}</div>`;
    if (it.kind === "sticker") return `<div class="cos-prev">${stickerHtml(it.id)}</div>`;
    const en = entranceFx(it.id);
    return `<div class="cos-prev"><div class="pcol ${en.cls}" data-replay><div class="pava">${en.fx}${avatarHtml(me, 56)}</div></div></div>`;
  };
  render(`
    ${shopHead(d.credits)}
    <div class="seg small" id="cosSeg">${["name", "enter", "sticker"].map((k) => `<button data-v="${k}" class="${cosKind === k ? "on" : ""}">${esc(t("cos_" + k))}</button>`).join("")}</div>
    <div class="cos-grid">
      ${d.items.filter((it) => it.kind === cosKind).sort((a, b) => a.price - b.price).map((it) => `
        <div class="card cos ${it.worn ? "worn" : ""} ${it.plan ? "members p-" + it.plan : ""}">
          ${preview(it)}
          ${it.plan ? `<span class="tag plan-tag p-${it.plan}">${icon("spark")} ${esc(planName(it.plan))}</span>` : ""}
          ${it.worn ? `<button class="btn small block ghost" data-off="${it.kind}">${icon("check")} ${esc(t("equipped"))}</button>`
            : it.owned ? `<button class="btn small block outline" data-wear="${it.id}">${esc(t("equip"))}</button>`
            : it.plan ? `<a class="btn small block outline" href="#/plans">${esc(t("get_plan", { plan: planName(it.plan) }))}</a>`
            : it.reward_day ? `<div class="btn small block ghost cos-reward">${icon("calendar")} ${esc(t("day_n", { n: it.reward_day }))}</div>`
            : `<button class="btn small block" data-cbuy="${it.id}" ${d.credits >= it.price ? "" : "disabled"}>${coin()} ${it.price}</button>`}
        </div>`).join("")}
    </div>`);
  bindShopSeg();
  $$("#cosSeg button").forEach((b) => b.onclick = () => { cosKind = b.dataset.v; store("sc-cos", cosKind); viewCosmetics(); });
  $$("[data-replay]").forEach((el) => el.onclick = () => { const c = el.className; el.className = "pcol"; void el.offsetWidth; el.className = c; });
  const act = async (b, path, body) => {
    b.disabled = true;
    const res = await api(`/api/cosmetics/${path}`, body);
    if (!res.ok) { toast(errText(res)); b.disabled = false; return; }
    S.me = res.user; myEmotes = null;
    if (path === "buy") { sfx("sparkle"); toast(t("bought")); }
    viewCosmetics();
  };
  $$("[data-cbuy]").forEach((b) => b.onclick = () => act(b, "buy", { item: b.dataset.cbuy }));
  $$("[data-wear]").forEach((b) => b.onclick = () => act(b, "wear", { kind: b.dataset.wear.split("_")[0], item: b.dataset.wear }));
  $$("[data-off]").forEach((b) => b.onclick = () => act(b, "wear", { kind: b.dataset.off, item: "" }));
}

// ------------------------------------------------------------------ mock IELTS test
const mk = { stream: null, rec: null, chunks: [], blobs: [], loop: null, voice: null };
function mockStop() {
  clearInterval(mk.loop); mk.loop = null;
  if (mk.voice) { mk.voice.pause(); mk.voice = null; }
  if (mk.rec && mk.rec.state !== "inactive") { mk.rec.onstop = null; mk.rec.stop(); }
  mk.rec = null;
  if (mk.stream) mk.stream.getTracks().forEach((x) => x.stop());
  mk.stream = null;
}
async function viewMock() {
  leaveHooks.push(mockStop);
  const d = await api("/api/mock");
  const mockT = (k) => t(d.test && d.test.lang === "ko" ? k + "_ko" : k);
  if (d.lang_soon) { render(`<div class="page-head">${backBtn("#/record")}</div><div class="card center stack"><h3>${esc(t("mock_lang_soon"))}</h3></div>`); return; }
  if (!d.test) return;
  const L = d.limits, T = d.test;
  render(`
    <div class="page-head">${backBtn("#/record")}<span class="tag accent">${esc(t("mock_left_" + L.per, { n: L.left }))}</span></div>
    <h1 style="margin-bottom:16px">${esc(mockT("mock_title"))}</h1>
    <div class="stack">
      ${[1, 2, 3].map((n) => `<div class="card row mock-part"><span class="num">${n}</span><div><b>${esc(t("mock_p" + n))}</b>
        <div class="muted small">${esc(t("mock_p" + n + "_sub"))}</div></div></div>`).join("")}
      ${L.left > 0 ? `<button class="btn block big" id="mockGo">${icon("mic")} ${esc(t("mock_start"))}</button>`
        : `<div class="card center stack"><h3>${esc(t("mock_none_left"))}</h3>
            ${S.me.plan !== "pro" ? `<a class="btn small" href="#/plans">${icon("spark")} ${esc(t("upgrade"))}</a>` : ""}</div>`}
    </div>`);
  const go1 = $("#mockGo");
  if (!go1) return;
  go1.onclick = async () => {
    try {
      mk.stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
    } catch (e) { toast(t("mic_denied")); return; }
    mk.blobs = [];
    mockQuestions(T, 1);
  };
}
function mockVoice(T, part, i, then) {
  // the examiner reads the question; the recording is paused meanwhile, so the voice is not scored
  if (mk.voice) mk.voice.pause();
  const a = new Audio(`/api/mock/voice/${T.id}/${part}/${i}`);
  mk.voice = a;
  let done = false;
  const finish = () => { if (done) return; done = true; clearTimeout(guard); if (mk.voice === a) then(); };
  const guard = setTimeout(finish, 15000);
  a.onended = finish; a.onerror = finish;
  a.play().catch(finish);
}
function mockRecorder() {
  const mime = pickMime(false);
  mk.chunks = [];
  mk.rec = new MediaRecorder(mk.stream, mime ? { mimeType: mime, audioBitsPerSecond: 64000 } : undefined);
  mk.rec.ondataavailable = (e) => { if (e.data.size) mk.chunks.push(e.data); };
  return new Promise((resolve) => {
    mk.rec.onstop = () => {
      const type = (mk.rec && mk.rec.mimeType) || mime || "audio/webm";
      resolve(new Blob(mk.chunks, { type }));
    };
  });
}
function mockScreen(title, body) {
  render(`
    <div class="page-head"><span class="tag accent">${esc(title)}</span><span class="rec-dot" id="recDot"></span></div>
    <div class="stack mock">${body}</div>`);
}
function mockQuestions(T, n) {
  // Part 1 (n = 1) or Part 3 (n = 3): one recording, the player taps Next after each answer
  const part = n === 1 ? "p1" : "p3", qs = T[part], [minS, maxS] = T.timing[part];
  const done = mockRecorder();
  let i = 0, qStart = 0, listening = true;
  mk.rec.start(1000); mk.rec.pause();
  const ask = () => {
    listening = true; qStart = 0;
    mockScreen(`${t("part_n", { n })}${n === 1 ? " · " + T.p1_topic : ""}`, `
      <div class="muted small">${esc(t("question_n", { i: i + 1, n: qs.length }))}</div>
      <div class="hero"><div class="q" style="margin-bottom:0">${esc(qs[i])}</div></div>
      <p class="timer center" id="mkTime">${esc(t("examiner_speaking"))}</p>
      <button class="btn block big" id="mkNext" disabled>${esc(i + 1 < qs.length ? t("next_question") : t("finish_part"))}</button>`);
    $("#mkNext").onclick = next;
    mockVoice(T, part, i, () => { listening = false; qStart = Date.now(); if (mk.rec && mk.rec.state === "paused") mk.rec.resume(); });
  };
  const next = () => {
    if (listening || (Date.now() - qStart) / 1000 < minS) return;
    if (mk.rec.state === "recording") mk.rec.pause();
    i += 1;
    if (i < qs.length) { ask(); return; }
    clearInterval(mk.loop);
    mk.rec.stop();
  };
  clearInterval(mk.loop);
  mk.loop = setInterval(() => {
    if (listening) return;
    const s = (Date.now() - qStart) / 1000;
    const el = document.getElementById("mkTime"), b = document.getElementById("mkNext"), dot = document.getElementById("recDot");
    if (el) el.textContent = mmss(s);
    if (dot) dot.classList.add("on");
    if (b) b.disabled = s < minS;
    if (s >= maxS) next();
  }, 250);
  ask();
  done.then((blob) => { mk.blobs[n - 1] = blob; n === 1 ? mockCueCard(T) : mockSend(T); });
}
function mockCueCard(T) {
  const c = T.p2, prep = T.timing.p2_prep, [minS, maxS] = T.timing.p2;
  let phase = "listen", t0 = 0, done = null;
  mockScreen(t("part_n", { n: 2 }), `
    <div class="cue card"><b>${esc(c.title)}</b><div class="muted small" style="margin-top:8px">${esc(t("you_should_say"))}</div>
      <ul>${c.points.map((p) => `<li>${esc(p)}</li>`).join("")}</ul></div>
    <div class="muted small center" id="mkPhase">${esc(t("examiner_speaking"))}</div>
    <p class="timer center" id="mkTime"></p>
    <button class="btn block big" id="mkBtn" disabled>${esc(t("start_speaking"))}</button>`);
  const talk = () => {
    phase = "talk"; t0 = Date.now();
    done = mockRecorder(); mk.rec.start(1000);
    $("#mkPhase").textContent = t("rec_now");
    $("#mkBtn").textContent = t("finish_part");
    done.then((blob) => { mk.blobs[1] = blob; mockQuestions(T, 3); });
  };
  const stop = () => { clearInterval(mk.loop); if (mk.rec && mk.rec.state !== "inactive") mk.rec.stop(); };
  $("#mkBtn").onclick = () => {
    if (phase === "prep") talk();
    else if (phase === "talk" && (Date.now() - t0) / 1000 >= minS) stop();
  };
  mockVoice(T, "p2", 0, () => { phase = "prep"; t0 = Date.now(); $("#mkPhase").textContent = t("prep_time"); $("#mkBtn").disabled = false; });
  clearInterval(mk.loop);
  mk.loop = setInterval(() => {
    const el = document.getElementById("mkTime"), b = document.getElementById("mkBtn"), dot = document.getElementById("recDot");
    if (!el || phase === "listen") return;
    const s = (Date.now() - t0) / 1000;
    if (phase === "prep") { el.textContent = mmss(Math.max(prep - s, 0)); if (s >= prep) talk(); return; }
    el.innerHTML = `${mmss(s)} <small>/ ${mmss(maxS)}</small>`;
    if (dot) dot.classList.add("on");
    b.disabled = s < minS;
    if (s >= maxS) stop();
  }, 250);
}
function mockSend(T) {
  if (mk.stream) mk.stream.getTracks().forEach((x) => x.stop());
  mk.stream = null;
  mockScreen(t(T.lang === "ko" ? "mock_title_ko" : "mock_title"), `<div class="card analysing"><div class="spinner"></div><h2 id="upText">${esc(t("uploading", { pct: 0 }))}</h2>
    <div class="progress-line" style="margin-top:14px"><i id="upBar"></i></div><div class="error center" id="err"></div></div>`);
  const fd = new FormData();
  fd.append("set", T.id);
  mk.blobs.forEach((b, k) => fd.append(`part${k + 1}`, b, `part${k + 1}.${extFor(b.type)}`));
  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/mock");
  xhr.setRequestHeader("X-SC", "1");
  xhr.upload.onprogress = (e) => {
    if (!e.lengthComputable) return;
    const pct = Math.round(100 * e.loaded / e.total);
    const bar = document.getElementById("upBar"), tx = document.getElementById("upText");
    if (bar) bar.style.width = pct + "%";
    if (tx) tx.textContent = t("uploading", { pct });
  };
  xhr.onload = () => {
    let res = {};
    try { res = JSON.parse(xhr.responseText); } catch (e) { /* not JSON */ }
    if (res.ok) { go(`#/result/${res.id}`); return; }
    const er = document.getElementById("err");
    if (er) er.textContent = errText(res);
  };
  xhr.onerror = () => { const er = document.getElementById("err"); if (er) er.textContent = t("err_network"); };
  xhr.send(fd);
}

// ------------------------------------------------------------------ start
(async function start() {
  fillIcons(document.body);
  await setLang(guessLang());
  await refreshMe();
  await route();
  if (S.me) queueRestore();
  setInterval(checkChallenges, 8000);
  setTimeout(checkChallenges, 1500);
  setTimeout(checkDailyReward, 4000);
  setInterval(checkDailyReward, 30 * 60 * 1000);
})();
