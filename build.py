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
PHOTOS_DIR = ROOT / "photos"
IMAGES_DIR = ROOT / "images"
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


def format_date_display(date_str: str) -> str:
    """Format YYYY-MM-DD as '07 Mar 2026'."""
    if not date_str:
        return ""
    try:
        dt = datetime.strptime(date_str.strip()[:10], "%Y-%m-%d")
        return dt.strftime("%d %b %Y")
    except ValueError:
        return date_str


def _parse_date(date_str: str):
    """Parse YYYY-MM-DD to date, or None."""
    if not date_str or not isinstance(date_str, str):
        return None
    try:
        return datetime.strptime(date_str.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def load_concerts() -> tuple[list[dict], list[dict]]:
    """Load concerts from YAML. Returns (upcoming, past), each sorted latest first."""
    path = CONTENT_DIR / "concerts.yaml"
    if not path.exists():
        return [], []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    items = data.get("concerts", data) if isinstance(data, dict) else data
    if not isinstance(items, list):
        return [], []
    today = datetime.now().date()
    upcoming = []
    past = []
    for c in items:
        c["date_display"] = format_date_display(c.get("date", ""))
        if c.get("url") and not c.get("tickets"):
            c["tickets"] = c["url"]
        d = _parse_date(c.get("date", ""))
        if d is not None and d >= today:
            upcoming.append(c)
        else:
            past.append(c)
    def date_key(c):
        return (c.get("date", ""), c.get("venue", ""))
    upcoming.sort(key=date_key)
    past.sort(key=date_key, reverse=True)
    return upcoming, past


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


def process_images(src_dir: Path, dist_dir: Path, url_prefix: str) -> list[dict]:
    """
    Copy originals and create resized + thumbnail versions from src_dir into dist_dir.
    Returns list of asset info dicts (used for gallery rendering).
    """
    if not src_dir.exists():
        return []
    dist_dir.mkdir(parents=True, exist_ok=True)
    (dist_dir / "original").mkdir(exist_ok=True)
    (dist_dir / "1600").mkdir(exist_ok=True)
    (dist_dir / "thumb").mkdir(exist_ok=True)

    assets = []
    extensions = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

    for path in sorted(src_dir.rglob("*")):
        if path.suffix.lower() not in extensions or not path.is_file():
            continue
        rel = path.relative_to(src_dir)
        name = path.name
        base = path.stem

        subdir = rel.parent
        (dist_dir / "original" / subdir).mkdir(parents=True, exist_ok=True)
        (dist_dir / "1600" / subdir).mkdir(parents=True, exist_ok=True)
        (dist_dir / "thumb" / subdir).mkdir(parents=True, exist_ok=True)

        shutil.copy2(path, dist_dir / "original" / subdir / name)
        orig_url = f"{url_prefix}/original/{rel.as_posix()}"
        resized_url = orig_url
        thumb_url = orig_url

        try:
            with Image.open(path) as img:
                img = img.convert("RGB") if img.mode in ("RGBA", "P") else img
                w, h = img.size
                if w == 0:
                    continue

                if w > RESIZED_WIDTH:
                    resized = img.resize((RESIZED_WIDTH, int(h * RESIZED_WIDTH / w)), Image.Resampling.LANCZOS)
                else:
                    resized = img
                resized_name = f"{base}-1600.jpg"
                resized.save(dist_dir / "1600" / subdir / resized_name, "JPEG", quality=88)
                resized_url = f"{url_prefix}/1600/{(subdir / resized_name).as_posix()}"

                if w > THUMB_WIDTH:
                    thumb = img.resize((THUMB_WIDTH, int(h * THUMB_WIDTH / w)), Image.Resampling.LANCZOS)
                else:
                    thumb = img
                thumb_name = f"{base}-thumb.jpg"
                thumb.save(dist_dir / "thumb" / subdir / thumb_name, "JPEG", quality=85)
                thumb_url = f"{url_prefix}/thumb/{(subdir / thumb_name).as_posix()}"
        except Exception as e:
            print(f"  Warning: could not process {name}: {e}")

        assets.append({
            "original": orig_url,
            "resized": resized_url,
            "thumb": thumb_url,
            "name": str(rel),
        })

    return assets


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
    upcoming_shows, past_shows = load_concerts()
    albums = load_albums()

    # Copy static
    if STATIC_DIR.exists():
        print("  Copying static/...")
        shutil.copytree(STATIC_DIR, DIST_DIR / "static")

    # Process photos (gallery)
    print("  Processing photos...")
    photos = process_images(PHOTOS_DIR, DIST_DIR / "photos", "photos")

    # Process images (banner, artwork, etc.)
    print("  Processing images...")
    process_images(IMAGES_DIR, DIST_DIR / "images", "images")

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
            concerts=upcoming_shows[:5],
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

    # Shows page (past and upcoming, latest first)
    print("  Writing shows/index.html...")
    (DIST_DIR / "shows").mkdir(exist_ok=True)
    template_concerts = env.get_template("concerts.html")
    (DIST_DIR / "shows" / "index.html").write_text(
        template_concerts.render(upcoming_shows=upcoming_shows, past_shows=past_shows, **subdir_common),
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
