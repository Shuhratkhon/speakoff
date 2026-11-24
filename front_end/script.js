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
  const opts = { method: method || (body ? "POST" : "GET"), headers: { "X-SC": "1" }, credentials: "same-origin" };
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

// ------------------------------------------------------------------ router
const ROUTES = {
  welcome: viewWelcome, signup: viewSignup, verify: viewVerify, create: viewCreate, signin: viewSignin,
  home: viewHome, progress: viewProgress, record: viewRecord, ranked: viewRanked, profile: viewProfile,
  result: viewResult, plans: viewPlans, match: viewMatch, u: viewUser, friends: viewFriends, challenge: viewChallenge, leaderboard: viewLeaderboard,
};
const PUBLIC = new Set(["welcome", "signup", "verify", "create", "signin"]);
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
  const tab = { result: "progress", plans: "profile", match: "ranked", u: "ranked", friends: "profile", challenge: "profile", leaderboard: "ranked" }[view] || view;
  tabbar.querySelectorAll("[data-tab]").forEach((a) => a.classList.toggle("on", a.dataset.tab === tab));
  window.scrollTo(0, 0);
  S.view = view;
  await ROUTES[view](arg);
  fillIcons(app);
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
function langSelect(id) {
  return `<select class="input" id="${id}" aria-label="${esc(t("app_language"))}">${Object.entries(S.langs)
    .map(([c, n]) => `<option value="${c}" ${c === S.lang ? "selected" : ""}>${esc(n)}</option>`).join("")}</select>`;
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
    go("#/home");
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

// ------------------------------------------------------------------ shared pieces
function ring(score, size = 132, label) {
  const r = 52, c = 2 * Math.PI * r, pct = Math.max(0, Math.min(100, score || 0)) / 100;
  return `<div class="ring ${size < 100 ? "sm" : ""}" style="width:${size}px;height:${size}px">
    <svg viewBox="0 0 120 120"><circle cx="60" cy="60" r="${r}" fill="none" stroke="var(--surface-2)" stroke-width="10"/>
    <circle cx="60" cy="60" r="${r}" fill="none" stroke="currentColor" class="${cls(score)}" stroke-width="10" stroke-linecap="round"
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
    const pic = d.state === "claimed" ? icon("check") : d.state === "missed" ? "–" : d.kind === "frame" ? `<span class="mini-frame"></span>` : coin();
    return `<div class="cal-day ${d.state} ${special}">
        <span class="cal-n">${esc(t("day_n", { n: d.n }))}</span>
        <span class="cal-coin">${pic}</span>
        <b>${d.kind === "frame" ? esc(t("cal_frame")) : d.amount}</b></div>`;
  };
  return `<div class="cal-head"><div class="eyebrow">${esc(t("daily_rewards"))}</div></div>
    <div class="cal-days" id="calDays">${c.days.map(box).join("")}
      <div class="cal-day future ${c.future.state}"><span class="future-t">${esc(t("future_rewards"))}</span><span class="future-arrow">→</span></div></div>
    ${c.can_claim ? `<button class="btn" id="claimBtn">${c.next_kind === "frame" ? `<span class="mini-frame"></span> ${esc(t("collect_frame"))}` : `${coin()} ${esc(t("collect_n", { n: c.next_amount }))}`}</button>`
      : `<div class="cal-done">${icon("check")} ${esc(t("come_back_tomorrow"))}</div>`}`;
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
  return `<a class="credits-pill" href="#/home" title="${esc(t("credits"))}">${coin()}<b>${(S.me && S.me.credits || 0).toLocaleString()}</b></a>`;
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
  toast(r.reward.kind === "frame" ? `🖼️ ${t("new_frame", { name: t("frame_streak") })}` : `+${r.reward.amount} ${t("credits")}`);
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
      ${daily ? `<div class="hero"><div class="eyebrow">${esc(t("question"))}</div><div class="q" style="margin-bottom:0">${esc(question)}</div></div>` : ""}
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
        <div class="timer" id="timer">0:00 <small>/ ${mmss(max)}</small></div>
        <button class="rec-btn" id="recBtn" aria-label="${esc(t("rec_start"))}">
          <svg class="track" viewBox="0 0 120 120"><circle cx="60" cy="60" r="56" fill="none" stroke="var(--surface-2)" stroke-width="6"/>
            <circle id="minArc" cx="60" cy="60" r="56" fill="none" stroke="var(--border)" stroke-width="6" stroke-dasharray="${2 * Math.PI * 56 * 60 / max} 999"/>
            <circle id="arc" cx="60" cy="60" r="56" fill="none" stroke="var(--bad)" stroke-width="6" stroke-linecap="round" stroke-dasharray="0 999"/></svg>
          <span class="core">${icon("mic")}</span>
        </button>
        <p class="muted small center" id="recHint">${esc(t("rec_hint", { max: mmss(max) }))}</p>
        <div id="after" class="stack" style="width:100%" hidden></div>
      </div>
      <label class="drop" id="drop">${icon("upload")} <b>${esc(t("or_upload"))}</b><div class="hint">${esc(t("upload_hint", { max: mmss(max) }))}</div>
        <input type="file" id="file" accept="audio/*,video/*" hidden></label>
      <div id="sendBox" class="stack" hidden><div class="progress-line"><i id="upBar"></i></div><p class="muted small center" id="upText"></p></div>
      <div class="error center" id="err"></div>
    </div>`);

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
    $("#modeSeg").style.opacity = .5;
    $("#drop").hidden = true;
    rec.timer = setInterval(() => {
      const s = (Date.now() - rec.start) / 1000;
      $("#timer").innerHTML = `<span class="pulse"></span>${mmss(s)} <small>/ ${mmss(max)}</small>`;
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
    const on = r.chosen.includes(s), v = r.scores[s];
    return `<div class="sec ${on ? "" : "off"}"><div class="name">${esc(t("sec_" + s))}</div>
      <div class="val ${on ? cls(v) : ""}">${on ? v : "0"}${on ? "" : ` <small>${esc(t("not_chosen"))}</small>`}</div>
      <div class="bar ${on ? cls(v) : ""}"><i style="width:${on ? v : 0}%"></i></div></div>`;
  };
  const g = r.grammar, f = r.fluency, v = r.vocabulary, p = r.pronunciation, cam = r.camera;
  render(`
    <div class="page-head"><div><div class="date">${esc(fmtDate(r.created, true))} · ${esc(t(r.mode === "video" ? "mode_video" : "mode_audio"))}</div>
      <h1>${esc(t("overall"))}</h1></div>${r.is_daily ? `<span class="tag accent">${esc(t("daily_badge"))}</span>` : ""}</div>
    <div class="stack">
      ${r.question ? `<div class="card"><div class="card-title">${esc(t("question"))}</div><p>${esc(r.question)}</p></div>` : ""}
      <div class="card row" style="gap:18px">
        ${ring(r.overall, 132, "/ 100")}
        <div class="levels">
          <div>${levelHtml(lv.cefr)}</div>
          <div class="level-row"><span class="muted">${esc(t("ielts"))}</span><b>${esc(lv.ielts)}</b></div>
          <div class="level-row"><span class="muted">${esc(t("toefl"))}</span><b>${esc(lv.toefl)}/6 · ${esc(lv.toefl_old)}/30</b></div>
        </div>
      </div>
      ${lv.too_short ? `<div class="notice">${esc(t("estimate_note"))}</div>` : ""}
      ${r.trimmed ? `<div class="notice warn">${esc(t("trimmed", { max: mmss(r.max_s) }))}</div>` : ""}
      ${r.repetition ? `<div class="notice bad">${esc(t("repetition_warn", { pct: r.repetition.pct, cap: r.repetition.cap }))}</div>` : ""}
      <div class="grid2">${SECTIONS.map(secCard).join("")}</div>
      ${cam ? `<div class="card row between"><div><h3>${esc(t("sec_on_camera"))}</h3><p class="muted small">${esc(t("on_camera_note"))}</p></div>
        <div class="val ${cls(cam.score)}" style="font-size:28px;font-weight:800">${cam.score}</div></div>` : ""}

      <div class="card">
        <div class="row between" style="margin-bottom:12px"><h2>${esc(t("feedback"))}</h2>
          <button class="btn small" id="play">${icon("play")} ${esc(t("play_feedback"))}</button></div>
        <audio id="voice" hidden controls></audio>
        <div class="feedback-text">${r.feedback.split("\n").map((x) => `<p>${esc(x)}</p>`).join("")}</div>
      </div>

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
        <dl class="kv"><dt>${esc(t("b1_words"))}</dt><dd>${v.b1}%</dd><dt>${esc(t("b2_words"))}</dt><dd>${v.b2}%</dd>
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
      <div class="card"><div class="card-title">${esc(t("your_recording"))}</div>
        ${r.audio ? `<audio src="/api/recordings/${r.id}/audio" controls preload="none"></audio>` : `<p class="muted">${esc(t("recording_deleted", { n: r.keep_days }))}</p>`}</div>
    </div>`);

  $("#play").onclick = async () => {
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
            <div class="meta"><div class="t">${esc(h.question || (h.status === "done" ? `${t("level")} ${levelParts(h.cefr)[0]}` : t("analysing")))}</div>
              <div class="s">${icon(h.mode === "video" ? "video" : "mic")} ${esc(fmtDate(h.created, true))}${h.is_daily ? ` · ${esc(t("daily_badge"))}` : ""}</div></div>
          </div>`).join("") : `<p class="empty">${esc(t("no_history"))}</p>`}
      </div>
    </div>`);
}

// ------------------------------------------------------------------ ranks, avatars, frames
const RANK_COLOR = Object.fromEntries(RANKS);
const ROMAN = ["", "I", "II", "III"];
function rankLabel(r) { return r ? `${t("rank_" + r.rank)}${r.div ? " " + ROMAN[r.div] : ""}` : ""; }
function emblem(r, size = 52) {
  const c = RANK_COLOR[r.rank];
  return `<div class="emblem" style="width:${size}px;height:${Math.round(size * 1.12)}px;font-size:${Math.round(size * .36)}px;background:linear-gradient(160deg, ${c}, ${c}99)">${r.div ? ROMAN[r.div] : "★"}</div>`;
}
function avatarHtml(c, size = 72) {
  const initial = esc((c.username || "?")[0].toUpperCase());
  const inner = c.bot ? `<span class="bot-face">🤖</span>` : c.photo ? `<img src="${esc(c.photo)}" alt="">` : initial;
  return `<div class="ava f-${esc(c.frame || "none")}" style="--s:${size}px"><div class="in" style="font-size:${Math.round(size * .42)}px">${inner}</div></div>`;
}
function skillChips(skills) {
  return (skills || []).map((s) => `<span class="skill-chip r-${s.rarity}">${s.icon} ${esc(t("sk_" + s.id))} <b>x${s.count}</b></span>`).join("");
}
function awardName(a) {
  return a.kind === "skill" ? `${t("sk_" + a.id)} x${a.count}` : `${t("ac_" + a.id)} ${achTierLabel(a.id, a.target)}`;
}
function achTierLabel(id, target) {
  if (id === "best_rank") return rankLabel({ rank: RANKS[Math.min(6, Math.floor(target / 300))][0], div: target >= 1800 ? null : 3 });
  return `x${target >= 1000 ? target.toLocaleString() : target}`;
}
function awardToast(list) {
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
        <div class="row" style="gap:16px">${emblem(r, 66)}
          <div style="flex:1;min-width:0"><div class="eyebrow">${esc(t("your_rank"))}</div>
            <div class="rank-name">${esc(rankLabel(r))}</div>
            <div class="muted small"><b style="color:var(--text)">${r.rp}</b> ${esc(t("rp"))} · ${esc(r.next ? t("next_div", { n: r.next - r.rp, rank: nextName }) : t("top_rank"))}</div></div></div>
        <div class="bar" style="margin-top:14px;color:${RANK_COLOR[r.rank]}"><i style="width:${pct}%"></i></div>
        <div class="muted small" style="margin-top:8px">${esc(t("season_ends", { date: fmtDate(d.season_end) }))}</div>
      </div>
      ${d.live ? `<a class="btn block" href="#/match/${d.live}">${icon("trophy")} ${esc(t("back_to_match"))}</a>`
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
            <div class="meta"><div class="t">${esc(h.opp_name)}${h.kind === "ghost" ? ` <span class="tag">${esc(t("replay_tag"))}</span>` : h.kind === "friendly" ? ` <span class="tag accent">${esc(t("friendly_tag"))}</span>` : ""}</div>
              <div class="s">${h.me ?? "–"} : ${h.opp ?? "–"} · ${esc(fmtDate(h.created * 1000, true))}</div></div>
            <b class="${(h.rp_delta || 0) >= 0 ? "good" : "bad"}">${h.rp_delta == null ? "" : (h.rp_delta > 0 ? "+" : "") + h.rp_delta}</b>
          </div>`).join("") : `<p class="empty">${esc(t("no_matches"))}</p>`}
      </div>
    </div>`);
}

let lbScope = store("sc-lb") || "national";
async function viewLeaderboard() {
  render(`<div class="splash"><div class="spinner"></div></div>`);
  const d = await api(`/api/ranked/leaderboard?scope=${lbScope}`);
  if (!d.board) return;
  const meRow = d.me_place ? `<div class="board-row me"><span class="pos">${d.me_place}</span>${avatarHtml(d.me, 40)}
    <span class="nm">${esc(S.me.username)} ${flag(d.country)}</span>${emblem(d.me.rank, 22)}<span class="muted small">${d.me.rank.rp}</span></div>` : "";
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
            <span class="nm">${esc(b.username)} ${lbScope === "global" ? flag(b.country) : ""}</span>${emblem(b.rank, 22)}<span class="muted small">${b.rank.rp}</span></a>`).join("")
          : `<p class="empty">${esc(t("no_matches"))}</p>`}
      </div>
    </div>`);
  $$("#lbSeg button").forEach((b) => b.onclick = () => { lbScope = b.dataset.v; store("sc-lb", lbScope); viewLeaderboard(); });
}
function nextDivision(r) {
  const rp = r.next;
  if (rp >= 1800) return { rank: "master", div: null };
  const index = Math.floor(rp / 300), step = Math.floor((rp % 300) / 100);
  return { rank: RANKS[index][0], div: 3 - step };
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
  leaveHooks.push(() => { rkStop(!rk.keep); rk.keep = false; });
  return arg === "search" ? matchSearch() : matchPlay(arg);
}

async function matchSearch() {
  render(`<div class="card analysing"><div class="spinner"></div><h2>${esc(t("mic_check"))}</h2></div>`);
  if (!(await rkMic())) {
    render(`<div class="card center stack" style="padding:28px"><h2>${esc(t("mic_denied"))}</h2>
      <a class="btn" href="#/ranked">${esc(t("back_ranked"))}</a></div>`);
    return;
  }
  const first = await api("/api/ranked/queue", {});
  if (first.state === "found") { rk.keep = true; return go(`#/match/${first.match}`); }
  if (first.state !== "searching") { go("#/ranked"); return; }
  const started = Date.now();
  render(`
    <div class="card analysing search">
      <div class="radar-ping"><span></span><span></span>${avatarHtml(S.me.card, 72)}</div>
      <h2>${esc(t("searching"))}</h2>
      <p class="timer" id="waited" style="margin-top:14px">0:00</p>
      <button class="btn outline" id="cancel" style="margin-top:8px">${esc(t("cancel"))}</button>
    </div>`);
  $("#cancel").onclick = async () => { await api("/api/ranked/leave", {}); go("#/ranked"); };
  leaveHooks.push(() => { if (!rk.keep) api("/api/ranked/leave", {}); });
  rk.loop = setInterval(() => { const el = document.getElementById("waited"); if (el) el.textContent = mmss((Date.now() - started) / 1000); }, 500);
  rk.poll = setInterval(async () => {
    const st = await api("/api/ranked/queue");
    if (st.state === "found") { rk.keep = true; clearInterval(rk.poll); go(`#/match/${st.match}`); }
    else if (st.state === "idle" || st.state === "limit") { clearInterval(rk.poll); go("#/ranked"); }
  }, 1500);
}

function playerCol(p, big) {
  const tags = [p.bot ? t("bot_tag") : "", p.ghost ? t("replay_tag") : ""].filter(Boolean);
  const link = !p.bot && !p.me && p.username !== "—" ? `href="#/u/${encodeURIComponent(p.username)}"` : "";
  return `<a class="pcol ${p.me ? "me" : ""}" ${link}>
    ${avatarHtml(p, big ? 84 : 64)}
    <div class="pname">${esc(p.me ? S.me.username : p.username)}</div>
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
      if (phase !== "vs") { phase = "vs"; drawVs(); }
      const el = document.getElementById("count"); if (el) el.textContent = Math.ceil(m.reveal_at - n);
    } else if (n < m.speak_at) {
      if (phase !== "q") { phase = "q"; drawQuestion(); }
      const el = document.getElementById("count"); if (el) el.textContent = Math.ceil(m.speak_at - n);
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

async function matchWaiting(id) {
  rkStop(true);
  const draw = (m) => {
    const opp = m.players.find((p) => !p.me);
    render(`<div class="card analysing">
      <div class="spinner"></div><h2>${esc(t("scoring"))}</h2>
      <p class="muted" style="margin-top:8px">${esc(t("scoring_sub"))}</p>
      <p class="muted small" style="margin-top:14px">${esc(opp.username)}: ${esc(t("opp_" + (opp.state === "speaking" ? "speaking" : opp.state === "scoring" ? "scoring" : "ready")))}</p>
    </div>`);
  };
  let m = await api(`/api/ranked/match/${id}`);
  if (m.status === "done") return matchResult(m);
  draw(m);
  rk.poll = setInterval(async () => {
    m = await api(`/api/ranked/match/${id}`);
    if (!m.id) return;
    if (m.status === "done") { clearInterval(rk.poll); matchResult(m); fillIcons(app); }
    else draw(m);
  }, 2500);
}

function matchResult(m) {
  const me = m.players.find((p) => p.me), opp = m.players.find((p) => !p.me);
  const res = me.result || "none";
  const scoreCell = (p) => p.overall != null ? `<b class="big-score ${cls(p.overall)}">${p.overall}</b>`
    : `<b class="big-score muted">–</b><div class="muted small">${esc(t(p.error || "ranked_missed", { n: p.error_n }))}</div>`;
  const bars = SECTIONS.map((s) => {
    const a = me.scores ? me.scores[s] : 0, b = opp.scores ? opp.scores[s] : 0;
    return `<div class="cmp"><span class="${a >= b ? "lead" : ""}">${me.scores ? a : "–"}</span>
      <div class="cmp-bars"><i class="l" style="width:${a / 2}%"></i><i class="r" style="width:${b / 2}%"></i></div>
      <span class="${b > a ? "lead" : ""}">${opp.scores ? b : "–"}</span><div class="cmp-name">${esc(t("sec_" + s))}</div></div>`;
  }).join("");
  const delta = me.rp_delta;
  render(`<div class="match stack">
    <div class="result-banner res-${res}">${esc(t(res === "none" ? "no_contest" : "result_" + res))}</div>
    ${m.kind === "friendly" ? `<div class="notice small">${esc(t("friendly_note"))}</div>` : m.kind === "bot" ? `<div class="notice small">${esc(t("match_note_bot"))}</div>` : m.kind === "ghost" ? `<div class="notice small">${esc(t("match_note_ghost", { name: opp.username }))}</div>` : ""}
    <div class="vs-row">
      <div class="stack center">${playerCol(me)}${scoreCell(me)}</div>
      <div class="vs">${esc(t("vs"))}</div>
      <div class="stack center">${playerCol(opp)}${scoreCell(opp)}</div>
    </div>
    <div class="card"><div class="card-title">${esc(t("question"))}</div><p>${esc(m.question || "")}</p></div>
    ${me.scores || opp.scores ? `<div class="card">${bars}</div>` : ""}
    ${delta != null ? `<div class="card row between">
        <div class="row">${emblem(me.rank_after, 40)}<div><div class="lab" style="font-weight:700">${esc(rankLabel(me.rank_after))}</div>
          <div class="muted small">${me.rp_after} ${esc(t("rp"))}</div></div></div>
        <b class="${delta >= 0 ? "good" : "bad"}" style="font-size:24px">${delta > 0 ? "+" : ""}${delta} ${esc(t("rp"))}</b></div>` : ""}
    ${(me.new_awards || []).length ? `<div class="card"><div class="card-title">${esc(t("unlocked"))}</div>
      ${me.new_awards.map((a) => `<div class="award-new"><span class="hexicon sm r-${a.rarity}">${a.icon}</span> <b>${esc(awardName(a))}</b> <span class="tag">${esc(t(a.kind === "skill" ? "tab_skills" : "tab_achievements"))}</span></div>`).join("")}</div>` : ""}
    <a class="btn block" href="#/match/search">${icon("trophy")} ${esc(t("play_again"))}</a>
    <a class="btn block ghost" href="#/ranked">${esc(t("back_ranked"))}</a>
  </div>`);
  if (!m._toasted) { m._toasted = true; awardToast(me.new_awards); }
}

// ------------------------------------------------------------------ statistics (profile)
function radarChart(v) {
  const keys = ["fluency", "grammar", "vocabulary", "pronunciation", "consistency", "win_rate"];
  const labels = [t("sec_fluency"), t("sec_grammar"), t("sec_vocabulary"), t("sec_pronunciation"), t("ax_consistency"), t("st_win_rate")];
  const W = 360, H = 300, cx = 180, cy = 152, R = 100;
  const pt = (i, f) => { const a = -Math.PI / 2 + i * Math.PI / 3; return [cx + R * f * Math.cos(a), cy + R * f * Math.sin(a)]; };
  let svg = `<svg class="radar" viewBox="0 0 ${W} ${H}" role="img"><defs><radialGradient id="radarFill"><stop offset="0" stop-color="#8A5CF6" stop-opacity=".75"/><stop offset="1" stop-color="#3574F0" stop-opacity=".45"/></radialGradient></defs>`;
  for (const f of [1, 2 / 3, 1 / 3]) svg += `<polygon class="rgrid" points="${keys.map((_, i) => pt(i, f).join(",")).join(" ")}"/>`;
  keys.forEach((_, i) => { const [x, y] = pt(i, 1); svg += `<line class="rgrid" x1="${cx}" y1="${cy}" x2="${x}" y2="${y}"/>`; });
  const poly = keys.map((k, i) => pt(i, Math.max(0.04, (v[k] || 0) / 100)).join(",")).join(" ");
  svg += `<polygon class="rarea" points="${poly}"/>`;
  keys.forEach((k, i) => { const [x, y] = pt(i, Math.max(0.04, (v[k] || 0) / 100)); svg += `<circle cx="${x}" cy="${y}" r="3.5" class="rdot"/>`; });
  keys.forEach((k, i) => {
    const [x, y] = pt(i, 1.22);
    const anchor = Math.abs(x - cx) < 8 ? "middle" : x > cx ? "start" : "end";
    svg += `<text x="${x}" y="${y + 4}" text-anchor="${anchor}">${esc(labels[i])}</text><text x="${x}" y="${y + 18}" text-anchor="${anchor}" class="rval">${v[k] || 0}</text>`;
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
    ["st_average", s.average], ["st_perfect", s.perfect], ["st_upsets", s.upsets],
  ];
  return `
    <div class="cstats">${circleStat(s.matches, t("st_matches"), "#D65DB1")}${circleStat(`${s.win_rate}%`, t("st_win_rate"), "#E5B84C")}${circleStat(s.top_score, t("st_top_score"), "#5FB865")}</div>
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
        <div style="min-width:0;flex:1"><h2>${esc(c.username)}</h2>
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
function friendRow(c, buttons) {
  return `<div class="friend-row">
    <a href="#/u/${encodeURIComponent(c.username)}" class="fr-ava">${avatarHtml(c, 46)}${c.online ? `<i class="dot-online" title="${esc(t("online"))}"></i>` : ""}</a>
    <a href="#/u/${encodeURIComponent(c.username)}" class="fr-main"><b>${esc(c.username)}</b>
      <span class="prank">${emblem(c.rank, 16)}<span>${esc(rankLabel(c.rank))} · ${c.rank.rp}</span></span></a>
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
        ${d.friends.length ? d.friends.map((c) => friendRow(c, `<button class="btn small" data-challenge="${esc(c.username)}">${icon("trophy")}</button>`)).join("")
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
  if (accept && r.match) go(`#/match/${r.match}`);
}
const seenChallenges = new Set();
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
        <div style="min-width:0;flex:1"><h2>${esc(m.username)}</h2>
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
        <div class="li"><span class="lab">${esc(t("theme"))}</span>${seg("themeSeg", [["dark", t("theme_dark"), "moon"], ["light", t("theme_light"), "sun"]], m.theme)}</div>
        <div class="li"><span class="lab">${esc(t("ai_voice"))}</span>${seg("voiceSeg", [["female", t("voice_female")], ["male", t("voice_male")]], m.voice)}</div>
        <div class="li"><div><div class="lab">${esc(t("app_language"))}</div><div class="muted small">${esc(t("language_note"))}</div></div>${langSelect("langSel")}</div>
      </div></div>

      <div><div class="card-title">${esc(t("account"))}</div><div class="list">
        ${m.contact.includes(":") ? "" : `<div class="li"><span class="lab">${esc(t(m.contact_type))}</span><span class="val">${esc(m.contact)}</span></div>`}
        ${m.google || m.apple ? `<div class="li"><span class="lab">${esc(t("signed_in_with"))}</span><span class="val">${[m.google ? "Google" : "", m.apple ? "Apple" : ""].filter(Boolean).join(", ")}</span></div>` : ""}
        <div class="li"><span class="lab">${esc(t("username"))}</span><span class="val">${esc(m.username)}</span></div>
        <div class="li"><span class="lab">${esc(t("country"))}</span>${countrySelect("countrySel", m.country)}</div>
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
  async function save(change) {
    const res = await api("/api/settings", change);
    if (res.ok) S.me = res.user;
    return res.ok;
  }
  $$("#themeSeg button").forEach((b) => b.onclick = async () => { setTheme(b.dataset.v); if (await save({ theme: b.dataset.v })) toast(t("saved")); viewProfile(); });
  $$("#voiceSeg button").forEach((b) => b.onclick = async () => { if (await save({ voice: b.dataset.v })) toast(t("saved")); viewProfile(); });
  $("#langSel").onchange = async (e) => { const ok = await save({ lang: e.target.value }); await setLang(e.target.value); viewProfile(); if (ok) toast(t("saved")); };
  $("#countrySel").onchange = async (e) => { if (await save({ country: e.target.value })) toast(t("saved")); };
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
        ? [t("feat_welcome"), t("feat_length", { max: mmss(p.max_s) }), t("feat_keep", { n: p.keep_days }), t("feat_daily_q"), t("feat_progress_simple"), t("feat_ranked", { n: p.ranked })]
        : [p.id === "pro" ? t("feat_unlimited") : t("feat_per_day", { n: p.per_day }), t("feat_length", { max: mmss(p.max_s) }), t("feat_keep", { n: p.keep_days }),
           t("feat_daily_q"), t("feat_progress_full"), t("feat_ranked", { n: p.ranked }), t("feat_no_ads"), ...(p.id === "pro" ? [t("feat_mock"), t("feat_trial")] : [])];
      return `<div class="plan ${p.id === "pro" ? "best" : ""}">
        ${cur === p.id ? `<span class="tag accent badge">${esc(t("current_plan"))}</span>` : period === "yearly" && p.save_pct ? `<span class="tag accent badge">${esc(t("save_pct", { n: p.save_pct }))}</span>` : ""}
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

// ------------------------------------------------------------------ start
(async function start() {
  fillIcons(document.body);
  await setLang(guessLang());
  await refreshMe();
  route();
  setInterval(checkChallenges, 8000);
  setTimeout(checkChallenges, 1500);
})();
