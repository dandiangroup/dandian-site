#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dandian site builder.
Читает articles/*.md (front-matter + markdown), кладёт результат в dist/:
  dist/index.html        — главная со списком статей
  dist/<slug>/index.html — страница каждой статьи
  dist/rss.xml           — лента для импорта в Дзен
  dist/assets/...        — обложки
  dist/robots.txt
Запуск:  python3 build.py
Зависимостей нет — только стандартная библиотека Python 3.
"""
import os, re, json, html, shutil
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
ART_DIR = os.path.join(ROOT, "articles")
ASSET_DIR = os.path.join(ROOT, "assets")
DIST = os.path.join(ROOT, "dist")

with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as f:
    CFG = json.load(f)

BASE = CFG["base_url"].rstrip("/")
OFFSET = CFG.get("timezone_offset", "+0300")

WD = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MO = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
RU_MO = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля",
         "августа", "сентября", "октября", "ноября", "декабря"]

# ---------- markdown (нужное подмножество) ----------
TOKEN = re.compile(r'\[(?P<lt>[^\]]+)\]\((?P<lu>[^)]+)\)|\*\*(?P<b>.+?)\*\*')

def inline(text):
    out, pos = [], 0
    for m in TOKEN.finditer(text):
        out.append(html.escape(text[pos:m.start()], quote=False))
        if m.group('lt') is not None:
            lt = html.escape(m.group('lt'), quote=False)
            lu = html.escape(m.group('lu'), quote=True)
            out.append(f'<a href="{lu}" target="_blank" rel="noopener">{lt}</a>')
        else:
            out.append(f"<strong>{html.escape(m.group('b'), quote=False)}</strong>")
        pos = m.end()
    out.append(html.escape(text[pos:], quote=False))
    return ''.join(out)

def md_to_html(body):
    blocks = re.split(r'\n\s*\n', body.strip())
    res = []
    for blk in blocks:
        lines = [l for l in blk.split('\n') if l.strip()]
        if not lines:
            continue
        if all(re.match(r'^\s*-\s+', l) for l in lines):
            items = ''.join(f'<li>{inline(re.sub(r"^\s*-\s+", "", l))}</li>' for l in lines)
            res.append(f'<ul>{items}</ul>')
        elif all(re.match(r'^\s*\d+\.\s+', l) for l in lines):
            items = ''.join(f'<li>{inline(re.sub(r"^\s*\d+\.\s+", "", l))}</li>' for l in lines)
            res.append(f'<ol>{items}</ol>')
        elif len(lines) == 1 and re.fullmatch(r'\*\*.+\*\*', lines[0]) and lines[0].count('**') == 2:
            txt = re.sub(r'^\*\*(.+)\*\*$', r'\1', lines[0])
            res.append(f'<h2>{inline(txt)}</h2>')
        else:
            res.append(f'<p>{inline(" ".join(lines))}</p>')
    return '\n'.join(res)

# ---------- front-matter ----------
def parse_article(path):
    raw = open(path, encoding='utf-8').read()
    m = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)$', raw, re.S)
    if not m:
        raise ValueError(f"Нет front-matter в {path}")
    meta = {}
    for line in m.group(1).split('\n'):
        if ':' in line:
            k, v = line.split(':', 1)
            meta[k.strip()] = v.strip()
    meta['_body'] = m.group(2).strip()
    meta['_dt'] = datetime.strptime(meta['date'], '%Y-%m-%d %H:%M')
    return meta

def rfc822(dt):
    return f"{WD[dt.weekday()]}, {dt.day:02d} {MO[dt.month-1]} {dt.year} {dt.hour:02d}:{dt.minute:02d}:00 {OFFSET}"

def ru_date(dt):
    return f"{dt.day} {RU_MO[dt.month-1]} {dt.year}"

def x(s):  # экранирование для XML по требованиям Дзена
    return (s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
             .replace('"', '&quot;').replace("'", '&apos;'))

# ---------- шаблоны ----------
CSS = """
:root{
  --paper:#FBF8F2; --ink:#232220; --soft:#5f5a50; --line:#e7e0d2;
  --green:#2f5d3a; --amber:#bd6f25; --lav:#6f5b93;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);
  font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
  font-size:18px;line-height:1.7;font-feature-settings:"liga" 1}
a{color:var(--green);text-underline-offset:3px;text-decoration-thickness:1px}
a:hover{color:var(--amber)}
img{max-width:100%;height:auto;display:block}
.wrap{max-width:720px;margin:0 auto;padding:0 22px}
.site-head{border-bottom:1px solid var(--line);background:rgba(251,248,242,.85)}
.site-head .wrap{display:flex;align-items:baseline;gap:14px;padding-top:22px;padding-bottom:22px}
.brand{font-family:Fraunces,Georgia,serif;font-weight:600;font-size:24px;letter-spacing:.01em;
  color:var(--ink);text-decoration:none}
.brand b{color:var(--amber)}
.tagline{color:var(--soft);font-size:14px}
.eyebrow{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--amber);
  font-weight:600;margin:0 0 10px}
h1{font-family:Fraunces,Georgia,serif;font-weight:600;line-height:1.12;
  font-size:clamp(30px,5.2vw,44px);letter-spacing:-.01em;margin:.1em 0 .35em}
h2{font-family:Fraunces,Georgia,serif;font-weight:600;font-size:25px;line-height:1.25;
  margin:1.9em 0 .5em;position:relative;padding-top:.5em}
h2::before{content:"";position:absolute;top:0;left:0;width:34px;height:3px;border-radius:2px;
  background:linear-gradient(90deg,var(--amber),var(--lav))}
article p,article li{color:#2c2a26}
ul,ol{padding-left:1.25em}
li{margin:.35em 0}
.meta{color:var(--soft);font-size:14px;margin-bottom:1.4em}
.cover{border-radius:14px;border:1px solid var(--line);margin:1.2em 0 1.6em;
  box-shadow:0 14px 30px -22px rgba(40,30,10,.5)}
.lead{font-size:20px;color:#3a3730}
hr.rule{border:0;height:1px;background:var(--line);margin:2.4em 0}
/* index */
.hero{padding:54px 0 34px}
.hero p{color:var(--soft);max-width:46ch;margin:.6em 0 0}
.cards{display:grid;gap:26px;padding-bottom:60px}
.card{display:grid;grid-template-columns:150px 1fr;gap:18px;align-items:start;
  text-decoration:none;color:inherit}
.card .thumb{border-radius:11px;border:1px solid var(--line);aspect-ratio:16/9;object-fit:cover;width:100%}
.card h3{font-family:Fraunces,Georgia,serif;font-weight:600;font-size:20px;line-height:1.25;margin:.15em 0 .3em}
.card .desc{color:var(--soft);font-size:15px;line-height:1.55;margin:0}
.card:hover h3{color:var(--amber)}
.back{display:inline-block;margin:30px 0 0;font-size:14px;color:var(--soft);text-decoration:none}
.back:hover{color:var(--amber)}
.foot{border-top:1px solid var(--line);color:var(--soft);font-size:13px;padding:26px 0 50px}
@media(max-width:540px){
  body{font-size:17px}
  .card{grid-template-columns:1fr;gap:10px}
  .card .thumb{aspect-ratio:16/9}
}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto}}
a:focus-visible,.card:focus-visible{outline:2px solid var(--lav);outline-offset:3px;border-radius:4px}
"""

HEAD = """<!doctype html><html lang="ru"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="alternate" type="application/rss+xml" title="{site}" href="{base}/rss.xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>{css}</style>
</head><body>
<header class="site-head"><div class="wrap">
<a class="brand" href="{base}/">Dan<b>Din</b></a><span class="tagline">{site}</span>
</div></header>
"""
FOOT = '<footer class="foot"><div class="wrap">© {year} Dandian · ароматы для дома и настроения</div></footer></body></html>'

def page_head(title, desc, site):
    return HEAD.format(title=html.escape(title), desc=html.escape(desc),
                       site=html.escape(site), base=BASE, css=CSS)

# ---------- сборка ----------
def build():
    if os.path.exists(DIST):
        shutil.rmtree(DIST)
    os.makedirs(DIST)
    shutil.copytree(ASSET_DIR, os.path.join(DIST, "assets"))
    if os.path.exists(os.path.join(ROOT, "robots.txt")):
        shutil.copy(os.path.join(ROOT, "robots.txt"), os.path.join(DIST, "robots.txt"))

    arts = [parse_article(os.path.join(ART_DIR, fn))
            for fn in os.listdir(ART_DIR) if fn.endswith(".md")]
    arts.sort(key=lambda a: a['_dt'], reverse=True)

    site = CFG["site_title"]
    year = datetime.now().year

    # страницы статей
    for a in arts:
        slug = a['slug']
        body_html = md_to_html(a['_body'])
        cover_url = f"{BASE}/assets/{a['cover']}"
        url = f"{BASE}/{slug}/"
        h = page_head(a['title'], a['description'], site)
        content = f"""<main class="wrap"><article>
<p class="eyebrow">{html.escape(a.get('category',''))}</p>
<h1>{html.escape(a['title'])}</h1>
<p class="meta">{ru_date(a['_dt'])}</p>
<img class="cover" src="{cover_url}" alt="{html.escape(a['title'])}" width="1600" height="893">
<p class="lead">{inline(a['description'])}</p>
{body_html}
<a class="back" href="{BASE}/">← Все статьи</a>
</article></main>"""
        outdir = os.path.join(DIST, slug)
        os.makedirs(outdir, exist_ok=True)
        with open(os.path.join(outdir, "index.html"), "w", encoding="utf-8") as f:
            f.write(h + content + FOOT.format(year=year))

    # главная
    cards = []
    for a in arts:
        cards.append(f"""<a class="card" href="{BASE}/{a['slug']}/">
<img class="thumb" src="{BASE}/assets/{a['cover']}" alt="" width="1600" height="893" loading="lazy">
<div><p class="eyebrow">{html.escape(a.get('category',''))}</p>
<h3>{html.escape(a['title'])}</h3>
<p class="desc">{html.escape(a['description'])}</p></div></a>""")
    idx = page_head(site, CFG["site_description"], site)
    idx += f"""<main class="wrap">
<section class="hero"><p class="eyebrow">Эфирные масла · по-человечески</p>
<h1>{html.escape(site)}</h1><p>{html.escape(CFG['site_description'])}</p></section>
<section class="cards">{''.join(cards)}</section></main>"""
    idx += FOOT.format(year=year)
    with open(os.path.join(DIST, "index.html"), "w", encoding="utf-8") as f:
        f.write(idx)

    # RSS для Дзена
    items = []
    for a in arts:
        url = f"{BASE}/{a['slug']}/"
        cover_url = f"{BASE}/assets/{a['cover']}"
        body_html = md_to_html(a['_body']).replace("]]>", "]]&gt;")
        items.append(f"""    <item>
      <title>{x(a['title'])}</title>
      <link>{x(url)}</link>
      <guid isPermaLink="true">{x(url)}</guid>
      <pubDate>{rfc822(a['_dt'])}</pubDate>
      <author>{x(CFG['author'])}</author>
      <category>{x(a.get('category',''))}</category>
      <description>{x(a['description'])}</description>
      <enclosure url="{x(cover_url)}" type="image/jpeg"/>
      <content:encoded><![CDATA[{body_html}]]></content:encoded>
      <yandex:full-text><![CDATA[{body_html}]]></yandex:full-text>
    </item>""")
    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:yandex="http://news.yandex.ru" xmlns:media="http://search.yahoo.com/mrss/" xmlns:content="http://purl.org/rss/1.0/modules/content/" version="2.0">
  <channel>
    <title>{x(site)}</title>
    <link>{x(BASE)}/</link>
    <description>{x(CFG['site_description'])}</description>
    <language>{CFG.get('language','ru')}</language>
{chr(10).join(items)}
  </channel>
</rss>
"""
    with open(os.path.join(DIST, "rss.xml"), "w", encoding="utf-8") as f:
        f.write(rss)

    print(f"Собрано статей: {len(arts)}")
    print(f"dist/: index.html, rss.xml, {len(arts)} страниц статей, assets/")
    if "ЗАМЕНИ" in BASE:
        print("\n⚠️  В config.json base_url ещё не заменён на реальный адрес сайта!")

if __name__ == "__main__":
    build()
