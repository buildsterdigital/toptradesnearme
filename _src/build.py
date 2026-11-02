#!/usr/bin/env python3
"""Builds the Top Trades Near preview site from data.json into ./site/"""
import json, math, html, os, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(HERE, "data.json")))
LIVE = os.environ.get("LIVE") == "1"
SITE = "https://toptradesnearme.co.uk"
OUT = os.path.join(HERE, "site-live" if LIVE else "site")
os.makedirs(OUT, exist_ok=True)
e = html.escape
BRAND = "Top Trades Near Me"

# GoHighLevel forms in the Top Trades Near Me sub-account (rRAiUOKmHY43FAxBFsPm)
FORMS = {"claim": "GPJqPB3I4ubYbyjVMrV9", "listed": "5D9mtepQQLMAKM11lmpK", "quote": "gUv916EvMBG5WQ7pqGPM"}
FORM_JS = '<script src="https://link.msgsndr.com/js/form_embed.js"></script>'


def ghl(key, title, height, forward=False, **params):
    """Embed a GHL form. params prefill fields by query key; forward=True also passes this page's own ?query on."""
    fid = FORMS[key]
    src = f"https://api.leadconnectorhq.com/widget/form/{fid}"
    if params:
        src += "?" + urllib.parse.urlencode(params)
    attrs = (f'src="{e(src)}" id="inline-{fid}" data-layout="{{\'id\':\'INLINE\'}}" data-trigger-type="alwaysShow" data-trigger-value="" '
             f'data-activation-type="alwaysActivated" data-activation-value="" data-deactivation-type="neverDeactivate" data-deactivation-value="" '
             f'data-form-name="{e(title)}" data-height="{height}" data-layout-iframe-id="inline-{fid}" data-form-id="{fid}" title="{e(title)}" '
             f'class="ghl" style="width:100%;height:{height}px;border:none;border-radius:8px"')
    fwd = ("<script>(function(f){if(location.search)f.src=f.src.split('?')[0]+location.search;})"
           f"(document.getElementById('inline-{fid}'));</script>") if forward else ""
    return f"<iframe {attrs}></iframe>{fwd}{FORM_JS}"


def P(name):
    """Link to a standalone page such as claim or privacy."""
    return f"/{name}/" if LIVE else f"{name}.html"


def claim_link(**params):
    return P("claim") + "?" + urllib.parse.urlencode(params)

FONTS = '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;700;800&family=Source+Sans+3:wght@400;600&family=IBM+Plex+Mono:wght@500&display=swap">'


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


def head(title, desc, path="/"):
    extra = (f'<link rel="canonical" href="{SITE}{path}">\n<meta property="og:title" content="{e(title)}">\n' if LIVE
             else '<meta name="claude:viewport-fit-sides" content="cover">\n')
    css = "/style.css" if LIVE else "style.css"
    return (f'<title>{e(title)}</title>\n<meta name="description" content="{e(desc)}">\n'
            f'{extra}{FONTS}\n<link rel="stylesheet" href="{css}">\n')


def header():
    trades = "".join(f'<a href="{L(t)}">{e(v["short"])}</a>' for t, v in D["trades"].items())
    return (f'<header class="top"><div class="wrap bar"><a class="logo" href="{L()}"><span class="mark">10</span>{BRAND}</a>'
            f'<nav>{trades}<a class="getlisted" href="{P('get-listed')}">Get listed</a></nav></div></header>'
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
            '<p class="fine">Your business listed and want it changed or removed? Email listings@toptradesnearme.co.uk and we will do it within 48 hours.</p>'
            f'<p class="fine"><a href="{P("claim")}">Claim your listing</a> · <a href="{P("get-listed")}">Get listed</a> · <a href="{P("privacy")}">Privacy</a></p></div>'
            '<div class="sitemap">' + "".join(links) + '</div></div></footer>')


def card(i, b, t=None, tw=None):
    if "rating" in b:
        stars = f'{b["rating"]:g}<span>/{b["scale"]}</span>'
        cnt = f'{b["reviews"]} reviews' if "reviews" in b else "review count not shown"
        rate = f'<div class="rate"><b>{stars}</b><small>{cnt} · {e(b["source"])}</small></div>'
    else:
        rate = '<div class="rate none"><small>Rating not checked yet</small></div>'
    own = (f'<p class="claim"><a href="{e(claim_link(organization=b["name"], trade=D["trades"][t]["short"], town=D["towns"][tw]["name"]))}" rel="nofollow">Your business? Claim this listing</a></p>' if t else "")
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
    others = " ".join(f'<a href="{L(t, o)}">{e(ov["name"])}</a>' for o, ov in D["towns"].items() if o != tw)
    other_trades = " ".join(f'<a href="{L(o, tw)}">{e(ov["name"])}</a>' for o, ov in D["trades"].items() if o != t)
    tips = "".join(f"<li>{e(x)}</li>" for x in tv["tips"])
    lst = "".join(card(i + 1, b, t, tw) for i, b in enumerate(items))
    body = f'''{header()}
<main class="wrap">
<p class="crumbs"><a href="{L()}">Home</a> / <a href="{L(t)}">{e(tv["name"])}</a> / {e(twv["name"])}</p>
<section class="hero"><h1>Top {e(tv["name"].lower())} in {e(twv["name"])}</h1>
<p class="lede">{e(tv["intro"])} Covering {e(twv["name"])} and nearby villages including {e(twv["villages"])}.</p>
<p class="stamp">{len(items)} firms listed · ratings checked {D["checked"]}</p></section>
<div class="grid">
<div class="main">
{sponsor(t)}
<div class="featured"><span class="tag">Sponsored spot</span><p><strong>One more sponsored spot free for a {e(tv["single"])} in {e(twv["name"])}.</strong> Top of the page, your photos, your number.</p><a href="{e(claim_link(trade=tv["short"], town=twv["name"]))}" rel="nofollow">Ask about it</a></div>
<ol class="list">{lst}</ol>
<section class="areas"><h2>Villages covered from {e(twv["name"])}</h2><div class="chips">{"".join(f"<span>{e(v.strip())}</span>" for v in twv["villages"].split(","))}</div></section>
<section class="tips"><h2>Before you hire a {e(tv["single"])} in {e(twv["name"])}</h2><ul>{tips}</ul></section>
<p class="also">{e(tv["name"])} nearby: {others}</p>
<p class="also">Other trades in {e(twv["name"])}: {other_trades}</p>
</div>
<aside class="quote"><h2>Get up to 3 quotes</h2><p>Tell us the job once. We pass it to up to three {e(tv["name"].lower())} in {e(twv["name"])}.</p>
{ghl("quote", f"Quote request: {tv['short']} in {twv['name']}", 760, trade=tv["short"], town=twv["name"])}
<p class="msg">Free, no obligation. We share your details only with the firms we pass your job to. <a href="{P('privacy')}">Privacy</a></p></aside>
</div></main>
{footer()}'''
    doc = f'<!doctype html>\n<html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n{head(title, desc, L(t, tw))}</head><body>{body}</body></html>'
    if LIVE:
        os.makedirs(os.path.join(OUT, t, tw), exist_ok=True)
        open(os.path.join(OUT, t, tw, "index.html"), "w").write(doc)
    else:
        open(os.path.join(OUT, f"{t}-{tw}.html"), "w").write(doc)


def trade_index(t):
    tv = D["trades"][t]
    n = sum(len(D["listings"][f"{t}/{tw}"]) for tw in D["towns"])
    towns = "".join(f'<a href="{L(t, tw)}">{e(twv["name"])} <span>{len(D["listings"][f"{t}/{tw}"])}</span></a>' for tw, twv in D["towns"].items())
    tips = "".join(f"<li>{e(x)}</li>" for x in tv["tips"])
    others = "".join(f'<a href="{L(o)}">{e(ov["name"])}</a>' for o, ov in D["trades"].items() if o != t)
    title = f'{tv["name"]} in Oxfordshire, ranked by reviews ({D["checked"][-4:]})'
    desc = f'Find {tv["name"].lower()} in {len(D["towns"])} Oxfordshire towns, ranked by public reviews. {tv["intro"]}'
    body = f'''{header()}
<main class="wrap">
<p class="crumbs"><a href="{L()}">Home</a> / {e(tv["name"])}</p>
<section class="hero"><h1>{e(tv["name"])} in Oxfordshire</h1>
<p class="lede">{e(tv["intro"])} Pick your town to see local firms ranked by public reviews.</p>
<p class="stamp">{n} listings · {len(D["towns"])} towns · checked {D["checked"]}</p></section>
<div class="trade"><h2>Choose your town</h2><div class="towns">{towns}</div></div>
<section class="tips"><h2>Before you hire a {e(tv["single"])}</h2><ul>{tips}</ul></section>
<p class="also">Other trades: {others}</p>
</main>
{footer()}'''
    doc = f'<!doctype html>\n<html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n{head(title, desc, L(t))}</head><body>{body}</body></html>'
    if LIVE:
        os.makedirs(os.path.join(OUT, t), exist_ok=True)
        open(os.path.join(OUT, t, "index.html"), "w").write(doc)
    else:
        open(os.path.join(OUT, f"{t}.html"), "w").write(doc)


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
<p class="msg">We use these details to contact you about your listing. <a href="{P('privacy')}">Privacy</a></p>''')
    simple("get-listed", "Get listed", "Local trade not on Top Trades Near Me yet? Ask to be listed. Free.", f'''
<section class="hero"><h1>Get your business listed</h1>
<p class="lede">Listing is free. We add firms that work in the towns we cover and rank everyone by public reviews, so the better your reviews, the higher you sit.</p></section>
<div class="formbox">{ghl("listed", "Get listed", 1000, forward=True)}</div>
<p class="msg">We use these details to check and list your business and to contact you about it. <a href="{P('privacy')}">Privacy</a></p>''')
    simple("privacy", "Privacy notice", "How Top Trades Near Me uses the details you send us.", '''
<section class="hero"><h1>Privacy notice</h1><p class="stamp">Last updated 2 November 2026</p></section>
<div class="prose">
<p>Top Trades Near Me is run by Buildster Digital, 12 Red Bridge Hollow, Oxford OX1 4XS. Questions about your data: listings@toptradesnearme.co.uk.</p>
<h2>If you ask for quotes</h2>
<p>We collect your name, phone, email (if given), postcode and the job you describe. We use them to pass your job to up to three local firms who do that kind of work, and to check the request with you. The legal basis is your request. Those firms then contact you directly and handle your details under their own privacy terms.</p>
<h2>If you run a listed business</h2>
<p>Business listings use publicly available details such as name, area, services and public review ratings. If you claim a listing or ask to be listed, we use the details you send to update your listing and to contact you about it, including sponsored spots. You can ask us to change or remove a listing at any time.</p>
<h2>Who processes it</h2>
<p>Form entries are stored in our customer system, HighLevel (LeadConnector), which acts as our processor. We do not sell your details.</p>
<h2>How long we keep it</h2>
<p>Quote requests are kept for up to 12 months, then deleted. Business contact details are kept while the listing is active and for 12 months after.</p>
<h2>Your rights</h2>
<p>You can ask for a copy of your data, or for it to be corrected or deleted, by emailing listings@toptradesnearme.co.uk. You can also complain to the Information Commissioner's Office at ico.org.uk.</p>
</div>''')


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
<p class="cta"><a class="btn" href="{P('claim')}">Claim your listing</a> <a class="btn ghost" href="{P('get-listed')}">Not listed? Get listed free</a></p></section>
</main>
{footer()}'''
    h = head(f"{BRAND}: Oxfordshire roofers, driveways and plumbers", "Oxfordshire trades ranked by public reviews.", "/")
    if LIVE:
        doc = f'<!doctype html>\n<html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">\n{h}</head><body>{body}</body></html>'
    else:
        doc = h + body
    open(os.path.join(OUT, "index.html"), "w").write(doc)


for t in D["trades"]:
    trade_index(t)
    for tw in D["towns"]:
        page(t, tw)
index()
pages()
if LIVE:
    import shutil
    shutil.copy(os.path.join(HERE, "site", "style.css"), os.path.join(OUT, "style.css"))
    urls = ["/"] + [P(x) for x in ("claim", "get-listed")] + [L(t) for t in D["trades"]] + [L(t, tw) for t in D["trades"] for tw in D["towns"]]
    open(os.path.join(OUT, "sitemap.xml"), "w").write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "".join(f"<url><loc>{SITE}{u}</loc></url>\n" for u in urls) + "</urlset>\n")
    open(os.path.join(OUT, "robots.txt"), "w").write(f"User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n")
    open(os.path.join(OUT, "CNAME"), "w").write("toptradesnearme.co.uk\n")
    open(os.path.join(OUT, "404.html"), "w").write('<!doctype html><meta charset="utf-8"><title>Page not found</title><p>Page not found. <a href="/">Go to Top Trades Near Me</a></p>')
print("built", len(os.listdir(OUT)), "files")
