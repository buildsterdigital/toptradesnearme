#!/usr/bin/env python3
"""Builds the Top Trades Near preview site from data.json into ./site/"""
import json, math, html, os

HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(HERE, "data.json")))
LIVE = os.environ.get("LIVE") == "1"
SITE = "https://toptradesnearme.co.uk"
OUT = os.path.join(HERE, "site-live" if LIVE else "site")
os.makedirs(OUT, exist_ok=True)
e = html.escape
BRAND = "Top Trades Near Me"

FONTS = '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;700;800&family=Source+Sans+3:wght@400;600&family=IBM+Plex+Mono:wght@500&display=swap">'


def L(t=None, tw=None):
    """Link to a page: folder URLs on the live site, flat files in the preview."""
    if t is None:
        return "/" if LIVE else "index.html"
    return f"/{t}/{tw}/" if LIVE else f"{t}-{tw}.html"


def score(b):
    if "rating" not in b:
        return 0
    r = b["rating"] / b["scale"]
    return r * (math.log10(b["reviews"] + 1) if "reviews" in b else 0.5)


def head(title, desc, path="/"):
    extra = (f'<link rel="canonical" href="{SITE}{path}">\n<meta property="og:title" content="{e(title)}">\n' if LIVE
             else '<meta name="claude:viewport-fit-sides" content="cover">\n')
    css = "/style.css" if LIVE else "style.css"
    return (f'<title>{e(title)}</title>\n<meta name="description" content="{e(desc)}">\n'
            f'{extra}{FONTS}\n<link rel="stylesheet" href="{css}">\n')


def header():
    trades = "".join(f'<a href="{L(t, "oxford")}">{e(v["short"])}</a>' for t, v in D["trades"].items())
    return (f'<header class="top"><div class="wrap bar"><a class="logo" href="{L()}"><span class="mark">10</span>{BRAND}</a>'
            f'<nav>{trades}<a class="getlisted" href="{L()}#get-listed">Get listed</a></nav></div></header>'
            + ("" if LIVE else '<div class="preview">Preview only. Listings checked ' + D["checked"] + '. Not live yet.</div>'))


def footer():
    links = []
    for t, tv in D["trades"].items():
        for tw, twv in D["towns"].items():
            links.append(f'<a href="{L(t, tw)}">{e(tv["short"])} in {e(twv["name"])}</a>')
    return ('<footer><div class="wrap foot"><div><p class="logo small"><span class="mark">10</span>' + BRAND + '</p>'
            '<p>Local trades ranked by public reviews. Run by <strong>Buildster Digital</strong>, Oxford.</p>'
            '<p class="fine">How we rank: rating out of the maximum, weighted by how many reviews it is based on. Firms without a checked rating are listed after, in no order. Sponsored listings are paid placements, always labelled, and sit outside the ranking.</p>'
            '<p class="fine">Top Trades Near Me is run by Buildster Digital, part of the same group as Revive Roofing, Revive Plumbing and Revive Driveways.</p>'
            '<p class="fine">Your business listed and want it changed or removed? Email listings@toptradesnearme.co.uk and we will do it within 48 hours.</p></div>'
            '<div class="sitemap">' + "".join(links) + '</div></div></footer>')


def card(i, b):
    if "rating" in b:
        stars = f'{b["rating"]:g}<span>/{b["scale"]}</span>'
        cnt = f'{b["reviews"]} reviews' if "reviews" in b else "review count not shown"
        rate = f'<div class="rate"><b>{stars}</b><small>{cnt} · {e(b["source"])}</small></div>'
    else:
        rate = '<div class="rate none"><small>Rating not checked yet</small></div>'
    own = ""
    link = f'<a class="more" href="{e(b["url"])}" target="_blank" rel="nofollow noopener">View profile</a>' if b.get("url") else ""
    pos = i if "rating" in b else "–"
    return (f'<li class="biz"><div class="pos">{pos}</div><div class="body"><h3>{e(b["name"])}</h3>'
            f'<p class="meta">{e(b["base"])}{(" · " + e(b["services"])) if b.get("services") else ""}</p>{own}</div>{rate}{link}</li>')


def sponsor(t):
    b = D["sponsors"][t]
    rate = (f'<div class="rate"><b>{b["rating"]:g}<span>/{b["scale"]}</span></b><small>{b["reviews"]} reviews · {e(b["source"])}</small></div>' if "rating" in b else "")
    link = f'<a class="more" href="{e(b["url"])}" target="_blank" rel="noopener">Visit website</a>' if b.get("url") else ""
    return (f'<div class="sponsored"><span class="tag">Sponsored</span><div class="sp-row"><div class="body"><h3>{e(b["name"])}</h3>'
            f'<p class="meta">{e(b["base"])}</p><p>{e(b["services"])}</p><p class="phone">{e(b["phone"])}</p></div>{rate}</div>{link}</div>')


def page(t, tw):
    tv, twv = D["trades"][t], D["towns"][tw]
    items = sorted(D["listings"][f"{t}/{tw}"], key=score, reverse=True)
    title = f'{len(items)} best {tv["name"].lower()} in {twv["name"]} ({D["checked"][-4:]})'
    desc = f'Compare {tv["name"].lower()} in {twv["name"]}: ratings, review counts and what to check before you hire. {tv["intro"]}'
    others = "".join(f'<a href="{L(t, o)}">{e(ov["name"])}</a>' for o, ov in D["towns"].items() if o != tw)
    other_trades = "".join(f'<a href="{L(o, tw)}">{e(ov["name"])}</a>' for o, ov in D["trades"].items() if o != t)
    tips = "".join(f"<li>{e(x)}</li>" for x in tv["tips"])
    lst = "".join(card(i + 1, b) for i, b in enumerate(items))
    body = f'''{header()}
<main class="wrap">
<p class="crumbs"><a href="{L()}">Home</a> / {e(tv["name"])} / {e(twv["name"])}</p>
<section class="hero"><h1>Top {e(tv["name"].lower())} in {e(twv["name"])}</h1>
<p class="lede">{e(tv["intro"])} Covering {e(twv["name"])} and nearby villages including {e(twv["villages"])}.</p>
<p class="stamp">{len(items)} firms listed · ratings checked {D["checked"]}</p></section>
<div class="grid">
<div class="main">
{sponsor(t)}
<div class="featured"><span class="tag">Sponsored spot</span><p><strong>One more sponsored spot free for a {e(tv["single"])} in {e(twv["name"])}.</strong> Top of the page, your photos, your number.</p><a href="{L()}#get-listed">Claim it</a></div>
<ol class="list">{lst}</ol>
<section class="areas"><h2>Villages covered from {e(twv["name"])}</h2><div class="chips">{"".join(f"<span>{e(v.strip())}</span>" for v in twv["villages"].split(","))}</div></section>
<section class="tips"><h2>Before you hire a {e(tv["single"])} in {e(twv["name"])}</h2><ul>{tips}</ul></section>
<p class="also">{e(tv["name"])} nearby: {others}</p>
<p class="also">Other trades in {e(twv["name"])}: {other_trades}</p>
</div>
<aside class="quote"><h2>Get up to 3 quotes</h2><p>Tell us the job once. We pass it to up to three {e(tv["name"].lower())} in {e(twv["name"])}.</p>
<form class="qf" id="qf-{t}-{tw}"><label for="q-job-{t}-{tw}">What needs doing?</label><textarea id="q-job-{t}-{tw}" rows="3" required></textarea>
<label for="q-pc-{t}-{tw}">Postcode</label><input id="q-pc-{t}-{tw}" required>
<label for="q-ph-{t}-{tw}">Phone</label><input id="q-ph-{t}-{tw}" type="tel" required>
<button type="submit">Send my job</button><p class="msg" hidden>Preview only: on the live site this goes into the Buildster lead pipeline.</p></form></aside>
</div></main>
{footer()}
<script>document.querySelectorAll('.qf').forEach(f=>f.addEventListener('submit',ev=>{{ev.preventDefault();f.querySelector('.msg').hidden=false;}}));</script>'''
    doc = f'<!doctype html>\n<html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n{head(title, desc, L(t, tw))}</head><body>{body}</body></html>'
    if LIVE:
        os.makedirs(os.path.join(OUT, t, tw), exist_ok=True)
        open(os.path.join(OUT, t, tw, "index.html"), "w").write(doc)
    else:
        open(os.path.join(OUT, f"{t}-{tw}.html"), "w").write(doc)


def index():
    tiles = []
    for t, tv in D["trades"].items():
        towns = "".join(f'<a href="{L(t, tw)}">{e(twv["name"])} <span>{len(D["listings"][f"{t}/{tw}"])}</span></a>' for tw, twv in D["towns"].items())
        tiles.append(f'<div class="trade"><h2>{e(tv["name"])}</h2><p>{e(tv["intro"])}</p><div class="towns">{towns}</div></div>')
    soon = "".join(f"<span>{x}</span>" for x in ["Electricians", "Patios", "Heat pumps", "Builders", "Fencing", "Landscapers", "Kitchens", "Loft conversions"])
    total = sum(len(v) for v in D["listings"].values())
    body = f'''{header()}
<main class="wrap">
<section class="hero home"><h1>Find a trade near you that other people rate.</h1>
<p class="lede">Roofers, driveway firms and plumbers across Oxfordshire, ranked by real public reviews. No pay-to-be-number-one.</p>
<p class="stamp">{total} listings · {len(D["towns"])} towns · 3 trades · checked {D["checked"]}</p></section>
<div class="trades">{"".join(tiles)}</div>
<section class="soon"><h2>Coming next</h2><div class="chips">{soon}</div><p>Then the rest of the 60-mile ring: Reading, Swindon, Newbury, High Wycombe, Aylesbury and Cheltenham.</p></section>
<section class="getlisted-box" id="get-listed"><h2>Are you a trade?</h2>
<p>Every firm here is listed free. Want a sponsored spot at the top of your town page, more reviews, or your details changed? We will sort it.</p>
<form class="qf" id="gl"><label for="gl-biz">Business name</label><input id="gl-biz" required><label for="gl-ph">Mobile</label><input id="gl-ph" type="tel" required><button type="submit">Get featured</button><p class="msg" hidden>Preview only: on the live site this goes into Buildster's pipeline.</p></form></section>
</main>
{footer()}
<script>document.querySelectorAll('.qf').forEach(f=>f.addEventListener('submit',ev=>{{ev.preventDefault();f.querySelector('.msg').hidden=false;}}));</script>'''
    h = head(f"{BRAND}: Oxfordshire roofers, driveways and plumbers", "Oxfordshire trades ranked by public reviews.", "/")
    if LIVE:
        doc = f'<!doctype html>\n<html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">\n{h}</head><body>{body}</body></html>'
    else:
        doc = h + body
    open(os.path.join(OUT, "index.html"), "w").write(doc)


for t in D["trades"]:
    for tw in D["towns"]:
        page(t, tw)
index()
if LIVE:
    import shutil
    shutil.copy(os.path.join(HERE, "site", "style.css"), os.path.join(OUT, "style.css"))
    urls = ["/"] + [L(t, tw) for t in D["trades"] for tw in D["towns"]]
    open(os.path.join(OUT, "sitemap.xml"), "w").write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "".join(f"<url><loc>{SITE}{u}</loc></url>\n" for u in urls) + "</urlset>\n")
    open(os.path.join(OUT, "robots.txt"), "w").write(f"User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n")
    open(os.path.join(OUT, "CNAME"), "w").write("toptradesnearme.co.uk\n")
    open(os.path.join(OUT, "404.html"), "w").write('<!doctype html><meta charset="utf-8"><title>Page not found</title><p>Page not found. <a href="/">Go to Top Trades Near Me</a></p>')
print("built", len(os.listdir(OUT)), "files")
