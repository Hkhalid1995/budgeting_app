import re
import io


def extract_receipt_data(image_bytes: bytes) -> dict:
    """
    Extract receipt data using Tesseract OCR (free, no API needed).
    Returns dict with: raw_text, amount, merchant, error
    """
    try:
        import pytesseract
        from PIL import Image

        image = Image.open(io.BytesIO(image_bytes))

        # Convert to RGB if needed (handles HEIC, RGBA, etc.)
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")

        # Upscale small images for better OCR accuracy
        w, h = image.size
        if w < 1000:
            scale = 1000 / w
            image = image.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        raw_text = pytesseract.image_to_string(image, lang="eng")

        amount = _parse_amount(raw_text)
        merchant = _parse_merchant(raw_text)

        return {
            "raw_text": raw_text,
            "amount": amount,
            "merchant": merchant,
            "confidence": 1 if amount else 0.5,
            "error": None,
        }

    except ImportError:
        return {
            "raw_text": "", "amount": None, "merchant": None, "confidence": 0,
            "error": "pytesseract not installed. Add to requirements.txt.",
        }
    except Exception as e:
        return {
            "raw_text": "", "amount": None, "merchant": None, "confidence": 0,
            "error": str(e),
        }


def _parse_amount(text: str) -> float | None:
    lines = text.lower().split("\n")
    priority_keywords = ["total", "grand total", "amount due", "payable",
                         "net amount", "bill amount", "subtotal"]
    amount_re = re.compile(r"[\d,]+(?:\.\d{1,2})?")

    # First pass — priority lines
    for keyword in priority_keywords:
        for line in lines:
            if keyword in line:
                nums = amount_re.findall(line.replace(" ", ""))
                for n in reversed(nums):
                    val = _clean_num(n)
                    if val and val > 0:
                        return val

    # Second pass — largest number on receipt
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
        if len(line) > 3 and not re.match(r"^[\d\s\-\/\.\:]+$", line):
            return line[:50]
    return None
