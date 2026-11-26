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

## Buttons

`.btn` (`static/style.css`) is the base button style (accent-colored outline, fills with
accent color on hover) and is the default used across the site (CTAs in Featured Release,
section "All/Full ..." links, 404 back-link, etc.). `.btn-ghost` is a muted variant (dimmer
border/text, dimmer hover fill) — apply it *together with* `.btn` (`class="btn btn-ghost"`),
never alone, since it only overrides colors and relies on `.btn` for layout/sizing. Currently
used for all hero CTAs (`templates/index.html`) so they read as equal-weight actions.

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

**Per-page titles** now come from `content/i18n.yaml`: each template's `{% block title %}`
and the matching `title_part=` in `build.py` read the same key, so they stay in sync per
language.

| Page | i18n key (template block and `title_part`) |
|---|---|
| Home | `t.home_title` (full title, no suffix, `full_title=`) |
| About | `page.title` (frontmatter of `content/pages/[cs/]about.md`) |
| Shows | `t.nav_shows` |
| Discography | `t.nav_albums` |
| Photos | `t.nav_photos` |
| Contact | `t.nav_contact` |
| EPK | `t.epk_title` |
| 404 | `t.not_found_title` (English only) |

If you add a new page, add its key to every language in `i18n.yaml` and use it in both
places.

## Languages (English + Czech)

English is built at the site root, Czech under `/cs/` (`LANGUAGES` in `build.py`; the render
section loops over them). The 404 page and the `bio/` redirect are English only.

- **Interface strings**: `content/i18n.yaml`, one dict per language; templates use
  `{{ t.<key> }}`. A key missing from `cs` falls back to `en`. Never hardcode visible text
  in templates. When adding a string, add it to both languages.
- **Data overrides**: any YAML item field `<field>_cs` replaces `<field>` on Czech pages
  (`localize_items()`): `role_cs` in `band-members.yaml`, `one_liner_cs` in `epk.yaml`.
  Album types are mapped through `release_types`. Concert dates use `months`. A concert
  `comment` starting with `with ` gets `comment_with` instead (`Hrají také: ` in Czech).
  Reviews and concert/venue names are not translated.
- **Markdown pages**: `content/pages/cs/<slug>.md`. A missing one falls back to the English
  page.
- **Meta descriptions**: Czech ones live in `i18n.yaml` (`default_meta_description`,
  `meta_descriptions`) and override `site.yaml` on Czech pages.
- **Links**: `base` is the relative path to the site root (assets: `{{ base }}/static/...`),
  `home` is the relative path to the current language's root (pages:
  `{{ home }}shows/`). Keep both relative because the dev build is served from `/dev/`.
- **SEO**: every page gets `hreflang` alternates (en, cs, x-default→en) and a nav link to the
  other language (`.nav-lang`). The sitemap lists both languages. JSON-LD is the same on
  both.
- **Cookie banner**: `static/consent.js` takes its text from the `data-i18n` attribute on its
  script tag (filled from `consent_*` keys).
