# willcastner.com

A static personal site. One Python file, no dependencies, no build tooling.

## Writing a post

```sh
python3 build.py --new "Post title"   # creates posts/YYYY-MM-DD-slug.md
```

Edit the file it prints. Delete the `draft: true` line when it's ready to publish.
Then:

```sh
python3 build.py
git add -A && git commit -m "new post" && git push
```

GitHub Pages redeploys within a minute or so.

## Preview locally

```sh
python3 build.py --serve   # http://localhost:8000
```

## Layout

| Path              | What it is                                            |
| ----------------- | ----------------------------------------------------- |
| `posts/`          | Blog posts, `YYYY-MM-DD-slug.md`                       |
| `pages/index.md`  | The blurb on the homepage                              |
| `pages/*.md`      | Standalone pages — `about.md` becomes `/about/`        |
| `templates/base.html` | The single layout wrapping every page              |
| `static/`         | Copied verbatim to the site root (`style.css`, images) |
| `docs/`           | **Generated.** Served by Pages. Never edit by hand.    |

## Front matter

Optional `key: value` lines between `---` fences at the top of a file:

```
---
title: How this site is built
summary: Shown in the page description and RSS.
date: 2026-08-10      # overrides the date in the filename
draft: true           # excluded from the build
---
```

## Markdown support

A deliberate subset: headings, paragraphs, `**bold**`, `*italic*`, `` `code` ``,
links, images, ordered and unordered lists, blockquotes, fenced code blocks, and
horizontal rules. A block starting with an HTML tag passes through verbatim, so
anything else can be written as raw HTML.

## Deployment

Pushing to `main` publishes. Pages is configured to serve the `docs/` folder,
and `docs/CNAME` binds the custom domain. Site config (name, URL, domain) lives
at the top of `build.py`.
