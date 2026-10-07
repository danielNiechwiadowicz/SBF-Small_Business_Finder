"""
Step 2: merge Places + GitHub results, score each company, write tracker.csv.

Usage:
    python main.py

Works with either input file alone. Rerunning keeps anything you typed into
the tracking columns (contact_name, date_contacted, status, notes, ...).
"""
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import pandas as pd

from config import (DATA_DIR, DATA_LANGUAGES, FULLSTACK_LANGUAGES, GENERIC_HOSTS,
                    MY_LANGUAGES, PLACES_QUERIES)

TRACKER = DATA_DIR / "tracker.csv"
MANUAL_COLS = ["contact_name", "contact_email", "date_contacted",
               "follow_up_date", "status", "notes"]
SUFFIXES = r"\b(llc|l\.l\.c|inc|incorporated|corp|corporation|co|company|ltd|lp|pllc)\b"



# Normalization helpers

def domain(url):
    if not isinstance(url, str) or not url.strip():
        return None
    url = url.strip()
    if "://" not in url:
        url = "http://" + url
    host = urlparse(url).netloc.lower().split(":")[0]
    host = host[4:] if host.startswith("www.") else host
    if not host or any(host == g or host.endswith("." + g) for g in GENERIC_HOSTS):
        return None
    return host


def norm_name(name):
    if not isinstance(name, str):
        return None
    n = re.sub(SUFFIXES, "", name.lower())
    n = re.sub(r"[^a-z0-9]+", " ", n).strip()
    return n or None


def load(name):
    path = DATA_DIR / name
    if path.exists():
        return pd.read_csv(path, dtype=str).fillna("")
    print(f"(no {name}, skipping)")
    return pd.DataFrame()


# Merge
def merge(places, github):
    records = []
    used_gh = set()

    gh_by_domain, gh_by_name = {}, {}
    for i, g in github.iterrows():
        if d := domain(g["website"]):
            gh_by_domain.setdefault(d, i)
        if n := norm_name(g["name"]):
            gh_by_name.setdefault(n, i)

    for _, p in places.iterrows():
        rec = {
            "name": p["name"], "website": p["website"], "address": p["address"],
            "phone": p["phone"], "places_queries": p["matched_query"],
            "km_away": p.get("km_to_nearest_center", ""),
            "github_url": "", "github_email": "", "languages": "", "last_push": "",
            "sources": "places",
        }
        d, n = domain(p["website"]), norm_name(p["name"])
        gi = gh_by_domain.get(d) if d else None
        if gi is None and n:
            gi = gh_by_name.get(n)
        if gi is not None and gi not in used_gh:
            g = github.loc[gi]
            used_gh.add(gi)
            rec.update(github_url=g["github_url"], github_email=g["email"],
                       languages=g["languages"], last_push=g["last_push"],
                       sources="places+github")
            rec["website"] = rec["website"] or g["website"]
        records.append(rec)

    for i, g in github.iterrows():
        if i in used_gh:
            continue
        records.append({
            "name": g["name"], "website": g["website"], "address": g["location"],
            "phone": "", "places_queries": "", "km_away": "",
            "github_url": g["github_url"], "github_email": g["email"],
            "languages": g["languages"], "last_push": g["last_push"],
            "sources": "github",
        })
    return pd.DataFrame(records)


# Scoring
def lane_and_score(r):
    score, reasons = 0, []
    langs = {l.strip() for l in r["languages"].split(",") if l.strip()}

    if r["sources"] == "places+github":
        score += 3; reasons.append("in both sources")
    if domain(r["website"]):
        score += 1; reasons.append("has website")

    if r["last_push"]:
        days = (datetime.now(timezone.utc)
                - datetime.fromisoformat(r["last_push"].replace("Z", "+00:00"))).days
        if days <= 365:
            score += 2; reasons.append("active on GitHub this year")
        elif days <= 730:
            score += 1; reasons.append("active on GitHub recently")

    overlap = langs & MY_LANGUAGES
    if overlap:
        score += 1; reasons.append("uses " + "/".join(sorted(overlap)))

    # Lane: languages first, then the Places query that found it
    fs, da = bool(langs & FULLSTACK_LANGUAGES), bool(langs & DATA_LANGUAGES)
    if fs and da:
        lane = "either"
    elif fs:
        lane = "full-stack"
    elif da:
        lane = "data"
    else:
        lanes = {PLACES_QUERIES.get(q.strip(), "")
                 for q in r["places_queries"].split(";")} - {""}
        lane = lanes.pop() if len(lanes) == 1 else ("either" if lanes else "unknown")

    return pd.Series({"score": score, "lane": lane, "why": "; ".join(reasons)})


def run():
    places, github = load("places.csv"), load("github_orgs.csv")
    if places.empty and github.empty:
        raise SystemExit("Run ingest_places.py and/or ingest_github.py first.")
    for df, cols in ((places, ["name", "website", "address", "phone",
                               "matched_query", "km_to_nearest_center"]),
                     (github, ["name", "website", "email", "location",
                               "languages", "last_push", "github_url"])):
        for c in cols:
            if c not in df.columns:
                df[c] = ""

    df = merge(places, github)
    df = pd.concat([df, df.apply(lane_and_score, axis=1)], axis=1)
    df["key"] = df.apply(
        lambda r: domain(r["website"]) or f"name:{norm_name(r['name'])}", axis=1)
    df = df.drop_duplicates("key")

    # Keep anything you've typed into the tracker on previous runs
    for c in MANUAL_COLS:
        df[c] = ""
    if TRACKER.exists():
        old = pd.read_csv(TRACKER, dtype=str).fillna("").set_index("key")
        for c in MANUAL_COLS:
            if c in old.columns:
                df[c] = df["key"].map(old[c]).fillna("")
        # Companies you were tracking that no longer appear in the data
        missing = old[~old.index.isin(df["key"])].reset_index()
        if not missing.empty:
            df = pd.concat([df, missing], ignore_index=True)

    order = ["score", "lane", "name", "why", "website", "address", "phone",
             "github_url", "github_email", "languages", "last_push",
             "sources", "places_queries", "km_away"] + MANUAL_COLS + ["key"]
    df = df[order].sort_values(["score", "name"], ascending=[False, True])
    df.to_csv(TRACKER, index=False)

    print(f"Saved {TRACKER} with {len(df)} companies")
    print(df["lane"].value_counts().to_string())
    print("\nTop 10:")
    print(df.head(10)[["score", "lane", "name", "why"]].to_string(index=False))