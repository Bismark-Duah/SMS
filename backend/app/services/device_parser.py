"""
device_parser.py — Pure-Python Offline Device Forensics & Telemetry Parser
Extracts human-readable Device Brand/Model, OS, Browser, and IP from HTTP requests.
100% Offline • Zero External Dependencies • Sub-millisecond Execution
"""
import re
from typing import Dict, Any, Optional

def get_client_ip(headers: Dict[str, str], fallback_ip: Optional[str] = None) -> str:
    """
    Extract the real client IP address from proxy / reverse proxy headers.
    """
    # 1. Cloudflare / Render / Standard Reverse Proxies
    for header in ["cf-connecting-ip", "x-forwarded-for", "x-real-ip", "forwarded"]:
        val = headers.get(header) or headers.get(header.title()) or headers.get(header.upper())
        if val:
            # X-Forwarded-For can be a comma-separated list of IPs: "client, proxy1, proxy2"
            ips = [ip.strip() for ip in val.split(",") if ip.strip()]
            if ips:
                return ips[0]

    return fallback_ip or "127.0.0.1"


def parse_device_forensics(user_agent: Optional[str]) -> Dict[str, str]:
    """
    Parse a raw HTTP User-Agent string into structured forensic metadata.
    Returns: {
        "device_category": "Mobile" | "Tablet" | "Desktop" | "Bot",
        "device_brand": "TECNO Spark 10 Pro" | "Apple iPhone 14" | "Windows 11 PC" etc.,
        "os_name": "Android 14" | "iOS 17.2" | "Windows 11" | "macOS Sonoma",
        "browser_name": "Chrome Mobile 122" | "Safari 17" | "Edge 121"
    }
    """
    if not user_agent or not user_agent.strip():
        return {
            "device_category": "Desktop",
            "device_brand": "Unknown Client",
            "os_name": "Unknown OS",
            "browser_name": "Generic HTTP Client"
        }

    ua = user_agent.strip()
    ua_lower = ua.lower()

    # ── 1. Bot / Crawler Detection ───────────────────────────────────────────
    if any(bot in ua_lower for bot in ["bot", "crawler", "spider", "postman", "curl", "python-requests", "pytest", "insomnia"]):
        return {
            "device_category": "Bot",
            "device_brand": "Automated Tool / Script",
            "os_name": "Server Environment",
            "browser_name": "HTTP Client / CLI"
        }

    # ── 2. Device Category ───────────────────────────────────────────────────
    is_tablet = bool(re.search(r"ipad|tablet|tab|sm-t|gt-p|mediapad", ua_lower))
    is_mobile = bool(re.search(r"mobi|android|iphone|ipod|blackberry|opera mini|iemobile|windows phone", ua_lower)) and not is_tablet

    if is_tablet:
        category = "Tablet"
    elif is_mobile:
        category = "Mobile"
    else:
        category = "Desktop"

    # ── 3. Operating System Detection ────────────────────────────────────────
    os_name = "Unknown OS"
    if "iphone" in ua_lower or "ipad" in ua_lower or "ipod" in ua_lower:
        ios_ver = re.search(r"os\s*([0-9_\.]+)", ua_lower)
        if ios_ver:
            ver_str = ios_ver.group(1).replace("_", ".")
            os_name = f"iOS {ver_str}"
        else:
            os_name = "iOS"
    elif "android" in ua_lower:
        and_ver = re.search(r"android\s*([0-9\.]+)", ua_lower)
        if and_ver:
            os_name = f"Android {and_ver.group(1)}"
        else:
            os_name = "Android"
    elif "windows nt 10.0" in ua_lower:
        os_name = "Windows 10 / 11"
    elif "windows nt 6.3" in ua_lower:
        os_name = "Windows 8.1"
    elif "windows nt 6.1" in ua_lower:
        os_name = "Windows 7"
    elif "macintosh" in ua_lower or "mac os x" in ua_lower:
        mac_ver = re.search(r"mac os x\s*([0-9_\.]+)", ua_lower)
        if mac_ver:
            ver_str = mac_ver.group(1).replace("_", ".")
            os_name = f"macOS {ver_str}"
        else:
            os_name = "macOS"
    elif "cros" in ua_lower:
        os_name = "Chrome OS"
    elif "linux" in ua_lower:
        os_name = "Linux"
    elif "linux" in ua_lower:
        os_name = "Linux"

    # ── 4. Mobile Phone & Tablet Brand / Model Detection ─────────────────────
    device_brand = "Unknown Device"

    # Popular African Mobile Brands (TECNO, Infinix, Itel, Samsung, Apple, etc.)
    if "tecno" in ua_lower:
        tecno_match = re.search(r"(tecno[ -]?[a-z0-9\+]+)", ua, re.IGNORECASE)
        device_brand = tecno_match.group(1).upper() if tecno_match else "TECNO Mobile"
    elif "infinix" in ua_lower:
        infinix_match = re.search(r"(infinix[ -]?[a-z0-9\+]+)", ua, re.IGNORECASE)
        device_brand = infinix_match.group(1).upper() if infinix_match else "Infinix Mobile"
    elif "itel" in ua_lower:
        itel_match = re.search(r"(itel[ -]?[a-z0-9\+]+)", ua, re.IGNORECASE)
        device_brand = itel_match.group(1).upper() if itel_match else "Itel Mobile"
    elif "samsung" in ua_lower or "sm-" in ua_lower:
        sm_match = re.search(r"(sm-[a-z0-9]+)", ua, re.IGNORECASE)
        device_brand = f"Samsung Galaxy ({sm_match.group(1).upper()})" if sm_match else "Samsung Galaxy"
    elif "iphone" in ua_lower:
        device_brand = "Apple iPhone"
    elif "ipad" in ua_lower:
        device_brand = "Apple iPad"
    elif "redmi" in ua_lower:
        redmi_match = re.search(r"(redmi[ -]?[a-z0-9\+]+)", ua, re.IGNORECASE)
        device_brand = redmi_match.group(1).upper() if redmi_match else "Xiaomi Redmi"
    elif "xiaomi" in ua_lower or "mi " in ua_lower:
        device_brand = "Xiaomi Smartphone"
    elif "huawei" in ua_lower or "honor" in ua_lower:
        device_brand = "Huawei Smartphone"
    elif "oppo" in ua_lower:
        device_brand = "Oppo Smartphone"
    elif "vivo" in ua_lower:
        device_brand = "Vivo Smartphone"
    elif "pixel" in ua_lower:
        pixel_match = re.search(r"(pixel[ -]?[0-9a-z]+)", ua, re.IGNORECASE)
        device_brand = f"Google {pixel_match.group(1).title()}" if pixel_match else "Google Pixel"
    elif "nokia" in ua_lower:
        device_brand = "Nokia Mobile"
    elif category == "Mobile":
        device_brand = "Android Smartphone"
    elif category == "Tablet":
        device_brand = "Android Tablet"
    elif "windows" in ua_lower:
        device_brand = "Windows PC / Laptop"
    elif "macintosh" in ua_lower:
        device_brand = "Apple Mac"
    elif "linux" in ua_lower:
        device_brand = "Linux Workstation"
    else:
        device_brand = "Personal Computer"

    # ── 5. Browser Detection ─────────────────────────────────────────────────
    browser_name = "Generic Web Browser"

    if "edg/" in ua_lower or "edge/" in ua_lower:
        edge_ver = re.search(r"edg[e]?\/([0-9\.]+)", ua_lower)
        browser_name = f"Microsoft Edge {edge_ver.group(1).split('.')[0]}" if edge_ver else "Microsoft Edge"
    elif "opr/" in ua_lower or "opera" in ua_lower:
        browser_name = "Opera Browser"
    elif "samsungbrowser" in ua_lower:
        browser_name = "Samsung Internet"
    elif "chrome" in ua_lower and "safari" in ua_lower:
        chrome_ver = re.search(r"chrome\/([0-9\.]+)", ua_lower)
        ver = chrome_ver.group(1).split(".")[0] if chrome_ver else ""
        if category == "Mobile":
            browser_name = f"Chrome Mobile {ver}".strip()
        else:
            browser_name = f"Google Chrome {ver}".strip()
    elif "firefox" in ua_lower:
        ff_ver = re.search(r"firefox\/([0-9\.]+)", ua_lower)
        ver = ff_ver.group(1).split(".")[0] if ff_ver else ""
        browser_name = f"Mozilla Firefox {ver}".strip()
    elif "safari" in ua_lower and "version/" in ua_lower:
        saf_ver = re.search(r"version\/([0-9\.]+)", ua_lower)
        ver = saf_ver.group(1).split(".")[0] if saf_ver else ""
        browser_name = f"Apple Safari {ver}".strip()

    return {
        "device_category": category,
        "device_brand": device_brand,
        "os_name": os_name,
        "browser_name": browser_name
    }
