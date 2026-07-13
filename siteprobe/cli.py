"""siteprobe CLI dispatch: `siteprobe crawl ...` | `siteprobe sitemap ...`."""
import sys

USAGE = """siteprobe — SEO site-health checks

usage:
  siteprobe crawl   <url> [--max-pages N] [--depth N] [--timeout S] [--report-file F]
  siteprobe sitemap <url> [--sitemap URL] [--timeout S] [--no-check] [--report-file F]

commands:
  crawl     crawl the site, report broken links (4xx/5xx/timeouts) and internal redirects
  sitemap   validate sitemap.xml: URL statuses, redirects, hreflang alternates

examples:
  siteprobe crawl https://example.com --max-pages 300
  siteprobe sitemap https://example.com
"""


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(USAGE)
        return 0
    if argv[0] in ("-V", "--version"):
        from . import __version__
        print(f"siteprobe {__version__}")
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd == "crawl":
        from . import crawl
        return crawl.run(rest)
    if cmd == "sitemap":
        from . import sitemap
        return sitemap.run(rest)
    print(f"unknown command: {cmd}\n", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
