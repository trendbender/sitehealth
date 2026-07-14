"""sitehealth crawl — link crawler / 404 & redirect checker.

Two-phase: (1) fully crawl up to --max-pages pages and extract internal links;
(2) HEAD-check every discovered link that wasn't reached — so no link is left
unchecked regardless of the page cap.
"""
import sys
import argparse
import time
from collections import deque
from urllib.parse import urljoin, urlparse, urldefrag
import requests
from bs4 import BeautifulSoup

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; sitehealth/0.1; +https://github.com/trendbender/sitehealth)"
}


def normalize(url):
    url, _ = urldefrag(url)
    return url.rstrip("/")


def is_internal(url, base_netloc):
    try:
        return urlparse(url).netloc == base_netloc
    except Exception:
        return False


def fetch(url, session, timeout):
    try:
        resp = session.get(url, timeout=timeout, allow_redirects=True, headers=DEFAULT_HEADERS)
        return resp.status_code, resp.url, resp.text if resp.ok else ""
    except requests.exceptions.TooManyRedirects:
        return 999, url, ""
    except requests.exceptions.ConnectionError:
        return 0, url, ""
    except requests.exceptions.Timeout:
        return -1, url, ""
    except Exception:
        return -2, url, ""


def fetch_head(url, session, timeout):
    try:
        resp = session.head(url, timeout=timeout, allow_redirects=True, headers=DEFAULT_HEADERS)
        if resp.status_code == 405:  # some servers refuse HEAD
            resp = session.get(url, timeout=timeout, allow_redirects=True, headers=DEFAULT_HEADERS, stream=True)
            resp.close()
        return resp.status_code, resp.url
    except requests.exceptions.TooManyRedirects:
        return 999, url
    except requests.exceptions.ConnectionError:
        return 0, url
    except requests.exceptions.Timeout:
        return -1, url
    except Exception:
        return -2, url


def extract_links(html, base_url):
    links = set()
    try:
        soup = BeautifulSoup(html, "lxml")
        for tag in soup.find_all("a", href=True):
            href = tag["href"].strip()
            if href.startswith(("mailto:", "tel:", "javascript:", "#")):
                continue
            links.add(normalize(urljoin(base_url, href)))
    except Exception:
        pass
    return links


def crawl(start_url, max_pages, max_depth, timeout):
    parsed = urlparse(start_url)
    base_netloc = parsed.netloc
    session = requests.Session()
    session.max_redirects = 10

    visited = {}
    queue = deque([(normalize(start_url), 0, "—")])
    seen = {normalize(start_url)}
    broken, redirects, ok_count, crawl_count = [], [], 0, 0

    # Phase 1 — full crawl up to max_pages
    while queue and crawl_count < max_pages:
        url, depth, found_on = queue.popleft()
        status, final_url, html = fetch(url, session, timeout)
        final_url = normalize(final_url)
        crawl_count += 1
        visited[url] = {"status": status, "final_url": final_url, "depth": depth, "found_on": found_on, "phase": 1}
        if status in (0, -1, -2) or status >= 400:
            broken.append({"url": url, "status": status, "found_on": found_on})
        elif 300 <= status < 400 and is_internal(final_url, base_netloc):
            redirects.append({"url": url, "final": final_url, "found_on": found_on})
        elif status == 200:
            ok_count += 1
        if status == 200 and html and depth < max_depth:
            for link in extract_links(html, url):
                if link not in seen and is_internal(link, base_netloc):
                    seen.add(link)
                    queue.append((link, depth + 1, url))
        time.sleep(0.03)

    # Phase 2 — HEAD-check remaining discovered links
    p2_count = 0
    while queue:
        url, depth, found_on = queue.popleft()
        if url in visited:
            continue
        status, final_url = fetch_head(url, session, timeout)
        final_url = normalize(final_url)
        p2_count += 1
        visited[url] = {"status": status, "final_url": final_url, "depth": depth, "found_on": found_on, "phase": 2}
        if status in (0, -1, -2) or status >= 400:
            broken.append({"url": url, "status": status, "found_on": found_on})
        elif 300 <= status < 400 and is_internal(final_url, base_netloc):
            redirects.append({"url": url, "final": final_url, "found_on": found_on})
        elif status == 200:
            ok_count += 1
        time.sleep(0.02)

    return {"base": f"{parsed.scheme}://{base_netloc}", "pages_crawled": crawl_count,
            "links_checked": p2_count, "ok": ok_count, "broken": broken,
            "redirects": redirects, "visited": visited}


def build_report(result, start_url):
    L = ["sitehealth — link crawl / 404 check", f"Site: {start_url}",
         f"Pages fully crawled: {result['pages_crawled']}"]
    if result["links_checked"]:
        L.append(f"Extra links checked (HEAD): {result['links_checked']}")
    L += [f"OK (2xx): {result['ok']}", f"Broken (4xx/5xx/timeout): {len(result['broken'])}",
          f"Redirects (3xx): {len(result['redirects'])}", ""]
    if result["broken"]:
        L.append(f"=== BROKEN LINKS ({len(result['broken'])}) ===")
        for it in sorted(result["broken"], key=lambda x: x["status"]):
            s = {0: "CONN_ERR", -1: "TIMEOUT", -2: "ERR", 999: "TOO_MANY_REDIRECT"}.get(it["status"], str(it["status"]))
            L.append(f"  [{s}] {it['url']}")
            L.append(f"      found on: {it['found_on']}")
        L.append("")
    if result["redirects"]:
        L.append(f"=== REDIRECTS ({len(result['redirects'])}) ===")
        for it in result["redirects"][:50]:
            L.append(f"  {it['url']}")
            L.append(f"      -> {it['final']}")
        if len(result["redirects"]) > 50:
            L.append(f"  ... and {len(result['redirects']) - 50} more")
        L.append("")
    if not result["broken"] and not result["redirects"]:
        L.append("No broken links or redirects found.")
    return "\n".join(L)


def run(argv=None):
    p = argparse.ArgumentParser(prog="sitehealth crawl", description="Link crawler / 404 & redirect checker")
    p.add_argument("url", help="Start URL (e.g. https://example.com)")
    p.add_argument("--max-pages", type=int, default=500, help="Max pages to fully crawl (default 500); all discovered links are still status-checked")
    p.add_argument("--depth", type=int, default=10, help="Max crawl depth (default 10)")
    p.add_argument("--timeout", type=int, default=10, help="Request timeout seconds (default 10)")
    p.add_argument("--report-file", help="Save full report to this file")
    a = p.parse_args(argv)
    print(f"Crawling {a.url} (max-pages={a.max_pages}, depth={a.depth})...", file=sys.stderr)
    result = crawl(a.url, a.max_pages, a.depth, a.timeout)
    report = build_report(result, a.url)
    if a.report_file:
        open(a.report_file, "w").write(report)
        print(f"Full report saved to {a.report_file}", file=sys.stderr)
    print(report)
