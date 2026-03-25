# Insinistra site — roadmap

Prioritized follow-ups for the official band static site, aligned with [TECH_REQUIREMENTS.md](TECH_REQUIREMENTS.md) (generator constraints) and [requirements.txt](requirements.txt) (Python dependencies). **TECH_REQUIREMENTS.md** is the original build spec; parts of its folder layout are outdated versus the current repo (see “Baseline” below).

---

## Key points (executive summary)

- **Strengths today**: Solid information architecture (Home, About, Shows, Discography, Photos, Contact, EPK); broad DSP and social coverage; manual tour data plus Bandsintown follow snippet; EPK for press; image pipeline and gallery; GoatCounter analytics; fully static output suitable for CDN hosting.
- **Biggest discovery gap**: Almost no **SEO or link-preview metadata** (descriptions, Open Graph, canonical URLs) and no **JSON-LD** (`MusicGroup`, events, releases) — this is where many label campaigns invest for search and sharing.
- **Crawl hygiene**: No generated **sitemap.xml** or **robots.txt** yet; worth adding given `/slug/index.html` URL patterns.
- **Fan and campaign tooling**: No mailing list CTA, merch link, smart links / pre-saves, or embedded players — add as campaigns need them.

---

## Baseline (constraints)

- **Stack**: Python 3.11+, Jinja2, Markdown, PyYAML, Pillow — see [requirements.txt](requirements.txt).
- **Build**: `python build.py` → static site in `dist/`. No backend, no database — see [TECH_REQUIREMENTS.md](TECH_REQUIREMENTS.md).
- **Current tree (high level)**: `templates/`, `content/` (pages, `concerts.yaml`, `albums.yaml`, `epk.yaml`, `videos.yaml`, `band-members.yaml`, `reviews.yaml`, `gallery.yaml`, etc.), `static/`, `photos/`, `images/` — generator logic in `build.py`.

---

## P1 — Discoverability

- [ ] **Per-page `<title>` and meta description** (extend `base.html` / blocks; source text from frontmatter or a small `site.yaml`).
- [ ] **Open Graph and Twitter Card tags** (at minimum `og:title`, `og:description`, `og:image`, `og:url`; plus Twitter equivalents or `twitter:card`).
- [ ] **Canonical URL** per page using the live site base URL (configurable at build time).
- [ ] **JSON-LD (JSON-LD in `<script type="application/ld+json">`)**:
  - [ ] `MusicGroup` on the home (or global) template with `sameAs` pointing to official social and DSP URLs.
  - [ ] `MusicEvent` for upcoming shows (venue, date, ticket URL when present).
  - [ ] Optional `MusicAlbum` / `MusicRecording` for releases on the discography or album detail flows, if you add stable URLs per release.
- [ ] **Generated `sitemap.xml` and `robots.txt`** in `dist/` listing HTML entry points.

---

## P2 — Campaigns and fan experience

- [ ] **Smart links** (Linkfire, Feature.fm, etc.) for singles/albums and pre-save campaigns; surface on home and discography.
- [ ] **Optional embeds**: Spotify (or Apple Music) player on featured release or album pages.
- [ ] **Newsletter signup** (Mailchimp, Brevo, etc.) in footer or home — coordinate with privacy copy if emails are collected.
- [ ] **Merch store** link in nav or footer when a store exists.
- [ ] **Tour UX**: optional Bandsintown events widget or Songkick embed to complement YAML; optional `.ics` download for upcoming dates.

---

## P3 — Polish and maintenance

- [ ] **Branded `404.html`** if the host supports custom error pages.
- [ ] **Privacy policy** (short page) if newsletter or non-essential cookies are added; GoatCounter is relatively privacy-friendly but document what you use.
- [ ] **Accessibility**: meaningful `title` on the Bandsintown iframe (replace generic “newsletter-widget” in pasted embed code); keyboard/focus checks on nav and modals.
- [ ] **Refresh [TECH_REQUIREMENTS.md](TECH_REQUIREMENTS.md)** to match the real input paths (`photos/`, `images/`, extra templates and content files) so new contributors are not misled.

---

## Out of scope here

Implementation of the checklist items above is tracked in this file only unless separately requested. Hosting, DNS, and GitHub Pages `CNAME` are deployment concerns outside this roadmap.
