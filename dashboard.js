// Firm dashboard: login, my leads, lead board, my page, account.
// Talks to Supabase from the browser. What each firm can see is enforced by the
// database's row level security (see supabase/schema.sql), not by this file.
(function () {
  const cfg = JSON.parse(document.getElementById("dash-config").textContent);
  const app = document.getElementById("dash");
  if (!cfg.url || !window.supabase) {
    app.innerHTML = '<p class="msg"><strong>Firm logins open soon.</strong> Claim your listing and we will email you your login as soon as it is ready.</p>';
    return;
  }
  const sb = window.supabase.createClient(cfg.url, cfg.anon);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = (p) => "£" + (p / 100).toFixed(p % 100 ? 2 : 0);
  const town = (t) => cfg.towns[t] || t;
  const trade = (t) => cfg.trades[t] || t;
  const day = (d) => new Date(d).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
  const params = new URLSearchParams(location.search);
  let firm = null, tab = params.get("tab") || "leads";

  function say(el, text, bad) { el.textContent = text; el.className = "dash-note" + (bad ? " bad" : ""); }

  // ---------- logged out ----------
  function loginView() {
    app.innerHTML = `<form class="dash-box" id="login"><h2>Log in</h2>
      <label>Email<input type="email" name="email" autocomplete="username" required></label>
      <label>Password<input type="password" name="password" autocomplete="current-password" required></label>
      <button class="btn" type="submit">Log in</button>
      <button class="linkish" type="button" id="forgot">Forgot your password, or first time here?</button>
      <p class="dash-note" id="note" aria-live="polite"></p></form>`;
    const f = app.querySelector("#login"), note = app.querySelector("#note");
    f.onsubmit = async (e) => {
      e.preventDefault();
      say(note, "Logging in…");
      const { error } = await sb.auth.signInWithPassword({ email: f.email.value.trim(), password: f.password.value });
      if (error) say(note, "That email and password don't match. Try again or reset your password.", true);
    };
    app.querySelector("#forgot").onclick = async () => {
      const email = f.email.value.trim();
      if (!email) return say(note, "Type your email above first, then press this again.", true);
      await sb.auth.resetPasswordForEmail(email, { redirectTo: location.origin + location.pathname });
      say(note, "If that email has a firm login, we've sent a link to set your password. Check your inbox.");
    };
  }

  function setPasswordView() {
    app.innerHTML = `<form class="dash-box" id="setpw"><h2>Choose your password</h2>
      <label>New password (at least 10 characters)<input type="password" name="pw" minlength="10" autocomplete="new-password" required></label>
      <button class="btn" type="submit">Save password</button><p class="dash-note" id="note" aria-live="polite"></p></form>`;
    const f = app.querySelector("#setpw");
    f.onsubmit = async (e) => {
      e.preventDefault();
      const { error } = await sb.auth.updateUser({ password: f.pw.value });
      if (error) return say(app.querySelector("#note"), error.message, true);
      history.replaceState(null, "", location.pathname);
      start();
    };
  }

  // ---------- logged in ----------
  async function start() {
    const { data: { session } } = await sb.auth.getSession();
    if (!session) return loginView();
    const { data } = await sb.from("firms").select("*").maybeSingle();
    firm = data;
    if (!firm) {
      app.innerHTML = `<div class="dash-box"><h2>Nearly there</h2><p>Your login works, but it isn't linked to a firm yet. We'll link it within one working day. Questions? Email listings@toptradesnearme.co.uk.</p><button class="btn ghost" id="out">Log out</button></div>`;
      app.querySelector("#out").onclick = () => sb.auth.signOut();
      return;
    }
    shell();
  }

  function shell() {
    const tabs = [["leads", "My leads"], ["board", "Buy leads"], ["page", "My page"], ["account", "Account"]];
    app.innerHTML = `<div class="dash-head"><div><p class="stamp">Logged in</p><h2>${esc(firm.name)}</h2></div>
      <a class="btn ghost" href="/firm/${esc(firm.slug)}/">View my public page</a></div>
      <div class="dash-stats" id="stats"></div>
      <nav class="dash-tabs" role="tablist">${tabs.map(([k, v]) => `<button role="tab" data-tab="${k}" aria-selected="${k === tab}">${v}</button>`).join("")}</nav>
      <section id="pane" class="dash-pane"></section>`;
    app.querySelectorAll("[data-tab]").forEach((b) => (b.onclick = () => { tab = b.dataset.tab; shell(); }));
    stats();
    ({ leads, board, page, account })[tab]();
  }

  async function stats() {
    const { data } = await sb.from("lead_purchases").select("amount_pence, created_at");
    const all = data || [], since = new Date(); since.setDate(1); since.setHours(0, 0, 0, 0);
    const month = all.filter((p) => new Date(p.created_at) >= since);
    const { count } = await sb.from("lead_board").select("*", { count: "exact", head: true }).eq("mine", false).filter("sold", "lt", 3);
    document.getElementById("stats").innerHTML =
      `<div><b>${month.length}</b><span>leads this month</span></div><div><b>${all.length}</b><span>leads in total</span></div>` +
      `<div><b>${count ?? 0}</b><span>leads you can buy now</span></div>`;
  }

  const pane = () => document.getElementById("pane");

  async function leads() {
    const { data, error } = await sb.from("lead_purchases")
      .select("created_at, exclusive, amount_pence, leads(id, trade, town, summary, created_at, lead_contacts(name, phone, email, postcode, details))")
      .order("created_at", { ascending: false });
    if (error) return (pane().innerHTML = `<p class="dash-note bad">Couldn't load your leads. Try again in a minute.</p>`);
    const bought = params.get("bought");
    const head = bought ? `<p class="dash-note">Payment received. If your new lead isn't below yet, it will be in a few seconds: <a href="?tab=leads">refresh</a>.</p>` : "";
    if (!data.length) return (pane().innerHTML = head + `<p>No leads yet. When a homeowner near you asks for quotes, it shows up under <a href="?tab=board">Buy leads</a>.</p>`);
    pane().innerHTML = head + `<ul class="dash-list">${data.map((p) => {
      const l = p.leads, c = l.lead_contacts || {};
      return `<li><p class="rv-head"><b>${esc(trade(l.trade))}, ${esc(town(l.town))}</b> · bought ${day(p.created_at)} · ${p.exclusive ? "exclusive" : "shared with up to 2 others"} · ${money(p.amount_pence)}</p>
        <p>${esc(l.summary)}</p>
        <p class="contact"><b>${esc(c.name)}</b>${c.phone ? ` · <a href="tel:${esc(c.phone)}">${esc(c.phone)}</a>` : ""}${c.email ? ` · <a href="mailto:${esc(c.email)}">${esc(c.email)}</a>` : ""}${c.postcode ? ` · ${esc(c.postcode)}` : ""}</p>
        ${c.details ? `<p class="msg">${esc(c.details)}</p>` : ""}</li>`;
    }).join("")}</ul><p class="msg">Use these details only to quote for this job. Wrong number or a fake job? Email listings@toptradesnearme.co.uk within 7 days for a credit.</p>`;
  }

  async function board() {
    const { data, error } = await sb.from("lead_board").select("*").order("created_at", { ascending: false });
    if (error) return (pane().innerHTML = `<p class="dash-note bad">Couldn't load leads. Try again in a minute.</p>`);
    const mineFirst = (data || []).filter((l) => !l.mine && l.sold < l.max_buyers)
      .sort((a, b) => (firm.towns.includes(b.town) - firm.towns.includes(a.town)));
    if (!mineFirst.length) return (pane().innerHTML = `<p>No open leads for your trade right now. We'll text you when one comes in.</p>`);
    pane().innerHTML = `<ul class="dash-list">${mineFirst.map((l) => `<li>
      <p class="rv-head"><b>${esc(trade(l.trade))}, ${esc(town(l.town))}</b>${firm.towns.includes(l.town) ? ' <span class="ok">Your area</span>' : ""} · ${day(l.created_at)} · <b>${l.sold} of ${l.max_buyers}</b> sold</p>
      <p>${esc(l.summary)}</p>
      <p class="cta"><button class="btn" data-buy="${l.id}">Buy for ${money(l.price_pence)}</button>
      ${l.exclusive_price_pence && l.sold === 0 ? `<button class="btn ghost" data-buy="${l.id}" data-excl="1">Buy exclusive for ${money(l.exclusive_price_pence)}</button>` : ""}</p>
      <p class="dash-note" aria-live="polite"></p></li>`).join("")}</ul>
      <p class="msg">You see the homeowner's name and number straight after paying. A shared lead goes to no more than 3 firms. <a href="/terms/">Terms</a> part 6.</p>`;
    pane().querySelectorAll("[data-buy]").forEach((b) => (b.onclick = async () => {
      const note = b.closest("li").querySelector(".dash-note");
      b.disabled = true; say(note, "Taking you to secure payment…");
      const { data, error } = await sb.functions.invoke("buy-lead", { body: { lead_id: b.dataset.buy, exclusive: !!b.dataset.excl } });
      if (error || !data?.url) {
        let msg = "Something went wrong. Please try again.";
        try { msg = (await error.context.json()).error || msg; } catch (_) {}
        b.disabled = false; return say(note, msg, true);
      }
      location.href = data.url;
    }));
  }

  async function page() {
    const { data: reqs } = await sb.from("change_requests").select("status, created_at, note").order("created_at", { ascending: false }).limit(5);
    const f = firm;
    pane().innerHTML = `<form class="dash-box wide" id="edit"><p>Change what shows on your public page. We check every change and put it live within one working day.</p>
      <label>About your firm<textarea name="about" rows="4" maxlength="800">${esc(f.about)}</textarea></label>
      <label>Services (one per line)<textarea name="services" rows="4">${esc((f.services || []).join("\n"))}</textarea></label>
      <label>Phone<input name="phone" value="${esc(f.phone)}" inputmode="tel"></label>
      <label>Website<input name="website" type="url" value="${esc(f.website)}" placeholder="https://"></label>
      <fieldset><legend>Towns you want leads from</legend><div class="dash-towns">${Object.entries(cfg.towns).map(([k, v]) =>
        `<label><input type="checkbox" name="towns" value="${k}"${f.towns.includes(k) ? " checked" : ""}>${esc(v)}</label>`).join("")}</div></fieldset>
      <button class="btn" type="submit">Send changes</button><p class="dash-note" id="note" aria-live="polite"></p>
      <p class="msg">For photos or a new logo, use the <a href="/for-firms/">change my listing form</a>.</p></form>
      ${reqs && reqs.length ? `<h3>Recent changes</h3><ul class="dash-list">${reqs.map((r) => `<li>${day(r.created_at)}: ${esc({ pending: "waiting for us to check", approved: "live", rejected: "not accepted" }[r.status])}${r.note ? " · " + esc(r.note) : ""}</li>`).join("")}</ul>` : ""}`;
    const form = pane().querySelector("#edit");
    form.onsubmit = async (e) => {
      e.preventDefault();
      const changes = {
        about: form.about.value.trim(), phone: form.phone.value.trim(), website: form.website.value.trim(),
        services: form.services.value.split("\n").map((s) => s.trim()).filter(Boolean),
        towns: [...form.querySelectorAll("[name=towns]:checked")].map((i) => i.value),
      };
      const { error } = await sb.from("change_requests").insert({ firm_id: f.id, changes });
      say(form.querySelector("#note"), error ? "Couldn't send that. Please try again." : "Thanks, we've got your changes and will check them within one working day.", !!error);
      if (!error) setTimeout(page, 1500);
    };
    pane().querySelector(".dash-towns").closest("fieldset").hidden = Object.keys(cfg.towns).length > 400;
  }

  function account() {
    pane().innerHTML = `<div class="dash-box wide"><h3>Billing</h3><p>Update your card, download invoices, switch to yearly or cancel your sponsored spot.</p>
      ${cfg.billing ? `<p class="cta"><a class="btn ghost" href="${esc(cfg.billing)}">Manage billing</a></p>` : "<p>Email listings@toptradesnearme.co.uk.</p>"}
      <h3>Password</h3><form id="pw"><label>New password (at least 10 characters)<input type="password" name="pw" minlength="10" autocomplete="new-password" required></label>
      <button class="btn ghost" type="submit">Change password</button><p class="dash-note" id="note" aria-live="polite"></p></form>
      <h3>Log out</h3><button class="btn ghost" id="out">Log out</button></div>`;
    pane().querySelector("#pw").onsubmit = async (e) => {
      e.preventDefault();
      const { error } = await sb.auth.updateUser({ password: e.target.pw.value });
      say(pane().querySelector("#note"), error ? error.message : "Password changed.", !!error);
    };
    pane().querySelector("#out").onclick = () => sb.auth.signOut();
  }

  sb.auth.onAuthStateChange((event) => {
    if (event === "PASSWORD_RECOVERY") return setPasswordView();
    if (event === "SIGNED_OUT") { firm = null; loginView(); }
    if (event === "SIGNED_IN" && !firm && !/type=(invite|recovery)/.test(location.hash)) start();
  });
  if (/type=(invite|recovery)/.test(location.hash)) {
    sb.auth.getSession().then(() => setPasswordView());
  } else start();
})();
