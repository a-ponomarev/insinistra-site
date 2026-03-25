#!/usr/bin/env python3
"""
Static site generator for band website.
Run: python build.py
Output: dist/ (ready to deploy)
"""

import json
import os
import re
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
from xml.sax.saxutils import escape

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

VALID_PORTRAIT_CROPS = frozenset({"top", "center", "bottom"})


def _normalize_portrait_crop(value) -> str | None:
    """Return a valid crop keyword or None if missing/invalid."""
    if value is None or not isinstance(value, str):
        return None
    s = value.strip().lower()
    return s if s in VALID_PORTRAIT_CROPS else None


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


def load_markdown_page(path: Path, body_context: dict | None = None) -> tuple[dict, str]:
    """Load a .md file; return (frontmatter dict, html body)."""
    raw = path.read_text(encoding="utf-8")
    data, body = parse_frontmatter(raw)
    if body_context and data.get("jinja_body"):
        body = Template(body).render(**body_context)
    data["content_html"] = _external_links_new_tab(markdown(body))
    return data, data.get("title", path.stem)


def _apply_site_url_env(site: dict) -> None:
    """Override site_url from SITE_URL when set (build-time staging/production)."""
    env_site = os.environ.get("SITE_URL", "").strip()
    if env_site:
        site["site_url"] = env_site.rstrip("/")


def load_site_config() -> dict:
    """Load site.yaml for SEO defaults (meta descriptions per route)."""
    defaults = {
        "default_meta_description": (
            "Insinistra — symphonic metal from Prague. Official site: music, shows, and press."
        ),
        "meta_descriptions": {},
        "site_url": "",
        "default_og_image": "images/1600/banner-1600.jpg",
        "same_as": [],
    }
    path = CONTENT_DIR / "site.yaml"
    if not path.exists():
        out = defaults.copy()
        _apply_site_url_env(out)
        return out
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            out = defaults.copy()
            _apply_site_url_env(out)
            return out
        merged = {
            **defaults,
            **{k: v for k, v in data.items() if k not in ("meta_descriptions", "same_as")},
        }
        route_defaults = defaults["meta_descriptions"].copy()
        extra = data.get("meta_descriptions")
        if isinstance(extra, dict):
            route_defaults.update(extra)
        merged["meta_descriptions"] = route_defaults
        sa = data.get("same_as")
        if isinstance(sa, list):
            merged["same_as"] = [str(x).strip() for x in sa if str(x).strip()]
        else:
            merged["same_as"] = list(defaults["same_as"])
        _apply_site_url_env(merged)
        return merged
    except (yaml.YAMLError, OSError):
        out = defaults.copy()
        _apply_site_url_env(out)
        return out


def _clean_meta_description(text: str) -> str:
    """Plain single-line meta description, capped for search snippets."""
    if not text or not isinstance(text, str):
        return ""
    return " ".join(text.split()).strip()[:320]


def resolve_meta_description(slug: str, page: dict | None, site: dict) -> str:
    """Frontmatter description wins, then site.meta_descriptions[slug], then default."""
    if page:
        d = page.get("description")
        if isinstance(d, str) and d.strip():
            return _clean_meta_description(d)
    routes = site.get("meta_descriptions") or {}
    if isinstance(routes.get(slug), str) and routes[slug].strip():
        return _clean_meta_description(routes[slug])
    return _clean_meta_description(site.get("default_meta_description") or "")


def social_meta_context(
    site: dict,
    *,
    path_segment: str,
    title_part: str,
    meta_description: str,
    og_image_rel: str | None = None,
) -> dict:
    """
    Open Graph + Twitter Card + canonical URL for base.html.
    If site_url is empty, social_meta_enabled is False and canonical_url is empty (set site_url in site.yaml or SITE_URL env for production).
    """
    site_url = (site.get("site_url") or "").strip().rstrip("/")
    if not site_url:
        return {"social_meta_enabled": False, "canonical_url": ""}
    img = (og_image_rel or site.get("default_og_image") or "").strip().lstrip("/")
    seg = (path_segment or "").strip().strip("/")
    canonical = f"{seg}/" if seg else ""
    base = site_url + "/"
    og_url = urljoin(base, canonical)
    og_image = urljoin(base, img) if img else ""
    title = f"{title_part} | Insinistra"
    desc = meta_description or ""
    return {
        "social_meta_enabled": True,
        "canonical_url": og_url,
        "og_type": "website",
        "og_title": title,
        "og_description": desc,
        "og_image": og_image,
        "og_url": og_url,
        "twitter_card": "summary_large_image",
        "twitter_title": title,
        "twitter_description": desc,
        "twitter_image": og_image,
    }


def page_canonical_url(site_url: str, path_segment: str) -> str:
    """Absolute URL for a site path (trailing slash), matching social_meta canonical rules."""
    base = (site_url or "").strip().rstrip("/")
    if not base:
        return ""
    seg = (path_segment or "").strip().strip("/")
    canonical = f"{seg}/" if seg else ""
    return urljoin(base + "/", canonical)


def _music_group_node(site: dict) -> dict | None:
    site_url = (site.get("site_url") or "").strip().rstrip("/")
    if not site_url:
        return None
    same_raw = site.get("same_as") or []
    same_as: list[str] = []
    seen: set[str] = set()
    if isinstance(same_raw, list):
        for x in same_raw:
            if not isinstance(x, str):
                continue
            u = x.strip()
            if u and u not in seen:
                seen.add(u)
                same_as.append(u)
    return {
        "@type": "MusicGroup",
        "@id": f"{site_url}/#music-group",
        "name": "Insinistra",
        "url": f"{site_url}/",
        "sameAs": same_as,
    }


def _music_events_nodes(site: dict, upcoming_shows: list[dict]) -> list[dict]:
    site_url = (site.get("site_url") or "").strip().rstrip("/")
    if not site_url:
        return []
    mg_id = f"{site_url}/#music-group"
    nodes: list[dict] = []
    for i, c in enumerate(upcoming_shows):
        date_raw = (c.get("date") or "")[:10]
        if len(date_raw) < 10:
            continue
        venue = (c.get("venue") or "").strip() or "Venue TBA"
        locality = (c.get("location") or "").strip()
        evt: dict = {
            "@type": "MusicEvent",
            "@id": f"{site_url}/shows/#event-{date_raw}-{i}",
            "name": f"Insinistra at {venue}",
            "startDate": date_raw,
            "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
            "eventStatus": "https://schema.org/EventScheduled",
            "location": {
                "@type": "Place",
                "name": venue,
            },
            "performer": {"@id": mg_id},
        }
        if locality:
            evt["location"]["address"] = {
                "@type": "PostalAddress",
                "addressLocality": locality,
            }
        ticket_url = (c.get("tickets") or "").strip()
        fb = (c.get("facebook") or "").strip()
        primary = (
            ticket_url if ticket_url.startswith("http") else (fb if fb.startswith("http") else "")
        )
        if primary:
            evt["url"] = primary
        if ticket_url.startswith("http"):
            evt["offers"] = {
                "@type": "Offer",
                "url": ticket_url,
                "availability": "https://schema.org/InStock",
            }
        nodes.append(evt)
    return nodes


def _music_album_nodes(site: dict, albums: list[dict]) -> list[dict]:
    site_url = (site.get("site_url") or "").strip().rstrip("/")
    if not site_url:
        return []
    mg_id = f"{site_url}/#music-group"
    nodes: list[dict] = []
    for a in albums:
        title = (a.get("title") or "").strip()
        if not title:
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "release"
        ext_url = (a.get("url") or "").strip()
        node: dict = {
            "@type": "MusicAlbum",
            "@id": f"{site_url}/albums/#{slug}",
            "name": title,
            "byArtist": {"@id": mg_id},
        }
        date_pub = (a.get("date") or "")[:10]
        if len(date_pub) >= 10:
            node["datePublished"] = date_pub
        img_rel = (a.get("artwork") or "").strip().lstrip("/")
        if img_rel:
            node["image"] = urljoin(site_url + "/", img_rel)
        if ext_url.startswith("http"):
            node["url"] = ext_url
        nodes.append(node)
    return nodes


def structured_data_script_json(site: dict, extra_nodes: list[dict] | None = None) -> str:
    """application/ld+json document, or empty string when site_url is unset."""
    mg = _music_group_node(site)
    if not mg:
        return ""
    graph: list[dict] = [mg]
    if extra_nodes:
        graph.extend(extra_nodes)
    return json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False)


def write_sitemap_xml(dist_dir: Path, site_url: str, page_slugs: list[str], extra_segments: list[str]) -> None:
    base = site_url.strip().rstrip("/")
    lastmod = datetime.now().date().isoformat()
    urls: list[str] = [page_canonical_url(base, "")]
    for slug in sorted(page_slugs):
        urls.append(page_canonical_url(base, slug))
    for seg in sorted(extra_segments):
        urls.append(page_canonical_url(base, seg))
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for loc in urls:
        lines.append("  <url>")
        lines.append(f"    <loc>{escape(loc)}</loc>")
        lines.append(f"    <lastmod>{lastmod}</lastmod>")
        lines.append("  </url>")
    lines.append("</urlset>")
    (dist_dir / "sitemap.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_robots_txt(dist_dir: Path, site_url: str) -> None:
    base = site_url.strip().rstrip("/")
    (dist_dir / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {base}/sitemap.xml\n",
        encoding="utf-8",
    )


def load_pages(body_context: dict | None = None) -> list[dict]:
    """Load all Markdown pages from content/pages/."""
    pages_dir = CONTENT_DIR / "pages"
    if not pages_dir.exists():
        return []
    pages = []
    for path in sorted(pages_dir.glob("*.md")):
        data, title = load_markdown_page(path, body_context)
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
        "booking_email": "booking@insinistra.com",
        "press_email": "press@insinistra.com",
        "booking_contact_name": None,
        "featured_video_id": None,
        "featured_tracks": [],
        "press_photos": [],
        "press_kit_url": "",
        "stage_plot_url": "",
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


def load_gallery_config() -> dict:
    """Load gallery UI config from content/gallery.yaml (portrait thumb crop)."""
    defaults = {
        "portrait_crop": "top",
        "portrait_crop_overrides": {},
    }
    path = CONTENT_DIR / "gallery.yaml"
    if not path.exists():
        return {"portrait_crop": defaults["portrait_crop"], "portrait_crop_overrides": {}}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            return {"portrait_crop": defaults["portrait_crop"], "portrait_crop_overrides": {}}
        for key, value in defaults.items():
            if key not in data:
                data[key] = value
        pc = _normalize_portrait_crop(data.get("portrait_crop")) or "top"
        data["portrait_crop"] = pc
        raw_ov = data.get("portrait_crop_overrides")
        overrides: dict[str, str] = {}
        if isinstance(raw_ov, dict):
            for k, v in raw_ov.items():
                if k is None:
                    continue
                key_norm = str(k).strip().replace("\\", "/")
                val = _normalize_portrait_crop(v)
                if val:
                    overrides[key_norm] = val
        data["portrait_crop_overrides"] = overrides
        return data
    except (yaml.YAMLError, OSError):
        return {"portrait_crop": defaults["portrait_crop"], "portrait_crop_overrides": {}}


def apply_gallery_portrait_overrides(photo_albums: list[dict], gallery_config: dict) -> None:
    """Set photo['portrait_crop'] only when a valid per-path override exists."""
    ov = gallery_config.get("portrait_crop_overrides") or {}
    for album in photo_albums:
        for p in album.get("photos", []):
            norm = (p.get("name") or "").replace("\\", "/")
            if norm in ov:
                p["portrait_crop"] = ov[norm]
            else:
                p.pop("portrait_crop", None)


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
    site_config = load_site_config()
    epk_config = load_epk_config()
    gallery_config = load_gallery_config()
    pages = load_pages(
        {
            "press_kit_url": epk_config.get("press_kit_url") or "",
            "stage_plot_url": epk_config.get("stage_plot_url") or "",
        }
    )
    upcoming_shows, past_shows = load_concerts()
    albums = load_albums()
    videos = load_videos()

    # Process photos (gallery)
    print("  Processing photos...")
    photos = process_images(PHOTOS_DIR, DIST_DIR / "photos", "photos")
    photo_albums, all_photos_ordered = group_photos_by_album(photos)
    apply_gallery_portrait_overrides(photo_albums, gallery_config)

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

    current_year = datetime.now().year
    copyright_start_year = 2026
    copyright_year = (
        str(copyright_start_year)
        if current_year <= copyright_start_year
        else f"{copyright_start_year}\u2013{current_year}"
    )
    common = {
        "current_year": current_year,
        "copyright_year": copyright_year,
        "gallery_portrait_crop": gallery_config["portrait_crop"],
    }
    subdir_common = {**common, "base": ".."}

    # Render homepage
    print("  Writing index.html...")
    featured_album = next((a for a in albums if a.get("featured")), None)
    albums_for_discography = [a for a in albums if not a.get("featured")][:4]
    template_index = env.get_template("index.html")
    home_desc = resolve_meta_description("home", None, site_config)
    (DIST_DIR / "index.html").write_text(
        template_index.render(
            base="",
            is_index=True,
            meta_description=home_desc,
            **social_meta_context(
                site_config,
                path_segment="",
                title_part="Home",
                meta_description=home_desc,
            ),
            **common,
            pages=pages,
            concerts=upcoming_shows[:5],
            albums=albums,
            featured_album=featured_album,
            albums_for_discography=albums_for_discography,
            videos=videos[:6],
            photo_albums=photo_albums,
            all_photos_ordered=all_photos_ordered,
            structured_data_json=structured_data_script_json(site_config),
        ),
        encoding="utf-8",
    )

    # Render each Markdown page (e.g. about -> about/index.html)
    for page in pages:
        slug = page["slug"]
        print(f"  Writing {slug}/index.html...")
        out_dir = DIST_DIR / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        meta_desc = resolve_meta_description(slug, page, site_config)
        sm = social_meta_context(
            site_config,
            path_segment=slug,
            title_part=page.get("title") or slug,
            meta_description=meta_desc,
        )
        if slug == "about":
            template_about = env.get_template("about.html")
            (out_dir / "index.html").write_text(
                template_about.render(
                    page=page,
                    band_members=band_members,
                    reviews=reviews,
                    meta_description=meta_desc,
                    structured_data_json=structured_data_script_json(site_config),
                    **sm,
                    **subdir_common,
                ),
                encoding="utf-8",
            )
        else:
            template_page = env.get_template("page.html")
            (out_dir / "index.html").write_text(
                template_page.render(
                    page=page,
                    meta_description=meta_desc,
                    structured_data_json=structured_data_script_json(site_config),
                    **sm,
                    **subdir_common,
                ),
                encoding="utf-8",
            )

    # Shows page (past and upcoming, latest first)
    print("  Writing shows/index.html...")
    (DIST_DIR / "shows").mkdir(exist_ok=True)
    template_concerts = env.get_template("concerts.html")
    shows_desc = resolve_meta_description("shows", None, site_config)
    (DIST_DIR / "shows" / "index.html").write_text(
        template_concerts.render(
            upcoming_shows=upcoming_shows,
            past_shows=past_shows,
            meta_description=shows_desc,
            structured_data_json=structured_data_script_json(
                site_config, _music_events_nodes(site_config, upcoming_shows)
            ),
            **social_meta_context(
                site_config,
                path_segment="shows",
                title_part="Shows",
                meta_description=shows_desc,
            ),
            **subdir_common,
        ),
        encoding="utf-8",
    )

    # Albums page
    print("  Writing albums/index.html...")
    (DIST_DIR / "albums").mkdir(exist_ok=True)
    template_albums = env.get_template("albums.html")
    albums_desc = resolve_meta_description("albums", None, site_config)
    (DIST_DIR / "albums" / "index.html").write_text(
        template_albums.render(
            albums=albums,
            meta_description=albums_desc,
            structured_data_json=structured_data_script_json(
                site_config, _music_album_nodes(site_config, albums)
            ),
            **social_meta_context(
                site_config,
                path_segment="albums",
                title_part="Discography",
                meta_description=albums_desc,
            ),
            **subdir_common,
        ),
        encoding="utf-8",
    )

    # Photos page (full gallery)
    print("  Writing photos/index.html...")
    (DIST_DIR / "photos").mkdir(exist_ok=True)
    template_photos = env.get_template("photos.html")
    photos_desc = resolve_meta_description("photos", None, site_config)
    (DIST_DIR / "photos" / "index.html").write_text(
        template_photos.render(
            photo_albums=photo_albums,
            all_photos_ordered=all_photos_ordered,
            meta_description=photos_desc,
            structured_data_json=structured_data_script_json(site_config),
            **social_meta_context(
                site_config,
                path_segment="photos",
                title_part="Photos",
                meta_description=photos_desc,
            ),
            **subdir_common,
        ),
        encoding="utf-8",
    )

    # EPK page (Electronic Press Kit)
    print("  Writing epk/index.html...")
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
    epk_desc = resolve_meta_description("epk", None, site_config)
    (DIST_DIR / "epk" / "index.html").write_text(
        template_epk.render(
            epk=epk_config,
            about_page=about_page,
            band_members=band_members,
            reviews=reviews,
            albums=albums,
            videos=videos,
            upcoming_shows=upcoming_shows[:5],
            recent_shows=past_shows[:5],
            photo_albums=photo_albums,
            all_photos_ordered=all_photos_ordered,
            image_assets=image_assets,
            epk_press_photos=press_photos,
            meta_description=epk_desc,
            structured_data_json=structured_data_script_json(site_config),
            **social_meta_context(
                site_config,
                path_segment="epk",
                title_part="Electronic Press Kit",
                meta_description=epk_desc,
            ),
            **subdir_common,
        ),
        encoding="utf-8",
    )

    site_url = (site_config.get("site_url") or "").strip()
    if site_url:
        print("  Writing sitemap.xml, robots.txt...")
        write_sitemap_xml(
            DIST_DIR,
            site_url,
            [p["slug"] for p in pages],
            ["shows", "albums", "photos", "epk"],
        )
        write_robots_txt(DIST_DIR, site_url)

    print("Done. Site is in dist/")


if __name__ == "__main__":
    main()
