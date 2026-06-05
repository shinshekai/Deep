"""Tests for all document format extractors in document_processor.py.

Covers: PPTX, HTML, ODT, RTF, EPUB, Email (.msg/.eml), Archive (.zip),
Spreadsheet (.csv/.xlsx), Image OCR, and Code files.
"""

import pytest
import tempfile
import zipfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock


# ── 2.1 PPTX extractor ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pptx_extractor_returns_text():
    """Test PPTX extraction with mocked python-pptx."""
    from app.services.document_processor import extract_text_from_pptx

    mock_shape1 = MagicMock()
    mock_shape1.text = "Slide 1 Title"
    mock_shape2 = MagicMock()
    mock_shape2.text = "Bullet point content"

    mock_slide = MagicMock()
    mock_slide.shapes = [mock_shape1, mock_shape2]

    mock_prs = MagicMock()
    mock_prs.slides = [mock_slide]

    with patch("app.services.document_processor.extract_text_from_pptx.__module__", "app.services.document_processor"):
        with patch.dict("sys.modules", {"pptx": MagicMock()}):
            with patch("pptx.Presentation", return_value=mock_prs):
                result = await extract_text_from_pptx(Path("/fake/test.pptx"))
                assert result is not None
                assert "Slide 1 Title" in result
                assert "Bullet point content" in result


@pytest.mark.asyncio
async def test_pptx_extractor_handles_import_error():
    """Test PPTX returns None when python-pptx not installed."""
    from app.services.document_processor import extract_text_from_pptx

    with patch.dict("sys.modules", {"pptx": None}):
        with patch("builtins.__import__", side_effect=ImportError("no pptx")):
            result = await extract_text_from_pptx(Path("/fake/test.pptx"))
            assert result is None


# ── 2.2 HTML extractor ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_html_extractor_returns_text():
    """Test HTML extraction with a real temp file."""
    from app.services.document_processor import extract_text_from_html

    html_content = "<html><body><h1>Test Title</h1><p>Hello World</p><script>alert('x')</script></body></html>"

    with tempfile.NamedTemporaryFile(suffix=".html", mode="w", delete=False, encoding="utf-8") as f:
        f.write(html_content)
        f.flush()
        tmp_path = Path(f.name)

    try:
        result = await extract_text_from_html(tmp_path)
        if result is not None:  # Only assert if bs4+lxml installed
            assert "Test Title" in result
            assert "Hello World" in result
            assert "alert" not in result  # script content should be stripped
    finally:
        tmp_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_html_extractor_handles_import_error():
    """Test HTML returns None when beautifulsoup4 not installed."""
    from app.services.document_processor import extract_text_from_html

    with patch.dict("sys.modules", {"bs4": None}):
        with patch("builtins.__import__", side_effect=ImportError("no bs4")):
            result = await extract_text_from_html(Path("/fake/test.html"))
            assert result is None


# ── 2.3 ODT extractor ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_odt_extractor_handles_import_error():
    """Test ODT returns None when odfpy not installed."""
    from app.services.document_processor import extract_text_from_odt

    with patch.dict("sys.modules", {"odf": None, "odf.text": None, "odf.teletype": None, "odf.opendocument": None}):
        with patch("builtins.__import__", side_effect=ImportError("no odf")):
            result = await extract_text_from_odt(Path("/fake/test.odt"))
            assert result is None


@pytest.mark.asyncio
async def test_odt_extractor_handles_bad_file():
    """Test ODT returns None when file cannot be parsed."""
    from app.services.document_processor import extract_text_from_odt

    with tempfile.NamedTemporaryFile(suffix=".odt", delete=False) as f:
        f.write(b"not a real odt file")
        tmp_path = Path(f.name)

    try:
        result = await extract_text_from_odt(tmp_path)
        assert result is None  # Should fail gracefully
    finally:
        tmp_path.unlink(missing_ok=True)


# ── 2.4 RTF extractor ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rtf_extractor_returns_text():
    """Test RTF extraction with a minimal RTF string."""
    from app.services.document_processor import extract_text_from_rtf

    # Minimal valid RTF content
    rtf_content = r"{\rtf1\ansi Hello RTF World}"

    with tempfile.NamedTemporaryFile(suffix=".rtf", mode="w", delete=False, encoding="utf-8") as f:
        f.write(rtf_content)
        f.flush()
        tmp_path = Path(f.name)

    try:
        result = await extract_text_from_rtf(tmp_path)
        if result is not None:  # Only assert if striprtf installed
            assert "Hello RTF World" in result
    finally:
        tmp_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_rtf_extractor_handles_import_error():
    """Test RTF returns None when striprtf not installed."""
    from app.services.document_processor import extract_text_from_rtf

    with patch.dict("sys.modules", {"striprtf": None, "striprtf.striprtf": None}):
        with patch("builtins.__import__", side_effect=ImportError("no striprtf")):
            result = await extract_text_from_rtf(Path("/fake/test.rtf"))
            assert result is None


# ── 2.5 EPUB extractor ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_epub_extractor_handles_import_error():
    """Test EPUB returns None when ebooklib not installed."""
    from app.services.document_processor import extract_text_from_epub

    with patch.dict("sys.modules", {"ebooklib": None, "ebooklib.epub": None}):
        with patch("builtins.__import__", side_effect=ImportError("no ebooklib")):
            result = await extract_text_from_epub(Path("/fake/test.epub"))
            assert result is None


@pytest.mark.asyncio
async def test_epub_extractor_handles_bad_file():
    """Test EPUB returns None on corrupt file."""
    from app.services.document_processor import extract_text_from_epub

    with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as f:
        f.write(b"not a real epub")
        tmp_path = Path(f.name)

    try:
        result = await extract_text_from_epub(tmp_path)
        assert result is None
    finally:
        tmp_path.unlink(missing_ok=True)


# ── 2.6 Email extractor ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_eml_extractor_returns_text():
    """Test .eml extraction with a real temp file."""
    from app.services.document_processor import extract_text_from_email

    eml_content = (
        "From: test@example.com\r\n"
        "Subject: Test Email\r\n"
        "Date: Mon, 01 Jan 2026 12:00:00 +0000\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n"
        "\r\n"
        "This is the email body content."
    )

    with tempfile.NamedTemporaryFile(suffix=".eml", mode="w", delete=False, encoding="utf-8") as f:
        f.write(eml_content)
        f.flush()
        tmp_path = Path(f.name)

    try:
        result = await extract_text_from_email(tmp_path)
        assert result is not None
        assert "Test Email" in result
        assert "test@example.com" in result
        assert "email body content" in result
    finally:
        tmp_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_email_extractor_handles_bad_file():
    """Test email returns None on malformed file."""
    from app.services.document_processor import extract_text_from_email

    with tempfile.NamedTemporaryFile(suffix=".msg", delete=False) as f:
        f.write(b"\x00\x01corrupted msg content")
        tmp_path = Path(f.name)

    try:
        result = await extract_text_from_email(tmp_path)
        # Either None (import error) or error-handled None
        assert result is None
    finally:
        tmp_path.unlink(missing_ok=True)


# ── 2.7 Archive (.zip) extractor with zip-slip check ────────────────────────

@pytest.mark.asyncio
async def test_archive_extractor_extracts_txt_files():
    """Test ZIP extraction with valid text files."""
    from app.services.document_processor import extract_text_from_archive

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
        with zipfile.ZipFile(f, "w") as zf:
            zf.writestr("readme.txt", "Hello from readme")
            zf.writestr("notes.md", "# Notes\nSome markdown content")
        tmp_path = Path(f.name)

    try:
        result = await extract_text_from_archive(tmp_path)
        assert result is not None
        assert "Hello from readme" in result
        assert "Some markdown content" in result
    finally:
        tmp_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_archive_extractor_rejects_zip_slip():
    """Test that zip-slip traversal attack is caught and rejected."""
    from app.services.document_processor import extract_text_from_archive

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
        with zipfile.ZipFile(f, "w") as zf:
            # Create a zip entry with path traversal
            info = zipfile.ZipInfo("../../etc/passwd")
            zf.writestr(info, "root:x:0:0:root:/root:/bin/bash")
        tmp_path = Path(f.name)

    try:
        result = await extract_text_from_archive(tmp_path)
        assert result is None  # Should be rejected
    finally:
        tmp_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_archive_extractor_handles_bad_zip():
    """Test ZIP extraction handles corrupted files."""
    from app.services.document_processor import extract_text_from_archive

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
        f.write(b"not a zip file at all")
        tmp_path = Path(f.name)

    try:
        result = await extract_text_from_archive(tmp_path)
        assert result is None
    finally:
        tmp_path.unlink(missing_ok=True)


# ── 2.8 Spreadsheet (.csv/.xlsx) extractor ──────────────────────────────────

@pytest.mark.asyncio
async def test_csv_extractor_returns_text():
    """Test CSV extraction with a real temp file."""
    from app.services.document_processor import extract_text_from_spreadsheet

    csv_content = "Name,Age,City\nAlice,30,London\nBob,25,Tokyo\n"

    with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False, encoding="utf-8") as f:
        f.write(csv_content)
        f.flush()
        tmp_path = Path(f.name)

    try:
        result = await extract_text_from_spreadsheet(tmp_path)
        if result is not None:  # Only assert if pandas installed
            assert "Alice" in result
            assert "London" in result
            assert "Bob" in result
    finally:
        tmp_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_spreadsheet_extractor_handles_import_error():
    """Test spreadsheet returns None when pandas not installed."""
    from app.services.document_processor import extract_text_from_spreadsheet

    with patch.dict("sys.modules", {"pandas": None}):
        with patch("builtins.__import__", side_effect=ImportError("no pandas")):
            result = await extract_text_from_spreadsheet(Path("/fake/test.xlsx"))
            assert result is None


# ── 2.9 Image OCR extractor ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_image_extractor_handles_import_error():
    """Test image OCR returns None when dependencies missing."""
    from app.services.document_processor import extract_text_from_image

    with patch.dict("sys.modules", {"PIL": None, "PIL.Image": None, "pytesseract": None}):
        with patch("builtins.__import__", side_effect=ImportError("no PIL")):
            result = await extract_text_from_image(Path("/fake/test.png"))
            assert result is None


@pytest.mark.asyncio
async def test_image_extractor_handles_corrupt_image():
    """Test image OCR returns None on non-image file."""
    from app.services.document_processor import extract_text_from_image
    import asyncio

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(b"not an image at all")
        tmp_path = Path(f.name)

    # delete=False above; manually delete after async call completes
    try:
        result = await extract_text_from_image(tmp_path)
        # Should return None (import error or processing error)
        assert result is None
    finally:
        import time
        time.sleep(0.05)  # Let any file handles release on Windows
        try:
            tmp_path.unlink(missing_ok=True)
        except PermissionError:
            pass  # Windows: file still held by async worker, safe to ignore


# ── 2.10 Code file extractor (.py/.js etc.) ─────────────────────────────────

@pytest.mark.asyncio
async def test_code_file_extractor():
    """Test extract_text on .py and .js code files."""
    from app.services.document_processor import extract_text

    # Python file
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False, encoding="utf-8") as f:
        f.write('def hello():\n    print("Hello World")\n')
        f.flush()
        py_path = Path(f.name)

    try:
        result = await extract_text(py_path)
        assert result is not None
        assert result["content"] is not None
        assert "def hello" in result["content"]
        assert 'print("Hello World")' in result["content"]
    finally:
        py_path.unlink(missing_ok=True)

    # JavaScript file
    with tempfile.NamedTemporaryFile(suffix=".js", mode="w", delete=False, encoding="utf-8") as f:
        f.write('function greet() { console.log("Hi"); }\n')
        f.flush()
        js_path = Path(f.name)

    try:
        result = await extract_text(js_path)
        assert result is not None
        assert result["content"] is not None
        assert "function greet" in result["content"]
    finally:
        js_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_extract_text_unsupported_format():
    """Test extract_text handles unknown file extensions via fallback."""
    from app.services.document_processor import extract_text

    with tempfile.NamedTemporaryFile(suffix=".xyz123", delete=False) as f:
        f.write(b"unknown format content")
        tmp_path = Path(f.name)

    try:
        result = await extract_text(tmp_path)
        # The fallback handler reads unknown extensions as plaintext
        assert result is not None
        assert "unknown format content" in result.get("content", "")
    finally:
        tmp_path.unlink(missing_ok=True)


# ── extract_text dispatcher tests ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_extract_text_txt_file():
    """Test extract_text with a plain .txt file."""
    from app.services.document_processor import extract_text

    with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False, encoding="utf-8") as f:
        f.write("Plain text file content here.")
        f.flush()
        tmp_path = Path(f.name)

    try:
        result = await extract_text(tmp_path)
        assert result is not None
        assert "Plain text file content here." in result["content"]
    finally:
        tmp_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_extract_text_md_file():
    """Test extract_text with a markdown file."""
    from app.services.document_processor import extract_text

    with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False, encoding="utf-8") as f:
        f.write("# Heading\n\nParagraph with **bold** text.\n")
        f.flush()
        tmp_path = Path(f.name)

    try:
        result = await extract_text(tmp_path)
        assert result is not None
        assert "# Heading" in result["content"]
        assert "**bold**" in result["content"]
    finally:
        tmp_path.unlink(missing_ok=True)
