import requests


def search_web(query):
    url = "https://api.duckduckgo.com/"

    params = {
        "q": query,
        "format": "json"
    }

    response = requests.get(url, params=params)

    data = response.json()

    results = []

    for topic in data.get("RelatedTopics", []):
        if "Text" in topic:
            results.append({
                "title": topic.get("Text"),
                "url": topic.get("FirstURL")
            })

    return results