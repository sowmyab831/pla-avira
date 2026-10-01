import requests
from bs4 import BeautifulSoup


def crawl_page(url):

    response = requests.get(url)

    soup = BeautifulSoup(response.text, "html.parser")

    title = soup.title.string if soup.title else "No Title"

    text = soup.get_text()

    return {
        "title": title,
        "content": text[:5000]
    }