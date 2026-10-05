"""
Step 1b: find GitHub organizations located in the Houston area.

Usage:
    export GITHUB_TOKEN=ghp_...        # strongly recommended (5,000 req/hr vs 60)
    python ingest_github.py
    python ingest_github.py --limit 20 # quick test run

Output: data/github_orgs.csv
"""
import argparse
import os
import time
from collections import Counter

import pandas as pd
import requests

from config import (DATA_DIR, GITHUB_EXCLUDE_KEYWORDS, GITHUB_LOCATIONS,
                    GITHUB_MAX_ORGS_PER_LOCATION)

API = "https://api.github.com"


def make_session():
    s = requests.Session()
    s.headers["Accept"] = "application/vnd.github+json"
    s.headers["X-GitHub-Api-Version"] = "2022-11-28"
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        s.headers["Authorization"] = f"Bearer {token}"
    else:
        print("WARNING: no GITHUB_TOKEN set; limited to 60 requests/hour.")
    return s


def get(s, url, params=None):
    """GET with automatic waiting on rate limits."""
    while True:
        r = s.get(url, params=params, timeout=30)
        if r.status_code in (403, 429):
            if "Retry-After" in r.headers:                      # secondary limit
                wait = int(r.headers["Retry-After"]) + 1
            elif r.headers.get("X-RateLimit-Remaining") == "0":  # primary limit
                wait = int(r.headers["X-RateLimit-Reset"]) - time.time() + 2
            else:
                r.raise_for_status()
            print(f"  rate limited, waiting {wait:.0f}s ...")
            time.sleep(max(wait, 1))
            continue
        r.raise_for_status()
        return r


def search_orgs(s, location, max_orgs):
    """Return org logins whose profile location matches `location`."""
    logins, page = [], 1
    while len(logins) < max_orgs:
        r = get(s, f"{API}/search/users", params={
            "q": f'type:org location:"{location}"',
            "per_page": 100, "page": page,
        })
        items = r.json().get("items", [])
        if not items:
            break
        logins += [i["login"] for i in items]
        page += 1
        time.sleep(2)  # search API allows ~30 req/min when authenticated
    return logins[:max_orgs]


def org_details(s, login):
    org = get(s, f"{API}/orgs/{login}").json()
    repos = get(s, f"{API}/orgs/{login}/repos",
                params={"sort": "pushed", "per_page": 30, "type": "public"}).json()
    repos = [r for r in repos if not r.get("fork")]

    langs = Counter(r["language"] for r in repos if r.get("language"))
    pushes = [r["pushed_at"] for r in repos if r.get("pushed_at")]

    return {
        "github_login": login,
        "name": org.get("name") or login,
        "description": org.get("description") or "",
        "website": org.get("blog") or "",
        "email": org.get("email") or "",
        "location": org.get("location") or "",
        "public_repos": org.get("public_repos", 0),
        "languages": ", ".join(l for l, _ in langs.most_common(5)),
        "last_push": max(pushes) if pushes else "",
        "github_url": org.get("html_url", f"https://github.com/{login}"),
    }


def looks_like_non_employer(row):
    text = f"{row['name']} {row['github_login']} {row['description']}".lower()
    return any(k in text for k in GITHUB_EXCLUDE_KEYWORDS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=GITHUB_MAX_ORGS_PER_LOCATION,
                    help="max orgs per location")
    args = ap.parse_args()

    s = make_session()

    logins = []
    for loc in GITHUB_LOCATIONS:
        found = search_orgs(s, loc, args.limit)
        print(f"{loc:15s} {len(found):4d} orgs")
        logins += found
    logins = list(dict.fromkeys(logins))  # dedupe, keep order
    print(f"{len(logins)} unique orgs; fetching details ...")

    rows = []
    for i, login in enumerate(logins, 1):
        try:
            rows.append(org_details(s, login))
        except requests.HTTPError as e:
            print(f"  skip {login}: {e}")
        if i % 25 == 0:
            print(f"  {i}/{len(logins)}")

    df = pd.DataFrame(rows)
    if df.empty:
        print("No orgs found.")
        return
    before = len(df)
    df = df[df["public_repos"] > 0]
    df = df[~df.apply(looks_like_non_employer, axis=1)]
    print(f"Kept {len(df)} of {before} after filtering clubs/empty orgs.")

    out = DATA_DIR / "github_orgs.csv"
    df.to_csv(out, index=False)
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
