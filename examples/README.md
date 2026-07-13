# Examples

```bash
# 1) Find broken links & internal redirects (crawl up to 300 pages)
siteprobe crawl https://example.com --max-pages 300 --report-file crawl.txt

# 2) Validate the sitemap (auto-discovered) and check every URL's status + hreflang
siteprobe sitemap https://example.com --report-file sitemap.txt

# 3) Just list what's in the sitemap, no status checks
siteprobe sitemap https://example.com --no-check

# 4) Point at an explicit sitemap index
siteprobe sitemap https://example.com --sitemap https://example.com/sitemap_index.xml
```

Exit is always 0 on completion; findings are in the report. Negative status codes are
transport-level: `-1` timeout, `0` connection error, `-2` other, `999` too-many-redirects.
