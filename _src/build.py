#!/usr/bin/env python3
"""Builds the Top Trades Near preview site from data.json into ./site/"""
import json, math, html, os, shutil, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(HERE, "data.json")))
LIVE = os.environ.get("LIVE") == "1"
SITE = "https://toptradesnearme.co.uk"
OUT = os.path.join(HERE, "site-live" if LIVE else "site")
os.makedirs(OUT, exist_ok=True)
e = html.escape
BRAND = "Top Trades Near Me"
# Logo mark (map pin with a house), same drawing as brand/logo-mark.svg
MARK = '<svg class="mark" viewBox="0 0 40 40" aria-hidden="true"><path d="M20 1.5C11.2 1.5 4.5 8.3 4.5 16.8C4.5 27.8 20 38.5 20 38.5S35.5 27.8 35.5 16.8C35.5 8.3 28.8 1.5 20 1.5Z" fill="#f2c230"/><path d="M12.5 18.2L20 11.5L27.5 18.2V25.5H12.5Z" fill="#18252b" stroke="#18252b" stroke-width="1.5" stroke-linejoin="round"/><rect x="18.2" y="20" width="3.6" height="5.5" fill="#f2c230"/></svg>'
BRAND_FILES = ["favicon.ico", "favicon.svg", "apple-touch-icon.png", "icon-192.png", "icon-512.png", "logo-mark.svg", "og-image.png", "badge.svg"]

# GoHighLevel forms in the Top Trades Near Me sub-account (rRAiUOKmHY43FAxBFsPm)
FORMS = {"claim": "GPJqPB3I4ubYbyjVMrV9", "listed": "5D9mtepQQLMAKM11lmpK", "quote": "gUv916EvMBG5WQ7pqGPM"}
# Firm accounts. Empty values mean that part is not switched on yet, and the
# page falls back to email. PORTAL = GHL client portal login, BILLING = Stripe
# customer portal login link, FORMS["change"] = "TT - Change my listing" form.
PORTAL = D.get("portal", {}).get("login", "")
BILLING = D.get("portal", {}).get("billing", "")
FORMS["change"] = D.get("portal", {}).get("change_form", "")
FORMS["review"] = D.get("portal", {}).get("review_form", "")
SERVICES = D.get("services", {})  # single-service pages (e.g. flat roofing, damp proofing) for a few towns
FIRMS = D.get("firms", {})  # claimed firms that have a profile page, by slug
CLAIMED = {n: slug for slug, f in FIRMS.items() for n in [f["name"]] + f.get("listed_as", [])}
INDEXNOW_KEY = "7437c4ec36f61a7c86dc2cd2e2ca6ef5"  # public by design: served at /<key>.txt
FORM_JS = '<script src="https://link.msgsndr.com/js/form_embed.js" defer></script>'


def ghl(key, title, height, forward=False, **params):
    """Embed a GHL form. params prefill fields by query key; forward=True also passes this page's own ?query on."""
    fid = FORMS[key]
    src = f"https://api.leadconnectorhq.com/widget/form/{fid}"
    if params:
        src += "?" + urllib.parse.urlencode(params)
    attrs = (f'src="{e(src)}" id="inline-{fid}" data-layout="{{\'id\':\'INLINE\'}}" data-trigger-type="alwaysShow" data-trigger-value="" '
             f'data-activation-type="alwaysActivated" data-activation-value="" data-deactivation-type="neverDeactivate" data-deactivation-value="" '
             f'data-form-name="{e(title)}" data-height="{height}" data-layout-iframe-id="inline-{fid}" data-form-id="{fid}" title="{e(title)}" '
             f'class="ghl" loading="lazy" style="width:100%;height:{height}px;border:none;border-radius:8px"')
    fwd = ("<script>(function(f){if(location.search)f.src=f.src.split('?')[0]+location.search;})"
           f"(document.getElementById('inline-{fid}'));</script>") if forward else ""
    return f"<iframe {attrs}></iframe>{fwd}{FORM_JS}"


def P(name):
    """Link to a standalone page such as claim or privacy."""
    return f"/{name}/" if LIVE else f"{name}.html"


def F(slug):
    """Link to a claimed firm's profile page."""
    return f"/firm/{slug}/" if LIVE else f"firm-{slug}.html"


def claim_link(**params):
    return P("claim") + "?" + urllib.parse.urlencode(params)

FONTS = '' # fonts are self-hosted: @font-face rules at the top of style.css, files in fonts/


# Structured data (schema.org JSON-LD). No ratings in it: Google does not allow review
# stars taken from other sites, and the ranking on the page stays the only place ratings show.
TYPES = {"roofers": "RoofingContractor", "plumbers": "Plumber", "driveways": "HomeAndConstructionBusiness"}
ORG_ID = "https://toptradesnearme.co.uk/#org"


def ld(*objs):
    if not LIVE:
        return ""
    data = {"@context": "https://schema.org", "@graph": list(objs)}
    return '<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + "</script>"


def crumbs_ld(*steps):
    """steps: (name, path) pairs from Home down to this page."""
    return {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, "item": SITE + u} for i, (n, u) in enumerate(steps)]}


def iso_checked():
    import datetime
    return datetime.datetime.strptime(D["checked"], "%d %b %Y").date().isoformat()


def villages(tw):
    return [v.strip() for v in D["towns"][tw]["villages"].split(",") if v.strip()]


def L(t=None, tw=None):
    """Link to a page: folder URLs on the live site, flat files in the preview."""
    if t is None:
        return "/" if LIVE else "index.html"
    if tw is None:
        return f"/{t}/" if LIVE else f"{t}.html"
    return f"/{t}/{tw}/" if LIVE else f"{t}-{tw}.html"


def score(b):
    if "rating" not in b:
        return 0
    r = b["rating"] / b["scale"]
    return r * (math.log10(b["reviews"] + 1) if "reviews" in b else 0.5)


# Areas (counties) group towns. An area gets pages once it has at least one town with listings;
# its "soon" towns only show on the map and area list as coming next. Villages never get pages.
HUB = (51.752, -1.258)  # Oxford: where we started; Revive sponsor distance is measured from here
for a in D["areas"]:
    assert a not in D["towns"], f"area slug {a} clashes with a town slug"
LIVE_AREAS = [a for a in D["areas"] if any(v["area"] == a for v in D["towns"].values())]


def area_towns(a):
    return [tw for tw, v in D["towns"].items() if v["area"] == a]


def miles(p, q):
    la1, lo1, la2, lo2 = map(math.radians, (p[0], p[1], q[0], q[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 7917.6 * math.asin(math.sqrt(h))


def pos(tw):
    return (D["towns"][tw]["lat"], D["towns"][tw]["lon"])


def nearest(tw, n=8):
    others = [o for o in D["towns"] if o != tw]
    return sorted(others, key=lambda o: miles(pos(tw), pos(o)))[:n]


def region():
    names = [D["areas"][a]["name"] for a in LIVE_AREAS]
    return names[0] if len(names) == 1 else "southern and central England"


def count(t, tw):
    return len(D["listings"].get(f"{t}/{tw}", []))


# Weak pages stay up for visitors but ask search engines not to index them (Google's doorway and
# thin-content rules). A page is weak when it lists 3 firms or fewer, or shows exactly the same firms
# as another town's page for that trade. Of two identical pages we keep the town most firms are based
# in (ties: the town added first). Rules, not a fixed list, so pages come back once they grow.
MIN_FIRMS = 4
TOWN_ORDER = {tw: i for i, tw in enumerate(D["towns"])}


def _weak_pages():
    weak, same_as, groups = set(), {}, {}
    for key, items in D["listings"].items():
        t, tw = key.split("/")
        if len(items) < MIN_FIRMS:
            weak.add((t, tw))
        else:
            groups.setdefault((t, tuple(sorted(b["name"] for b in items))), []).append(tw)
    for (t, _), towns in groups.items():
        if len(towns) < 2:
            continue
        def based(tw):
            name = D["towns"][tw]["name"].lower()
            return sum(1 for b in D["listings"][f"{t}/{tw}"] if b.get("base", "").lower() == name)
        keep = sorted(towns, key=lambda tw: (-based(tw), TOWN_ORDER[tw]))[0]
        for tw in towns:
            if tw != keep:
                weak.add((t, tw))
                same_as[(t, tw)] = keep
    return weak, same_as


WEAK, SAME_AS = _weak_pages()


def finder_data():
    towns = [{"s": tw, "n": v["name"], "a": v["area"], "lat": v["lat"], "lon": v["lon"],
              "c": {t: count(t, tw) for t in D["trades"]}} for tw, v in D["towns"].items()]
    soon = [{"n": x[0], "a": a, "lat": x[1], "lon": x[2]} for a, av in D["areas"].items() for x in av["soon"]]
    data = {"live": LIVE, "hub": HUB, "trades": {t: v["short"] for t, v in D["trades"].items()},
            "areas": {a: v["name"] for a, v in D["areas"].items()}, "liveAreas": LIVE_AREAS, "towns": towns, "soon": soon}
    return json.dumps(data, separators=(",", ":")).replace("</", "<\\/")


def map_block(t="", a=""):
    """Map of towns (Leaflet + OpenStreetMap, both free). Live towns link to the trade's town page."""
    r = "/" if LIVE else ""
    return (f'<div class="map" id="map" data-trade="{t}" data-area="{a}" role="region" aria-label="Map of the towns we cover"></div>'
            f'<p class="map-key"><span class="dot now"></span>Listed now {'<span class="dot later"></span>Coming soon ' if any(v["soon"] for v in D["areas"].values()) else ""}</p>'
            f'<link rel="stylesheet" href="{r}vendor/leaflet/leaflet.css">'
            f'<script type="application/json" id="finder-data">{finder_data()}</script>'
            f'<script src="{r}vendor/leaflet/leaflet.js" defer></script><script src="{r}finder.js" defer></script>')


def fit(*options, limit=60):
    """First option that fits in a search result title (about 60 characters), else the shortest."""
    return next((o for o in options if len(o) <= limit), min(options, key=len))


def head(title, desc, path="/"):
    extra = (f'<link rel="canonical" href="{SITE}{path}">\n<meta property="og:title" content="{e(title)}">\n'
             f'<meta property="og:description" content="{e(desc)}">\n<meta property="og:type" content="website">\n'
             f'<meta property="og:url" content="{SITE}{path}">\n<meta property="og:site_name" content="{BRAND}">\n'
             f'<meta property="og:image" content="{SITE}/og-image.png">\n<meta property="og:image:width" content="1200">\n'
             f'<meta property="og:image:height" content="630">\n<meta property="og:image:alt" content="{BRAND}: local trades across southern and central England, ranked by public reviews">\n'
             f'<meta name="twitter:card" content="summary_large_image">\n' if LIVE
             else '<meta name="claude:viewport-fit-sides" content="cover">\n')
    r = "/" if LIVE else ""
    css = r + "style.css"
    icons = (f'<link rel="icon" href="{r}favicon.ico" sizes="48x48">\n<link rel="icon" href="{r}favicon.svg" type="image/svg+xml">\n'
             f'<link rel="apple-touch-icon" href="{r}apple-touch-icon.png">\n<meta name="theme-color" content="#18252b">\n')
    return (f'<title>{e(title)}</title>\n<meta name="description" content="{e(desc)}">\n'
            f'{extra}{icons}<link rel="preload" href="{r}fonts/archivo-latin-800-normal.woff2" as="font" type="font/woff2" crossorigin>\n'
            f'<link rel="preload" href="{r}fonts/source-sans-3-latin-400-normal.woff2" as="font" type="font/woff2" crossorigin>\n'
            f'<link rel="stylesheet" href="{css}">\n')


def header():
    trades = "".join(f'<a href="{L(t)}">{e(v["short"])}</a>' for t, v in D["trades"].items())
    return (f'<header class="top"><div class="wrap bar"><a class="logo" href="{L()}">{MARK}<span>Top Trades <b>Near Me</b></span></a>'
            f'<nav>{trades}<a href="{P('for-firms')}">Firm login</a><a class="getlisted" href="{P('get-listed')}">Get listed</a></nav></div></header>'
            + ("" if LIVE else '<div class="preview">Preview only. Listings checked ' + D["checked"] + '. Not live yet.</div>'))


def footer():
    links = []
    for t, tv in D["trades"].items():
        links.append(f'<a href="{L(t)}">All {e(tv["name"].lower())}</a>')
        for a in LIVE_AREAS:
            links.append(f'<a href="{L(t, a)}">{e(tv["short"])} in {e(D["areas"][a]["name"])}</a>')
    return ('<footer><div class="wrap foot"><div><p class="logo small">' + MARK + BRAND + '</p>'
            '<p>Local trades ranked by public reviews. Run by <strong>Buildster Digital</strong>, Oxford.</p>'
            '<p class="fine">How we rank: Google rating out of 5, weighted by how many Google reviews it is based on. Firms with no Google rating we could find are listed after, in no order. Sponsored listings are paid placements, always labelled, and sit outside the ranking.</p>'
            '<p class="fine">Top Trades Near Me is run by Buildster Digital, part of the same group as Revive Roofing, Revive Plumbing and Revive Driveways.</p>'
            '<p class="fine">We do not vet, endorse or guarantee any firm listed. Check insurance, certificates and written quotes before you hire.</p>'
            '<p class="fine">Your business listed and want it changed or removed, or want us to stop contacting you? Email listings@toptradesnearme.co.uk and we will do it within 48 hours.</p>'
            f'<p class="fine"><a href="{P("for-firms")}">Firm login</a> · <a href="{P("review")}">Leave a review</a> · <a href="{P("claim")}">Claim your listing</a> · <a href="{P("get-listed")}">Get listed</a> · <a href="{P("privacy")}">Privacy</a> · <a href="{P("terms")}">Terms</a></p></div>'
            '<div class="sitemap">' + "".join(links) + '</div></div></footer>')


def card(i, b, t=None, tw=None):
    if "rating" in b:
        stars = f'{b["rating"]:g}<span>/{b["scale"]}</span>'
        cnt = f'{b["reviews"]} reviews' if "reviews" in b else "review count not shown"
        rate = f'<div class="rate"><b>{stars}</b><small>{cnt} · {e(b["source"])}</small></div>'
    else:
        rate = '<div class="rate none"><small>No Google rating found</small></div>'
    slug = CLAIMED.get(b["name"])
    if slug:
        if FIRMS[slug].get("claimed"):
            own = f'<p class="claimed"><span class="ok">Claimed</span> <a href="{F(slug)}">See profile and photos</a></p>'
        else:
            own = f'<p class="claimed"><span class="ok no">Not yet claimed</span> <a href="{F(slug)}">See profile and photos</a></p>'
    else:
        own = (f'<p class="claim"><a href="{e(claim_link(organization=b["name"], trade=(D["trades"].get(t) or SERVICES[t])["short"], town=D["towns"][tw]["name"]))}" rel="nofollow">Your business? Claim this listing</a></p>' if t else "")
    link = f'<a class="more" href="{e(b["url"])}" target="_blank" rel="nofollow noopener">{"Google reviews" if b.get("source") == "Google" else "View profile"}</a>' if b.get("url") else ""
    pos = i if "rating" in b else "–"
    return (f'<li class="biz"><div class="pos">{pos}</div><div class="body"><h3>{e(b["name"])}</h3>'
            f'<p class="meta">{e(b["base"])}{(" · " + e(b["services"])) if b.get("services") else ""}</p>{own}</div>{rate}{link}</li>')


SPONSOR_MILES = 30  # Revive covers towns up to 30 miles from Oxford (John, 3 Nov 2026)


def sponsored_here(tw):
    return miles(HUB, pos(tw)) <= SPONSOR_MILES


def extra_sponsors(t, tw):
    return [b for b in D.get("extra_sponsors", []) if b["trade"] == t and tw in b["towns"]]


def sponsor_box(t, tw):
    out = [sponsor(t)] if sponsored_here(tw) else []
    out += [sponsor(t, b) for b in extra_sponsors(t, tw)]
    return "\n".join(out)


def spots_left(t, tw):
    return 2 - (1 if sponsored_here(tw) else 0) - len(extra_sponsors(t, tw))


def sponsor(t, b=None):
    b = b or D["sponsors"][t]
    rate = (f'<div class="rate"><b>{b["rating"]:g}<span>/{b["scale"]}</span></b><small>{b["reviews"]} reviews · {e(b["source"])}</small></div>' if "rating" in b else "")
    link = f'<a class="more" href="{e(b["url"])}" target="_blank" rel="sponsored noopener">Visit website</a>' if b.get("url") else ""
    slug = CLAIMED.get(b["name"])
    if slug:
        link = f'<a class="more" href="{F(slug)}">See profile</a> ' + link
    return (f'<div class="sponsored"><span class="tag">Sponsored</span><div class="sp-row"><div class="body"><h3>{e(b["name"])}</h3>'
            f'<p class="meta">{e(b["base"])}</p><p>{e(b["services"])}</p><p class="phone">{e(b["phone"])}</p></div>{rate}</div>{link}</div>')


def featured_box(t, tw, tv, twv):
    n = spots_left(t, tw)
    if n <= 0:
        return ""
    lead = "One more sponsored spot" if n == 1 else "Two sponsored spots"
    return (f'<div class="featured"><span class="tag">Sponsored spot</span><p><strong>{lead} free for a {e(tv["single"])} in {e(twv["name"])}.</strong> '
            f'Top of the page, your photos, your number.</p><a href="{e(claim_link(trade=tv["short"], town=twv["name"]))}" rel="nofollow">Ask about it</a></div>')


def local_facts(t, tw, items):
    """One line of facts drawn from this town's own listings, plus a pointer when choice is thin."""
    tv, name = D["trades"][t], D["towns"][tw]["name"]
    rated = [b for b in items if "rating" in b and "reviews" in b]
    out = []
    if rated and len(items) > 1:
        high = sum(1 for b in rated if b["rating"] / b["scale"] >= 0.9)
        total = sum(b["reviews"] for b in rated)
        based = sum(1 for b in items if b.get("base", "").lower() == name.lower())
        if high == len(items):
            first = f'All {len(items)} firms here have 4.5 stars or more on Google' if len(items) > 2 else "Both firms here have 4.5 stars or more on Google"
        elif high == 0:
            first = f'None of the {len(items)} firms here has 4.5 stars or more on Google'
        else:
            first = f'{high} of the {len(items)} firms here {"has" if high == 1 else "have"} 4.5 stars or more on Google'
        bits = [first, f'{total:,} Google reviews between them']
        if based:
            bits.append(f'{based} {"is" if based == 1 else "are"} based in {name} itself')
        out.append(f'<p class="facts">{e(", ".join(bits[:-1]) + " and " + bits[-1])}.</p>')
    if (t, tw) in SAME_AS:
        o = SAME_AS[(t, tw)]
        out.append(f'<p class="facts">The same firms cover <a href="{L(t, o)}">{e(D["towns"][o]["name"])}</a>, close by.</p>')
    elif len(items) < MIN_FIRMS:
        more = [o for o in nearest(tw, 12) if count(t, o) >= MIN_FIRMS and (t, o) not in WEAK][:2]
        if more:
            links = " and ".join(f'<a href="{L(t, o)}">{e(D["towns"][o]["name"])}</a>' for o in more)
            out.append(f'<p class="facts">We found only {len(items)} {e(tv["name"].lower() if len(items) != 1 else tv["single"])} in {e(name)} so far. For more choice, see {links}.</p>')
    return "".join(out)


def page(t, tw):
    tv, twv = D["trades"][t], D["towns"][tw]
    items = sorted(D["listings"][f"{t}/{tw}"], key=score, reverse=True)
    yr = D["checked"][-4:]
    full = tv["name"].lower()
    amp = [f'{len(items)} best {full.replace(" and ", " & ")} in {twv["name"]} ({yr})',
           f'{full.replace(" and ", " & ").capitalize()} in {twv["name"]} ({yr})'] if " and " in full else []
    title = fit(f'{len(items)} best {full} in {twv["name"]} ({yr})', *amp,
                f'{len(items)} best {tv["short"].lower()} in {twv["name"]} ({yr})',
                f'Best {tv["short"].lower()} in {twv["name"]} ({yr})')
    vs = villages(tw)
    top = next((b for b in items if "rating" in b and "reviews" in b), None)
    lead = (f'{len(items)} {tv["name"].lower()} in {twv["name"]} ranked by Google reviews. '
            + (f'Top rated: {top["name"]}, {top["rating"]:g}/{top["scale"]} from {top["reviews"]} reviews. ' if top else ''))
    desc = lead + 'Free quotes.'
    for k in range(4, 0, -1):  # then name as many villages as fit in about 160 characters
        cand = lead + f'Covers {", ".join(vs[:k])}. Free quotes.'
        if len(cand) <= 160:
            desc = cand
            break
    if len(desc) > 160:  # very long firm names: fall back to villages only
        for k in range(4, 0, -1):
            desc = (f'{len(items)} {tv["name"].lower()} in {twv["name"]} ranked by Google reviews. '
                    f'Also covering {", ".join(vs[:k])} and nearby villages. Free quotes.')
            if len(desc) <= 160:
                break
    others = " ".join(f'<a href="{L(t, o)}">{e(D["towns"][o]["name"])}</a>' for o in nearest(tw))
    ar = twv["area"]
    other_trades = " ".join(f'<a href="{L(o, tw)}">{e(ov["name"])}</a>' for o, ov in D["trades"].items() if o != t)
    tips = "".join(f"<li>{e(x)}</li>" for x in tv["tips"])
    lst = "".join(card(i + 1, b, t, tw) for i, b in enumerate(items))
    trade_l = tv["name"].lower()
    rated = [b for b in items if "rating" in b][:3]

    def rate_txt(b):
        return f'{b["rating"]:g} out of {b["scale"]}' + (f' from {b["reviews"]} reviews' if "reviews" in b else "")
    if rated:
        best = "; ".join(f'{b["name"]} ({rate_txt(b)})' for b in rated)
        answer = (f'The highest-rated {trade_l} in {twv["name"]} on Google are {best}. '
                  f'Ratings checked {D["checked"]}.')
    else:
        answer = f'We could not find Google ratings for the {trade_l} listed in {twv["name"]} yet, so they are shown in no order.'
    faqs = [
        (f'Who are the best-rated {trade_l} in {twv["name"]}?', answer),
        ("How is this list ranked?",
         "By Google star rating, weighted by how many reviews it is based on, so 4.8 stars from 200 reviews ranks above 5 stars from 2. "
         "Firms cannot pay to move up. Sponsored spots are labelled and sit outside the ranked list."),
        (f'Do these {trade_l} cover villages near {twv["name"]}?',
         f'Usually, yes. Villages near {twv["name"]} include {", ".join(vs)}. Check with the firm when you ask for a quote.'),
        (f'How do I get quotes from {trade_l} in {twv["name"]}?',
         f'Use the free quote form on this page. We pass your job to up to three {trade_l} in {twv["name"]}, or you can contact any firm above directly.'),
    ] + [(q.format(town=twv["name"]), a.format(town=twv["name"])) for q, a in tv.get("faq", [])]
    faq_html = "".join(f"<h3>{e(q)}</h3><p>{e(a)}</p>" for q, a in faqs)
    body = f'''{header()}
<main class="wrap">
<p class="crumbs"><a href="{L()}">Home</a> / <a href="{L(t)}">{e(tv["name"])}</a> / <a href="{L(t, ar)}">{e(D["areas"][ar]["name"])}</a> / {e(twv["name"])}</p>
<section class="hero"><h1>Top {e(tv["name"].lower())} in {e(twv["name"])}</h1>
<p class="lede">{e(tv["intro"])} Covering {e(twv["name"])} and nearby villages including {e(twv["villages"])}.</p>
<p class="stamp">{len(items)} firms listed · Google ratings checked {D["checked"]}</p>
<p class="answer">{e(answer)}</p>{local_facts(t, tw, items)}</section>
<div class="grid">
<div class="main">
{sponsor_box(t, tw)}
{featured_box(t, tw, tv, twv)}
<ol class="list">{lst}</ol>
<section class="areas"><h2>{e(tv["name"])} for villages near {e(twv["name"])}</h2><p>Need a {e(tv["single"])} in {e(", ".join(vs[:-1]))} or {e(vs[-1])}? These villages are close to {e(twv["name"])}, so the firms above usually work there too. Check with the firm when you ask for a quote.</p></section>
<section class="tips"><h2>Before you hire a {e(tv["single"])} in {e(twv["name"])}</h2><ul>{tips}</ul></section>
<section class="faq"><h2>Questions about {e(trade_l)} in {e(twv["name"])}</h2>{faq_html}</section>
<p class="also">{e(tv["name"])} nearby: {others} <a href="{L(t, ar)}">All of {e(D["areas"][ar]["name"])}</a></p>
<p class="also">Other trades in {e(twv["name"])}: {other_trades}</p>{svc_links(tw)}
</div>
<aside class="quote"><h2>Get up to 3 quotes</h2><p>Tell us the job once. We pass it to up to three {e(tv["name"].lower())} in {e(twv["name"])}.</p>
{ghl("quote", f"Quote request: {tv['short']} in {twv['name']}", 760, trade=tv["short"], town=twv["name"])}
<p class="msg">Free, no obligation. We share your details only with the up to three firms we pass your job to, which may include sponsored firms. We do not vet or guarantee firms. <a href="{P('privacy')}">Privacy</a> · <a href="{P('terms')}">Terms</a></p></aside>
</div></main>
{footer()}'''
    data = ld(crumbs_ld(("Home", "/"), (tv["name"], L(t)), (D["areas"][ar]["name"], L(t, ar)), (twv["name"], L(t, tw))),
              {"@type": "CollectionPage", "@id": SITE + L(t, tw), "url": SITE + L(t, tw), "name": title, "description": desc,
               "isPartOf": {"@id": SITE + "/#site"}, "dateModified": iso_checked(),
               "spatialCoverage": [{"@type": "City", "name": twv["name"]}] + [{"@type": "Place", "name": v} for v in vs],
               "mainEntity": {"@type": "ItemList", "name": f'{tv["name"]} in {twv["name"]}', "numberOfItems": len(items),
                              "itemListOrder": "https://schema.org/ItemListOrderDescending",
                              "itemListElement": [{"@type": "ListItem", "position": i + 1,
                                                   "item": {"@type": TYPES.get(t, "HomeAndConstructionBusiness"), "name": b["name"],
                                                            "areaServed": twv["name"]}} for i, b in enumerate(items)]}},
              {"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q,
                                                   "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faqs]})
    robots = '<meta name="robots" content="noindex,follow">\n' if (t, tw) in WEAK else ""
    doc = f'<!doctype html>\n<html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n{robots}{head(title, desc, L(t, tw))}{data}</head><body>{body}</body></html>'
    if LIVE:
        os.makedirs(os.path.join(OUT, t, tw), exist_ok=True)
        open(os.path.join(OUT, t, tw, "index.html"), "w").write(doc)
    else:
        open(os.path.join(OUT, f"{t}-{tw}.html"), "w").write(doc)


def write(doc, *parts):
    """Save a page: folder URL on the live site, flat file in the preview."""
    if LIVE:
        os.makedirs(os.path.join(OUT, *parts), exist_ok=True)
        open(os.path.join(OUT, *parts, "index.html"), "w").write(doc)
    else:
        open(os.path.join(OUT, "-".join(parts) + ".html"), "w").write(doc)


def wrap_doc(title, desc, path, body, data=""):
    return f'<!doctype html>\n<html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n{head(title, desc, path)}{data}</head><body>{body}</body></html>'


def town_links(t, a):
    return "".join(f'<a href="{L(t, tw)}">{e(D["towns"][tw]["name"])} <span>{count(t, tw)}</span></a>' for tw in area_towns(a))


def trade_index(t):
    tv = D["trades"][t]
    n = sum(count(t, tw) for tw in D["towns"])
    groups = "".join(f'<div class="trade"><h2><a href="{L(t, a)}">{e(D["areas"][a]["name"])}</a></h2><div class="towns">{town_links(t, a)}</div></div>' for a in LIVE_AREAS)
    soon = "".join(f"<span>{e(D['areas'][a]['name'])}</span>" for a in D["areas"] if a not in LIVE_AREAS)
    tips = "".join(f"<li>{e(x)}</li>" for x in tv["tips"])
    others = "".join(f'<a href="{L(o)}">{e(ov["name"])}</a>' for o, ov in D["trades"].items() if o != t)
    title = fit(f'{tv["name"]} in {region()}, ranked by reviews ({D["checked"][-4:]})',
                f'{tv["short"]} in {region()}, ranked by reviews ({D["checked"][-4:]})',
                f'{tv["name"]}: {len(D["towns"])} towns ranked by reviews ({D["checked"][-4:]})',
                f'{tv["short"]}: {len(D["towns"])} towns ranked by reviews ({D["checked"][-4:]})')
    desc = f'Find {tv["name"].lower()} in {len(D["towns"])} towns in {region()}, ranked by public reviews. {tv["intro"]}'
    if len(desc) > 160:
        desc = f'Find {tv["name"].lower()} in {len(D["towns"])} towns in {region()}, ranked by Google reviews. Free quotes.'
    body = f'''{header()}
<main class="wrap">
<p class="crumbs"><a href="{L()}">Home</a> / {e(tv["name"])}</p>
<section class="hero"><h1>{e(tv["name"])} in {e(region())}</h1>
<p class="lede">{e(tv["intro"])} Pick your town on the map or from the list to see local firms ranked by public reviews.</p>
<p class="stamp">{n} listings · {len(D["towns"])} towns · checked {D["checked"]}</p></section>
<div class="mapbox">{map_block(t)}</div>
<div class="trades">{groups}</div>
{f'<section class="soon"><h2>Coming next</h2><div class="chips">{soon}</div></section>' if soon else ""}
<section class="tips"><h2>Before you hire a {e(tv["single"])}</h2><ul>{tips}</ul></section>
<p class="also">Other trades: {others}</p>
</main>
{footer()}'''
    write(wrap_doc(title, desc, L(t), body, ld(crumbs_ld(("Home", "/"), (tv["name"], L(t))))), t)


def area_page(t, a):
    tv, av = D["trades"][t], D["areas"][a]
    towns = area_towns(a)
    n = sum(count(t, tw) for tw in towns)
    soon = "".join(f"<span>{e(x[0])}</span>" for x in av["soon"])
    tips = "".join(f"<li>{e(x)}</li>" for x in tv["tips"])
    other_trades = " ".join(f'<a href="{L(o, a)}">{e(ov["name"])}</a>' for o, ov in D["trades"].items() if o != t)
    other_areas = " ".join(f'<a href="{L(t, o)}">{e(D["areas"][o]["name"])}</a>' for o in LIVE_AREAS if o != a)
    yr = D["checked"][-4:]
    title = fit(f'{tv["name"]} in {av["name"]}: {len(towns)} towns ranked by reviews ({yr})',
                f'{tv["name"]} in {av["name"]}: {len(towns)} towns ranked ({yr})',
                f'{tv["short"]} in {av["name"]}: {len(towns)} towns ranked ({yr})',
                f'{tv["short"]} in {av["name"]} ranked by reviews ({yr})')
    names = [D["towns"][x]["name"] for x in towns]
    for k in range(4, 0, -1):  # name as many towns as fit in about 160 characters
        desc = f'{tv["name"]} in {av["name"]}, ranked by Google reviews, in {len(towns)} towns including {", ".join(names[:k])}. Free quotes.'
        if len(desc) <= 160:
            break
    body = f'''{header()}
<main class="wrap">
<p class="crumbs"><a href="{L()}">Home</a> / <a href="{L(t)}">{e(tv["name"])}</a> / {e(av["name"])}</p>
<section class="hero"><h1>{e(tv["name"])} in {e(av["name"])}</h1>
<p class="lede">Choose your town. Each town page lists local {e(tv["name"].lower())} ranked by public reviews, and covers the villages around it.</p>
<p class="stamp">{n} listings · {len(towns)} towns · checked {D["checked"]}</p></section>
<div class="area-grid">
<div class="trade"><h2>Towns in {e(av["name"])}</h2><div class="towns">{town_links(t, a)}</div></div>
<div class="mapbox">{map_block(t, a)}</div>
</div>
{f'<section class="soon"><h2>Coming next in {e(av["name"])}</h2><div class="chips">{soon}</div></section>' if soon else ""}
{svc_strip(towns, f"Specialist services in {av['name']}")}
<section class="tips"><h2>Before you hire a {e(tv["single"])} in {e(av["name"])}</h2><ul>{tips}</ul></section>
<p class="also">Other trades in {e(av["name"])}: {other_trades}</p>
{f'<p class="also">{e(tv["name"])} in other areas: {other_areas}</p>' if other_areas else ""}
</main>
{footer()}'''
    write(wrap_doc(title, desc, L(t, a), body, ld(crumbs_ld(("Home", "/"), (tv["name"], L(t)), (av["name"], L(t, a))))), t, a)


def simple(name, title, desc, inner):
    body = f'''{header()}
<main class="wrap narrow">
<p class="crumbs"><a href="{L()}">Home</a> / {e(title)}</p>
{inner}
</main>
{footer()}'''
    doc = f'<!doctype html>\n<html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">\n{head(f"{title} | {BRAND}", desc, P(name))}</head><body>{body}</body></html>'
    if LIVE:
        os.makedirs(os.path.join(OUT, name), exist_ok=True)
        open(os.path.join(OUT, name, "index.html"), "w").write(doc)
    else:
        open(os.path.join(OUT, f"{name}.html"), "w").write(doc)


def pages():
    simple("claim", "Claim your listing", "Run a business listed on Top Trades Near Me? Claim your listing to update your details. Free.", f'''
<section class="hero"><h1>Claim your listing</h1>
<p class="lede">Your business is already listed free. Claim it to correct your details, add your services and hear about sponsored spots on your town page. Claiming is free and does not change your place in the ranking.</p></section>
<div class="formbox">{ghl("claim", "Claim your listing", 900, forward=True)}</div>
<p class="msg">We use these details to check who you are, update your listing and contact you about it, including sponsored spots. <a href="{P('privacy')}">Privacy</a> · <a href="{P('terms')}">Terms</a></p>''')
    simple("get-listed", "Get listed", "Local trade not on Top Trades Near Me yet? Ask to be listed. Free.", f'''
<section class="hero"><h1>Get your business listed</h1>
<p class="lede">Listing is free. We add firms that work in the towns we cover and rank everyone by public reviews, so the better your reviews, the higher you sit.</p></section>
<div class="formbox">{ghl("listed", "Get listed", 1000, forward=True)}</div>
<p class="msg">We use these details to check and list your business and to contact you about it, including sponsored spots. <a href="{P('privacy')}">Privacy</a> · <a href="{P('terms')}">Terms</a></p>''')
    simple("privacy", "Privacy notice", "How Top Trades Near Me collects, uses and protects personal data, and your rights under UK GDPR.", f'''
<section class="hero"><h1>Privacy notice</h1><p class="stamp">Last updated 3 November 2026</p></section>
<div class="prose">
<p>This notice explains what personal data Top Trades Near Me collects, why, who we share it with, how long we keep it and your rights. It covers people who ask for quotes, people who run businesses we list, and anyone who visits the site or contacts us.</p>

<h2>Who we are</h2>
<p>Top Trades Near Me (toptradesnearme.co.uk) is run by Buildster Digital, the trading name of John Collins, a sole trader, 12 Red Bridge Hollow, Oxford OX1 4XS. We are the controller of the personal data described here.</p>
<p>Contact us about your data at listings@toptradesnearme.co.uk or by post to the address above. Buildster Digital is part of the same group as Revive Roofing, Revive Plumbing and Revive Driveways.</p>

<h2>If you ask for quotes</h2>
<p><strong>What we collect:</strong> your name, phone number, email address (if you give it), postcode, the trade and town, and the job you describe.</p>
<p><strong>What we do with it:</strong> we may call or message you to check the request, then pass your details and job to up to three local firms that do that kind of work, so they can contact you and quote. We also keep a record of the request so we can deal with questions or complaints.</p>
<p><strong>Legal basis:</strong> taking steps at your request (passing your job on is the service you asked for), and our legitimate interest in checking requests and preventing spam.</p>
<p><strong>Who gets it:</strong> the firms we pass your job to. They may include sponsored firms, and firms in the same group as us (Revive Roofing, Revive Plumbing, Revive Driveways). Each firm becomes responsible for your details once it has them and uses them under its own privacy terms. We will not pass your job to more than three firms, and we will not use your details to market other services to you.</p>

<h2>If you run a business we list</h2>
<p><strong>Where listing details come from:</strong> public sources such as the firm's own website, public review sites and trade directories, Google and social media pages, and Companies House. We record the business name, trading area, services, public contact details, website and public review ratings. For sole traders and partnerships, some of this (for example a name or mobile number) is personal data.</p>
<p><strong>Why:</strong> to run a free public directory that helps people find local trades, and to tell listed firms about their listing, how to claim it, and our paid sponsored spots and marketing services from Buildster Digital. The legal basis is our legitimate interests in running the directory and in business-to-business marketing. We have weighed these against your interests: we only use business details that are already public, we only list them in a business context, and you can have your listing changed or removed at any time.</p>
<p><strong>How we contact firms:</strong> by phone (we check numbers against the Telephone Preference Service and Corporate TPS first and do not call numbers registered there unless you have told us we may), by post, by messages through your own website contact form or business social media page, and by email to limited companies and LLPs. Every marketing email includes a simple way to opt out. We do not send marketing emails or texts to sole traders or partnerships unless they have asked for them.</p>
<p><strong>If you leave a review:</strong> we use your name, email, town, the firm and your review to check it is yours, check it and publish it. We publish your first name, the first letter of your surname, your town and the review, never your email. We may pass your review (but not your email) to the firm so it can reply. The legal basis is our legitimate interest in running fair, checked reviews. You can ask us to take your review down at any time.</p>
<p><strong>If you claim a listing, ask to be listed or buy a sponsored spot:</strong> we use the details you send (name, business, phone, email, trade, town, message) to check who you are, update your listing, contact you and provide the service. The legal basis is taking steps towards, and performing, a contract with you.</p>
<p><strong>If you have a firm login:</strong> we also keep your login email, a record of when you log in, and the changes and photos you send us. Your password is held by HighLevel and we never see it. We use this to run your account and profile page, check changes before they go live, and keep your account secure. The legal basis is performing our contract with you.</p>
<p><strong>Objecting and removal:</strong> you can tell us at any time to stop contacting you, or to change or remove your listing. Email listings@toptradesnearme.co.uk and we will do it within 48 hours. We keep a short note of your business name and contact details on a do-not-contact list, so that we do not add or contact you again by mistake.</p>

<h2>If you pay us</h2>
<p>Payments for sponsored spots are taken by Stripe. Stripe handles your card details and we never see or store your full card number. We receive your name, email, billing details and payment history. Stripe also uses payment data to prevent fraud and meet its own legal duties, under its own privacy policy. The legal basis is performing our contract with you and our legal duty to keep financial records.</p>

<h2>If you email or call us</h2>
<p>We keep your message, your contact details and our reply so we can deal with your request. The legal basis is our legitimate interest in answering you, or taking steps towards a contract if you are asking about our services.</p>

<h2>When you visit the site</h2>
<p>We do not use analytics or advertising cookies on this site, and we do not track you across other sites.</p>
<p>The site is hosted by GitHub (GitHub Pages), which records technical data such as your IP address to deliver pages and keep them secure. Our fonts are loaded from Google Fonts, which means your browser sends your IP address to Google. Our forms are provided by HighLevel (LeadConnector). When you open a page with a form, the form may store small cookies or similar data in your browser that it needs to work, to stop spam and to record which page the form was sent from. If we add analytics or any other cookies that are not strictly needed, we will ask for your consent first and update this notice.</p>
<p>We use Google Search Console and Bing Webmaster Tools to see how the site appears in search results. These give us totals, not information about individual visitors, and add nothing to your browser.</p>

<h2>Service providers we use</h2>
<p>These providers process data on our behalf, under contracts that require them to keep it secure and use it only on our instructions:</p>
<ul>
<li>HighLevel (LeadConnector): forms, contact records, firm logins and our customer system.</li>
<li>Zoho: our email (for example listings@ and hello@toptradesnearme.co.uk).</li>
<li>GitHub: website hosting.</li>
<li>Google: website fonts, and search reporting.</li>
</ul>
<p>Stripe acts for its own purposes as well as ours, as explained above. We may also share data with professional advisers, or where the law requires it. We do not sell personal data.</p>

<h2>Data stored outside the UK</h2>
<p>Some of these providers, including HighLevel, Stripe, GitHub and Google, are based in or store data in the United States or the EU. Where data leaves the UK we rely on the protections UK law allows, such as UK adequacy regulations (including the UK Extension to the EU-US Data Privacy Framework) or the ICO's international data transfer agreement or addendum.</p>

<h2>How long we keep it</h2>
<ul>
<li>Quote requests: up to 12 months, then deleted.</li>
<li>Listing details: while the listing is on the site, and for 12 months after it is removed.</li>
<li>Contact with firms who did not buy anything: up to 24 months from our last contact.</li>
<li>Customer and payment records: 6 years after the end of the financial year they relate to, as tax law requires.</li>
<li>Do-not-contact list: for as long as we contact businesses, so that your request keeps working.</li>
<li>Emails: up to 24 months, unless they form part of the records above.</li>
</ul>

<h2>Your rights</h2>
<p>Under UK data protection law you can ask us to:</p>
<ul>
<li>give you a copy of the personal data we hold about you;</li>
<li>correct it if it is wrong;</li>
<li>delete it;</li>
<li>restrict how we use it;</li>
<li>give it to you or another organisation in a reusable format, where that applies.</li>
</ul>
<p>You can also <strong>object</strong> at any time to our use of your data based on legitimate interests, and you can always stop direct marketing. We do not make decisions about you by automated means that have legal or similarly significant effects. Our ranking simply sorts public review ratings by a fixed formula, explained on every page.</p>
<p>To use any of these rights, email listings@toptradesnearme.co.uk. We will reply within one month. It is free.</p>

<h2>Complaints</h2>
<p>If you are unhappy with how we have handled your data, please tell us first at listings@toptradesnearme.co.uk and we will look into it. You also have the right to complain to the Information Commissioner's Office (ICO), the UK data protection regulator, at <a href="https://ico.org.uk/make-a-complaint/" rel="noopener">ico.org.uk/make-a-complaint</a> or on 0303 123 1113.</p>

<h2>Changes</h2>
<p>We will update this notice when what we do changes, and show the new date at the top. See also our <a href="{P('terms')}">terms of use and sponsored listing terms</a>.</p>
</div>''')
    simple("terms", "Terms of use", "Terms for using Top Trades Near Me, how listings and rankings work, and terms for sponsored listings and firm accounts.", f'''
<section class="hero"><h1>Terms of use</h1><p class="stamp">Last updated 3 November 2026</p></section>
<div class="prose">
<p>These terms apply to anyone using toptradesnearme.co.uk. Parts 4 to 6 apply to businesses that buy a sponsored listing, claim a listing, use a firm login or buy leads. The site is run by Buildster Digital, the trading name of John Collins, a sole trader, 12 Red Bridge Hollow, Oxford OX1 4XS (listings@toptradesnearme.co.uk).</p>

<h2>1. What this site is</h2>
<p>Top Trades Near Me is a free directory of local trades. It lists firms using publicly available information and ranks them by their public review ratings. It is an information service only. We are not a party to any work, quote or contract between you and a firm.</p>

<h2>2. We do not endorse or guarantee any firm</h2>
<p>A firm being listed, ranked highly, claimed or sponsored does not mean we recommend, vet, approve or guarantee it. We do not check firms' qualifications, insurance, trade memberships, licences, prices or the quality of their work. Ratings and review counts come from third-party sites and can change or be wrong. Before you hire anyone, do your own checks: ask for proof of insurance and any certificates, get written quotes, check recent reviews and agree terms in writing. Any agreement you make is between you and the firm, and the firm is responsible for its work.</p>
<p>We try to keep the information accurate and up to date but cannot promise that it always is. If something is wrong, email listings@toptradesnearme.co.uk.</p>

<h2>3. How the ranking works</h2>
<p>Firms with a Google rating are sorted by that rating out of 5, weighted by how many Google reviews it is based on. Firms with no Google rating we could find are listed after, in no order. Nobody can pay to change their place in the ranking. Claiming a listing does not change its place.</p>
<p>Sponsored listings are paid advertisements. They are always labelled "Sponsored" and shown in a separate box outside the ranked list. Some sponsored spots are taken by Revive Roofing, Revive Plumbing and Revive Driveways, which are in the same group as Buildster Digital.</p>

<h2>4. Sponsored listing terms (for businesses)</h2>
<p>These apply when a business buys a sponsored spot. By ordering you confirm you are acting for a business, not as a consumer.</p>
<ul>
<li><strong>What you get:</strong> a labelled sponsored spot on the town page or pages you choose, for the trade you choose, showing your business name, area, services, phone number, website link and public rating. The spot sits outside the ranked list and does not change your ranking.</li>
<li><strong>Availability:</strong> spots are limited and offered first come, first served. We decide the order of sponsored spots on a page.</li>
<li><strong>Price and billing:</strong> the price is the one agreed when you order. Fees are billed monthly in advance through Stripe. Where we offer a free first month, billing starts after it unless you cancel first. We will give you at least 30 days' notice of any price change.</li>
<li><strong>Cancelling:</strong> there is no minimum term. You can cancel at any time by emailing listings@toptradesnearme.co.uk. Your spot stays until the end of the month you have paid for, and we do not refund part months.</li>
<li><strong>Your content:</strong> you must make sure everything you give us is true, not misleading, and that you have the right to use it, including logos and photos. You must hold the insurance, registrations and qualifications your work legally needs. We may edit, refuse or remove content that is inaccurate, misleading, unlawful or that breaks advertising rules.</li>
<li><strong>Ending a sponsorship:</strong> we may suspend or end a sponsored spot if you break these terms, if we receive serious or repeated complaints about your business, or if we stop running the page. If we end it for a reason that is not your fault, we will refund any unused prepaid fees.</li>
<li><strong>No guaranteed results:</strong> we do not promise any number of visits, calls, leads or jobs.</li>
<li><strong>Liability:</strong> we are not liable for loss of profit, business or opportunity, or for indirect loss. Our total liability to you under a sponsorship is limited to the fees you paid in the 12 months before the claim. Nothing in these terms limits liability that cannot be limited by law, such as for death or personal injury caused by negligence, or for fraud.</li>
</ul>

<h2>5. Claimed listings and firm accounts (for businesses)</h2>
<p>These apply when a business claims its listing or uses a firm login. By claiming you confirm you are the owner of the business or allowed to act for it.</p>
<ul>
<li><strong>Your profile:</strong> once we have checked who you are, your business gets a profile page with the details, photos and areas you send us. We check every change before it goes live, usually within one working day.</li>
<li><strong>Your login:</strong> keep your password private and tell us straight away if you think someone else has used it. You are responsible for what is done with your login.</li>
<li><strong>Photos and content:</strong> only send photos of your own work that you have the right to use, with no customer's personal details, faces or house numbers on show unless they have agreed. Everything must be true and not misleading. You let us show it on the site and in our own posts about the site while you are listed. We may edit, refuse or remove anything that breaks these terms or the law.</li>
<li><strong>Reviews:</strong> you must not write, buy or swap reviews of your own business or a rival, or offer anything in return for a good review. Breaking this ends your account and listing.</li>
<li><strong>Ranking:</strong> claiming, a profile page or a login never changes your place in the ranked list.</li>
<li><strong>Closing your account:</strong> you can close your login or ask us to take your profile down at any time by emailing listings@toptradesnearme.co.uk. Your free listing stays unless you ask us to remove it too. We may close an account that breaks these terms. Paid sponsored spots follow part 4.</li>
</ul>

<h2>6. Buying leads (for businesses)</h2>
<p>These apply when a business buys a homeowner's job request (a lead) from us.</p>
<ul>
<li><strong>What a lead is:</strong> a job request from a homeowner who has asked us to pass their details to local firms. We check each request before we offer it. We tell you the trade, town, a summary of the job and when it came in before you buy.</li>
<li><strong>How many firms:</strong> a shared lead is sold to no more than three firms. An exclusive lead is sold to one firm only. We tell you which it is before you buy.</li>
<li><strong>Price and payment:</strong> the price is shown before you buy and is paid by card through Stripe. When payment goes through we send you the homeowner's name, phone, email and job details.</li>
<li><strong>Using the homeowner's details:</strong> use them only to contact that homeowner about that job. Do not pass them on, add them to marketing lists or contact them about anything else. You become responsible for their data under data protection law once you have it.</li>
<li><strong>Bad leads:</strong> if a lead has a wrong phone number and email, is a test or fake request, or is for work outside the trade or town shown, tell us within 7 days of buying it and we will give you a credit for another lead. We do not give credits because a homeowner chose another firm or did not go ahead.</li>
<li><strong>No guaranteed jobs:</strong> a lead is an introduction. We do not promise the homeowner will reply, accept a quote or hire you.</li>
</ul>

<h2>7. Listings and removal</h2>
<p>Any business can ask us to correct or remove its free listing, or to stop contacting it, by emailing listings@toptradesnearme.co.uk. We will do it within 48 hours. We may decline to list, or may remove, any business at our discretion.</p>

<h2>8. Using the site</h2>
<p>Do not copy the directory in bulk, scrape it, or use it to send spam. Links to other websites are provided for convenience and we are not responsible for their content.</p>

<h2>9. Our liability to site users</h2>
<p>The site is free and provided as it is. We are not responsible for the work, conduct, prices or advice of any firm listed, or for any loss from your dealings with them. Nothing in these terms limits liability that cannot be limited by law, or affects your legal rights as a consumer.</p>

<h2>10. General</h2>
<p>We may update these terms and will show the new date at the top. These terms are governed by the law of England and Wales, and the courts of England and Wales have jurisdiction. How we use personal data is explained in our <a href="{P('privacy')}">privacy notice</a>.</p>
</div>''')

def index():
    first = next(iter(D["trades"]))
    picks = "".join(f'<label><input type="radio" name="trade" value="{t}"{" checked" if t == first else ""}><span>{e(tv["name"])}</span></label>' for t, tv in D["trades"].items())
    cards = []
    for a, av in D["areas"].items():
        if a in LIVE_AREAS:
            tws = area_towns(a)
            cards.append(f'<a class="area live" data-area="{a}" href="{L(first, a)}"><b>{e(av["name"])}</b><span>{len(tws)} towns</span></a>')
        else:
            names = ", ".join(x[0] for x in av["soon"][:4])
            cards.append(f'<div class="area"><b>{e(av["name"])}</b><span>Coming soon: {e(names)}</span></div>')
    soon = "".join(f"<span>{x}</span>" for x in ["Electricians", "Patios", "Heat pumps", "Builders", "Fencing", "Landscapers", "Kitchens", "Loft conversions"])
    total = sum(len(v) for v in D["listings"].values())
    body = f'''{header()}
<main class="wrap">
<section class="finder">
<div class="find">
<h1>Find a trade near you that other people rate.</h1>
<p class="lede">Local firms ranked by real public reviews. No pay-to-be-number-one.</p>
<form class="steps" id="finder" action="{L(first)}">
<fieldset><legend><span class="n">1</span>What do you need?</legend><div class="pick">{picks}</div></fieldset>
<div class="pc"><label for="pc"><span class="n">2</span>Where is the job?</label>
<div class="pcrow"><input id="pc" name="pc" autocomplete="postal-code" placeholder="Postcode, e.g. OX4 1AB" maxlength="9"><button type="submit">Find firms</button></div>
<button type="button" class="linkish" id="locate" hidden>Use my location</button>
<p id="pcout" class="pcout" aria-live="polite"></p></div>
</form>
<p class="stamp">{total} listings · {len(D["towns"])} towns · checked {D["checked"]}</p>
</div>
<div class="mapbox">{map_block()}</div>
</section>
{svc_strip()}
<section class="arealist"><h2>Or pick your area</h2><div class="areas-grid">{"".join(cards)}</div></section>
<section class="soon"><h2>More trades coming</h2><div class="chips">{soon}</div></section>
<section class="getlisted-box" id="get-listed"><h2>Are you a trade?</h2>
<p>Every firm here is listed free. Want a sponsored spot at the top of your town page, more reviews, or your details changed? We will sort it.</p>
<p class="cta"><a class="btn" href="{P('claim')}">Claim your listing</a> <a class="btn ghost" href="{P('get-listed')}">Not listed? Get listed free</a></p></section>
</main>
{footer()}'''
    h = head(f"{BRAND}: local roofers, driveways and plumbers ranked by reviews", f"Find roofers, driveway firms and plumbers in {region()}, ranked by public reviews. Search by postcode or pick your area on the map.", "/")
    if LIVE:
        org = {"@type": "Organization", "@id": ORG_ID, "name": BRAND, "url": SITE + "/", "logo": SITE + "/icon-512.png",
               "email": "listings@toptradesnearme.co.uk",
               "parentOrganization": {"@type": "Organization", "name": "Buildster Digital"}}
        if D.get("social"):
            org["sameAs"] = D["social"]
        site = {"@type": "WebSite", "@id": SITE + "/#site", "url": SITE + "/", "name": BRAND, "publisher": {"@id": ORG_ID}, "inLanguage": "en-GB"}
        doc = f'<!doctype html>\n<html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">\n{h}{ld(org, site)}</head><body>{body}</body></html>'
    else:
        doc = h + body
    open(os.path.join(OUT, "index.html"), "w").write(doc)

def ranks(slug):
    """Where a claimed firm sits in each ranked list, using the same score as the town pages."""
    names = {n for n, sl in CLAIMED.items() if sl == slug}
    out = []
    for key, items in D["listings"].items():
        t, tw = key.split("/")
        ranked = sorted(items, key=score, reverse=True)
        for i, b in enumerate(ranked):
            if b["name"] in names:
                out.append((t, tw, i + 1 if "rating" in b else None, len(ranked), b))
    return out


def firm_page(slug):
    f = FIRMS[slug]
    r = "/" if LIVE else ""
    src = (lambda x: f"/firm/{slug}/{x}") if LIVE else (lambda x: f"firm/{slug}/{x}")
    rs = ranks(slug)
    trades = [t for t in f.get("trades", []) if t in D["trades"]] or sorted({t for t, *_ in rs})
    tnames = ", ".join(D["trades"][t]["name"].lower() for t in trades)
    rated = next((b for *_, b in rs if "rating" in b), None) or ({"rating": f["rating"], "scale": f.get("scale", 5), "reviews": f.get("google_reviews", "?"), "source": f.get("source", "Google")} if "rating" in f else None)
    count = f'{e(rated["source"])} rating' if f.get("hide_review_count") else f'{rated.get("reviews", "?")} reviews · {e(rated["source"])}' if rated else ""
    rate = (f'<div class="rate"><b>{rated["rating"]:g}<span>/{rated["scale"]}</span></b><small>{count}</small></div>' if rated else "")
    logo = f'<img class="firm-logo{" dark" if f.get("logo_dark") else ""}" src="{src(f["logo"])}" alt="{e(f["name"])} logo" width="96" height="96">' if f.get("logo") else ""
    contact = []
    if f.get("phone"):
        contact.append(f'<a class="btn" href="tel:{e(f["phone"].replace(" ", ""))}">Call {e(f["phone"])}</a>')
    if f.get("mobile"):
        contact.append(f'<a class="btn ghost" href="tel:{e(f["mobile"].replace(" ", ""))}">Mobile {e(f["mobile"])}</a>')
    if f.get("text_only"):
        contact.append(f'<a class="btn ghost" href="sms:{e(f["text_only"].replace(" ", ""))}">Text {e(f["text_only"])}</a>')
    if f.get("website"):
        contact.append(f'<a class="btn ghost" href="{e(f["website"])}" target="_blank" rel="noopener">Website</a>')
    services = "".join(f"<li>{e(x)}</li>" for x in f.get("services", []))
    photos = "".join(f'<figure><img src="{src(ph["file"])}" alt="{e(ph.get("alt", ""))}" loading="lazy"><figcaption>{e(ph.get("alt", ""))}</figcaption></figure>' for ph in f.get("photos", []))
    covers = f.get("towns") or sorted({tw for _, tw, *_ in rs})
    towns = " ".join(f'<a href="{L(trades[0], tw)}">{e(D["towns"][tw]["name"])}</a>' for tw in covers if tw in D["towns"]) if trades else ""
    rank_rows = "".join(f'<li><a href="{L(t, tw)}">{e(D["trades"][t]["name"])} in {e(D["towns"][tw]["name"])}</a>: '
                        f'{f"number {pos} of {n}" if pos else f"listed, no Google rating found ({n} firms)"}</li>'
                        for t, tw, pos, n, _ in sorted(rs, key=lambda x: (x[2] or 999, x[1])))
    if f.get("claimed"):
        status = f'<p class="claimed"><span class="ok">Claimed</span> by the business on {e(f["claimed"])}</p>' if f["claimed"] is not True else '<p class="claimed"><span class="ok">Claimed</span> by the business</p>'
    else:
        status = (f'<p class="claimed"><span class="ok no">Not yet claimed</span> '
                  f'<a href="{e(claim_link(organization=f["name"], trade=D["trades"][trades[0]]["short"] if trades else "", town=D["towns"][covers[0]]["name"] if covers and covers[0] in D["towns"] else ""))}" rel="nofollow">Your business? Claim this page</a></p>')
    if f.get("email"):
        contact.append(f'<a class="btn ghost" href="mailto:{e(f["email"])}">Email</a>')
    facts = "".join(f"<li>{e(x)}</li>" for x in f.get("highlights", []))
    hours = "".join(f"<li>{e(x)}</li>" for x in f.get("hours", []))
    badges = "".join(f'<span class="badge-reg">{e(x)}</span>' for x in f.get("badges", []))
    if hours or f.get("address"):
        where = (f'<section class="firm-sec"><h2>{"Opening hours and address" if hours else "Address"}</h2>'
                 + (f"<ul>{hours}</ul>" if hours else "") + (f'<p>{e(f["address"])}</p>' if f.get("address") else "")
                 + (f'<p>Email: <a href="mailto:{e(f["email"])}">{e(f["email"])}</a></p>' if f.get("email") else "") + "</section>")
    else:
        where = ""
    title = f'{f["name"]}: {tnames} in {f.get("base", region())}'
    desc = (f.get("about") or f'{f["name"]}, {tnames} based in {f.get("base", "")}.')[:155]
    body = f"""{header()}
<main class="wrap narrow firm">
<p class="crumbs"><a href="{L()}">Home</a>{f' / <a href="{L(trades[0])}">{e(D["trades"][trades[0]]["name"])}</a>' if trades else ""} / {e(f["name"])}</p>
<section class="hero firm-head">{logo}<div>{status}
<h1>{e(f["name"])}</h1><p class="lede">{e(tnames.capitalize())}{(" · " + e(f["base"])) if f.get("base") else ""}</p>{f'<p class="badges">{badges}</p>' if badges else ""}</div>{rate}</section>
<p class="cta">{" ".join(contact)}</p>
{f'<section class="firm-sec"><h2>About</h2><p>{e(f["about"])}</p></section>' if f.get("about") else ""}
{f'<p class="msg">{e(f["note"])}</p>' if f.get("note") else ""}
{f'<section class="firm-sec"><h2>At a glance</h2><ul>{facts}</ul></section>' if facts else ""}
{f'<section class="firm-sec"><h2>Services</h2><ul class="cols">{services}</ul></section>' if services else ""}
{f'<section class="firm-sec"><h2>Photos of our work</h2><div class="gallery">{photos}</div></section>' if photos else ""}
{where}
{reviews_block(slug, f)}
{f'<section class="firm-sec"><h2>Towns covered</h2>{("<p>" + e(f["areas_note"]) + "</p>") if f.get("areas_note") else ""}<p class="also">{towns}</p></section>' if towns else ""}
{f'<section class="firm-sec"><h2>Where it ranks</h2><ul>{rank_rows}</ul><p class="msg">Ranked by Google rating, weighted by number of reviews. Claiming a listing or having this page does not change the ranking.</p></section>' if rank_rows else ""}
<p class="msg">This page is written from details {"the business gave us" if f.get("claimed") else "about the business"}. Something wrong? Email listings@toptradesnearme.co.uk. Run this business? <a href="{P('for-firms')}">{"Log in to update it" if f.get("claimed") else "Claim it and log in to update it"}</a>.</p>
</main>
{footer()}"""
    data = ld(crumbs_ld(("Home", "/"), (f["name"], F(slug))),
              {"@type": TYPES.get(trades[0], "HomeAndConstructionBusiness") if trades else "HomeAndConstructionBusiness",
               "@id": SITE + F(slug) + "#firm", "name": f["name"], "url": SITE + F(slug),
               **({"telephone": f["phone"]} if f.get("phone") else {}), **({"email": f["email"]} if f.get("email") else {}),
               **({"logo": f'{SITE}/firm/{slug}/{f["logo"]}', "image": [f'{SITE}/firm/{slug}/{ph["file"]}' for ph in f.get("photos", [])] or f'{SITE}/firm/{slug}/{f["logo"]}'} if f.get("logo") else {}), **({"sameAs": [f["website"]]} if f.get("website") else {}), **({"address": {"@type": "PostalAddress", "streetAddress": f["address"], "addressCountry": "GB"}} if f.get("address") else {}),
               "areaServed": [D["towns"][tw]["name"] for tw in covers if tw in D["towns"]]})
    write(wrap_doc(title, desc, F(slug), body, data), "firm", slug)
    folder = os.path.join(HERE, "firms", slug)
    if os.path.isdir(folder):
        dest = os.path.join(OUT, "firm", slug)
        os.makedirs(dest, exist_ok=True)
        shutil.copytree(folder, dest, dirs_exist_ok=True)


def stars(n):
    return f'<span class="stars" aria-label="{n} out of 5">' + "★" * n + "☆" * (5 - n) + "</span>"


def reviews_block(slug, f):
    rv = sorted(f.get("reviews", []), key=lambda r: r.get("date_iso", ""), reverse=True)
    ask = f'<p class="cta"><a class="btn ghost" href="{e(review_link(f["name"]))}" rel="nofollow">Used {e(f["name"])}? Leave a review</a></p>'
    if not rv:
        return f'<section class="firm-sec"><h2>Reviews on Top Trades</h2><p>No reviews here yet.</p>{ask}<p class="msg">Every review is checked before it goes live. Good and bad reviews are published the same way. <a href="{P("reviews-policy")}">How reviews work</a></p></section>'
    avg = sum(r["rating"] for r in rv) / len(rv)
    items = "".join(
        f'<li class="review"><p class="rv-head">{stars(r["rating"])} <b>{e(r["name"])}</b>{(", " + e(r["town"])) if r.get("town") else ""} · {e(r["date"])}</p>'
        f'<p>{e(r["text"])}</p>'
        + (f'<p class="reply"><b>Reply from {e(f["name"])}:</b> {e(r["reply"])}</p>' if r.get("reply") else "")
        + "</li>" for r in rv)
    return (f'<section class="firm-sec"><h2>Reviews on Top Trades</h2><p class="rv-sum">{stars(round(avg))} {avg:.1f} out of 5 from {len(rv)} review{"s" if len(rv) != 1 else ""}</p>'
            f'<ul class="reviews">{items}</ul>{ask}<p class="msg">Every review is checked before it goes live. Good and bad reviews are published the same way, and the firm can reply. These reviews do not change the ranking. <a href="{P("reviews-policy")}">How reviews work</a></p></section>')


def review_link(name):
    return P("review") + "?" + urllib.parse.urlencode({"firm": name})


def review_pages():
    form = (f'<div class="formbox">{ghl("review", "Leave a review", 1150, forward=True)}</div>' if FORMS["review"]
            else '<p>Email your review to <a href="mailto:hello@toptradesnearme.co.uk?subject=Review">hello@toptradesnearme.co.uk</a> with the firm\'s name, the town and roughly when the work was done.</p>')
    simple("review", "Leave a review", "Had work done by a local trade? Leave an honest review on Top Trades Near Me.", f"""
<section class="hero"><h1>Leave a review</h1><p class="lede">Had work done by a firm on Top Trades Near Me? Tell other people how it went, good or bad.</p></section>
{form}
<p class="msg">We check every review before it goes live, usually within two working days, and may email you to check it is yours. We show your first name, the first letter of your surname and your town, never your email. <a href="{P('reviews-policy')}">How reviews work</a> · <a href="{P('privacy')}">Privacy</a></p>""")
    simple("reviews-policy", "How reviews work", "How reviews on Top Trades Near Me are collected, checked and published.", f"""
<section class="hero"><h1>How reviews work</h1><p class="stamp">Last updated 3 November 2026</p></section>
<div class="prose">
<h2>Who can leave a review</h2>
<p>Anyone who has had work done, or had a quote, from a firm listed on this site. You must be the customer, or live in the home where the work was done. You must not work for the firm, be related to its owner, or work for a rival.</p>
<h2>How we check reviews</h2>
<ul>
<li>We may email or call you to check the review is yours and that the work happened. If we cannot check it, we do not publish it.</li>
<li>We read every review before it goes live, usually within two working days.</li>
<li>We publish good and bad reviews in the same way. We never hide, edit or delay a review because of its rating or because a firm asks us to.</li>
<li>We do not publish a review if it is abusive, discriminatory, gives someone's personal details, is about something other than the firm's work, or looks fake. If we turn a review down we tell you why.</li>
<li>Nobody is paid or rewarded for a review. Firms cannot write, buy or swap reviews, and cannot pick which customers they ask.</li>
<li>Staff of Top Trades Near Me, Buildster Digital and Revive firms cannot review any firm on this site.</li>
</ul>
<h2>How firms can respond</h2>
<p>The firm can post one public reply under each review. If a firm thinks a review breaks these rules, it can ask us to look again. We check the facts with both sides and decide; we do not take a review down just because the firm disagrees with it.</p>
<h2>Reviews and the ranking</h2>
<p>The ranked lists on town pages use Google ratings only. Reviews left on this site show on the firm's profile page and do not change its place in the ranking.</p>
<h2>Reporting a review</h2>
<p>If you think a review is fake or breaks these rules, email listings@toptradesnearme.co.uk with the firm's name and the review.</p>
</div>""")


def dashboard():
    sbc = D.get("portal", {}).get("supabase", {})
    cfg = {"url": sbc.get("url", ""), "anon": sbc.get("key", ""), "billing": BILLING,
           "towns": {k: v["name"] for k, v in sorted(D["towns"].items(), key=lambda x: x[1]["name"])},
           "trades": {k: v["name"] for k, v in D["trades"].items()}}
    lib = (f'<script src="{"/" if LIVE else ""}vendor/supabase/supabase.js"></script>' if cfg["url"] else "")
    inner = f"""
<section class="hero"><h1>Firm dashboard</h1><p class="lede">Your leads, your page and your account in one place.</p></section>
<div id="dash" class="dash"><p class="msg">Loading…</p></div>
<script type="application/json" id="dash-config">{json.dumps(cfg, ensure_ascii=False).replace("</", "<\\/")}</script>
{lib}<script src="{'/' if LIVE else ''}dashboard.js" defer></script>
<noscript><p>The dashboard needs JavaScript turned on.</p></noscript>"""
    simple("dashboard", "Firm dashboard", "Log in to your Top Trades Near Me firm dashboard.", inner)
    path = os.path.join(OUT, "dashboard", "index.html") if LIVE else os.path.join(OUT, "dashboard.html")
    doc = open(path).read().replace("<head>", '<head><meta name="robots" content="noindex">', 1)
    open(path, "w").write(doc)


def for_firms():
    login = (f'<p class="cta"><a class="btn" href="{e(PORTAL)}">Log in to your firm account</a></p>'
             f'<p class="msg">First time? Use the email you claimed your listing with and choose "Forgot password" to set one.</p>' if PORTAL
             else '<p class="msg"><strong>Firm logins open soon.</strong> Claim your listing now and we will email you your login as soon as it is ready.</p>')
    change = (f'<div class="formbox">{ghl("change", "Change my listing", 1100)}</div>' if FORMS["change"]
              else '<p>Email your changes and photos to <a href="mailto:listings@toptradesnearme.co.uk?subject=Change%20my%20listing">listings@toptradesnearme.co.uk</a> and we will update your page within one working day.</p>')
    bill = (f'<p class="cta"><a class="btn ghost" href="{e(BILLING)}">Manage billing</a></p><p class="msg">Enter the email you pay with and Stripe emails you a one-time link. Update your card, download invoices, switch to yearly or cancel.</p>' if BILLING
            else '<p>To update your card, get an invoice or cancel, email listings@toptradesnearme.co.uk. Online billing opens soon.</p>')
    simple("for-firms", "Firm login", "Log in to manage your listing on Top Trades Near Me: your profile page, photos, sponsored spot, leads and billing.", f"""
<section class="hero"><h1>Firm login</h1><p class="lede">Your listing on Top Trades Near Me is free. Claim it to get a profile page with your photos, and manage it all here.</p></section>
<section class="firm-sec">{login}</section>
<section class="firm-sec"><h2>What your firm account does</h2><ul>
<li>Your own profile page: about you, services, towns covered, phone, website and photos of your work.</li>
<li>Change your details and add photos. We check every change and put it live within one working day.</li>
<li>See your sponsored spot, your plan and every enquiry we have passed to you.</li>
<li>Manage billing through Stripe: card, invoices, yearly plan or cancel.</li>
</ul><p class="msg">Claiming, a profile page or a login never changes your place in the ranking. See <a href="{P('terms')}">terms</a> part 5.</p></section>
<section class="firm-sec"><h2>Change my listing or add photos</h2>{change}
<p class="msg">Only send photos of your own work that you have the right to use, with no customer details on show. We use what you send to update your page. <a href="{P('privacy')}">Privacy</a></p></section>
<section class="firm-sec"><h2>Billing</h2>{bill}</section>
<section class="firm-sec"><h2>Badge for your website</h2><p>Show customers you're listed with a free badge that links to your town page. <a href="{P('badge')}">Get your badge</a></p></section>
<section class="firm-sec"><h2>Not claimed yet?</h2><p class="cta"><a class="btn" href="{P('claim')}">Claim your listing</a> <a class="btn ghost" href="{P('get-listed')}">Not listed? Get listed free</a></p></section>""")


def badge_page():
    """Badge firms can put on their own site, linking back to their town page."""
    towns = sorted(((v["name"], k) for k, v in D["towns"].items()))
    topts = "".join(f'<option value="{k}">{e(n)}</option>' for n, k in towns)
    tr = "".join(f'<option value="{t}" data-n="{e(v["name"].lower())}">{e(v["name"])}</option>' for t, v in D["trades"].items())
    simple("badge", "Show you're listed", "Free badge for firms listed on Top Trades Near Me. Add it to your website so customers can see your rating and reviews.", f"""
<section class="hero"><h1>Show customers you're listed</h1><p class="lede">Put this free badge on your website. It links to your town page, where customers can see your Google rating next to other local firms.</p></section>
<section class="firm-sec"><p><img src="{SITE}/badge.svg" alt="Listed on Top Trades Near Me" width="220" height="64"></p>
<p><label>Your trade <select id="bt">{tr}</select></label> <label>Your town <select id="bw">{topts}</select></label></p>
<p>Copy this code and paste it into your website, for example in the footer. Your web designer can do it in a minute.</p>
<textarea id="bc" rows="4" readonly style="width:100%;font:13px var(--mono)"></textarea>
<p class="cta"><button type="button" class="btn" id="bcopy">Copy code</button></p>
<p class="msg">The badge says you are listed. It does not say you are recommended, vetted or top rated, and it never changes your place in the ranking. Not listed yet? <a href="{P('get-listed')}">Get listed free</a>.</p></section>
<script>(function(){{var t=document.getElementById("bt"),w=document.getElementById("bw"),c=document.getElementById("bc");
function up(){{var n=t.options[t.selectedIndex].dataset.n,tn=w.options[w.selectedIndex].text;
c.value='<a href="{SITE}/'+t.value+'/'+w.value+'/" title="'+t.options[t.selectedIndex].text+' in '+tn+' on Top Trades Near Me"><img src="{SITE}/badge.svg" alt="Listed on Top Trades Near Me: '+n+' in '+tn+'" width="220" height="64"></a>';}}
t.onchange=w.onchange=up;up();document.getElementById("bcopy").onclick=function(){{c.select();try{{navigator.clipboard.writeText(c.value)}}catch(x){{document.execCommand("copy")}}this.textContent="Copied";}};}})();</script>""")


def llms_txt():
    """Plain summary for AI assistants (llmstxt.org format)."""
    n = sum(len(v) for v in D["listings"].values())
    out = [f"# {BRAND}", "",
           f"> Local roofers, driveway companies and plumbers in {len(D['towns'])} towns across {region()}, ranked by their Google rating "
           f"weighted by review count. {n} listings, ratings checked {D['checked']}. Run by Buildster Digital, Oxford.", "",
           "How the ranking works: Google star rating (out of 5) multiplied by log10(number of reviews + 1). Firms cannot pay to move up. "
           "Sponsored spots are labelled and sit outside the ranked list. Firms with no Google rating are listed after, in no order. "
           "Each town page also covers the villages around it.",
           "Disclosure: Buildster Digital is in the same group as Revive Roofing, Revive Plumbing and Revive Driveways, which appear only in labelled sponsored boxes.",
           "Homeowners can ask for free quotes from up to three local firms on any town page.", "",
           "## Trades", ""]
    for t, tv in D["trades"].items():
        out.append(f"- [{tv['name']}]({SITE}{L(t)}): {tv['intro']}")
    for t, tv in D["trades"].items():
        out += ["", f"## {tv['name']} by area", ""]
        out += [f"- [{tv['name']} in {D['areas'][a]['name']}]({SITE}{L(t, a)}): " + ", ".join(D["towns"][x]["name"] for x in area_towns(a))
                for a in LIVE_AREAS]
    out += ["", "## Optional", "",
            f"- [Privacy notice]({SITE}{P('privacy')})", f"- [Terms]({SITE}{P('terms')})",
            f"- [Claim a listing (for firms)]({SITE}{P('claim')})", "",
            f"Town pages follow the pattern {SITE}/<trade>/<town>/, for example {SITE}{L(next(iter(D['trades'])), next(iter(D['towns'])))}.", ""]
    return "\n".join(out)



def svc_links(tw):
    """Links from a town page to the single-service pages for that town."""
    got = [(sl, sv) for sl, sv in SERVICES.items() if tw in sv["towns"]]
    if not got:
        return ""
    return f'<p class="also">Also in {e(D["towns"][tw]["name"])}: ' + " ".join(f'<a href="{L(sl, tw)}">{e(sv["name"])}</a>' for sl, sv in got) + "</p>"


def svc_sponsors(sl, tw):
    """Revive (within 30 miles of Oxford) first, then any named extra sponsors that already sponsor the parent trade."""
    sv = SERVICES[sl]
    out = []
    if sponsored_here(tw):
        out.append(dict(D["sponsors"]["roofers"], services=sv["sponsor"]["services"]))
    for name in sv.get("extra_sponsors", {}).get(tw, []):
        out += [b for b in D.get("extra_sponsors", []) if b["name"] == name][:1]
    return out


def svc_strip(towns=None, h="Specialist services"):
    """Cards linking to the single-service pages (optionally only for some towns)."""
    cards = [f'<a class="area live" href="{L(sl, tw)}"><b>{e(sv["name"])}</b><span>{e(D["towns"][tw]["name"])} · {len(sv["towns"][tw])} firms</span></a>'
             for sl, sv in SERVICES.items() for tw in sv["towns"] if towns is None or tw in towns]
    return f'<section class="arealist svc"><h2>{e(h)}</h2><div class="areas-grid">{"".join(cards)}</div></section>' if cards else ""


def service_page(sl, tw):
    sv, twv = SERVICES[sl], D["towns"][tw]
    town = twv["name"]
    fmt = lambda x: x.replace("{town}", town)
    items = sorted(sv["towns"][tw], key=score, reverse=True)
    yr = sv["checked"][-4:]
    name_l = sv["name"].lower()
    title = fit(f'{sv["name"]} in {town}: {len(items)} firms ranked ({yr})', f'{sv["name"]} in {town} ({yr})')
    top = next((b for b in items if "rating" in b and "reviews" in b), None)
    desc = (f'{len(items)} {name_l} firms in {town} ranked by Google reviews, with prices and what to ask. Free quotes from up to 3 firms.')
    if len(desc) > 160:
        desc = f'{sv["name"]} in {town}: firms ranked by Google reviews, prices and free quotes.'
    rated = [b for b in items if "rating" in b][:3]
    rt = lambda b: f'{b["rating"]:g} out of {b["scale"]}' + (f' from {b["reviews"]} reviews' if "reviews" in b else "")
    answer = (f'The highest-rated firms Google shows for {name_l} in {town} are ' + "; ".join(f'{b["name"]} ({rt(b)})' for b in rated)
              + f'. Ratings checked {sv["checked"]}.') if rated else ""
    sps = svc_sponsors(sl, tw)
    sp_html = "\n".join(sponsor(None, b) for b in sps)
    left = 2 - len(sps)
    feat = (f'<div class="featured"><span class="tag">Sponsored spot</span><p><strong>{"One more sponsored spot" if left == 1 else "Two sponsored spots"} free for a {e(sv["single"])} in {e(town)}.</strong> '
            f'Top of the page, your photos, your number.</p><a href="{e(claim_link(trade=sv["short"], town=town))}" rel="nofollow">Ask about it</a></div>') if left > 0 else ""
    lst = "".join(card(i + 1, b, sl, tw) for i, b in enumerate(items))
    guide = "".join(f'<section class="guide"><h2>{e(fmt(h))}</h2>{fmt(body)}</section>' for h, body in sv["guide"])
    tips = "".join(f"<li>{e(fmt(x))}</li>" for x in sv["tips"])
    faqs = [(f'How do I get quotes for {name_l} in {town}?',
             f'Use the free quote form on this page. We pass your job to up to three firms that do {name_l} in {town}, or you can contact any firm above directly.'),
            ("How is this list ranked?",
             "By Google star rating, weighted by how many reviews it is based on. Firms cannot pay to move up. Sponsored spots are labelled and sit outside the ranked list.")] \
        + [(fmt(q), fmt(a)) for q, a in sv["faq"]]
    faq_html = "".join(f"<h3>{e(q)}</h3><p>{e(a)}</p>" for q, a in faqs)
    par = sv.get("parent")
    if par:
        crumbs = f'<a href="{L()}">Home</a> / <a href="{L(par)}">{e(D["trades"][par]["name"])}</a> / <a href="{L(par, tw)}">{e(town)}</a> / {e(sv["name"])}'
        steps = [("Home", "/"), (D["trades"][par]["name"], L(par)), (town, L(par, tw)), (sv["name"], L(sl, tw))]
        back = f'<p class="also">All roofers in {e(town)}, for tiled and slate roofs too: <a href="{L(par, tw)}">Roofers in {e(town)}</a></p>'
    else:
        crumbs = f'<a href="{L()}">Home</a> / {e(sv["name"])} / {e(town)}'
        steps = [("Home", "/"), (f'{sv["name"]} in {town}', L(sl, tw))]
        back = ""
    others = " ".join(f'<a href="{L(o, tw)}">{e(SERVICES[o]["name"]) if o in SERVICES else e(D["trades"][o]["name"])}</a>'
                      for o in list(D["trades"]) + [x for x in SERVICES if tw in SERVICES[x]["towns"]] if o != sl and o != par)
    body = f'''{header()}
<main class="wrap">
<p class="crumbs">{crumbs}</p>
<section class="hero"><h1>{e(sv["name"])} in {e(town)}</h1>
<p class="lede">{e(sv["intro"])} Covering {e(town)} and nearby villages including {e(twv["villages"])}.</p>
<p class="stamp">{len(items)} firms listed · Google ratings checked {sv["checked"]}</p>
{f'<p class="answer">{e(answer)}</p>' if answer else ""}</section>
<div class="grid">
<div class="main">
{sp_html}
{feat}
<p class="note">{e(fmt(sv["list_note"]))}</p>
<ol class="list">{lst}</ol>
{guide}
<section class="tips"><h2>Before you hire a {e(sv["single"])} in {e(town)}</h2><ul>{tips}</ul></section>
<section class="faq"><h2>Questions about {e(name_l)} in {e(town)}</h2>{faq_html}</section>
{back}
<p class="also">Other trades in {e(town)}: {others}</p>
</div>
<aside class="quote"><h2>Get up to 3 quotes</h2><p>Tell us the job once. We pass it to up to three firms that do {e(name_l)} in {e(town)}.</p>
{ghl("quote", f"Quote request: {sv['short']} in {town}", 760, trade=sv["short"], town=town)}
<p class="msg">Free, no obligation. We share your details only with the up to three firms we pass your job to, which may include sponsored firms. We do not vet or guarantee firms. <a href="{P('privacy')}">Privacy</a> · <a href="{P('terms')}">Terms</a></p></aside>
</div></main>
{footer()}'''
    data = ld(crumbs_ld(*steps),
              {"@type": "CollectionPage", "@id": SITE + L(sl, tw), "url": SITE + L(sl, tw), "name": title, "description": desc,
               "isPartOf": {"@id": SITE + "/#site"},
               "spatialCoverage": [{"@type": "City", "name": town}],
               "mainEntity": {"@type": "ItemList", "name": f'{sv["name"]} in {town}', "numberOfItems": len(items),
                              "itemListElement": [{"@type": "ListItem", "position": i + 1,
                                                   "item": {"@type": "HomeAndConstructionBusiness", "name": b["name"], "areaServed": town}}
                                                  for i, b in enumerate(items)]}},
              {"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faqs]})
    write(wrap_doc(title, desc, L(sl, tw), body, data), sl, tw)


for t in D["trades"]:
    trade_index(t)
    for a in LIVE_AREAS:
        area_page(t, a)
    for tw in D["towns"]:
        page(t, tw)
index()
pages()
for_firms()
badge_page()
review_pages()
dashboard()
for slug in FIRMS:
    firm_page(slug)
for sl, sv in SERVICES.items():
    for tw in sv["towns"]:
        service_page(sl, tw)
if LIVE:
    import shutil
    shutil.copy(os.path.join(HERE, "style.css"), os.path.join(OUT, "style.css"))
    urls = ["/"] + [P(x) for x in ("claim", "get-listed", "for-firms", "badge", "review", "reviews-policy", "privacy", "terms")] + [F(x) for x in FIRMS] + [L(t) for t in D["trades"]] + [L(t, a) for t in D["trades"] for a in LIVE_AREAS] + [L(t, tw) for t in D["trades"] for tw in D["towns"] if (t, tw) not in WEAK] + [L(sl, tw) for sl in SERVICES for tw in SERVICES[sl]["towns"]]
    # lastmod = the day a page's content last changed, so Google can see what is new.
    import datetime, hashlib
    state_file = os.path.join(HERE, "lastmod.json")
    state = json.load(open(state_file)) if os.path.exists(state_file) else {}
    today = os.environ.get("BUILD_DATE") or datetime.date.today().isoformat()
    lastmod = {}
    for u in urls:
        fp = os.path.join(OUT, u.strip("/"), "index.html") if u != "/" else os.path.join(OUT, "index.html")
        h = hashlib.sha1(open(fp, "rb").read()).hexdigest()
        old = state.get(u)
        lastmod[u] = old[1] if old and old[0] == h else today
        state[u] = [h, lastmod[u]]
    json.dump({u: state[u] for u in urls}, open(state_file, "w"), indent=0, sort_keys=True)
    open(os.path.join(OUT, "sitemap.xml"), "w").write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "".join(f"<url><loc>{SITE}{u}</loc><lastmod>{lastmod[u]}</lastmod></url>\n" for u in urls) + "</urlset>\n")
    # IndexNow: lets Bing (and Yandex, Seznam, Naver) know about changed pages straight away
    open(os.path.join(OUT, INDEXNOW_KEY + ".txt"), "w").write(INDEXNOW_KEY)
    open(os.path.join(OUT, "_redirects"), "w").write(
        "https://toptradesnearme.com/* https://toptradesnearme.co.uk/:splat 301!\n"
        "https://www.toptradesnearme.com/* https://toptradesnearme.co.uk/:splat 301!\n"
        "https://www.toptradesnearme.co.uk/* https://toptradesnearme.co.uk/:splat 301!\n")
    bots = ["Googlebot", "Bingbot", "Google-Extended", "GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-SearchBot",
            "Claude-User", "PerplexityBot", "Perplexity-User", "Applebot", "Applebot-Extended", "DuckAssistBot", "Amazonbot", "meta-externalagent"]
    open(os.path.join(OUT, "robots.txt"), "w").write(
        "# Search engines and AI assistants are welcome to read and cite this site.\n"
        + "# Claim links carry each firm's name in the address. They are all one form, so crawlers skip them.\n"
        + "".join(f"User-agent: {b}\n" for b in bots) + "Allow: /\nDisallow: /claim/?\n\nUser-agent: *\nAllow: /\nDisallow: /claim/?\n\nSitemap: " + SITE + "/sitemap.xml\n")
    open(os.path.join(OUT, "llms.txt"), "w").write(llms_txt())
    open(os.path.join(OUT, "CNAME"), "w").write("toptradesnearme.co.uk\n")
    open(os.path.join(OUT, "404.html"), "w").write('<!doctype html><meta charset="utf-8"><title>Page not found</title><p>Page not found. <a href="/">Go to Top Trades Near Me</a></p>')
for f in BRAND_FILES:
    shutil.copy(os.path.join(HERE, "brand", f), os.path.join(OUT, f))
shutil.copy(os.path.join(HERE, "finder.js"), os.path.join(OUT, "finder.js"))
shutil.copy(os.path.join(HERE, "dashboard.js"), os.path.join(OUT, "dashboard.js"))
shutil.copytree(os.path.join(HERE, "vendor"), os.path.join(OUT, "vendor"), dirs_exist_ok=True)
shutil.copytree(os.path.join(HERE, "fonts"), os.path.join(OUT, "fonts"), dirs_exist_ok=True)
print("built", len(os.listdir(OUT)), "files")
