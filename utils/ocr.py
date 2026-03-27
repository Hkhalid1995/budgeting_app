import re
import json
import streamlit as st


def _vision_client():
    from google.cloud import vision
    from google.oauth2 import service_account

    raw = st.secrets["GOOGLE_VISION_CREDENTIALS"]

    # Handle both string and dict (Streamlit sometimes parses TOML into dict)
    if isinstance(raw, str):
        creds_dict = json.loads(raw)
    else:
        creds_dict = dict(raw)

    # Fix escaped newlines in private key — common issue when pasting into Streamlit secrets
    if "private_key" in creds_dict:
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

    credentials = service_account.Credentials.from_service_account_info(creds_dict)
    return vision.ImageAnnotatorClient(credentials=credentials)


def extract_receipt_data(image_bytes: bytes) -> dict:
    try:
        has_vision = "GOOGLE_VISION_CREDENTIALS" in st.secrets
    except Exception:
        has_vision = False

    if not has_vision:
        return {
            "raw_text": "", "amount": None, "merchant": None, "confidence": 0,
            "error": "OCR not configured — add GOOGLE_VISION_CREDENTIALS to Streamlit secrets.",
        }

    try:
        from google.cloud import vision
        client = _vision_client()
        image = vision.Image(content=image_bytes)
        response = client.text_detection(image=image)

        if response.error.message:
            return {"raw_text": "", "amount": None, "merchant": None, "confidence": 0,
                    "error": response.error.message}

        raw_text = response.text_annotations[0].description if response.text_annotations else ""
        amount = _parse_amount(raw_text)
        merchant = _parse_merchant(raw_text)

        return {
            "raw_text": raw_text,
            "amount": amount,
            "merchant": merchant,
            "confidence": 1 if amount else 0.5,
            "error": None,
        }

    except Exception as e:
        return {"raw_text": "", "amount": None, "merchant": None, "confidence": 0,
                "error": str(e)}


def _parse_amount(text: str) -> float | None:
    lines = text.lower().split("\n")
    priority_patterns = ["total", "grand total", "amount due", "payable", "net amount", "bill amount"]
    amount_re = re.compile(r"[\d,]+(?:\.\d{1,2})?")

    for keyword in priority_patterns:
        for line in lines:
            if keyword in line:
                nums = amount_re.findall(line.replace(" ", ""))
                for n in reversed(nums):
                    val = _clean_num(n)
                    if val and val > 0:
                        return val

    all_amounts = []
    for line in lines:
        nums = amount_re.findall(line.replace(" ", ""))
        for n in nums:
            val = _clean_num(n)
            if val and val > 10:
                all_amounts.append(val)

    return max(all_amounts) if all_amounts else None


def _clean_num(s: str) -> float | None:
    try:
        return float(s.replace(",", ""))
    except Exception:
        return None


def _parse_merchant(text: str) -> str | None:
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for line in lines[:5]:
        if len(line) > 3 and not re.match(r"^[\d\s\-\/]+$", line):
            return line[:50]
    return None
