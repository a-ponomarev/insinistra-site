#!/usr/bin/env python3
"""
Static site generator for band website.
Run: python build.py
Output: dist/ (ready to deploy)
"""

import re
import shutil
from datetime import datetime
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader
from markdown import markdown
from PIL import Image

# Paths
ROOT = Path(__file__).resolve().parent
TEMPLATES_DIR = ROOT / "templates"
CONTENT_DIR = ROOT / "content"
STATIC_DIR = ROOT / "static"
PHOTOS_RAW_DIR = ROOT / "photos" / "raw"
DIST_DIR = ROOT / "dist"

# Image sizes
RESIZED_WIDTH = 1600
THUMB_WIDTH = 400


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Extract YAML frontmatter from Markdown. Returns (data, body)."""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.DOTALL)
    if not match:
        return {}, text
    try:
        data = yaml.safe_load(match.group(1)) or {}
        return data, match.group(2)
    except yaml.YAMLError:
        return {}, text


def load_markdown_page(path: Path) -> tuple[dict, str]:
    """Load a .md file; return (frontmatter dict, html body)."""
    raw = path.read_text(encoding="utf-8")
    data, body = parse_frontmatter(raw)
    data["content_html"] = markdown(body)
    return data, data.get("title", path.stem)


def load_pages() -> list[dict]:
    """Load all Markdown pages from content/pages/."""
    pages_dir = CONTENT_DIR / "pages"
    if not pages_dir.exists():
        return []
    pages = []
    for path in sorted(pages_dir.glob("*.md")):
        data, title = load_markdown_page(path)
        data["slug"] = path.stem
        data["title"] = title
        pages.append(data)
    return pages


def load_concerts() -> list[dict]:
    """Load concerts from YAML, sorted by date (newest first)."""
    path = CONTENT_DIR / "concerts.yaml"
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    items = data.get("concerts", data) if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []
    # Sort by date descending
    def date_key(c):
        d = c.get("date", "")
        return (d, c.get("venue", ""))
    return sorted(items, key=date_key, reverse=True)


def load_albums() -> list[dict]:
    """Load albums from YAML, sorted by date newest first. Derives year for display."""
    path = CONTENT_DIR / "albums.yaml"
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    items = data.get("albums", data) if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []
    for a in items:
        d = a.get("date") or ""
        if isinstance(d, str) and len(d) >= 4:
            a["year"] = int(d[:4])
        else:
            a["year"] = None
    return sorted(items, key=lambda a: a.get("date") or "", reverse=True)


def process_photos(dist_photos: Path) -> list[dict]:
    """
    Copy originals and create resized + thumbnail from photos/raw/.
    Returns list of photo info dicts for templates.
    """
    if not PHOTOS_RAW_DIR.exists():
        return []
    dist_photos.mkdir(parents=True, exist_ok=True)
    (dist_photos / "original").mkdir(exist_ok=True)
    (dist_photos / "1600").mkdir(exist_ok=True)
    (dist_photos / "thumb").mkdir(exist_ok=True)

    photos = []
    extensions = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

    for path in sorted(PHOTOS_RAW_DIR.iterdir()):
        if path.suffix.lower() not in extensions or not path.is_file():
            continue
        name = path.name
        base = path.stem
        ext = path.suffix.lower()
        if ext == ".jpeg":
            ext = ".jpg"

        # Copy original
        dest_orig = dist_photos / "original" / name
        shutil.copy2(path, dest_orig)
        orig_url = f"photos/original/{name}"

        # Resized (~1600px) and thumbnail (~400px)
        try:
            with Image.open(path) as img:
                img = img.convert("RGB") if img.mode in ("RGBA", "P") else img
                w, h = img.size
                if w == 0:
                    continue

                # 1600px width
                if w > RESIZED_WIDTH:
                    ratio = RESIZED_WIDTH / w
                    new_size = (RESIZED_WIDTH, int(h * ratio))
                    resized = img.resize(new_size, Image.Resampling.LANCZOS)
                else:
                    resized = img
                resized_name = f"{base}-1600.jpg"
                resized_path = dist_photos / "1600" / resized_name
                resized.save(resized_path, "JPEG", quality=88)
                resized_url = f"photos/1600/{resized_name}"

                # Thumbnail
                if w > THUMB_WIDTH:
                    ratio = THUMB_WIDTH / w
                    thumb_size = (THUMB_WIDTH, int(h * ratio))
                    thumb = img.resize(thumb_size, Image.Resampling.LANCZOS)
                else:
                    thumb = img
                thumb_name = f"{base}-thumb.jpg"
                thumb_path = dist_photos / "thumb" / thumb_name
                thumb.save(thumb_path, "JPEG", quality=85)
                thumb_url = f"photos/thumb/{thumb_name}"
        except Exception as e:
            print(f"  Warning: could not process {name}: {e}")
            resized_url = orig_url
            thumb_url = orig_url

        photos.append({
            "original": orig_url,
            "resized": resized_url,
            "thumb": thumb_url,
            "name": name,
        })

    return photos


def main() -> None:
    print("Building band site...")
    # Recreate dist
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True)

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))

    # Load data
    print("  Loading content...")
    pages = load_pages()
    concerts = load_concerts()
    albums = load_albums()

    # Copy static
    if STATIC_DIR.exists():
        print("  Copying static/...")
        shutil.copytree(STATIC_DIR, DIST_DIR / "static")

    # Process photos
    print("  Processing photos...")
    dist_photos = DIST_DIR / "photos"
    photos = process_photos(dist_photos)

    common = {"nav_pages": pages, "current_year": datetime.now().year}
    subdir_common = {**common, "base": ".."}

    # Render homepage
    print("  Writing index.html...")
    template_index = env.get_template("index.html")
    (DIST_DIR / "index.html").write_text(
        template_index.render(
            base="",
            **common,
            pages=pages,
            concerts=concerts[:5],
            albums=albums,
            photos=photos[:6],
        ),
        encoding="utf-8",
    )

    # Render each Markdown page (e.g. about -> about/index.html)
    for page in pages:
        slug = page["slug"]
        print(f"  Writing {slug}/index.html...")
        out_dir = DIST_DIR / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        template_page = env.get_template("page.html")
        (out_dir / "index.html").write_text(
            template_page.render(page=page, **subdir_common),
            encoding="utf-8",
        )

    # Concerts page
    print("  Writing concerts/index.html...")
    (DIST_DIR / "concerts").mkdir(exist_ok=True)
    template_concerts = env.get_template("concerts.html")
    (DIST_DIR / "concerts" / "index.html").write_text(
        template_concerts.render(concerts=concerts, **subdir_common),
        encoding="utf-8",
    )

    # Albums page
    print("  Writing albums/index.html...")
    (DIST_DIR / "albums").mkdir(exist_ok=True)
    template_albums = env.get_template("albums.html")
    (DIST_DIR / "albums" / "index.html").write_text(
        template_albums.render(albums=albums, **subdir_common),
        encoding="utf-8",
    )

    print("Done. Site is in dist/")


if __name__ == "__main__":
    main()
