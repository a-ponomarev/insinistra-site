# Tech Requirements: Python Static Site Generator for Band Website

**Task:** Build a simple static site generator in Python that creates a fully static band website from templates and content files.

The generator must run with:

```
python build.py
```

and produce a ready-to-deploy site in the `dist/` directory.

---

## Requirements

- Use:
  - Python 3.11+
  - Jinja2 templates
  - Markdown pages
  - YAML data files
  - Pillow for image resizing
- Keep dependencies minimal.

---

## Input Structure

```
templates/
content/
static/
photos/raw/
```

- **templates/**  
  - `base.html`  
  - `index.html`  
  - `page.html`  
  - `concerts.html`  
  - `albums.html`

- **content/**  
  - `pages/*.md` — Markdown pages with title frontmatter  
  - `concerts.yaml`  
  - `albums.yaml`

- **static/**  
  - CSS and images copied as-is

- **photos/raw/**  
  - Source photos

---

## Output Structure

Generated into: **dist/**

Must include:

- `index.html`
- generated pages (e.g. `/about/index.html`)
- concerts page
- albums page
- copied static files
- processed photos

The site must work as pure static HTML.

---

## Features

The generator must:

1. Generate pages from Markdown files using templates
2. Generate concerts page from `concerts.yaml` (sorted by date)
3. Generate albums page from `albums.yaml`
4. Generate homepage using template data
5. Copy `static/` into `dist/`
6. Process images from `photos/raw/`:
   - original copy
   - resized version (~1600px width)
   - thumbnail (~400px width)
   - Preserve aspect ratio.

---

## Build Command

Running:

```
python build.py
```

must:

- recreate `dist/`
- generate the site
- print basic progress messages

---

## Constraints

- Clean and readable code
- Simple structure
- Easy to extend
- Fully static output
- No backend
- No database
