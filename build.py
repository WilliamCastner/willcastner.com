#!/usr/bin/env python3
"""Build the static site. Stdlib only.

    python3 build.py           build into docs/
    python3 build.py --serve   build, then serve docs/ at localhost:8000
    python3 build.py --new "Post title"   scaffold a new post in posts/

Sources:
    posts/YYYY-MM-DD-slug.md   blog posts
    pages/name.md              standalone pages (about, etc.)
    templates/base.html        the one layout
    static/*                   copied verbatim
"""

import html
import re
import shutil
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "docs"

SITE_NAME = "Will Castner"
SITE_URL = "https://willcastner.com"
SITE_DESC = "Personal site of Will Castner."
DOMAIN = "willcastner.com"

# Shown as a row of links under the bio on the homepage.
LINKS = [
    ("Email", "mailto:william@mechanize.work"),
    ("GitHub", "https://github.com/WilliamCastner"),
]

WORDS_PER_MINUTE = 200


# --------------------------------------------------------------------------
# markdown subset
# --------------------------------------------------------------------------

def inline(text):
    """Inline markdown -> HTML. Code spans are protected from other rules."""
    spans = []

    def stash(m):
        spans.append(html.escape(m.group(1)))
        return f"\x00{len(spans) - 1}\x00"

    text = re.sub(r"`([^`]+)`", stash, text)
    text = html.escape(text)
    text = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", r'<img src="\2" alt="\1">', text)
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"(?<!\w)_([^_]+)_(?!\w)", r"<em>\1</em>", text)
    text = re.sub(r"\x00(\d+)\x00", lambda m: f"<code>{spans[int(m.group(1))]}</code>", text)
    return text


def markdown(src):
    """Block-level markdown subset -> HTML."""
    out = []
    lines = src.replace("\r\n", "\n").split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]

        if not line.strip():
            i += 1
            continue

        # fenced code block
        if line.startswith("```"):
            i += 1
            block = []
            while i < len(lines) and not lines[i].startswith("```"):
                block.append(lines[i])
                i += 1
            i += 1
            out.append("<pre><code>" + html.escape("\n".join(block)) + "</code></pre>")
            continue

        # raw HTML block: passes through verbatim until a blank line
        if re.match(r"<(/?)([a-zA-Z][\w-]*)", line):
            block = []
            while i < len(lines) and lines[i].strip():
                block.append(lines[i])
                i += 1
            out.append("\n".join(block))
            continue

        # heading
        m = re.match(r"(#{1,6})\s+(.*)", line)
        if m:
            level = len(m.group(1))
            out.append(f"<h{level}>{inline(m.group(2).strip())}</h{level}>")
            i += 1
            continue

        # horizontal rule
        if re.fullmatch(r"(-{3,}|\*{3,})", line.strip()):
            out.append("<hr>")
            i += 1
            continue

        # blockquote
        if line.startswith(">"):
            block = []
            while i < len(lines) and lines[i].startswith(">"):
                block.append(lines[i].lstrip(">").strip())
                i += 1
            out.append("<blockquote>" + markdown("\n".join(block)) + "</blockquote>")
            continue

        # list (unordered or ordered)
        m = re.match(r"\s*([-*]|\d+\.)\s+", line)
        if m:
            ordered = m.group(1).endswith(".")
            items = []
            while i < len(lines) and re.match(r"\s*([-*]|\d+\.)\s+", lines[i]):
                items.append(re.sub(r"^\s*([-*]|\d+\.)\s+", "", lines[i]))
                i += 1
            tag = "ol" if ordered else "ul"
            body = "".join(f"<li>{inline(it)}</li>" for it in items)
            out.append(f"<{tag}>{body}</{tag}>")
            continue

        # paragraph
        block = []
        while i < len(lines) and lines[i].strip() and not re.match(
            r"(#{1,6}\s|```|>|<[a-zA-Z/]|\s*([-*]|\d+\.)\s)", lines[i]
        ):
            block.append(lines[i].strip())
            i += 1
        out.append("<p>" + inline(" ".join(block)) + "</p>")

    return "\n".join(out)


# --------------------------------------------------------------------------
# content loading
# --------------------------------------------------------------------------

def parse_front_matter(raw):
    """Leading `key: value` lines, terminated by a blank line."""
    meta, body = {}, raw
    if raw.startswith("---\n"):
        end = raw.find("\n---\n", 3)
        if end != -1:
            head, body = raw[4:end], raw[end + 5:]
            for line in head.split("\n"):
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip().lower()] = v.strip()
    return meta, body.lstrip("\n")


def load_posts():
    posts = []
    for path in sorted((ROOT / "posts").glob("*.md")):
        meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
        if meta.get("draft", "").lower() in ("true", "yes", "1"):
            continue
        stem = path.stem
        m = re.match(r"(\d{4}-\d{2}-\d{2})-(.+)", stem)
        if m:
            day, slug = date.fromisoformat(m.group(1)), m.group(2)
        else:
            day, slug = date.today(), stem
        if meta.get("date"):
            day = date.fromisoformat(meta["date"])
        words = len(re.findall(r"\w+", body))
        posts.append({
            "title": meta.get("title", slug.replace("-", " ").title()),
            "date": day,
            "slug": slug,
            "summary": meta.get("summary", ""),
            "minutes": max(1, round(words / WORDS_PER_MINUTE)),
            "html": markdown(body),
        })
    posts.sort(key=lambda p: (p["date"], p["slug"]), reverse=True)
    return posts


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------

TEMPLATE = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")


def render(path_parts, title, content, description=SITE_DESC):
    """Write an index.html at docs/<path_parts>/ with `content` inside the layout."""
    depth = len(path_parts)
    page = TEMPLATE.format(
        title=html.escape(title),
        description=html.escape(description),
        sitename=html.escape(SITE_NAME),
        root="../" * depth if depth else "",
        content=content,
        year=date.today().year,
    )
    target = OUT.joinpath(*path_parts)
    target.mkdir(parents=True, exist_ok=True)
    (target / "index.html").write_text(page, encoding="utf-8")


def feed_list(posts):
    """The month/year + title + read-time list used on the homepage."""
    if not posts:
        return '<p class="post-meta">Nothing here yet.</p>'
    items = []
    for p in posts:
        items.append(
            f'<a class="feed-item" href="/writing/{p["slug"]}/">'
            f'<span class="feed-calendar">'
            f'<span class="feed-month">{p["date"].strftime("%b")}</span>{p["date"].year}</span>'
            f'<span class="feed-title">{html.escape(p["title"])}</span>'
            f'<span class="feed-length">{p["minutes"]} min read</span>'
            f"</a>"
        )
    return '<div class="feed">' + "".join(items) + "</div>"


def links_row():
    if not LINKS:
        return ""
    anchors = "".join(f'<a href="{url}">{html.escape(label)}</a>' for label, url in LINKS)
    return f'<nav class="links">{anchors}</nav>'


def rfc3339(d):
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc).isoformat()


def build_feed(posts):
    entries = []
    for p in posts[:20]:
        url = f"{SITE_URL}/writing/{p['slug']}/"
        entries.append(f"""  <entry>
    <title>{html.escape(p['title'])}</title>
    <link href="{url}"/>
    <id>{url}</id>
    <updated>{rfc3339(p['date'])}</updated>
    <content type="html">{html.escape(p['html'])}</content>
  </entry>""")
    updated = rfc3339(posts[0]["date"]) if posts else rfc3339(date.today())
    feed = f"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>{html.escape(SITE_NAME)}</title>
  <link href="{SITE_URL}/"/>
  <link rel="self" href="{SITE_URL}/feed.xml"/>
  <id>{SITE_URL}/</id>
  <updated>{updated}</updated>
{chr(10).join(entries)}
</feed>
"""
    (OUT / "feed.xml").write_text(feed, encoding="utf-8")


def build():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    posts = load_posts()

    # home: name, bio, links, then the full post list
    home_md = ROOT / "pages" / "index.md"
    bio = markdown(parse_front_matter(home_md.read_text(encoding="utf-8"))[1]) if home_md.exists() else ""
    home = (
        f'<h1 class="name">{html.escape(SITE_NAME)}</h1>'
        f'<div class="bio">{bio}</div>'
        f"{links_row()}"
        f'<span class="section-label">Writing</span>'
        f"{feed_list(posts)}"
    )
    render([], SITE_NAME, home)

    # posts
    for p in posts:
        body = (
            f'<a class="backlink" href="/">&larr; {html.escape(SITE_NAME)}</a>'
            f'<article><h1 class="post-title">{html.escape(p["title"])}</h1>'
            f'<p class="post-meta">{p["date"].strftime("%B %-d, %Y")} '
            f'&middot; {p["minutes"]} min read</p>'
            f'{p["html"]}</article>'
        )
        render(["writing", p["slug"]], f'{p["title"]} — {SITE_NAME}', body,
               p["summary"] or SITE_DESC)

    # standalone pages
    for path in sorted((ROOT / "pages").glob("*.md")):
        if path.stem == "index":
            continue
        meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
        title = meta.get("title", path.stem.title())
        page = (
            f'<a class="backlink" href="/">&larr; {html.escape(SITE_NAME)}</a>'
            f'<article><h1 class="post-title">{html.escape(title)}</h1>'
            f"{markdown(body)}</article>"
        )
        render([path.stem], f"{title} — {SITE_NAME}", page)

    build_feed(posts)

    for item in (ROOT / "static").iterdir():
        if item.is_file():
            shutil.copy2(item, OUT / item.name)

    (OUT / "CNAME").write_text(DOMAIN + "\n", encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")

    print(f"built {len(posts)} post(s) -> {OUT}")


def new_post(title):
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    path = ROOT / "posts" / f"{date.today().isoformat()}-{slug}.md"
    if path.exists():
        sys.exit(f"{path} already exists")
    path.write_text(
        f"---\ntitle: {title}\nsummary: \ndraft: true\n---\n\nWrite here.\n",
        encoding="utf-8",
    )
    print(path)


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--new":
        new_post(" ".join(args[1:]) or "Untitled")
    else:
        build()
        if args and args[0] == "--serve":
            import functools
            from http.server import HTTPServer, SimpleHTTPRequestHandler
            handler = functools.partial(SimpleHTTPRequestHandler, directory=str(OUT))
            print("serving http://localhost:8000 (ctrl-c to stop)")
            HTTPServer(("localhost", 8000), handler).serve_forever()
