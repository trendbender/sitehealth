# sitehealth

A tiny, dependency-light **SEO site-health CLI**. Two jobs, no paid APIs:

- **`crawl`** — crawl the site and report **broken links** (4xx/5xx/timeouts) and **internal redirects**. Two-phase: it fully crawls up to `--max-pages` pages *and* HEAD-checks every remaining discovered link, so no link is left unchecked regardless of the cap.
- **`sitemap`** — validate **`sitemap.xml`**: discovers it (robots.txt / common paths), walks sitemap-index recursion, checks every URL's status, and flags **hreflang** alternates whose `href` is missing from the sitemap.

Runs locally. Output is a plain-text report (stdout or `--report-file`).

## Install
```bash
pip install sitehealth
```

## Usage
```bash
# broken links + redirects
sitehealth crawl https://example.com --max-pages 300

# sitemap health (auto-discovers the sitemap)
sitehealth sitemap https://example.com

# point at an explicit sitemap, save a report
sitehealth sitemap https://example.com --sitemap https://example.com/sitemap_index.xml --report-file out.txt
```

### `crawl` options
| flag | default | meaning |
|---|---|---|
| `--max-pages` | 500 | pages to *fully* crawl for links (all discovered links are still status-checked) |
| `--depth` | 10 | max crawl depth |
| `--timeout` | 10 | per-request timeout (s) |
| `--report-file` | — | also write the full report to a file |

### `sitemap` options
| flag | default | meaning |
|---|---|---|
| `--sitemap` | auto | explicit sitemap URL (skips discovery) |
| `--no-check` | off | only list URLs, don't fetch statuses |
| `--timeout` | 10 | per-request timeout (s) |
| `--report-file` | — | also write the full report to a file |

## Example output
```
sitehealth — link crawl / 404 check
Site: https://example.com
Pages fully crawled: 128
OK (2xx): 121
Broken (4xx/5xx/timeout): 3
Redirects (3xx): 4

=== BROKEN LINKS (3) ===
  [404] https://example.com/old-page
      found on: https://example.com/blog/
```

## Notes
- Status codes: negative/zero values are transport-level (`-1` timeout, `0` connection error, `-2` other, `999` too-many-redirects).
- Respect target sites: there is a small delay between requests; keep `--max-pages` sane on sites you don't own.

## License
MIT © 2026 KlientLab. Part of our open SEO toolkit — see **https://klientlab.ru/tools/**.
