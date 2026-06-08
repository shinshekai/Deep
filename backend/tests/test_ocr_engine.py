from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _reset_engine():
    from app.services.ocr_engine import reset_ocr_engine

    reset_ocr_engine()
    yield
    reset_ocr_engine()


def _make_pytesseract_mock(conf="95", text="Hello"):
    mock = MagicMock()
    mock.image_to_data.return_value = {
        "text": [text, ""],
        "conf": [conf, "-1"],
        "left": [10, 0],
        "top": [20, 0],
        "width": [100, 0],
        "height": [30, 0],
    }
    return mock


def _make_easyocr_mock(text="Hello", conf=0.98):
    mock_reader = MagicMock()
    mock_reader.readtext.return_value = [([[0, 0], [100, 0], [100, 30], [0, 30]], text, conf)]
    mock_module = MagicMock()
    mock_module.Reader.return_value = mock_reader
    return mock_module


class TestOCREnginePytesseract:
    def test_recognize_returns_list_of_dicts(self):
        from app.services.ocr_engine import OCREngine

        mock_pt = _make_pytesseract_mock()
        with patch.dict(
            "sys.modules", {"pytesseract": mock_pt, "PIL": MagicMock(), "PIL.Image": MagicMock()}
        ):
            engine = OCREngine(backend="pytesseract")
            results = engine.recognize(Path("test.png"))
        assert len(results) == 1
        assert results[0]["text"] == "Hello"
        assert results[0]["confidence"] == 0.95
        assert results[0]["bbox"] == [10, 20, 110, 50]

    def test_recognize_skips_empty_text(self):
        from app.services.ocr_engine import OCREngine

        mock_pt = MagicMock()
        mock_pt.image_to_data.return_value = {
            "text": ["", "World", ""],
            "conf": ["-1", "80", "-1"],
            "left": [0, 5, 0],
            "top": [0, 15, 0],
            "width": [0, 50, 0],
            "height": [0, 20, 0],
        }
        with patch.dict(
            "sys.modules", {"pytesseract": mock_pt, "PIL": MagicMock(), "PIL.Image": MagicMock()}
        ):
            engine = OCREngine(backend="pytesseract")
            results = engine.recognize(Path("test.png"))
        assert len(results) == 1
        assert results[0]["text"] == "World"


class TestOCREngineEasyocr:
    def test_recognize_returns_list_of_dicts(self):
        from app.services.ocr_engine import OCREngine

        mock_ez = _make_easyocr_mock()
        with patch.dict("sys.modules", {"easyocr": mock_ez}):
            engine = OCREngine(backend="easyocr")
            results = engine.recognize(Path("test.png"))
        assert len(results) == 1
        assert results[0]["text"] == "Hello"
        assert results[0]["confidence"] == pytest.approx(0.98)
        assert len(results[0]["bbox"]) == 8


class TestOCRFallback:
    def test_pytesseract_falls_back_to_easyocr(self):
        from app.services.ocr_engine import OCREngine

        mock_pt = MagicMock()
        mock_pt.image_to_data.side_effect = RuntimeError("tesseract not found")
        mock_ez = _make_easyocr_mock(text="Fallback")

        with patch.dict(
            "sys.modules",
            {
                "pytesseract": mock_pt,
                "PIL": MagicMock(),
                "PIL.Image": MagicMock(),
                "easyocr": mock_ez,
            },
        ):
            engine = OCREngine(backend="pytesseract")
            results = engine.recognize(Path("test.png"))
        assert len(results) == 1
        assert results[0]["text"] == "Fallback"

    def test_easyocr_falls_back_to_pytesseract(self):
        from app.services.ocr_engine import OCREngine

        mock_ez = MagicMock()
        mock_ez.Reader.side_effect = RuntimeError("no gpu")
        mock_pt = _make_pytesseract_mock(text="PyFallback")

        with patch.dict(
            "sys.modules",
            {
                "easyocr": mock_ez,
                "pytesseract": mock_pt,
                "PIL": MagicMock(),
                "PIL.Image": MagicMock(),
            },
        ):
            engine = OCREngine(backend="easyocr")
            results = engine.recognize(Path("test.png"))
        assert len(results) == 1
        assert results[0]["text"] == "PyFallback"

    def test_both_backends_fail_returns_empty(self):
        from app.services.ocr_engine import OCREngine

        mock_pt = MagicMock()
        mock_pt.image_to_data.side_effect = RuntimeError("fail")
        mock_ez = MagicMock()
        mock_ez.Reader.side_effect = RuntimeError("fail")

        with patch.dict(
            "sys.modules",
            {
                "pytesseract": mock_pt,
                "PIL": MagicMock(),
                "PIL.Image": MagicMock(),
                "easyocr": mock_ez,
            },
        ):
            engine = OCREngine(backend="pytesseract")
            results = engine.recognize(Path("test.png"))
        assert results == []


class TestDefaultEngine:
    def test_get_ocr_engine_singleton(self):
        from app.services.ocr_engine import get_ocr_engine

        e1 = get_ocr_engine()
        e2 = get_ocr_engine()
        assert e1 is e2

    def test_reset_ocr_engine(self):
        from app.services.ocr_engine import get_ocr_engine

        e1 = get_ocr_engine()
        from app.services.ocr_engine import reset_ocr_engine

        reset_ocr_engine()
        e2 = get_ocr_engine()
        assert e1 is not e2


class TestBackendSelection:
    def test_backend_from_env(self):
        with patch.dict("os.environ", {"OCR_BACKEND": "easyocr"}):
            from app.services.ocr_engine import OCREngine

            engine = OCREngine()
            assert engine.backend == "easyocr"

    def test_unknown_backend_tries_fallback(self):
        from app.services.ocr_engine import OCREngine

        mock_pt = _make_pytesseract_mock(text="Fallback")
        with patch.dict(
            "sys.modules", {"pytesseract": mock_pt, "PIL": MagicMock(), "PIL.Image": MagicMock()}
        ):
            engine = OCREngine(backend="unknown")
            results = engine.recognize(Path("test.png"))
        assert len(results) == 1
        assert results[0]["text"] == "Fallback"
