"""
Step 1a: find local companies with the Google Places API (New) Text Search.

Usage:
    export GOOGLE_PLACES_API_KEY=...
    python ingest_places.py            # shows planned request count, then stops
    python ingest_places.py --confirm  # actually runs (this costs API credit)

Output: data/places.csv
"""
import argparse
import math
import os
import time

import pandas as pd
import requests

from config import (DATA_DIR, EXCLUDE_NAME_KEYWORDS, MAX_DISTANCE_KM,
                    PLACES_QUERIES, SEARCH_CENTERS, SEARCH_RADIUS_M)

URL = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = ",".join([
    "places.id", "places.displayName", "places.formattedAddress",
    "places.websiteUri", "places.nationalPhoneNumber", "places.location",
    "places.primaryType", "places.types", "places.businessStatus",
    "nextPageToken",
])
MAX_PAGES = 3  # Text Search returns at most 60 results (3 pages of 20)


def haversine_km(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 6371 * 2 * math.asin(math.sqrt(h))


def text_search(key, query, center):
    headers = {"X-Goog-Api-Key": key, "X-Goog-FieldMask": FIELD_MASK}
    body = {
        "textQuery": query,
        "pageSize": 20,
        "locationBias": {"circle": {
            "center": {"latitude": center[0], "longitude": center[1]},
            "radius": SEARCH_RADIUS_M,
        }},
    }
    results = []
    for _ in range(MAX_PAGES):
        r = requests.post(URL, json=body, headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()
        results += data.get("places", [])
        token = data.get("nextPageToken")
        if not token:
            break
        body["pageToken"] = token
        time.sleep(1)
    return results


def to_row(p, query):
    loc = p.get("location", {})
    return {
        "place_id": p["id"],
        "name": p.get("displayName", {}).get("text", ""),
        "address": p.get("formattedAddress", ""),
        "website": p.get("websiteUri", ""),
        "phone": p.get("nationalPhoneNumber", ""),
        "lat": loc.get("latitude"),
        "lng": loc.get("longitude"),
        "primary_type": p.get("primaryType", ""),
        "types": ", ".join(p.get("types", [])),
        "status": p.get("businessStatus", ""),
        "matched_query": query,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirm", action="store_true", help="actually call the API")
    args = ap.parse_args()

    n_calls = len(PLACES_QUERIES) * len(SEARCH_CENTERS)
    print(f"Plan: {len(PLACES_QUERIES)} queries x {len(SEARCH_CENTERS)} centers "
          f"= {n_calls} searches, up to {n_calls * MAX_PAGES} requests.")
    if not args.confirm:
        print("Check your Places API pricing/free quota, then rerun with --confirm.")
        return

    key = os.environ.get("GOOGLE_PLACES_API_KEY")
    if not key:
        raise SystemExit("Set GOOGLE_PLACES_API_KEY first.")

    rows = []
    for query in PLACES_QUERIES:
        for area, center in SEARCH_CENTERS.items():
            try:
                found = text_search(key, query, center)
            except requests.HTTPError as e:
                print(f"  error on '{query}' @ {area}: {e}")
                continue
            rows += [to_row(p, query) for p in found]
            print(f"{query:30s} @ {area:15s} {len(found):3d}")

    df = pd.DataFrame(rows)
    if df.empty:
        print("No results.")
        return

    # One row per place; remember every query that found it
    queries = df.groupby("place_id")["matched_query"].agg(
        lambda q: "; ".join(sorted(set(q))))
    df = df.drop_duplicates("place_id").drop(columns="matched_query")
    df = df.merge(queries, on="place_id")

    # Filters
    before = len(df)
    df = df[df["status"].isin(["OPERATIONAL", ""])]
    df = df[~df["name"].str.lower().apply(
        lambda n: any(k in n for k in EXCLUDE_NAME_KEYWORDS))]
    df["km_to_nearest_center"] = df.apply(
        lambda r: min(haversine_km((r.lat, r.lng), c) for c in SEARCH_CENTERS.values()),
        axis=1).round(1)
    df = df[df["km_to_nearest_center"] <= MAX_DISTANCE_KM]
    print(f"Kept {len(df)} of {before} unique places after filtering.")

    out = DATA_DIR / "places.csv"
    df.to_csv(out, index=False)
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
