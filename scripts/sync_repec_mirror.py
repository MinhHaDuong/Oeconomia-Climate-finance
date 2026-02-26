#!/usr/bin/env python3
"""Download/sync a local RePEc mirror from public HTTP listings.

Default destination aligns with this project:
  $DATA/raw/repec/RePEc

Usage:
  uv run python scripts/sync_repec_mirror.py
  uv run python scripts/sync_repec_mirror.py --base-url https://ftp.repec.org/RePEc/
  uv run python scripts/sync_repec_mirror.py --max-files 1000
"""

import argparse
import os
import re
import sys
import time
from collections import deque
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from urllib3.exceptions import InsecureRequestWarning

sys.path.insert(0, os.path.dirname(__file__))
from utils import MAILTO, RAW_DIR


DEFAULT_BASE_URL = "https://ftp.repec.org/RePEc/"
DEFAULT_DEST = os.path.expanduser(
    os.environ.get("REPEC_ROOT", "~/data/datasets/external/RePEc")
)
DEFAULT_FILE_PATTERN = r"\.(rdf|redif|txt|rdf\.gz|redif\.gz|txt\.gz)$"


def parse_args():
    parser = argparse.ArgumentParser(description="Sync local RePEc mirror")
    parser.add_argument(
        "--base-url",
        type=str,
        default=DEFAULT_BASE_URL,
        help="Base HTTP URL for RePEc listing",
    )
    parser.add_argument(
        "--dest",
        type=str,
        default=DEFAULT_DEST,
        help="Destination directory for local mirror",
    )
    parser.add_argument(
        "--file-pattern",
        type=str,
        default=DEFAULT_FILE_PATTERN,
        help="Regex for files to download",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.1,
        help="Delay between HTTP requests in seconds",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="HTTP timeout in seconds",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=0,
        help="Stop after downloading N files (0 = no limit)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List planned actions without downloading files",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS certificate verification (use only if needed)",
    )
    return parser.parse_args()


def normalize_base_url(base_url):
    if not base_url.endswith("/"):
        return base_url + "/"
    return base_url


def relpath_from_url(file_url, base_url):
    rel = file_url[len(base_url):]
    rel = rel.lstrip("/")
    return rel


def make_session(verify_tls=True):
    session = requests.Session()
    session.headers.update({
        "User-Agent": f"ClimateFinancePipeline/1.0 (mailto:{MAILTO})",
    })
    session.verify = verify_tls
    if not verify_tls:
        requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
    return session


def fetch_html(session, url, timeout, delay):
    time.sleep(delay)
    resp = session.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def list_links(html, page_url):
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if not href:
            continue
        if href.startswith("?") or href.startswith("#"):
            continue
        abs_url = urljoin(page_url, href)
        links.append(abs_url)
    return links


def is_under_base(url, base_url):
    return url.startswith(base_url)


def is_directory_url(url):
    return url.endswith("/")


def should_download_file(url, compiled_pattern):
    path = urlparse(url).path.lower()
    name = os.path.basename(path)
    if not name:
        return False
    return bool(compiled_pattern.search(name))


def remote_size(session, url, timeout, delay):
    time.sleep(delay)
    try:
        resp = session.head(url, timeout=timeout, allow_redirects=True)
        if resp.status_code >= 400:
            return None
        value = resp.headers.get("Content-Length")
        return int(value) if value and value.isdigit() else None
    except requests.RequestException:
        return None


def needs_download(local_path, remote_len):
    if not os.path.exists(local_path):
        return True
    if remote_len is None:
        return False
    local_len = os.path.getsize(local_path)
    return local_len != remote_len


def download_file(session, url, local_path, timeout, delay):
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    time.sleep(delay)
    with session.get(url, timeout=timeout, stream=True) as resp:
        resp.raise_for_status()
        with open(local_path, "wb") as handle:
            for chunk in resp.iter_content(chunk_size=1 << 15):
                if chunk:
                    handle.write(chunk)


def sync_repec(base_url, dest, file_pattern, delay, timeout, max_files, dry_run, verify_tls):
    base_url = normalize_base_url(base_url)
    compiled_pattern = re.compile(file_pattern, flags=re.IGNORECASE)
    session = make_session(verify_tls=verify_tls)

    to_visit = deque([base_url])
    seen_dirs = set()
    seen_files = set()

    scanned_dirs = 0
    considered_files = 0
    downloaded = 0
    skipped = 0

    while to_visit:
        current = to_visit.popleft()
        if current in seen_dirs:
            continue
        seen_dirs.add(current)

        try:
            html = fetch_html(session, current, timeout=timeout, delay=delay)
        except requests.RequestException as exc:
            print(f"[WARN] cannot list {current}: {exc}")
            continue

        scanned_dirs += 1
        links = list_links(html, current)

        for link in links:
            if not is_under_base(link, base_url):
                continue
            if link == current:
                continue

            if is_directory_url(link):
                if link not in seen_dirs:
                    to_visit.append(link)
                continue

            if link in seen_files:
                continue
            seen_files.add(link)

            if not should_download_file(link, compiled_pattern):
                continue

            considered_files += 1
            rel = relpath_from_url(link, base_url)
            local_path = os.path.join(dest, rel)
            rlen = remote_size(session, link, timeout=timeout, delay=delay)
            if needs_download(local_path, rlen):
                if dry_run:
                    print(f"[DRY] download {link} -> {local_path}")
                else:
                    try:
                        download_file(session, link, local_path, timeout=timeout, delay=delay)
                        print(f"[OK] {rel}")
                    except requests.RequestException as exc:
                        print(f"[WARN] download failed {link}: {exc}")
                        continue
                downloaded += 1
                if max_files and downloaded >= max_files:
                    print("Reached --max-files limit")
                    return {
                        "scanned_dirs": scanned_dirs,
                        "considered_files": considered_files,
                        "downloaded": downloaded,
                        "skipped": skipped,
                        "dest": dest,
                        "base_url": base_url,
                    }
            else:
                skipped += 1

        if scanned_dirs % 50 == 0:
            print(
                f"Progress: dirs={scanned_dirs} files={considered_files} "
                f"downloaded={downloaded} skipped={skipped}"
            )

    return {
        "scanned_dirs": scanned_dirs,
        "considered_files": considered_files,
        "downloaded": downloaded,
        "skipped": skipped,
        "dest": dest,
        "base_url": base_url,
    }


def main():
    args = parse_args()
    result = sync_repec(
        base_url=args.base_url,
        dest=args.dest,
        file_pattern=args.file_pattern,
        delay=args.delay,
        timeout=args.timeout,
        max_files=args.max_files,
        dry_run=args.dry_run,
        verify_tls=not args.insecure,
    )

    print("Done.")
    print(f"  Base URL: {result['base_url']}")
    print(f"  Destination: {result['dest']}")
    print(f"  Directories scanned: {result['scanned_dirs']}")
    print(f"  Eligible files seen: {result['considered_files']}")
    print(f"  Downloaded/updated: {result['downloaded']}")
    print(f"  Skipped (already current): {result['skipped']}")


if __name__ == "__main__":
    main()
