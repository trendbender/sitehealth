"""sitehealth sitemap — sitemap.xml validator.

Discovers the sitemap (robots.txt / common paths) or takes it directly, walks
sitemap-index recursion, checks every URL's status, and flags hreflang alternates
whose href is missing from the sitemap.
"""
import sys
import argparse
import time
import xml.etree.ElementTree as ET
from urllib.parse import urljoin
import requests

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; sitehealth/0.1; +https://github.com/trendbender/sitehealth)"
}
SM = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
XH = "{http://www.w3.org/1999/xhtml}"
SESSION = requests.Session()
SESSION.headers.update(DEFAULT_HEADERS)


def discover_sitemap(base_url, timeout=10):
    try:
        resp = SESSION.get(urljoin(base_url, "/robots.txt"), timeout=timeout)
        if resp.ok:
            for line in resp.text.splitlines():
                if line.lower().startswith("sitemap:"):
                    sm = line.split(":", 1)[1].strip()
                    if sm:
                        return sm
    except Exception:
        pass
    for path in ("/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml"):
        url = urljoin(base_url, path)
        try:
            if SESSION.head(url, timeout=timeout).ok:
                return url
        except Exception:
            pass
    return None


def fetch_xml(url, timeout=10):
    try:
        resp = SESSION.get(url, timeout=timeout)
        if resp.ok:
            return resp.text
    except Exception:
        pass
    return None


def parse_sitemap(xml_text, source_url):
    urls, subs = [], []
    try:
        root = ET.fromstring(xml_text)
        if "sitemapindex" in root.tag.lower():
            for sm in root.findall(f".//{SM}sitemap"):
                loc = sm.findtext(f"{SM}loc", "").strip()
                if loc:
                    subs.append(loc)
        else:
            for el in root.findall(f".//{SM}url"):
                loc = el.findtext(f"{SM}loc", "").strip()
                if not loc:
                    continue
                alts = [{"hreflang": ln.get("hreflang", ""), "href": ln.get("href", "")}
                        for ln in el.findall(f"{XH}link")
                        if ln.get("rel") == "alternate" and ln.get("hreflang") and ln.get("href")]
                urls.append({"loc": loc, "lastmod": el.findtext(f"{SM}lastmod", "").strip(),
                             "hreflang": alts, "source": source_url})
    except ET.ParseError:
        pass
    return urls, subs


def collect_all_urls(sitemap_url, timeout=10, max_sitemaps=50):
    all_urls, visited, queue = [], set(), [sitemap_url]
    while queue and len(visited) < max_sitemaps:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)
        xml = fetch_xml(url, timeout)
        if not xml:
            continue
        urls, subs = parse_sitemap(xml, url)
        all_urls.extend(urls)
        queue.extend(s for s in subs if s not in visited)
    return all_urls, visited


def check_url(url, timeout):
    try:
        resp = SESSION.get(url, timeout=timeout, allow_redirects=True)
        return resp.status_code, resp.url
    except requests.exceptions.ConnectionError:
        return 0, url
    except requests.exceptions.Timeout:
        return -1, url
    except Exception:
        return -2, url


def build_report(sitemap_url, all_urls, results, sitemaps_checked, elapsed):
    L = ["sitehealth — sitemap check", f"Sitemap: {sitemap_url}",
         f"Sitemaps checked: {len(sitemaps_checked)}", f"URLs in sitemap: {len(all_urls)}",
         f"Time: {elapsed:.0f}s", ""]
    broken = [(u, st) for u, (st, _) in results.items() if st <= 0 or st >= 400]
    redirects = [(u, st, f) for u, (st, f) in results.items() if 300 <= st < 400]
    ok = sum(1 for _, (st, _) in results.items() if 200 <= st < 300)
    all_locs = {e["loc"] for e in all_urls}
    hreflang_issues = [{"page": e["loc"], "hreflang": a["hreflang"], "href": a["href"]}
                       for e in all_urls for a in e.get("hreflang", [])
                       if a["href"] not in all_locs and a["hreflang"] != "x-default"]
    L += [f"OK (2xx): {ok}", f"Broken (4xx/5xx/err): {len(broken)}",
          f"Redirects (3xx): {len(redirects)}", f"Hreflang issues: {len(hreflang_issues)}", ""]
    if broken:
        L.append(f"=== BROKEN URLS ({len(broken)}) ===")
        for u, st in sorted(broken, key=lambda x: x[1]):
            s = {0: "CONN_ERR", -1: "TIMEOUT", -2: "ERR"}.get(st, str(st))
            L.append(f"  [{s}] {u}")
        L.append("")
    if redirects:
        L.append(f"=== REDIRECTS ({len(redirects)}) ===")
        for u, st, f in redirects[:50]:
            L.append(f"  [{st}] {u}")
            L.append(f"       -> {f}")
        if len(redirects) > 50:
            L.append(f"  ... and {len(redirects) - 50} more")
        L.append("")
    if hreflang_issues:
        L.append(f"=== HREFLANG ISSUES ({len(hreflang_issues)}) ===")
        for it in hreflang_issues[:30]:
            L.append(f"  [{it['hreflang']}] {it['href']}  (href not in sitemap)")
            L.append(f"      on page: {it['page']}")
        if len(hreflang_issues) > 30:
            L.append(f"  ... and {len(hreflang_issues) - 30} more")
        L.append("")
    if not broken and not redirects and not hreflang_issues:
        L.append("All URLs in sitemap are OK. No issues found.")
    return "\n".join(L)


def run(argv=None):
    p = argparse.ArgumentParser(prog="sitehealth sitemap", description="Sitemap.xml validator")
    p.add_argument("url", help="Site base URL or direct sitemap URL")
    p.add_argument("--sitemap", help="Explicit sitemap URL (skips discovery)")
    p.add_argument("--timeout", type=int, default=10)
    p.add_argument("--report-file", help="Save full report to file")
    p.add_argument("--no-check", action="store_true", help="Only list URLs, don't check statuses")
    a = p.parse_args(argv)
    base = a.url if a.url.startswith("http") else "https://" + a.url
    sitemap_url = a.sitemap
    if not sitemap_url:
        print(f"Discovering sitemap for {base}...", file=sys.stderr)
        sitemap_url = discover_sitemap(base, a.timeout)
        if not sitemap_url:
            print("ERROR: could not find sitemap. Use --sitemap to specify.", file=sys.stderr)
            sys.exit(1)
        print(f"Found: {sitemap_url}", file=sys.stderr)
    all_urls, sitemaps_checked = collect_all_urls(sitemap_url, a.timeout)
    print(f"Found {len(all_urls)} URLs in {len(sitemaps_checked)} sitemap(s)", file=sys.stderr)
    if a.no_check:
        L = [f"sitehealth — sitemap listing ({len(all_urls)} URLs in {len(sitemaps_checked)} sitemap(s), statuses NOT checked)", ""]
        L += [e["loc"] for e in all_urls]
        report = "\n".join(L)
        if a.report_file:
            open(a.report_file, "w").write(report)
            print(f"Report saved to {a.report_file}", file=sys.stderr)
        print(report)
        return 0
    results, elapsed = {}, 0
    start = time.time()
    for i, e in enumerate(all_urls):
        u = e["loc"]
        if u not in results:
            results[u] = check_url(u, a.timeout)
            if (i + 1) % 50 == 0:
                print(f"  {i+1}/{len(all_urls)}", file=sys.stderr)
            time.sleep(0.05)
    elapsed = time.time() - start
    report = build_report(sitemap_url, all_urls, results, sitemaps_checked, elapsed)
    if a.report_file:
        open(a.report_file, "w").write(report)
        print(f"Report saved to {a.report_file}", file=sys.stderr)
    print(report)
