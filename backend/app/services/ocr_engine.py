import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class OCREngine:
    def __init__(self, backend: str | None = None):
        self.backend = (backend or os.environ.get("OCR_BACKEND", "pytesseract")).lower()
        self._easyocr_reader = None

    def recognize(self, image_path: Path) -> list[dict]:
        try:
            if self.backend == "pytesseract":
                return self._pytesseract(image_path)
            if self.backend == "easyocr":
                return self._easyocr(image_path)
        except Exception as e:
            logger.warning(f"{self.backend} failed ({e}), trying fallback")

        fallback = "easyocr" if self.backend == "pytesseract" else "pytesseract"
        try:
            if fallback == "pytesseract":
                return self._pytesseract(image_path)
            return self._easyocr(image_path)
        except Exception as e:
            logger.error(f"All OCR backends failed: {e}")
            return []

    def _pytesseract(self, image_path: Path) -> list[dict]:
        import pytesseract
        from PIL import Image

        img = Image.open(image_path)
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        results = []
        for i in range(len(data["text"])):
            text = data["text"][i].strip()
            conf = float(data["conf"][i]) if data["conf"][i] != "-1" else 0.0
            if text and conf > 0:
                x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
                results.append(
                    {
                        "text": text,
                        "confidence": conf / 100.0,
                        "bbox": [x, y, x + w, y + h],
                    }
                )
        return results

    def _easyocr(self, image_path: Path) -> list[dict]:
        import easyocr

        if self._easyocr_reader is None:
            self._easyocr_reader = easyocr.Reader(["en"], gpu=False)
        raw = self._easyocr_reader.readtext(str(image_path))
        return [
            {
                "text": item[1],
                "confidence": float(item[2]),
                "bbox": [int(c) for pt in item[0] for c in pt],
            }
            for item in raw
        ]


_default_engine: OCREngine | None = None


def get_ocr_engine() -> OCREngine:
    global _default_engine
    if _default_engine is None:
        _default_engine = OCREngine()
    return _default_engine


def reset_ocr_engine() -> None:
    global _default_engine
    _default_engine = None
