#!/usr/bin/env python3
"""
Interactive Wayback Machine scraper for archived Twitter/X status pages.

The CSV intentionally contains only the three requested columns:
date, tweet text, and the Wayback URL for the archived tweet. Attached images
are downloaded beside it in the user-selected folder.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import html
import json
import mimetypes
import re
import socket
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlencode, urlparse
from urllib.request import Request, urlopen


CDX_ENDPOINT = "https://web.archive.org/cdx/search/cdx"
AVAILABILITY_ENDPOINT = "https://archive.org/wayback/available"
USER_AGENT = "TwitterArchiveScraper/1.0 (+https://web.archive.org/)"
RETRY_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}


@dataclass(frozen=True)
class Capture:
    timestamp: str
    original: str
    archive_url: str
    status_id: str


@dataclass
class TweetData:
    date: str
    text: str
    image_urls: list[str]


class WaybackError(RuntimeError):
    pass


class TweetHTMLParser(HTMLParser):
    """Extract tweet-like metadata without third-party HTML dependencies."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.time_values: list[str] = []
        self.image_urls: list[str] = []
        self.tweet_text_chunks: list[str] = []
        self._tweet_text_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {k.lower(): v or "" for k, v in attrs}

        if tag == "meta":
            key = (
                attr.get("property")
                or attr.get("name")
                or attr.get("itemprop")
                or attr.get("data-rh")
            )
            content = attr.get("content")
            if key and content:
                self.meta[key.lower()] = html.unescape(content).strip()

        if tag == "time":
            value = attr.get("datetime") or attr.get("title")
            if value:
                self.time_values.append(html.unescape(value).strip())

        if tag == "img":
            src = attr.get("src") or attr.get("data-src")
            if src:
                self.image_urls.append(html.unescape(src).strip())

        class_name = attr.get("class", "").lower()
        data_testid = attr.get("data-testid", "").lower()
        if (
            data_testid == "tweettext"
            or "tweet-text" in class_name
            or "tweettext" in class_name
            or "js-tweet-text" in class_name
        ):
            self._tweet_text_depth += 1
        elif self._tweet_text_depth:
            self._tweet_text_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if self._tweet_text_depth:
            self._tweet_text_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._tweet_text_depth and data.strip():
            self.tweet_text_chunks.append(data)


def color(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m"


BLOCK_ART = {
    "BARBIE": (
        "██████   ██████   ███████   ██████   ████████  ███████",
        "██   ██  ██   ██  ██   ██  ██   ██     ██     ██",
        "██   ██  ██   ██  ██   ██  ██   ██     ██     ██",
        "██████   ██████   ██████   ██████      ██     █████",
        "██   ██  ██   ██  ██  ██   ██   ██     ██     ██",
        "██   ██  ██   ██  ██   ██  ██   ██     ██     ██",
        "██████   ██   ██  ██   ██  ██████   ████████  ███████",
    ),
    "BITCH": (
        "██████   ████████  ████████   ██████   ██   ██",
        "██   ██     ██        ██     ██        ██   ██",
        "██   ██     ██        ██     ██        ██   ██",
        "██████      ██        ██     ██        ███████",
        "██   ██     ██        ██     ██        ██   ██",
        "██   ██     ██        ██     ██        ██   ██",
        "██████   ████████     ██      ██████   ██   ██",
    ),
    "CULT": (
        " ██████  ██    ██  ██        ███████",
        "██       ██    ██  ██           ██",
        "██       ██    ██  ██           ██",
        "██       ██    ██  ██           ██",
        "██       ██    ██  ██           ██",
        "██       ██    ██  ██           ██",
        " ██████   ██████   ███████      ██",
    ),
}


def banner_width() -> int:
    return max(len(line) for lines in BLOCK_ART.values() for line in lines)


def print_banner() -> None:
    width = banner_width()
    separator = "=" * width

    print(separator)
    for line in BLOCK_ART["BARBIE"]:
        print(color(line, "95;1"))
    print()
    for line in BLOCK_ART["BITCH"]:
        print(color(line, "95;1"))
    print()
    for line in BLOCK_ART["CULT"]:
        print(color(line, "96;1"))
    print()
    print("Barbie Bitch Cult - The Twitter Archive Scraper".center(width))
    print(separator)
    print()


def prompt_value(label: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default not in (None, "") else ""
    while True:
        value = input(f"{label}{suffix}: ").strip()
        if value:
            return value
        if default is not None:
            return default
        print("This value is required.")


def prompt_float(label: str, default: float) -> float:
    while True:
        raw = prompt_value(label, str(default))
        try:
            value = float(raw)
        except ValueError:
            print("Enter a number.")
            continue
        if value < 0:
            print("Enter 0 or a positive number.")
            continue
        return value


def prompt_int(label: str, default: int) -> int:
    while True:
        raw = prompt_value(label, str(default))
        try:
            value = int(raw)
        except ValueError:
            print("Enter a whole number.")
            continue
        if value < 0:
            print("Enter 0 or a positive whole number.")
            continue
        return value


def clean_handle(handle: str) -> str:
    handle = handle.strip().lstrip("@")
    if not re.fullmatch(r"[A-Za-z0-9_]{1,15}", handle):
        raise ValueError("Twitter handles must be 1-15 letters, numbers, or underscores.")
    return handle


def request_bytes(url: str, timeout: float, attempts: int = 4) -> tuple[bytes, str, str]:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        request = Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "*/*",
                "Accept-Encoding": "gzip",
            },
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                body = response.read()
                if response.headers.get("Content-Encoding", "").lower() == "gzip":
                    body = gzip.decompress(body)
                content_type = response.headers.get("Content-Type", "")
                return body, response.geturl(), content_type
        except HTTPError as exc:
            last_error = exc
            if exc.code not in RETRY_STATUS_CODES:
                break
        except (URLError, TimeoutError, socket.timeout) as exc:
            last_error = exc

        if attempt < attempts:
            time.sleep(min(2 ** attempt, 20))

    raise WaybackError(f"Could not fetch {url}: {last_error}")


def request_json(url: str, timeout: float) -> object:
    body, _, _ = request_bytes(url, timeout)
    return json.loads(body.decode("utf-8", errors="replace"))


def request_text(url: str, timeout: float) -> str:
    body, _, _ = request_bytes(url, timeout)
    return body.decode("utf-8", errors="replace")


def cdx_url(params: dict[str, str]) -> str:
    return f"{CDX_ENDPOINT}?{urlencode(params)}"


def log(message: str) -> None:
    print(message, flush=True)


def discover_captures(handle: str, timeout: float, max_tweets: int = 0) -> list[Capture]:
    captures: dict[str, Capture] = {}
    for host in ("twitter.com", "x.com"):
        params = {
            "url": f"https://{host}/{handle}/status*",
            "output": "text",
            "fl": "timestamp,original",
            "collapse": "urlkey",
        }
        rows = parse_cdx_capture_text(request_text(cdx_url(params), timeout))
        log(f"  {host}: found {len(rows)} archived status URL(s)")
        for timestamp, original in rows:
            status_id = status_id_from_url(original)
            if not status_id:
                continue
            archive_url = archived_page_url(timestamp, original)
            current = captures.get(status_id)
            if current is None or timestamp < current.timestamp:
                captures[status_id] = Capture(timestamp, original, archive_url, status_id)

        if max_tweets and len(captures) >= max_tweets:
            break

    return sorted(captures.values(), key=lambda capture: capture.timestamp)


def parse_cdx_capture_text(text: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        timestamp, original = parts
        if re.fullmatch(r"\d{14}", timestamp):
            rows.append((timestamp, original.strip()))
    return rows


def parse_resume_key(rows: list[object]) -> str | None:
    if len(rows) >= 2 and rows[-2] == [] and isinstance(rows[-1], list) and rows[-1]:
        return str(rows[-1][0])
    return None


def status_id_from_url(url: str) -> str | None:
    match = re.search(r"/status(?:es)?/(\d+)", url)
    return match.group(1) if match else None


def archived_page_url(timestamp: str, original: str, modifier: str = "id_") -> str:
    return f"https://web.archive.org/web/{timestamp}{modifier}/{original}"


def fetch_archived_tweet(capture: Capture, timeout: float) -> tuple[str, str]:
    urls = [
        archived_page_url(capture.timestamp, capture.original, "id_"),
        archived_page_url(capture.timestamp, capture.original, "if_"),
        archived_page_url(capture.timestamp, capture.original, ""),
    ]
    last_error: Exception | None = None
    for url in urls:
        try:
            body, final_url, content_type = request_bytes(url, timeout)
            text = body.decode("utf-8", errors="replace")
            if is_tweet_payload(content_type, text):
                return text, final_url
        except WaybackError as exc:
            last_error = exc
    raise WaybackError(f"Could not fetch archived tweet {capture.original}: {last_error}")


def is_tweet_payload(content_type: str, text: str) -> bool:
    lowered = content_type.lower()
    stripped = text.lstrip()
    return (
        "text/html" in lowered
        or "application/json" in lowered
        or "text/json" in lowered
        or stripped.startswith("{")
        or stripped.startswith("[")
        or not content_type
    )


def parse_tweet_capture(raw_payload: str, capture: Capture) -> TweetData:
    parsed_json = parse_json_payload(raw_payload)
    if parsed_json is not None:
        return parse_tweet_json(parsed_json, capture)
    return parse_tweet_html(raw_payload, capture)


def parse_json_payload(raw_payload: str) -> object | None:
    stripped = raw_payload.lstrip()
    if not stripped.startswith(("{", "[")):
        return None
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return None


def parse_tweet_html(raw_html: str, capture: Capture) -> TweetData:
    parser = TweetHTMLParser()
    parser.feed(raw_html)

    text = first_present(
        normalize_tweet_description(" ".join(parser.tweet_text_chunks)),
        normalize_tweet_description(parser.meta.get("og:description", "")),
        normalize_tweet_description(parser.meta.get("twitter:description", "")),
        normalize_tweet_description(parser.meta.get("description", "")),
        normalize_tweet_description(regex_first(raw_html, r'"full_text"\s*:\s*"((?:\\.|[^"])*)"')),
        normalize_tweet_description(regex_first(raw_html, r'"text"\s*:\s*"((?:\\.|[^"])*)"')),
    )

    date = first_present(
        parse_date(parser.meta.get("article:published_time", "")),
        parse_date(parser.meta.get("date", "")),
        parse_date(parser.meta.get("datepublished", "")),
        *(parse_date(value) for value in parser.time_values),
        parse_epoch(regex_first(raw_html, r'data-time-ms=["\'](\d{12,})["\']')),
        parse_epoch(regex_first(raw_html, r'data-time=["\'](\d{9,11})["\']')),
        parse_date(unescape_json(regex_first(raw_html, r'"created_at"\s*:\s*"((?:\\.|[^"])*)"'))),
        parse_date(unescape_json(regex_first(raw_html, r'"datePublished"\s*:\s*"((?:\\.|[^"])*)"'))),
    )

    image_urls = discover_image_urls(raw_html, parser)
    return TweetData(date=date or timestamp_to_iso(capture.timestamp), text=text, image_urls=image_urls)


def parse_tweet_json(payload: object, capture: Capture) -> TweetData:
    tweet = find_json_tweet(payload, capture.status_id)
    text = extract_json_text(tweet) or extract_json_text(payload)
    date = extract_json_date(tweet) or extract_json_date(payload) or timestamp_to_iso(capture.timestamp)
    image_urls = discover_json_image_urls(payload)
    return TweetData(date=date, text=normalize_json_tweet_text(text), image_urls=image_urls)


def find_json_tweet(payload: object, status_id: str) -> object:
    exact_matches: list[dict[str, object]] = []
    likely_matches: list[dict[str, object]] = []

    for item in walk_json_dicts(payload):
        ids = {
            str(item.get("id", "")),
            str(item.get("id_str", "")),
            str(item.get("rest_id", "")),
            str(item.get("conversation_id", "")),
        }
        if status_id in ids:
            exact_matches.append(item)
        if has_tweet_text(item):
            likely_matches.append(item)

    for item in exact_matches:
        if has_tweet_text(item):
            return item
    if exact_matches:
        return exact_matches[0]
    if isinstance(payload, dict) and has_tweet_text(payload):
        return payload
    return likely_matches[0] if likely_matches else payload


def walk_json_dicts(value: object) -> Iterable[dict[str, object]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_json_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_json_dicts(child)


def has_tweet_text(item: dict[str, object]) -> bool:
    return bool(
        item.get("full_text")
        or item.get("text")
        or nested_get(item, ("legacy", "full_text"))
        or nested_get(item, ("note_tweet", "note_tweet_results", "result", "text"))
    )


def extract_json_text(value: object) -> str:
    if not isinstance(value, dict):
        return ""
    candidates = (
        value.get("full_text"),
        value.get("text"),
        nested_get(value, ("legacy", "full_text")),
        nested_get(value, ("legacy", "text")),
        nested_get(value, ("note_tweet", "note_tweet_results", "result", "text")),
        nested_get(value, ("tweet", "full_text")),
        nested_get(value, ("tweet", "text")),
    )
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate

    for item in walk_json_dicts(value):
        for key in ("full_text", "text"):
            candidate = item.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate
    return ""


def extract_json_date(value: object) -> str:
    if not isinstance(value, dict):
        return ""
    candidates = (
        value.get("created_at"),
        value.get("createdAt"),
        value.get("date"),
        value.get("datePublished"),
        nested_get(value, ("legacy", "created_at")),
        nested_get(value, ("tweet", "created_at")),
    )
    for candidate in candidates:
        if isinstance(candidate, str):
            parsed = parse_date(candidate)
            if parsed:
                return parsed

    for item in walk_json_dicts(value):
        for key in ("created_at", "createdAt", "datePublished"):
            candidate = item.get(key)
            if isinstance(candidate, str):
                parsed = parse_date(candidate)
                if parsed:
                    return parsed
    return ""


def nested_get(value: dict[str, object], keys: tuple[str, ...]) -> object:
    current: object = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def discover_json_image_urls(payload: object) -> list[str]:
    candidates: list[str] = []
    for item in walk_json_dicts(payload):
        for key in ("media_url_https", "media_url", "url", "preview_image_url"):
            value = item.get(key)
            if isinstance(value, str) and "pbs.twimg.com/media/" in value:
                candidates.append(value)

        variants = item.get("variants")
        if isinstance(variants, list):
            for variant in variants:
                if isinstance(variant, dict):
                    value = variant.get("url")
                    if isinstance(value, str) and "pbs.twimg.com/media/" in value:
                        candidates.append(value)

    cleaned: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        url = normalize_image_url(candidate)
        if url and url not in seen and is_likely_tweet_attachment(url):
            cleaned.append(url)
            seen.add(url)
    return cleaned


def first_present(*values: str) -> str:
    for value in values:
        if value:
            return value
    return ""


def regex_first(text: str, pattern: str) -> str:
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return html.unescape(unescape_json(match.group(1))).strip()


def unescape_json(value: str) -> str:
    if not value:
        return ""
    try:
        return json.loads(f'"{value}"')
    except json.JSONDecodeError:
        return value.replace(r"\/", "/")


def normalize_tweet_description(value: str) -> str:
    value = html.unescape(unescape_json(value)).strip()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"^.+?\s+on\s+(?:Twitter|X):\s*[\"“](.*)[\"”]\s*$", r"\1", value)
    value = re.sub(r"\s*/\s*(?:Twitter|X)\s*$", "", value)
    value = value.strip(" \t\r\n\"“”")
    if value.lower() in {"twitter", "x"}:
        return ""
    return value


def normalize_json_tweet_text(value: str) -> str:
    value = html.unescape(unescape_json(value)).strip()
    value = value.strip(" \t\r\n\"“”")
    if value.lower() in {"twitter", "x"}:
        return ""
    return value


def parse_date(value: str) -> str:
    value = html.unescape(value or "").strip()
    if not value:
        return ""

    normalized = value.replace("Z", "+00:00")
    for candidate in (normalized, normalized.replace(" UTC", "+0000")):
        try:
            parsed = datetime.fromisoformat(candidate)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).isoformat()
        except ValueError:
            pass

    formats = (
        "%a %b %d %H:%M:%S %z %Y",
        "%I:%M %p - %d %b %Y",
        "%I:%M %p · %b %d, %Y",
        "%b %d, %Y",
    )
    for fmt in formats:
        try:
            parsed = datetime.strptime(value, fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).isoformat()
        except ValueError:
            continue

    return value


def parse_epoch(value: str) -> str:
    if not value:
        return ""
    try:
        number = int(value)
    except ValueError:
        return ""
    if number > 99999999999:
        number /= 1000
    return datetime.fromtimestamp(number, timezone.utc).isoformat()


def timestamp_to_iso(timestamp: str) -> str:
    try:
        return datetime.strptime(timestamp, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc).isoformat()
    except ValueError:
        return timestamp


def discover_image_urls(raw_html: str, parser: TweetHTMLParser) -> list[str]:
    candidates = []
    candidates.extend(parser.image_urls)
    for key in ("og:image", "twitter:image", "twitter:image:src"):
        if parser.meta.get(key):
            candidates.append(parser.meta[key])
    candidates.extend(re.findall(r'https?://pbs\.twimg\.com/media/[^\s"\'<>\\]+', raw_html))
    candidates.extend(re.findall(r'https?://web\.archive\.org/web/\d+[a-z_]*?/https?://pbs\.twimg\.com/media/[^\s"\'<>\\]+', raw_html))

    cleaned: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        url = normalize_image_url(candidate)
        if not url or url in seen:
            continue
        if is_likely_tweet_attachment(url):
            cleaned.append(url)
            seen.add(url)
    return cleaned


def normalize_image_url(url: str) -> str:
    url = html.unescape(unquote(url.strip().strip("'\"")))
    if not url:
        return ""
    if url.startswith("//"):
        url = "https:" + url
    wayback_original = original_url_from_wayback(url)
    if wayback_original:
        url = wayback_original
    if not url.startswith(("http://", "https://")):
        return ""
    parsed = urlparse(url)
    if parsed.netloc == "pbs.twimg.com" and parsed.path.startswith("/media/"):
        return url
    if "pbs.twimg.com/media/" in url:
        return url
    return ""


def original_url_from_wayback(url: str) -> str:
    match = re.match(r"https?://web\.archive\.org/web/\d+[a-z_]*?/(https?://.+)", url)
    return match.group(1) if match else ""


def is_likely_tweet_attachment(url: str) -> bool:
    lowered = url.lower()
    return "pbs.twimg.com/media/" in lowered and "profile_images" not in lowered


def download_images(
    image_urls: Iterable[str],
    image_folder: Path,
    capture: Capture,
    timeout: float,
) -> list[Path]:
    image_folder.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    for index, image_url in enumerate(image_urls, start=1):
        try:
            body, final_url, content_type = fetch_archived_image(image_url, capture.timestamp, timeout)
        except WaybackError as exc:
            log(f"  image skipped: {exc}")
            continue

        suffix = image_suffix(image_url, final_url, content_type)
        filename = f"{capture.status_id}_{index}{suffix}"
        target = unique_path(image_folder / filename)
        target.write_bytes(body)
        saved.append(target)
        log(f"  saved image: {target}")
    return saved


def fetch_archived_image(image_url: str, timestamp: str, timeout: float) -> tuple[bytes, str, str]:
    attempts = [
        archived_page_url(timestamp, image_url, "if_"),
        archived_page_url(timestamp, image_url, "id_"),
    ]

    closest = closest_available_url(image_url, timestamp, timeout)
    if closest:
        attempts.append(closest)

    last_error: Exception | None = None
    for url in attempts:
        try:
            body, final_url, content_type = request_bytes(url, timeout)
            if content_type.startswith("image/") or looks_like_image(body):
                return body, final_url, content_type
            last_error = WaybackError(f"{url} did not return image content")
        except WaybackError as exc:
            last_error = exc
    raise WaybackError(str(last_error or f"could not download {image_url}"))


def closest_available_url(url: str, timestamp: str, timeout: float) -> str:
    params = urlencode({"url": url, "timestamp": timestamp})
    try:
        data = request_json(f"{AVAILABILITY_ENDPOINT}?{params}", timeout)
    except (WaybackError, json.JSONDecodeError):
        return ""
    if not isinstance(data, dict):
        return ""
    closest = data.get("archived_snapshots", {}).get("closest", {})
    if not isinstance(closest, dict) or not closest.get("available"):
        return ""
    return str(closest.get("url", ""))


def looks_like_image(body: bytes) -> bool:
    return body.startswith((b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"GIF87a", b"GIF89a", b"RIFF"))


def image_suffix(original_url: str, final_url: str, content_type: str) -> str:
    for candidate in (original_url, final_url):
        parsed = urlparse(candidate)
        suffix = Path(parsed.path).suffix
        if suffix and len(suffix) <= 6:
            return suffix

    guessed = mimetypes.guess_extension(content_type.split(";")[0].strip())
    return guessed or ".img"


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(2, 10000):
        candidate = path.with_name(f"{path.stem}_{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not find unique filename for {path}")


def run_scrape(
    handle: str,
    output_csv: Path,
    image_folder: Path,
    delay: float,
    max_tweets: int,
    timeout: float,
) -> None:
    handle = clean_handle(handle)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    image_folder.mkdir(parents=True, exist_ok=True)

    log(f"Discovering archived tweets for @{handle}...")
    captures = discover_captures(handle, timeout, max_tweets)
    if max_tweets:
        captures = captures[:max_tweets]
    log(f"Found {len(captures)} unique archived tweet URL(s).")

    with output_csv.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["Date of the original Tweet", "The text of the tweet", "Internet archive URL"])

        for position, capture in enumerate(captures, start=1):
            log(f"[{position}/{len(captures)}] {capture.original}")
            try:
                raw_html, final_archive_url = fetch_archived_tweet(capture, timeout)
                tweet = parse_tweet_capture(raw_html, capture)
            except WaybackError as exc:
                log(f"  skipped: {exc}")
                continue

            archive_url = final_archive_url or capture.archive_url
            writer.writerow([tweet.date, tweet.text, archive_url])
            csv_file.flush()

            if tweet.image_urls:
                download_images(tweet.image_urls, image_folder, capture, timeout)

            if delay and position < len(captures):
                time.sleep(delay)

    log(f"Done. CSV saved to {output_csv}")
    log(f"Images saved to {image_folder}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape archived Twitter/X tweets from the Internet Archive into CSV."
    )
    parser.add_argument("--handle", help="Twitter/X handle, with or without @.")
    parser.add_argument("--output-csv", help="Output CSV filename.")
    parser.add_argument("--image-folder", help="Folder for preserved tweet images.")
    parser.add_argument("--delay", type=float, help="Delay between tweet fetches in seconds.")
    parser.add_argument("--max-tweets", type=int, help="Maximum tweets to scrape. 0 means all.")
    parser.add_argument("--timeout", type=float, help="Per-request timeout in seconds.")
    parser.add_argument("--no-banner", action="store_true", help="Skip the interactive banner.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    if not args.no_banner:
        print_banner()

    try:
        handle = clean_handle(args.handle or prompt_value("Twitter handle"))
        output_csv = Path(args.output_csv or prompt_value("Output CSV filename", f"{handle}_tweets.csv"))
        image_folder = Path(args.image_folder or prompt_value("Folder where tweet images should be saved", f"{handle}_images"))
        delay = args.delay if args.delay is not None else prompt_float("Delay in seconds", 0.5)
        max_tweets = args.max_tweets if args.max_tweets is not None else prompt_int("Max-tweets (0 means all tweets)", 0)
        timeout = args.timeout if args.timeout is not None else prompt_float("Max timeout in seconds", 10.0)
        run_scrape(handle, output_csv, image_folder, delay, max_tweets, timeout)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
