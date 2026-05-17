import asyncio
import hashlib
import logging
import os
import re
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus

import httpx
from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

log = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://trucks.riktom.com"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

EBAY_APP_ID          = os.environ.get("EBAY_APP_ID", "")
EBAY_VERIFICATION_TOKEN = os.environ.get("EBAY_VERIFICATION_TOKEN", "")
EBAY_ENDPOINT_URL    = "https://trucks.riktom.com/api/ebay/deletion-notification"
EBAY_FINDING_URL     = "https://svcs.ebay.com/services/search/FindingService/v1"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; TruckFinder/1.0; +https://trucks.riktom.com)"
}


async def fetch_ebay(query: str) -> list:
    """Fetch live eBay Motors listings via the Finding API."""
    if not EBAY_APP_ID:
        return []
    params = {
        "OPERATION-NAME":       "findItemsAdvanced",
        "SERVICE-VERSION":      "1.0.0",
        "SECURITY-APPNAME":     EBAY_APP_ID,
        "RESPONSE-DATA-FORMAT": "JSON",
        "REST-PAYLOAD":         "",
        "keywords":             query,
        "categoryId":           "6001",          # eBay Motors > Cars & Trucks
        "paginationInput.entriesPerPage": "8",
        "sortOrder":            "StartTimeNewest",
        "itemFilter(0).name":   "ListingType",
        "itemFilter(0).value":  "FixedPrice",
        "itemFilter(1).name":   "ListingType",
        "itemFilter(1).value":  "Auction",
        "outputSelector":       "PictureURLSuperSize",
    }
    results = []
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(EBAY_FINDING_URL, params=params, headers=HEADERS)
            r.raise_for_status()
        data = r.json()
        search_result = (
            data.get("findItemsAdvancedResponse", [{}])[0]
               .get("searchResult", [{}])[0]
        )
        items = search_result.get("item", [])
        for item in items:
            title     = item.get("title", [""])[0]
            url       = item.get("viewItemURL", [""])[0]
            price_obj = item.get("sellingStatus", [{}])[0].get("currentPrice", [{}])[0]
            price_val = price_obj.get("__value__", "")
            price     = f"${float(price_val):,.0f}" if price_val else ""
            pics      = item.get("pictureURLSuperSize", []) or item.get("galleryURL", [])
            image     = pics[0] if pics else ""
            if title and url:
                results.append({
                    "source": "eBay Motors",
                    "title":  title,
                    "price":  price,
                    "url":    url,
                    "image":  image,
                })
    except Exception as exc:
        print(f"[truck-finder] eBay fetch error: {exc}")
    return results


async def fetch_craigslist(query: str, year: str) -> list:
    """Craigslist RSS — blocked from VPS IPs; kept as fallback."""
    url = (
        f"https://www.craigslist.org/search/cta"
        f"?format=rss&query={quote_plus(query)}"
        f"&min_auto_year={year}&max_auto_year={year}"
        f"&srchType=A"
    )
    results = []
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url, headers=HEADERS, follow_redirects=True)
            r.raise_for_status()
        root = ET.fromstring(r.text)
        ns = {"enc": "http://purl.org/rss/1.0/modules/enclosure/"}
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            link  = (item.findtext("link")  or "").strip()
            desc  = (item.findtext("description") or "")
            m     = re.search(r'\$[\d,]+(?:\.\d{2})?', title + desc)
            price = m.group(0) if m else ""
            enc   = item.find("enc:enclosure", ns)
            image = enc.get("resource") if enc is not None else ""
            if title and link:
                results.append({
                    "source": "Craigslist",
                    "title":  title,
                    "price":  price,
                    "url":    link,
                    "image":  image,
                })
            if len(results) >= 6:
                break
    except Exception:
        pass
    return results


@app.get("/api/search")
async def search(
    year:  str = Query(...),
    make:  str = Query(...),
    model: str = Query(...),
):
    query = f"{year} {make} {model}"
    ebay_results, cl_results = await asyncio.gather(
        fetch_ebay(query),
        fetch_craigslist(query, year),
    )
    return {
        "query":    query,
        "listings": ebay_results + cl_results,
    }


@app.get("/api/ebay/deletion-notification")
async def ebay_deletion_challenge(challenge_code: str = Query(...)):
    """
    eBay Marketplace Account Deletion verification endpoint.
    eBay sends a GET with challenge_code; we respond with the SHA-256 hash of
    (challengeCode + verificationToken + endpointURL) as JSON.
    """
    hash_val = hashlib.sha256(
        (challenge_code + EBAY_VERIFICATION_TOKEN + EBAY_ENDPOINT_URL).encode()
    ).hexdigest()
    return JSONResponse({"challengeResponse": hash_val})


@app.post("/api/ebay/deletion-notification")
async def ebay_deletion_notification(request: Request):
    """
    Receive eBay Marketplace Account Deletion notifications.
    We don't store any eBay user data, so we just acknowledge receipt.
    """
    try:
        body = await request.json()
        log.info("[ebay-deletion] notification received: %s", body)
    except Exception:
        pass
    return JSONResponse({"acknowledged": True})


@app.get("/api/health")
async def health():
    return {"ok": True, "ebay_configured": bool(EBAY_APP_ID)}
