import pytest
from pathlib import Path
from app.services.document_processor import extract_text, recursive_chunk

@pytest.mark.asyncio
async def test_extract_text_txt(tmp_path):
    txt_file = tmp_path / "test.txt"
    txt_file.write_text("Hello World", encoding="utf-8")
    
    res = await extract_text(txt_file)
    assert res["type"] == "txt"
    assert res["content"] == "Hello World"
    assert res["page_count"] == 1
    assert res["pages"][0]["text"] == "Hello World"

@pytest.mark.asyncio
async def test_extract_text_md(tmp_path):
    md_file = tmp_path / "test.md"
    md_file.write_text("# Markdown", encoding="utf-8")
    
    res = await extract_text(md_file)
    assert res["type"] == "md"
    assert res["content"] == "# Markdown"

@pytest.mark.asyncio
async def test_extract_text_unsupported(tmp_path):
    bad_file = tmp_path / "test.xyz"
    bad_file.write_bytes(b"\x89PNG\r\n\x1a\n")  # Binary data that is not valid utf-8
    
    res = await extract_text(bad_file)
    assert res is None

def test_recursive_chunk():
    text = " ".join([f"word{i}" for i in range(100)])
    chunks = recursive_chunk(text, chunk_size=30, overlap=10)
    
    assert len(chunks) > 0
    assert chunks[0]["token_count"] == 30
    assert chunks[0]["start_token"] == 0
    assert chunks[0]["end_token"] == 30
    
    # second chunk should start at 30 - 10 = 20
    assert chunks[1]["start_token"] == 20
    assert chunks[1]["end_token"] == 50
