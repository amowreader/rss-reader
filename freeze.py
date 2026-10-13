import os
import shutil
from app import app

# Simple static builder using Flask's test client. This avoids crawling and
# POST-only endpoints by explicitly requesting the public pages we want.
DEST = "docs"
URLS = ["/", "/getting-started", "/login", "/signup", "/sample"]


def build():
    # clean
    if os.path.exists(DEST):
        shutil.rmtree(DEST)
    os.makedirs(DEST, exist_ok=True)

    # copy static assets
    if os.path.exists("static"):
        shutil.copytree("static", os.path.join(DEST, "static"))

    client = app.test_client()
    for url in URLS:
        rv = client.get(url)
        if rv.status_code != 200:
            print(f"Skipping {url}: status {rv.status_code}")
            continue
        content = rv.get_data()
        path = url.lstrip("/")
        outdir = os.path.join(DEST, path) if path else DEST
        os.makedirs(outdir, exist_ok=True)
        with open(os.path.join(outdir, "index.html"), "wb") as f:
            f.write(content)
        print(f"Wrote {os.path.join(outdir, 'index.html')}")


if __name__ == "__main__":
    build()
