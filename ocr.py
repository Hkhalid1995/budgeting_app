import re
import json
import streamlit as st


def _vision_client():
    """Build Vision client from Streamlit secrets."""
    from google.cloud import vision
    from google.oauth2 import service_account

    creds_dict = json.loads(st.secrets["GOOGLE_VISION_CREDENTIALS"])
    credentials = service_account.Credentials.from_service_account_info(creds_dict)
    return vision.ImageAnnotatorClient(credentials=credentials)


def extract_receipt_data(image_bytes: bytes) -> dict:
    """
    Send image to Google Vision OCR.
    Returns dict with: raw_text, amount, merchant, confidence
    Falls back gracefully if Vision is not configured.
    """
    # Check if Vision is configured
    try:
        has_vision = "GOOGLE_VISION_CREDENTIALS" in st.secrets
    except Exception:
        has_vision = False

    if not has_vision:
        return {
            "raw_text": "",
            "amount": None,
            "merchant": None,
            "confidence": 0,
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
    """
    Extract the most likely total amount from receipt text.
    Looks for patterns like: Total: 1,250, Rs 1250, PKR 1,250.00
    Prioritises lines containing 'total', 'grand', 'amount due'.
    """
    lines = text.lower().split("\n")

    # Priority: lines with total/grand/payable keywords
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

    # Fallback: largest number on receipt (likely the total)
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
    """Extract merchant name — usually first non-empty line of receipt."""
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if lines:
        # Skip lines that are just numbers or very short
        for line in lines[:5]:
            if len(line) > 3 and not re.match(r"^[\d\s\-\/]+$", line):
                return line[:50]
    return None
