import os
import requests


def search_google_maps_places(merchant: str, max_results: int = 5):
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")

    if not api_key:
        raise ValueError("GOOGLE_MAPS_API_KEY is not set")

    merchant = merchant.strip()
    if not merchant:
        return []

    url = "https://places.googleapis.com/v1/places:searchText"

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.googleMapsUri"
    }

    payload = {
        "textQuery": merchant,
        "languageCode": "zh-CN",
        "regionCode": "SG"
    }

    response = requests.post(url, headers=headers, json=payload, timeout=10)
    response.raise_for_status()

    data = response.json()
    places = data.get("places", [])

    results = []

    for place in places[:max_results]:
        name = place.get("displayName", {}).get("text", "")
        address = place.get("formattedAddress", "")
        url = place.get("googleMapsUri", "")

        results.append({
            "name": name,
            "address": address,
            "url": url
        })

    return results