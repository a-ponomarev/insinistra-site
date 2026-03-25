# Insinistra site — roadmap

Prioritized follow-ups for the official band static site, aligned with [TECH_REQUIREMENTS.md](TECH_REQUIREMENTS.md) (generator constraints) and [requirements.txt](requirements.txt) (Python dependencies). **TECH_REQUIREMENTS.md** is the original build spec; parts of its folder layout are outdated versus the current repo (see “Baseline” below).

---

## Key points (executive summary)

- **Strengths today**: Solid information architecture (Home, About, Shows, Discography, Photos, Contact, EPK); broad DSP and social coverage; manual tour listings in YAML; EPK for press; image pipeline and gallery; GoatCounter analytics; fully static output suitable for CDN hosting.
- **Discovery / SEO**: Per-page meta descriptions plus **Open Graph and Twitter Card**, **canonical URLs**, and **JSON-LD** (`MusicGroup` on all pages when `site_url` is set; `MusicEvent` on shows; `MusicAlbum` on discography). **`sitemap.xml`** and **`robots.txt`** are generated in `dist/` when `site_url` is set.
- **Crawl hygiene**: Sitemap lists HTML entry points; `robots.txt` references the sitemap. Omitted when `site_url` is empty (local builds without a public origin).
- **Fan and campaign tooling**: No mailing list CTA, merch link, smart links / pre-saves, or embedded players — add as campaigns need them.

---

## Baseline (constraints)

- **Stack**: Python 3.11+, Jinja2, Markdown, PyYAML, Pillow — see [requirements.txt](requirements.txt).
- **Build**: `python build.py` → static site in `dist/`. No backend, no database — see [TECH_REQUIREMENTS.md](TECH_REQUIREMENTS.md).
- **Current tree (high level)**: `templates/`, `content/` (pages, `concerts.yaml`, `albums.yaml`, `epk.yaml`, `videos.yaml`, `band-members.yaml`, `reviews.yaml`, `gallery.yaml`, etc.), `static/`, `photos/`, `images/` — generator logic in `build.py`.

---

## P1 — Discoverability

- [x] **Per-page `<title>` and meta description** — `content/site.yaml` (`default_meta_description`, `meta_descriptions` per route); Markdown `description` in frontmatter overrides. Rendered in [`templates/base.html`](templates/base.html); [`build.py`](build.py) passes `meta_description` per page.
- [x] **Open Graph and Twitter Card tags** — `site_url` and `default_og_image` in [`content/site.yaml`](content/site.yaml); [`build.py`](build.py) `social_meta_context()`; tags in [`templates/base.html`](templates/base.html) (`og:*`, `twitter:card` / title / description / image). Tags omitted when `site_url` is empty.
- [x] **Canonical URL** per page using the live site base URL (`site_url` in `site.yaml`, optional `SITE_URL` env override at build time); `<link rel="canonical">` in [`templates/base.html`](templates/base.html); same path logic as `og:url` in [`build.py`](build.py) `social_meta_context()`.
- [x] **JSON-LD** (`<script type="application/ld+json">` in [`templates/base.html`](templates/base.html)):
  - [x] `MusicGroup` on every page when `site_url` is set; `sameAs` from [`content/site.yaml`](content/site.yaml) (`same_as` list — keep aligned with [`templates/partials/social_links.html`](templates/partials/social_links.html)).
  - [x] `MusicEvent` for each **upcoming** show on [`templates/concerts.html`](templates/concerts.html) (`startDate`, venue / locality, ticket `Offer` when `tickets` URL exists, event `url` from tickets or Facebook).
  - [x] `MusicAlbum` for each release on the discography page ([`templates/albums.html`](templates/albums.html)) with Bandcamp `url`, `datePublished`, `image` when artwork path is set; stable fragment `@id` under `/albums/#…` (per-release site URLs can be added later).
- [x] **Generated `sitemap.xml` and `robots.txt`** in `dist/` when `site_url` is set — see [`build.py`](build.py) `write_sitemap_xml` / `write_robots_txt`.

---

## P2 — Campaigns and fan experience

- [ ] **Smart links** (Linkfire, Feature.fm, etc.) for singles/albums and pre-save campaigns; surface on home and discography.
- [ ] **Optional embeds**: Spotify (or Apple Music) player on featured release or album pages.
- [ ] **Newsletter signup** (Mailchimp, Brevo, etc.) in footer or home — coordinate with privacy copy if emails are collected.
- [ ] **Merch store** link in nav or footer when a store exists.
- [ ] **Tour UX**: optional third-party tour widget (e.g. Songkick embed) to complement YAML; optional `.ics` download for upcoming dates.

---

## P3 — Polish and maintenance

- [ ] **Branded `404.html`** if the host supports custom error pages.
- [ ] **Privacy policy** (short page) if newsletter or non-essential cookies are added; GoatCounter is relatively privacy-friendly but document what you use.
- [ ] **Accessibility**: meaningful `title` attributes on any embedded widgets; keyboard/focus checks on nav and modals.
- [ ] **Refresh [TECH_REQUIREMENTS.md](TECH_REQUIREMENTS.md)** to match the real input paths (`photos/`, `images/`, extra templates and content files) so new contributors are not misled.

---

## Out of scope here

Implementation of the checklist items above is tracked in this file only unless separately requested. Hosting, DNS, and GitHub Pages `CNAME` are deployment concerns outside this roadmap.
