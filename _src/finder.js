/* Town finder: trade picker, postcode lookup (postcodes.io, free) and the map (Leaflet + OpenStreetMap). */
(function () {
  var el = document.getElementById("finder-data");
  if (!el) return;
  var D = JSON.parse(el.textContent);
  var mapEl = document.getElementById("map");
  var form = document.getElementById("finder");
  var out = document.getElementById("pcout");

  function url(t, s) { return D.live ? "/" + t + "/" + s + "/" : t + "-" + s + ".html"; }
  function trade() {
    var c = document.querySelector('input[name="trade"]:checked');
    if (c) return c.value;
    return (mapEl && mapEl.dataset.trade) || Object.keys(D.trades)[0];
  }
  function miles(a, b, c, d) {
    var r = Math.PI / 180, x = Math.sin((c - a) * r / 2), y = Math.sin((d - b) * r / 2);
    return 7917.6 * Math.asin(Math.sqrt(x * x + Math.cos(a * r) * Math.cos(c * r) * y * y));
  }
  function closest(list, lat, lon) {
    var best = null;
    list.forEach(function (t) {
      var d = miles(lat, lon, t.lat, t.lon);
      if (!best || d < best.d) best = { t: t, d: d };
    });
    return best;
  }

  // Area cards follow the chosen trade
  function syncLinks() {
    var t = trade();
    document.querySelectorAll("a[data-area]").forEach(function (a) { a.href = url(t, a.dataset.area); });
    if (form) form.action = D.live ? "/" + t + "/" : t + ".html";
  }
  document.querySelectorAll('input[name="trade"]').forEach(function (r) { r.addEventListener("change", syncLinks); });
  syncLinks();

  function say(parts) {
    out.textContent = "";
    parts.forEach(function (p) {
      if (typeof p === "string") { out.appendChild(document.createTextNode(p)); return; }
      var a = document.createElement("a"); a.href = p.href; a.textContent = p.text; out.appendChild(a);
    });
  }

  function goNear(lat, lon) {
    var t = trade(), live = closest(D.towns, lat, lon), soon = closest(D.soon, lat, lon);
    var ring = miles(lat, lon, D.hub[0], D.hub[1]);
    if (live && live.d <= 12 && !(soon && soon.d < live.d)) {
      say(["Nearest town we cover: " + live.t.n + ". Taking you there…"]);
      location.href = url(t, live.t.s);
      return;
    }
    var msg = [];
    if (soon && soon.d <= 12 && ring <= 62) msg.push("We're adding " + soon.t.n + " soon. ");
    else msg.push(ring > 62 ? "That's outside the area we cover so far. " : "We don't cover that spot yet. ");
    msg.push("The nearest town we cover is ");
    msg.push({ href: url(t, live.t.s), text: live.t.n });
    msg.push(", about " + Math.round(live.d) + " miles away.");
    say(msg);
  }

  if (form) {
    form.addEventListener("submit", function (ev) {
      var pc = document.getElementById("pc").value.trim();
      if (!pc) return; // no postcode: fall through to the trade page
      ev.preventDefault();
      say(["Looking up " + pc.toUpperCase() + "…"]);
      var api = "https://api.postcodes.io/";
      fetch(api + "postcodes/" + encodeURIComponent(pc))
        .then(function (r) {
          if (r.ok) return r.json();
          // Part postcode such as "OX4": try it as an outward code
          var oc = pc.replace(/\s+/g, "").toUpperCase();
          if (oc.length > 4) oc = oc.slice(0, -3);
          return fetch(api + "outcodes/" + encodeURIComponent(oc)).then(function (r2) { return r2.ok ? r2.json() : null; });
        })
        .then(function (j) {
          var res = j && j.result;
          if (!res || res.latitude == null) { say(["We couldn't find that postcode. Check it, or pick your area below."]); return; }
          goNear(res.latitude, res.longitude);
        })
        .catch(function () { say(["Postcode search isn't working right now. Pick your area below."]); });
    });
    var loc = document.getElementById("locate");
    if (loc && navigator.geolocation) {
      loc.hidden = false;
      loc.addEventListener("click", function () {
        say(["Finding you…"]);
        navigator.geolocation.getCurrentPosition(
          function (p) { goNear(p.coords.latitude, p.coords.longitude); },
          function () { say(["Couldn't get your location. Type your postcode instead."]); },
          { timeout: 10000, maximumAge: 600000 });
      });
    }
  }

  if (!mapEl || !window.L) return;
  var area = mapEl.dataset.area;
  var map = L.map(mapEl, { scrollWheelZoom: false, zoomSnap: 0.5 }).setView(D.hub, 8);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  }).addTo(map);
  var ring = L.circle(D.hub, { radius: 96561, color: "#0d6577", weight: 2, dashArray: "6 6", fill: false, interactive: false }).addTo(map);
  var pts = [];
  D.soon.forEach(function (s) {
    if (area && s.a !== area) return;
    L.circleMarker([s.lat, s.lon], { radius: 5, color: "#55656c", weight: 1, fillColor: "#c9d1cf", fillOpacity: 0.95 })
      .bindTooltip(s.n + " · coming soon").addTo(map);
    pts.push([s.lat, s.lon]);
  });
  D.towns.forEach(function (s) {
    if (area && s.a !== area) return;
    var m = L.circleMarker([s.lat, s.lon], { radius: 8, color: "#18252b", weight: 2, fillColor: "#f2c230", fillOpacity: 1 }).addTo(map);
    m.bindTooltip(function () { var t = trade(); return s.n + " · " + s.c[t] + " " + D.trades[t].toLowerCase(); });
    m.on("click", function () { location.href = url(trade(), s.s); });
    pts.push([s.lat, s.lon]);
  });
  if (area && pts.length) map.fitBounds(pts, { padding: [24, 24] });
  else map.fitBounds(ring.getBounds(), { padding: [8, 8] });
})();
