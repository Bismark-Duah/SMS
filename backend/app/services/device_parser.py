"""
device_parser.py — Pure-Python Offline Universal Device Forensics & Telemetry Parser
Extracts precise human-readable Phone Brand/Model (Samsung, TECNO, Infinix, Itel, Xiaomi, Oppo, Vivo, Apple),
OS, Browser, and IP from HTTP requests.
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
    return str(val).strip().strip('"').strip("'")


def _clean_gpu_string(gpu_raw: str) -> str:
    """
    Extract the clean GPU/SoC core from browser unmasked strings like:
    'ANGLE (ARM, Mali-G52 MC2, OpenGL ES 3.2)' -> 'ARM Mali-G52 MC2'
    'ANGLE (Qualcomm, Adreno (TM) 610, OpenGL ES 3.2)' -> 'Adreno 610'
    """
    if not gpu_raw:
        return ""
    gpu = gpu_raw.strip()

    # Match ARM Mali
    mali_match = re.search(r"(?:ARM[,\s]+)?(Mali-[A-Z0-9]+(?:\s+[A-Z0-9]+)?)", gpu, re.IGNORECASE)
    if mali_match:
        return f"ARM {mali_match.group(1).strip()}"

    # Match Qualcomm Adreno
    adreno_match = re.search(r"Adreno[^\d]*(\d+)", gpu, re.IGNORECASE)
    if adreno_match:
        return f"Qualcomm Adreno {adreno_match.group(1)}"

    # Match PowerVR
    pvr_match = re.search(r"(PowerVR[^\,\)]*)", gpu, re.IGNORECASE)
    if pvr_match:
        return pvr_match.group(1).strip()

    # Match Apple GPU
    if "apple" in gpu.lower():
        return "Apple GPU"

    # Generic clean
    cleaned = re.sub(r"^ANGLE\s*\([^\,]*,\s*", "", gpu, flags=re.IGNORECASE)
    cleaned = re.sub(r",\s*OpenGL.*$", "", cleaned, flags=re.IGNORECASE).rstrip(")")
    return cleaned.strip() or gpu


def _decode_samsung_model(code: str) -> Optional[str]:
    """Translate Samsung hardware model codes (e.g. SM-A145F -> Samsung Galaxy A14)."""
    c = code.upper().strip()

    # Galaxy A Series
    a_match = re.search(r"SM-A([0-9])([0-9])([0-9]?)", c)
    if a_match:
        gen = a_match.group(1)
        sub = a_match.group(2)
        model_num = f"A{gen}{sub}"
        # Suffix handling
        if c.endswith("E") or c.endswith("F") or c.endswith("G") or c.endswith("M") or c.endswith("N") or c.endswith("U") or c.endswith("P") or c.endswith("B"):
            return f"Samsung Galaxy {model_num} ({c})"
        return f"Samsung Galaxy {model_num}"

    # Galaxy S Series
    if re.search(r"SM-S928", c): return f"Samsung Galaxy S24 Ultra ({c})"
    if re.search(r"SM-S926", c): return f"Samsung Galaxy S24+ ({c})"
    if re.search(r"SM-S921", c): return f"Samsung Galaxy S24 ({c})"
    if re.search(r"SM-S918", c): return f"Samsung Galaxy S23 Ultra ({c})"
    if re.search(r"SM-S916", c): return f"Samsung Galaxy S23+ ({c})"
    if re.search(r"SM-S911", c): return f"Samsung Galaxy S23 ({c})"
    if re.search(r"SM-S908", c): return f"Samsung Galaxy S22 Ultra ({c})"
    if re.search(r"SM-S906", c): return f"Samsung Galaxy S22+ ({c})"
    if re.search(r"SM-S901", c): return f"Samsung Galaxy S22 ({c})"
    if re.search(r"SM-G998", c): return f"Samsung Galaxy S21 Ultra ({c})"
    if re.search(r"SM-G996", c): return f"Samsung Galaxy S21+ ({c})"
    if re.search(r"SM-G991", c): return f"Samsung Galaxy S21 ({c})"
    if re.search(r"SM-G98", c): return f"Samsung Galaxy S20 ({c})"
    if re.search(r"SM-G97", c): return f"Samsung Galaxy S10 ({c})"

    # Galaxy M Series
    m_match = re.search(r"SM-M([0-9])([0-9])", c)
    if m_match:
        return f"Samsung Galaxy M{m_match.group(1)}{m_match.group(2)} ({c})"

    # Galaxy Note Series
    if re.search(r"SM-N98", c): return f"Samsung Galaxy Note 20 ({c})"
    if re.search(r"SM-N97", c): return f"Samsung Galaxy Note 10 ({c})"
    if re.search(r"SM-N96", c): return f"Samsung Galaxy Note 9 ({c})"

    # Galaxy Z Flip & Fold
    if re.search(r"SM-F7", c): return f"Samsung Galaxy Z Flip ({c})"
    if re.search(r"SM-F9", c): return f"Samsung Galaxy Z Fold ({c})"

    # Galaxy Tab
    if re.search(r"SM-T[0-9]", c): return f"Samsung Galaxy Tab ({c})"

    if c.startswith("SM-"):
        return f"Samsung Galaxy ({c})"

    return None


def _decode_tecno_model(code: str) -> Optional[str]:
    """Translate TECNO hardware model codes (e.g. CK7n -> TECNO Camon 20 Pro)."""
    c = code.upper().strip()

    # Camon Series
    if re.search(r"^CL[6-9]", c): return f"TECNO Camon 30 ({c})"
    if re.search(r"^CK[6-9]", c): return f"TECNO Camon 20 Pro ({c})"
    if re.search(r"^CK6", c): return f"TECNO Camon 20 ({c})"
    if re.search(r"^CI[6-8]", c): return f"TECNO Camon 19 ({c})"
    if re.search(r"^CH[6-9]", c): return f"TECNO Camon 18 ({c})"
    if re.search(r"^CG[6-8]", c): return f"TECNO Camon 17 ({c})"
    if re.search(r"^CD[6-8]", c): return f"TECNO Camon 16 ({c})"

    # Spark Series
    if re.search(r"^KJ[6-8]", c): return f"TECNO Spark 20 Pro ({c})"
    if re.search(r"^KJ5", c): return f"TECNO Spark 20 ({c})"
    if re.search(r"^LH7", c): return f"TECNO Spark 10 Pro ({c})"
    if re.search(r"^KI[5-8]", c): return f"TECNO Spark 10 ({c})"
    if re.search(r"^KG[5-8]", c): return f"TECNO Spark 8 / 8C ({c})"
    if re.search(r"^KF[6-8]", c): return f"TECNO Spark 7 ({c})"
    if re.search(r"^KE[5-7]", c): return f"TECNO Spark 6 ({c})"
    if re.search(r"^KD[6-7]", c): return f"TECNO Spark 5 ({c})"

    # Pop Series
    if re.search(r"^BG[6-8]", c): return f"TECNO Pop 8 ({c})"
    if re.search(r"^BF[6-8]", c): return f"TECNO Pop 7 ({c})"
    if re.search(r"^BE[6-8]", c): return f"TECNO Pop 6 ({c})"
    if re.search(r"^BD[1-5]", c): return f"TECNO Pop 5 ({c})"

    # Pova Series
    if re.search(r"^LH[8-9]", c): return f"TECNO Pova 5 ({c})"
    if re.search(r"^LG[6-8]", c): return f"TECNO Pova 4 ({c})"
    if re.search(r"^LF[6-8]", c): return f"TECNO Pova 3 ({c})"
    if re.search(r"^LE[6-8]", c): return f"TECNO Pova 2 ({c})"

    # Phantom Series
    if re.search(r"^AD[8-9]", c): return f"TECNO Phantom X ({c})"
    if re.search(r"^AC[8-9]", c): return f"TECNO Phantom V ({c})"

    if "TECNO" in c:
        return c

    return None


def _decode_infinix_model(code: str) -> Optional[str]:
    """Translate Infinix hardware model codes (e.g. X6812 -> Infinix Hot 11s)."""
    c = code.upper().strip()

    if re.search(r"^X6831", c): return f"Infinix Note 30 ({c})"
    if re.search(r"^X6832", c): return f"Infinix Hot 30 ({c})"
    if re.search(r"^X6812", c): return f"Infinix Hot 11s ({c})"
    if re.search(r"^X6816", c): return f"Infinix Hot 12 ({c})"
    if re.search(r"^X6817", c): return f"Infinix Hot 12i ({c})"
    if re.search(r"^X6823", c): return f"Infinix Hot 20 ({c})"
    if re.search(r"^X6836", c): return f"Infinix Hot 40 ({c})"
    if re.search(r"^X67[1-9]", c): return f"Infinix Note Series ({c})"
    if re.search(r"^X65[1-7]", c): return f"Infinix Smart Series ({c})"
    if re.search(r"^X688", c): return f"Infinix Hot 10 Play ({c})"
    if re.search(r"^X69[0-9]", c): return f"Infinix Note 10 ({c})"

    if c.startswith("X6"):
        return f"Infinix Mobile ({c})"

    return None


def _decode_itel_model(code: str) -> Optional[str]:
    """Translate Itel hardware model codes (e.g. W6501 -> Itel Vision 1)."""
    c = code.upper().strip()

    if re.search(r"^W6501", c): return f"Itel Vision 1 ({c})"
    if re.search(r"^W6502", c): return f"Itel Vision 1 Pro ({c})"
    if re.search(r"^S661", c): return f"Itel Vision 2 ({c})"
    if re.search(r"^S662", c): return f"Itel Vision 3 ({c})"
    if re.search(r"^S665", c): return f"Itel S23 ({c})"
    if re.search(r"^S666", c): return f"Itel S23+ ({c})"
    if re.search(r"^S667", c): return f"Itel S24 ({c})"
    if re.search(r"^A661", c): return f"Itel A58 ({c})"
    if re.search(r"^A662", c): return f"Itel A60 ({c})"
    if re.search(r"^A663", c): return f"Itel A60s ({c})"
    if re.search(r"^A665", c): return f"Itel A70 ({c})"
    if re.search(r"^P661", c): return f"Itel P38 ({c})"
    if re.search(r"^P662", c): return f"Itel P40 ({c})"
    if re.search(r"^P663", c): return f"Itel P55 ({c})"

    if c.startswith("W6") or c.startswith("S6") or c.startswith("A6") or c.startswith("P6"):
        return f"Itel Mobile ({c})"

    return None


def _decode_xiaomi_model(code: str) -> Optional[str]:
    """Translate Xiaomi / Redmi model codes."""
    c = code.upper().strip()

    if re.search(r"^231[0-9]", c): return f"Xiaomi Redmi Note 13 ({c})"
    if re.search(r"^230[0-9]", c): return f"Xiaomi Redmi Note 12 ({c})"
    if re.search(r"^220[0-9]", c): return f"Xiaomi Redmi Note 11 ({c})"
    if re.search(r"^210[0-9]", c): return f"Xiaomi Redmi Note 10 ({c})"
    if re.search(r"^220111", c): return f"Xiaomi Redmi Note 11 ({c})"
    if re.search(r"^220733", c): return f"Xiaomi Redmi A1 ({c})"
    if re.search(r"^23076", c): return f"Xiaomi Redmi 12 ({c})"
    if re.search(r"^23124", c): return f"Xiaomi Redmi 13C ({c})"
    if re.search(r"^22120", c): return f"Xiaomi Redmi 12C ({c})"
    if re.search(r"^220333", c): return f"Xiaomi Redmi 10C ({c})"

    if "REDMI" in c: return c
    if "POCO" in c: return c
    if "XIAOMI" in c: return c

    return None


def parse_device_forensics(user_agent: Optional[str], headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """
    Parse a raw HTTP User-Agent string, Client Hints, and WebGL GPU telemetry into structured forensic metadata.
    Returns: {
        "device_category": "Mobile" | "Tablet" | "Desktop" | "Bot",
        "device_brand": "Samsung Galaxy A14 (SM-A145F)" | "TECNO Camon 20 Pro" | "Apple iPhone 14",
        "os_name": "Android 14" | "iOS 17.2" | "Windows 11" | "macOS Sonoma",
        "browser_name": "Chrome Mobile 122" | "Safari 17" | "Edge 121"
    }
    """
    headers = headers or {}
    h_lower = {str(k).lower(): str(v) for k, v in headers.items()}

    # Extract client hints & hardware telemetry
    hint_model = _clean_header_val(h_lower.get("sec-ch-ua-model") or h_lower.get("x-client-device-model"))
    if hint_model in ["K", "unknown", "none", "null", "undefined"]: hint_model = ""
    hint_platform = _clean_header_val(h_lower.get("sec-ch-ua-platform") or h_lower.get("x-client-platform"))
    hint_mobile = _clean_header_val(h_lower.get("sec-ch-ua-mobile") or h_lower.get("x-client-mobile"))
    hint_touch = _clean_header_val(h_lower.get("x-client-touch"))
    hint_gpu_raw = _clean_header_val(h_lower.get("x-client-gpu"))
    hint_gpu = _clean_gpu_string(hint_gpu_raw)

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
    is_tablet = bool(re.search(r"ipad|tablet|tab|sm-t|gt-p|mediapad", ua_lower)) or "tablet" in hint_model.lower()
    is_mobile = bool(re.search(r"mobi|android|iphone|ipod|blackberry|opera mini|iemobile|windows phone", ua_lower)) and not is_tablet

    # Override with Client Hints or Touch Indicators
    if hint_mobile == "?1" or hint_mobile.lower() == "true" or (hint_touch.lower() == "true" and ("android" in hint_platform.lower() or "ios" in hint_platform.lower())):
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
        if category in ["Mobile", "Tablet"] or hint_platform.lower() == "android" or hint_touch.lower() == "true":
            os_name = "Android"
            category = "Mobile"
        else:
            os_name = "Linux"

    # ── 4. Mobile Phone & Tablet Brand / Model Detection ─────────────────────
    device_brand = None
    search_tokens = [hint_model, ua] if hint_model else [ua]

    for token in search_tokens:
        if not token: continue
        t = token.strip()

        # 4.1 Samsung Galaxy Decoder
        samsung_decoded = _decode_samsung_model(t)
        if not samsung_decoded:
            sm_in_token = re.search(r"\b(SM-[A-Z0-9]+)\b", t, re.IGNORECASE)
            if sm_in_token:
                samsung_decoded = _decode_samsung_model(sm_in_token.group(1))
        if samsung_decoded:
            device_brand = samsung_decoded
            category = "Mobile"
            if os_name in ["Unknown OS", "Linux"]: os_name = "Android"
            break

        # 4.2 TECNO Mobile Decoder
        tecno_decoded = _decode_tecno_model(t)
        if not tecno_decoded:
            tec_code = re.search(r"\b(CK[6-9][A-Za-z0-9]*|CL[6-9][A-Za-z0-9]*|CI[6-8][A-Za-z0-9]*|CH[6-9][A-Za-z0-9]*|CG[6-8][A-Za-z0-9]*|CD[6-8][A-Za-z0-9]*|KJ[5-8][A-Za-z0-9]*|LH[6-8][A-Za-z0-9]*|KI[5-8][A-Za-z0-9]*|KG[5-8][A-Za-z0-9]*|KF[6-8][A-Za-z0-9]*|KE[5-7][A-Za-z0-9]*|KD[6-7][A-Za-z0-9]*|BG[6-8][A-Za-z0-9]*|BF[6-8][A-Za-z0-9]*|BE[6-8][A-Za-z0-9]*|BD[1-5][A-Za-z0-9]*|AD[8-9][A-Za-z0-9]*)\b", t, re.IGNORECASE)
            if tec_code:
                tecno_decoded = _decode_tecno_model(tec_code.group(1))
        if tecno_decoded:
            device_brand = tecno_decoded
            category = "Mobile"
            if os_name in ["Unknown OS", "Linux"]: os_name = "Android"
            break

        # 4.3 Infinix Mobile Decoder
        infinix_decoded = _decode_infinix_model(t)
        if not infinix_decoded:
            inf_code = re.search(r"\b(X68[0-9]+[A-Za-z0-9]*|X67[0-9]+[A-Za-z0-9]*|X65[0-9]+[A-Za-z0-9]*|X69[0-9]+[A-Za-z0-9]*)\b", t, re.IGNORECASE)
            if inf_code:
                infinix_decoded = _decode_infinix_model(inf_code.group(1))
        if infinix_decoded:
            device_brand = infinix_decoded
            category = "Mobile"
            if os_name in ["Unknown OS", "Linux"]: os_name = "Android"
            break

        # 4.4 Itel Mobile Decoder
        itel_decoded = _decode_itel_model(t)
        if not itel_decoded:
            itel_code = re.search(r"\b(W65[0-9]+|S66[0-9]+|A66[0-9]+|P66[0-9]+|W50[0-9]+)\b", t, re.IGNORECASE)
            if itel_code:
                itel_decoded = _decode_itel_model(itel_code.group(1))
        if itel_decoded:
            device_brand = itel_decoded
            category = "Mobile"
            if os_name in ["Unknown OS", "Linux"]: os_name = "Android"
            break

        # 4.5 Xiaomi / Redmi / POCO Decoder
        xiaomi_decoded = _decode_xiaomi_model(t)
        if not xiaomi_decoded:
            mi_code = re.search(r"\b(231[0-9]+|230[0-9]+|220[0-9]+|210[0-9]+|220111[A-Za-z0-9]+|220733[A-Za-z0-9]+|23076[A-Za-z0-9]+|23124[A-Za-z0-9]+)\b", t, re.IGNORECASE)
            if mi_code:
                xiaomi_decoded = _decode_xiaomi_model(mi_code.group(1))
        if xiaomi_decoded:
            device_brand = xiaomi_decoded
            category = "Mobile"
            if os_name in ["Unknown OS", "Linux"]: os_name = "Android"
            break

        # 4.6 Oppo & Realme
        oppo_match = re.search(r"\b(CPH[0-9]{4})\b", t, re.IGNORECASE)
        if oppo_match:
            device_brand = f"Oppo Smartphone ({oppo_match.group(1).upper()})"
            category = "Mobile"
            break

        realme_match = re.search(r"\b(RMX[0-9]{4})\b", t, re.IGNORECASE)
        if realme_match:
            device_brand = f"Realme Smartphone ({realme_match.group(1).upper()})"
            category = "Mobile"
            break

        # 4.7 Vivo
        vivo_match = re.search(r"\b(V2[0-9]{3})\b", t, re.IGNORECASE)
        if vivo_match:
            device_brand = f"Vivo Smartphone ({vivo_match.group(1).upper()})"
            category = "Mobile"
            break

        # 4.8 Apple iPhone & iPad
        if "iphone" in t.lower():
            device_brand = "Apple iPhone"
            category = "Mobile"
            if os_name == "Unknown OS": os_name = "iOS"
            break
        if "ipad" in t.lower():
            device_brand = "Apple iPad"
            category = "Tablet"
            if os_name == "Unknown OS": os_name = "iPadOS"
            break

        # 4.9 Google Pixel
        pix_match = re.search(r"\b(Pixel[ -]?[0-9a-zA-Z ]+)\b", t, re.IGNORECASE)
        if pix_match:
            device_brand = f"Google {pix_match.group(1).strip().title()}"
            category = "Mobile"
            break

        # 4.10 Huawei / Honor
        huawei_match = re.search(r"\b(HMA-|VOG-|POT-|ELE-|JNY-|CDY-|ANG-)[A-Za-z0-9]+\b", t, re.IGNORECASE)
        if huawei_match or "huawei" in t.lower():
            device_brand = f"Huawei Smartphone ({huawei_match.group(0).upper()})" if huawei_match else "Huawei Smartphone"
            category = "Mobile"
            break

    # ── 4.11 Hardware / GPU Fallback if Model is Unresolved ──────────────────
    if not device_brand:
        if hint_model:
            device_brand = hint_model.title()
            if category != "Tablet": category = "Mobile"

        elif hint_gpu and category in ["Mobile", "Tablet"]:
            device_brand = f"Android Smartphone ({hint_gpu})"

        elif category == "Mobile":
            device_brand = "Android Smartphone"

        elif category == "Tablet":
            device_brand = "Android Tablet"

        elif "windows" in ua_lower or "windows" in os_name.lower():
            device_brand = "Windows PC / Laptop"

        elif "macintosh" in ua_lower or "macos" in os_name.lower():
            device_brand = "Apple Mac"

        elif "linux" in ua_lower and category == "Desktop":
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
