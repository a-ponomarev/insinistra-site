#!/usr/bin/env python3
"""
Static site generator for band website.
Run: python build.py
Output: dist/ (ready to deploy)
"""

import json
import re
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, Template
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
HERO_WIDTH = 3000  # Hero images (desktop + mobile) use this for better quality
THUMB_WIDTH = 400

# Banner: fixed height in CSS (px); hide below viewport width = banner_display_width + sidebar
BANNER_CSS_HEIGHT_PX = 320
SOCIAL_SIDEBAR_WIDTH_PX = 56  # body padding-left reserved for .social-sidebar
BANNER_HIDE_BREAKPOINT_DEFAULT = 576


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


def _external_links_new_tab(html: str) -> str:
    """Add target="_blank" rel="noopener noreferrer" to external links in HTML."""
    def repl(m):
        tag = m.group(0)
        if "target=" in tag:
            return tag
        return tag[:-1] + ' target="_blank" rel="noopener noreferrer">'
    return re.sub(r'<a\s+[^>]*href="https?://[^"]*"[^>]*>', repl, html)


def load_markdown_page(path: Path) -> tuple[dict, str]:
    """Load a .md file; return (frontmatter dict, html body)."""
    raw = path.read_text(encoding="utf-8")
    data, body = parse_frontmatter(raw)
    data["content_html"] = _external_links_new_tab(markdown(body))
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
    """Load albums from YAML, sorted by date newest first. Derives year and is_upcoming for display."""
    path = CONTENT_DIR / "albums.yaml"
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    items = data.get("albums", data) if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []
    today = datetime.now().date()
    for a in items:
        d = a.get("date") or ""
        if isinstance(d, str) and len(d) >= 4:
            a["year"] = int(d[:4])
        else:
            a["year"] = None
        parsed = _parse_date(d) if d else None
        a["is_upcoming"] = parsed is not None and parsed > today
    return sorted(items, key=lambda a: a.get("date") or "", reverse=True)


def load_videos() -> list[dict]:
    """Load YouTube video IDs from content/videos.yaml (list of {id, title?})."""
    path = CONTENT_DIR / "videos.yaml"
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    items = data.get("videos", data) if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []
    return [v for v in items if isinstance(v, dict) and v.get("id")]


def load_band_members(image_assets: list[dict]) -> list[dict]:
    """Load band members from YAML and resolve image URLs from image_assets."""
    path = CONTENT_DIR / "band-members.yaml"
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    members = data.get("members", data) if isinstance(data, dict) else data
    if not isinstance(members, list):
        return []
    # Build lookup: asset name (e.g. "members/maria.jpg") -> thumb/resized URLs
    # Use lowercase keys so "members/maria.JPG" on disk matches "members/maria.jpg" in YAML
    asset_by_name = {}
    for a in image_assets:
        key = a.get("name", "").replace("\\", "/").lower()
        asset_by_name[key] = a
    for m in members:
        img = (m.get("image") or "").strip().replace("\\", "/").lower()
        m["image_thumb"] = None
        m["image_resized"] = None
        if img:
            a = asset_by_name.get(img)
            if a:
                m["image_thumb"] = a.get("thumb")
                m["image_resized"] = a.get("resized")
    return members


def load_reviews() -> list[dict]:
    """Load short review citations from YAML for the About page."""
    path = CONTENT_DIR / "reviews.yaml"
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    reviews = data.get("reviews", data) if isinstance(data, dict) else data
    if not isinstance(reviews, list):
        return []
    return [r for r in reviews if isinstance(r, dict) and r.get("text")]


def load_epk_config() -> dict:
    """Load EPK config from content/epk.yaml. Returns dict with defaults for missing keys."""
    defaults = {
        "one_liner": "Symphonic metal from Prague.",
        "short_bio": "",
        "booking_email": "info@insinistra.com",
        "booking_contact_name": None,
        "rider_url": None,
        "stage_plot_url": None,
        "featured_video_id": None,
        "featured_tracks": [],
        "press_photos": [],
    }
    path = CONTENT_DIR / "epk.yaml"
    if not path.exists():
        return defaults
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            return defaults
        for key, value in defaults.items():
            if key not in data:
                data[key] = value
        return data
    except (yaml.YAMLError, OSError):
        return defaults


def process_images(src_dir: Path, dist_dir: Path, url_prefix: str) -> list[dict]:
    """
    Copy originals and create resized + thumbnail versions from src_dir into dist_dir.
    Skips any image whose target files already exist (already compressed last run).
    Returns list of asset info dicts (used for gallery rendering).
    """
    if not src_dir.exists():
        return []
    dist_dir.mkdir(parents=True, exist_ok=True)
    (dist_dir / "original").mkdir(exist_ok=True)
    (dist_dir / "1600").mkdir(exist_ok=True)
    (dist_dir / "3000").mkdir(exist_ok=True)
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

        resized_name = f"{base}-1600.jpg"
        hero_name = f"{base}-3000.jpg"
        thumb_name = f"{base}-thumb.jpg"
        orig_dest = dist_dir / "original" / subdir / name
        resized_dest = dist_dir / "1600" / subdir / resized_name
        hero_dest = dist_dir / "3000" / subdir / hero_name
        thumb_dest = dist_dir / "thumb" / subdir / thumb_name

        orig_url = f"{url_prefix}/original/{rel.as_posix()}"
        resized_url = f"{url_prefix}/1600/{(subdir / resized_name).as_posix()}"
        thumb_url = f"{url_prefix}/thumb/{(subdir / thumb_name).as_posix()}"

        is_hero = base in ("hero", "hero-mobile", "banner")
        skip = orig_dest.exists() and resized_dest.exists() and thumb_dest.exists()
        if is_hero:
            skip = skip and hero_dest.exists()
        if skip:
            assets.append({
                "original": orig_url,
                "resized": resized_url,
                "thumb": thumb_url,
                "name": str(rel),
            })
            continue

        (dist_dir / "original" / subdir).mkdir(parents=True, exist_ok=True)
        (dist_dir / "1600" / subdir).mkdir(parents=True, exist_ok=True)
        (dist_dir / "3000" / subdir).mkdir(parents=True, exist_ok=True)
        (dist_dir / "thumb" / subdir).mkdir(parents=True, exist_ok=True)

        shutil.copy2(path, orig_dest)

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
                resized.save(resized_dest, "JPEG", quality=88)

                if is_hero:
                    if w > HERO_WIDTH:
                        hero_img = img.resize((HERO_WIDTH, int(h * HERO_WIDTH / w)), Image.Resampling.LANCZOS)
                    else:
                        hero_img = img
                    hero_img.save(hero_dest, "JPEG", quality=88)

                if w > THUMB_WIDTH:
                    thumb = img.resize((THUMB_WIDTH, int(h * THUMB_WIDTH / w)), Image.Resampling.LANCZOS)
                else:
                    thumb = img
                thumb.save(thumb_dest, "JPEG", quality=85)
        except Exception as e:
            print(f"  Warning: could not process {name}: {e}")

        assets.append({
            "original": orig_url,
            "resized": resized_url,
            "thumb": thumb_url,
            "name": str(rel),
        })

    return assets


def group_photos_by_album(photos: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Group flat photo list by top-level folder (album). Returns (photo_albums, all_photos_ordered).
    photo_albums: list of {"name": "Live", "photos": [...]}; all_photos_ordered: flat list with indices.
    """
    by_album = defaultdict(list)
    for p in photos:
        name = (p.get("name") or "").replace("\\", "/")
        album_key = name.split("/")[0] if "/" in name else "Photos"
        by_album[album_key].append(p)
    photo_albums = [{"name": k, "photos": v} for k, v in sorted(by_album.items())]
    # Assign global index to each photo (for lightbox navigation)
    idx = 0
    all_photos_ordered = []
    for album in photo_albums:
        for p in album["photos"]:
            p["index"] = idx
            all_photos_ordered.append(p)
            idx += 1
    return photo_albums, all_photos_ordered


def get_banner_hide_breakpoint(images_dist: Path) -> int:
    """
    Compute max-width breakpoint (px) below which the site banner is hidden.
    Uses the resized banner image aspect ratio and BANNER_CSS_HEIGHT_PX so that
    when the viewport is narrower than the banner's display width at that height,
    the banner is hidden.
    """
    banner_path = images_dist / "1600" / "banner-1600.jpg"
    if not banner_path.exists():
        return BANNER_HIDE_BREAKPOINT_DEFAULT
    try:
        with Image.open(banner_path) as img:
            w, h = img.size
        if h <= 0:
            return BANNER_HIDE_BREAKPOINT_DEFAULT
        return int(BANNER_CSS_HEIGHT_PX * (w / h) + SOCIAL_SIDEBAR_WIDTH_PX)
    except Exception:
        return BANNER_HIDE_BREAKPOINT_DEFAULT


def main() -> None:
    print("Building band site...")
    # Recreate dist but keep photos/ and images/ (skip re-compressing existing outputs)
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    if DIST_DIR.exists():
        for item in DIST_DIR.iterdir():
            if item.name not in ("photos", "images"):
                if item.is_file():
                    item.unlink()
                else:
                    shutil.rmtree(item)

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    env.filters["tojson"] = lambda v: json.dumps(v)

    # Load data
    print("  Loading content...")
    pages = load_pages()
    upcoming_shows, past_shows = load_concerts()
    albums = load_albums()
    videos = load_videos()

    # Process photos (gallery)
    print("  Processing photos...")
    photos = process_images(PHOTOS_DIR, DIST_DIR / "photos", "photos")
    photo_albums, all_photos_ordered = group_photos_by_album(photos)

    # Process images (banner, artwork, etc.)
    print("  Processing images...")
    image_assets = process_images(IMAGES_DIR, DIST_DIR / "images", "images")
    band_members = load_band_members(image_assets)
    reviews = load_reviews()

    # Copy static and inject build-time values (e.g. banner breakpoint) into CSS
    if STATIC_DIR.exists():
        print("  Copying static/...")
        shutil.copytree(STATIC_DIR, DIST_DIR / "static")
    banner_breakpoint = get_banner_hide_breakpoint(DIST_DIR / "images")
    style_css = DIST_DIR / "static" / "style.css"
    if style_css.exists():
        style_content = style_css.read_text(encoding="utf-8")
        if "BANNER_BREAKPOINT" in style_content:
            style_css.write_text(
                Template(style_content).render(BANNER_BREAKPOINT=banner_breakpoint),
                encoding="utf-8",
            )

    common = {"nav_pages": pages, "current_year": datetime.now().year}
    subdir_common = {**common, "base": ".."}

    # Render homepage
    print("  Writing index.html...")
    featured_album = next((a for a in albums if a.get("featured")), None)
    albums_for_discography = [a for a in albums if not a.get("featured")][:4]
    template_index = env.get_template("index.html")
    (DIST_DIR / "index.html").write_text(
        template_index.render(
            base="",
            is_index=True,
            **common,
            pages=pages,
            concerts=upcoming_shows[:5],
            albums=albums,
            featured_album=featured_album,
            albums_for_discography=albums_for_discography,
            videos=videos[:6],
            photo_albums=photo_albums,
            all_photos_ordered=all_photos_ordered,
        ),
        encoding="utf-8",
    )

    # Render each Markdown page (e.g. about -> about/index.html)
    for page in pages:
        slug = page["slug"]
        print(f"  Writing {slug}/index.html...")
        out_dir = DIST_DIR / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        if slug == "about":
            template_about = env.get_template("about.html")
            (out_dir / "index.html").write_text(
                template_about.render(page=page, band_members=band_members, reviews=reviews, **subdir_common),
                encoding="utf-8",
            )
        else:
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

    # Photos page (full gallery)
    print("  Writing photos/index.html...")
    (DIST_DIR / "photos").mkdir(exist_ok=True)
    template_photos = env.get_template("photos.html")
    (DIST_DIR / "photos" / "index.html").write_text(
        template_photos.render(
            photo_albums=photo_albums,
            all_photos_ordered=all_photos_ordered,
            **subdir_common,
        ),
        encoding="utf-8",
    )

    # EPK page (Electronic Press Kit)
    print("  Writing epk/index.html...")
    epk_config = load_epk_config()
    about_page = next((p for p in pages if p.get("slug") == "about"), None)
    # Press photos: from epk.yaml list (with URL resolution) or filter image_assets by promo/banner/hero
    def is_press_asset(a: dict) -> bool:
        n = (a.get("name") or "").replace("\\", "/").lower()
        return "promo" in n or n.startswith("banner") or n.startswith("hero")
    yaml_press = epk_config.get("press_photos") or []
    if yaml_press:
        asset_by_name = {(a.get("name") or "").replace("\\", "/").lower(): a for a in image_assets}
        press_photos = []
        for item in yaml_press:
            name = (item.get("name") or "").strip().replace("\\", "/").lower()
            a = asset_by_name.get(name) if name else None
            if a:
                press_photos.append({"label": item.get("label") or name, "resized": a.get("resized"), "thumb": a.get("thumb"), "original": a.get("original")})
    else:
        press_photos = [{"label": (a.get("name") or "").split("/")[-1], "resized": a.get("resized"), "thumb": a.get("thumb"), "original": a.get("original")} for a in image_assets if is_press_asset(a)]
    (DIST_DIR / "epk").mkdir(exist_ok=True)
    template_epk = env.get_template("epk.html")
    (DIST_DIR / "epk" / "index.html").write_text(
        template_epk.render(
            epk=epk_config,
            about_page=about_page,
            band_members=band_members,
            reviews=reviews,
            albums=albums,
            videos=videos,
            upcoming_shows=upcoming_shows[:5],
            image_assets=image_assets,
            epk_press_photos=press_photos,
            **subdir_common,
        ),
        encoding="utf-8",
    )

    print("Done. Site is in dist/")


if __name__ == "__main__":
    main()
