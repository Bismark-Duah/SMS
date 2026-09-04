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
    for header in ["cf-connecting-ip", "x-forwarded-for", "x-real-ip", "forwarded"]:
        val = headers.get(header) or headers.get(header.title()) or headers.get(header.upper()) or headers.get(header.lower())
        if val:
            ips = [ip.strip() for ip in val.split(",") if ip.strip()]
            if ips:
                return ips[0]

    return fallback_ip or "127.0.0.1"


def _clean_header_val(val: Optional[str]) -> str:
    """Remove quotes and extra whitespace from Client Hint values."""
    if not val:
        return ""
    return val.strip().strip('"').strip("'")


def parse_device_forensics(user_agent: Optional[str], headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """
    Parse a raw HTTP User-Agent string and Client Hint headers into structured forensic metadata.
    Returns: {
        "device_category": "Mobile" | "Tablet" | "Desktop" | "Bot",
        "device_brand": "TECNO Spark 10 Pro" | "Apple iPhone 14" | "Samsung Galaxy" etc.,
        "os_name": "Android 14" | "iOS 17.2" | "Windows 11" | "macOS Sonoma",
        "browser_name": "Chrome Mobile 122" | "Safari 17" | "Edge 121"
    }
    """
    headers = headers or {}
    h_lower = {str(k).lower(): str(v) for k, v in headers.items()}

    # Extract client hint & hardware telemetry
    hint_model = _clean_header_val(h_lower.get("sec-ch-ua-model") or h_lower.get("x-client-device-model"))
    if hint_model in ["K", "unknown", "none", "null"]: hint_model = ""
    hint_platform = _clean_header_val(h_lower.get("sec-ch-ua-platform") or h_lower.get("x-client-platform"))
    hint_mobile = _clean_header_val(h_lower.get("sec-ch-ua-mobile") or h_lower.get("x-client-mobile"))
    hint_touch = _clean_header_val(h_lower.get("x-client-touch"))
    hint_gpu = _clean_header_val(h_lower.get("x-client-gpu"))
    hint_screen = _clean_header_val(h_lower.get("x-client-screen"))

    ua = (user_agent or "").strip()
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

    # Override with Client Hints or Touch Indicators
    if hint_mobile == "?1" or hint_mobile.lower() == "true" or (hint_touch.lower() == "true" and "android" in hint_platform.lower()):
        if not is_tablet:
            is_mobile = True
    elif hint_platform.lower() == "android" and not is_tablet:
        is_mobile = True

    if is_tablet:
        category = "Tablet"
    elif is_mobile:
        category = "Mobile"
    else:
        category = "Desktop"

    # ── 3. Operating System Detection ────────────────────────────────────────
    os_name = "Unknown OS"
    if "iphone" in ua_lower or "ipad" in ua_lower or "ipod" in ua_lower or "ios" in hint_platform.lower():
        ios_ver = re.search(r"os\s*([0-9_\.]+)", ua_lower)
        if ios_ver:
            ver_str = ios_ver.group(1).replace("_", ".")
            os_name = f"iOS {ver_str}"
        else:
            os_name = "iOS"
    elif "android" in ua_lower or "android" in hint_platform.lower():
        and_ver = re.search(r"android\s*([0-9\.]+)", ua_lower)
        if and_ver:
            os_name = f"Android {and_ver.group(1)}"
        else:
            os_name = "Android"
    elif "windows nt 10.0" in ua_lower or "windows" in hint_platform.lower():
        os_name = "Windows 10 / 11"
    elif "windows nt 6.3" in ua_lower:
        os_name = "Windows 8.1"
    elif "windows nt 6.1" in ua_lower:
        os_name = "Windows 7"
    elif "macintosh" in ua_lower or "mac os x" in ua_lower or "macos" in hint_platform.lower():
        mac_ver = re.search(r"mac os x\s*([0-9_\.]+)", ua_lower)
        if mac_ver:
            ver_str = mac_ver.group(1).replace("_", ".")
            os_name = f"macOS {ver_str}"
        else:
            os_name = "macOS"
    elif "cros" in ua_lower:
        os_name = "Chrome OS"
    elif "linux" in ua_lower:
        # If touch or mobile hint indicates Android running in desktop site mode
        if category in ["Mobile", "Tablet"] or hint_platform.lower() == "android" or hint_touch.lower() == "true":
            os_name = "Android"
            category = "Mobile"
        else:
            os_name = "Linux"

    # ── 4. Mobile Phone & Tablet Brand / Model Detection ─────────────────────
    device_brand = "Unknown Device"

    # Check Hint Model first if provided and valid
    raw_search_target = f"{ua} {hint_model}".strip()
    target_lower = raw_search_target.lower()

    # Decoding popular Ghanaian & African Phone Model Codes and Names
    if "tecno" in target_lower or re.search(r"\b(ck[0-9]|lh[0-9]|kg[0-9]|kj[0-9]|bf[0-9]|bd[0-9]|ad[0-9]|ki[0-9]|lg[0-9]|ch[0-9])", target_lower):
        tecno_match = re.search(r"(tecno[ -]?[a-z0-9\+ ]+)", raw_search_target, re.IGNORECASE)
        model_code = re.search(r"\b(ck[0-9][a-z0-9]*|lh[0-9][a-z0-9]*|kg[0-9][a-z0-9]*|kj[0-9][a-z0-9]*|bf[0-9][a-z0-9]*|bd[0-9][a-z0-9]*|ki[0-9][a-z0-9]*)", raw_search_target, re.IGNORECASE)
        if tecno_match and len(tecno_match.group(1).strip()) > 5:
            device_brand = tecno_match.group(1).strip().upper()
        elif model_code:
            code_str = model_code.group(1).upper()
            device_brand = f"TECNO Mobile ({code_str})"
        else:
            device_brand = "TECNO Smartphone"
        category = "Mobile"
        if os_name == "Unknown OS" or os_name == "Linux": os_name = "Android"

    elif "infinix" in target_lower or re.search(r"\b(x68[0-9]+|x65[0-9]+|x67[0-9]+|x69[0-9]+)", target_lower):
        infinix_match = re.search(r"(infinix[ -]?[a-z0-9\+ ]+)", raw_search_target, re.IGNORECASE)
        model_code = re.search(r"\b(x68[0-9]+[a-z0-9]*|x65[0-9]+[a-z0-9]*|x67[0-9]+[a-z0-9]*)", raw_search_target, re.IGNORECASE)
        if infinix_match and len(infinix_match.group(1).strip()) > 7:
            device_brand = infinix_match.group(1).strip().upper()
        elif model_code:
            code_str = model_code.group(1).upper()
            device_brand = f"Infinix ({code_str})"
        else:
            device_brand = "Infinix Mobile"
        category = "Mobile"
        if os_name == "Unknown OS" or os_name == "Linux": os_name = "Android"

    elif "itel" in target_lower or re.search(r"\b(w65[0-9]+|s66[0-9]+|a66[0-9]+|p66[0-9]+|a58|a60|p40|s23)", target_lower):
        itel_match = re.search(r"(itel[ -]?[a-z0-9\+ ]+)", raw_search_target, re.IGNORECASE)
        model_code = re.search(r"\b(w65[0-9]+|s66[0-9]+|a66[0-9]+|p66[0-9]+|a58|a60|p40|s23)", raw_search_target, re.IGNORECASE)
        if itel_match and len(itel_match.group(1).strip()) > 4:
            device_brand = itel_match.group(1).strip().upper()
        elif model_code:
            code_str = model_code.group(1).upper()
            device_brand = f"Itel ({code_str})"
        else:
            device_brand = "Itel Mobile"
        category = "Mobile"
        if os_name == "Unknown OS" or os_name == "Linux": os_name = "Android"

    elif "samsung" in target_lower or "sm-" in target_lower:
        sm_match = re.search(r"(sm-[a-z0-9]+)", raw_search_target, re.IGNORECASE)
        device_brand = f"Samsung Galaxy ({sm_match.group(1).upper()})" if sm_match else "Samsung Galaxy"
        category = "Mobile"
        if os_name == "Unknown OS" or os_name == "Linux": os_name = "Android"

    elif "iphone" in target_lower:
        device_brand = "Apple iPhone"
        category = "Mobile"
        os_name = os_name if os_name != "Unknown OS" else "iOS"

    elif "ipad" in target_lower:
        device_brand = "Apple iPad"
        category = "Tablet"
        os_name = os_name if os_name != "Unknown OS" else "iPadOS"

    elif "redmi" in target_lower:
        redmi_match = re.search(r"(redmi[ -]?[a-z0-9\+ ]+)", raw_search_target, re.IGNORECASE)
        device_brand = redmi_match.group(1).strip().upper() if redmi_match else "Xiaomi Redmi"
        category = "Mobile"
        if os_name == "Unknown OS" or os_name == "Linux": os_name = "Android"

    elif "poco" in target_lower:
        device_brand = "Xiaomi POCO Phone"
        category = "Mobile"
        if os_name == "Unknown OS" or os_name == "Linux": os_name = "Android"

    elif "xiaomi" in target_lower or "mi " in target_lower:
        device_brand = "Xiaomi Smartphone"
        category = "Mobile"
        if os_name == "Unknown OS" or os_name == "Linux": os_name = "Android"

    elif "huawei" in target_lower or "honor" in target_lower or re.search(r"\b(hma-|vog-|pot-|ele-)", target_lower):
        device_brand = "Huawei Smartphone"
        category = "Mobile"
        if os_name == "Unknown OS" or os_name == "Linux": os_name = "Android"

    elif "oppo" in target_lower or re.search(r"\b(cph[0-9]+)", target_lower):
        cph_match = re.search(r"(cph[0-9]+)", raw_search_target, re.IGNORECASE)
        device_brand = f"Oppo ({cph_match.group(1).upper()})" if cph_match else "Oppo Smartphone"
        category = "Mobile"
        if os_name == "Unknown OS" or os_name == "Linux": os_name = "Android"

    elif "vivo" in target_lower or re.search(r"\b(v2[0-9]+)", target_lower):
        device_brand = "Vivo Smartphone"
        category = "Mobile"
        if os_name == "Unknown OS" or os_name == "Linux": os_name = "Android"

    elif "pixel" in target_lower:
        pixel_match = re.search(r"(pixel[ -]?[0-9a-z ]+)", raw_search_target, re.IGNORECASE)
        device_brand = f"Google {pixel_match.group(1).strip().title()}" if pixel_match else "Google Pixel"
        category = "Mobile"
        if os_name == "Unknown OS" or os_name == "Linux": os_name = "Android"

    elif "nokia" in target_lower:
        device_brand = "Nokia Mobile"
        category = "Mobile"

    elif hint_model:
        device_brand = hint_model.title()
        if category != "Tablet":
            category = "Mobile"

    elif hint_gpu and category in ["Mobile", "Tablet"]:
        gpu_l = hint_gpu.lower()
        if any(m in gpu_l for m in ["mali-g57", "mali-g52", "mali-g77", "mali-g76", "mali-g72", "mali-g68", "mali-t", "helio", "dimensity"]):
            device_brand = f"TECNO / Infinix Mobile ({hint_gpu.split('(')[0].strip()})"
        elif "adreno" in gpu_l:
            adreno_match = re.search(r"adreno[^\d]*(\d+)", hint_gpu, re.IGNORECASE)
            ad_num = adreno_match.group(1) if adreno_match else "Snapdragon"
            device_brand = f"Snapdragon / Galaxy (Adreno {ad_num})"
        elif "powervr" in gpu_l:
            device_brand = "Itel Smartphone (PowerVR)"
        elif "apple" in gpu_l:
            device_brand = "Apple iPhone"
        else:
            device_brand = f"Android Smartphone ({hint_gpu.split('(')[0].strip()})"

    elif category == "Mobile":
        device_brand = "Android Smartphone"

    elif category == "Tablet":
        device_brand = "Android Tablet"

    elif "windows" in target_lower or "windows" in os_name.lower():
        device_brand = "Windows PC / Laptop"

    elif "macintosh" in target_lower or "macos" in os_name.lower():
        device_brand = "Apple Mac"

    elif "linux" in target_lower and category == "Desktop":
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
