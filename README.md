# Band Static Site Generator

A minimal Python static site generator for band websites. Generates a fully static site from Jinja2 templates, Markdown pages, and YAML data.

## Requirements

- Python 3.11+
- See `requirements.txt` for dependencies (Jinja2, Markdown, PyYAML, Pillow)

## Setup

```bash
pip install -r requirements.txt
```

## Build

```bash
python build.py
```

This recreates `dist/` and outputs a ready-to-deploy static site. Progress messages are printed to the console.

## Input structure

| Path | Purpose |
|------|---------|
| `templates/` | Jinja2 HTML templates (base, index, page, concerts, albums) |
| `content/pages/*.md` | Markdown pages with `title` (and optional) YAML frontmatter |
| `content/concerts.yaml` | Concert list (sorted by date) |
| `content/albums.yaml` | Album list |
| `static/` | CSS and assets copied as-is |
| `photos/raw/` | Source images; generator copies originals and creates 1600px + 400px versions |

## Output (`dist/`)

- `index.html` — homepage
- `{slug}/index.html` — one per Markdown page (e.g. `about/`, `contact/`)
- `concerts/index.html` — concerts page
- `albums/index.html` — albums page
- `static/` — copied from source
- `photos/original/`, `photos/1600/`, `photos/thumb/` — processed images

## Extending

- Add new pages by creating `content/pages/yourpage.md` with `title` in frontmatter.
- Add templates in `templates/` and render them from `build.py` with the same pattern as concerts/albums.
- Edit `templates/base.html` to change global layout and nav.
