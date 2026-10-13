import os
import shutil
import re
from app import app

# Simple static builder using Flask's test client. This avoids crawling and
# POST-only endpoints by explicitly requesting the public pages we want.
DEST = "docs"
URLS = ["/", "/getting-started", "/login", "/signup", "/sample"]
SITE_BASE_PATH = os.environ.get("SITE_BASE_PATH", "")


def _normalize_base_path(base_path: str) -> str:
    if not base_path:
        return ""
    cleaned = "/" + base_path.strip("/")
    return cleaned


def _rewrite_root_relative_links(html: str, base_path: str) -> str:
    if not base_path:
        return html
    pattern = re.compile(r'((?:href|src|action)=")/(?!/)')
    return pattern.sub(rf'\1{base_path}/', html)


def build():
    # clean
    if os.path.exists(DEST):
        shutil.rmtree(DEST)
    os.makedirs(DEST, exist_ok=True)

    # copy static assets
    if os.path.exists("static"):
        shutil.copytree("static", os.path.join(DEST, "static"))

    client = app.test_client()
    base_path = _normalize_base_path(SITE_BASE_PATH)
    for url in URLS:
        rv = client.get(url)
        if rv.status_code != 200:
            print(f"Skipping {url}: status {rv.status_code}")
            continue
        content = rv.get_data(as_text=True)
        content = _rewrite_root_relative_links(content, base_path)
        path = url.lstrip("/")
        outdir = os.path.join(DEST, path) if path else DEST
        os.makedirs(outdir, exist_ok=True)
        with open(os.path.join(outdir, "index.html"), "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Wrote {os.path.join(outdir, 'index.html')}")

        if path:
            alias_path = os.path.join(DEST, f"{path}.html")
            with open(alias_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Wrote {alias_path}")


if __name__ == "__main__":
    build()
