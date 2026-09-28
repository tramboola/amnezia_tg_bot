import ipaddress

import httpx


async def detect_public_ipv4():
    async with httpx.AsyncClient(timeout=5) as client:
        for url in ("https://api.ipify.org", "https://icanhazip.com"):
            try:
                response = await client.get(url)
                response.raise_for_status()
                address = ipaddress.IPv4Address(response.text.strip())
                if address.is_global:
                    return str(address)
            except (httpx.HTTPError, ValueError):
                continue
    return None
