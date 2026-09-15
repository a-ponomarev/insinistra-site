# Insinistra site — notes for Claude

Static site generator for the band Insinistra (symphonic metal, Prague). Custom Python
build script, no backend/database. See `README.md` for the general overview; this file
covers implementation details worth knowing before editing.

## Build

```bash
pip install -r requirements.txt
python build.py
```

Recreates `dist/` (gitignored) from `templates/` + `content/` + `static/` + `photos/raw/`.
`package.json` also defines a `build:js` step (esbuild bundling
`scripts/gallery-justified-entry.js` → `static/gallery-justified.js`), which `build.py`
invokes as part of the build.

**Always run `python build.py` after any edit, change, or undo** to templates, content,
static files, or the build script — don't skip this unless the user explicitly says to.

## Commit messages

Keep commit messages minimal: one sentence, at most two. State what changed; avoid long
paragraphs or exhaustive bullet lists unless the user asks for more detail.

## Stack

- **Templating**: Jinja2 (`templates/*.html`, `{% extends %}` / `{% block %}` inheritance
  from `templates/base.html`).
- **Content**: YAML files in `content/*.yaml` (`site.yaml`, `concerts.yaml`, `albums.yaml`,
  `videos.yaml`, `reviews.yaml`, `band-members.yaml`, `epk.yaml`, `gallery.yaml`) plus
  Markdown pages with YAML frontmatter in `content/pages/*.md`.
- **Images**: Pillow, resizing originals from `photos/raw/` into multiple sizes under
  `dist/photos/`.

## Page titles and meta descriptions

This is easy to get wrong because the pieces are split across three files.

**`<title>`** — `templates/base.html`:
```jinja
<title>{% block title %}Band{% endblock %}{% if not is_index %} | Insinistra{% endif %}</title>
```
Every child template overrides the `title` block with its own text. `base.html` appends
`" | Insinistra"` automatically — **except on the homepage**, which sets `is_index=True`
when rendered (in `build.py`) and supplies a full self-contained title
(`templates/index.html`: `{% block title %}Insinistra - Official Website{% endblock %}`)
that already starts with the band name.

**`<meta name="description">`** — driven by `resolve_meta_description(slug, page, site)` in
`build.py`, priority order:
1. Markdown frontmatter `description:` field (per-page, only applies to `content/pages/*.md`)
2. `content/site.yaml` → `meta_descriptions.<slug>` (e.g. `home`, `about`, `shows`, `albums`,
   `photos`, `epk`, `contact`)
3. `content/site.yaml` → `default_meta_description` (fallback)

The homepage has no Markdown/frontmatter file, so its description can only be changed via
`content/site.yaml`'s `meta_descriptions.home`.

**Open Graph / Twitter** — `social_meta_context()` in `build.py` builds `og:title`,
`og:description`, `twitter:title`, `twitter:description`, and the canonical URL, gated on
`site_url` being set in `site.yaml` (if empty, all of this is omitted). By default
`og_title`/`twitter_title` are built as `f"{title_part} | Insinistra"`; pass
`full_title=...` instead to override that composition (used for the homepage, which already
has the band name at the front of its title — see the `full_title` param added for that).
`og_description`/`twitter_description` always reuse the resolved `meta_description`.

**`og:image`/`twitter:image`** — `social_meta_context()` accepts an `og_image_rel` param to
override the image per page, but as of now no call site in `build.py` passes it, so every
page (home, about, shows, albums, photos, contact, epk) falls back to the single sitewide
`content/site.yaml` → `default_og_image` (currently `static/og-hero.jpg`, a 1200x630
screenshot of the homepage hero section). Changing `default_og_image` changes the social
share preview for the *entire site*, not just one page.

**Per-page `title_part` / template mapping** (kept in sync manually — no single source of
truth links a template's `{% block title %}` to its `build.py` render call):

| Page | Template title block | `build.py` `title_part` |
|---|---|---|
| Home | `Insinistra - Official Website` (full title, no suffix) | n/a (`full_title=`) |
| About | `{{ page.title }}` (frontmatter) | `page.get("title") or slug` |
| Shows | `Shows` | `"Shows"` |
| Discography | `Discography` | `"Discography"` |
| Photos | `Photos` | `"Photos"` |
| Contact | `Contact` | `"Contact"` |
| EPK | `Electronic Press Kit` | `"Electronic Press Kit"` |
| 404 | `Page not found` | n/a |

If you add a new page or change a title, update both the template's `{% block title %}`
and the matching `title_part=` (or `full_title=`) in its `social_meta_context()` call in
`build.py` — they don't derive from each other.
