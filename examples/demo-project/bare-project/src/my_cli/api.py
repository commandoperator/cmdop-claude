import httpx

def fetch(url: str) -> dict:
    return httpx.get(url).json()
