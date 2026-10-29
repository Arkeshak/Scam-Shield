"""Simple link checks that run on your own computer (no AI needed).
The AI model gets these results as extra evidence."""
import re
from urllib.parse import urlparse

URL_RE = re.compile(r"(https?://[^\s]+|www\.[^\s]+)", re.IGNORECASE)

SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "goo.gl", "cutt.ly", "is.gd", "rb.gy", "shorturl.at"}
SUSPICIOUS_TLDS = {"xyz", "top", "click", "icu", "buzz", "rest", "gq", "tk", "ml", "cf", "ga", "work", "support"}
BRANDS = ["paypal", "amazon", "apple", "google", "microsoft", "netflix", "dhl", "fedex", "ups", "hsbc", "facebook", "whatsapp"]


def extract_urls(text: str) -> list[str]:
    urls = URL_RE.findall(text or "")
    return [u.rstrip(".,;:!?)\"'") for u in urls]


def _normalize(host: str) -> str:
    # catch tricks like paypa1 -> paypal, amaz0n -> amazon
    table = str.maketrans({"0": "o", "1": "l", "3": "e", "5": "s", "4": "a", "$": "s"})
    return host.translate(table)


def is_official_domain(host: str, brand: str) -> bool:
    """brand.com and *.brand.com, plus country forms like brand.co.uk, brand.com.au.
    The match must reach the END of the host, so paypal.com.evil.xyz and paypal-secure.co.uk are NOT official."""
    if host.rsplit(".", 1)[-1] in SUSPICIOUS_TLDS:
        return False
    pattern = rf"(?:[a-z0-9-]+\.)*{re.escape(brand)}\.(?:com|(?:co|com)\.[a-z]{{2}})"
    return re.fullmatch(pattern, host) is not None


def check_url(url: str) -> dict:
    flags = []
    full = url if url.lower().startswith("http") else "http://" + url
    parsed = urlparse(full)
    host = (parsed.hostname or "").lower()

    if not host:
        return {"url": url, "flags": ["could not read the link"]}

    if re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", host):
        flags.append("link uses a raw IP address")
    if "xn--" in host:
        flags.append("link uses look-alike (punycode) characters")
    if host in SHORTENERS:
        flags.append("shortened link hides the real address")
    tld = host.rsplit(".", 1)[-1]
    if tld in SUSPICIOUS_TLDS:
        flags.append(f"link ends in .{tld}, often used in scams")
    if host.count("-") >= 3:
        flags.append("link has many hyphens")
    if host.count(".") >= 4:
        flags.append("link has many sub-domains")
    if "@" in parsed.netloc:
        flags.append("link has an @ sign that hides the real site")
    if parsed.scheme == "http":
        flags.append("link is not secure (no https)")

    norm = _normalize(host)
    for brand in BRANDS:
        if brand in norm:
            official = is_official_domain(host, brand)
            if not official:
                flags.append(f"uses the name '{brand}' but is not the official {brand}.com")
            break

    return {"url": url, "flags": flags}


def check_all_links(text: str) -> list[dict]:
    return [check_url(u) for u in extract_urls(text)]
