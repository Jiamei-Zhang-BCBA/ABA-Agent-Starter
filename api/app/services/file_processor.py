"""
FileProcessingPipeline — converts uploaded files to plain text for Claude.
Supports: .txt, .docx, .pdf (P1), .jpg/.png OCR and .mp3/.m4a whisper in P3.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Supported file extensions
TEXT_EXTENSIONS = {".txt", ".md"}
DOCX_EXTENSIONS = {".docx"}
PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}  # P3: OCR
AUDIO_EXTENSIONS = {".mp3", ".m4a", ".wav"}  # P3: Whisper


def parse_file(file_bytes: bytes, filename: str) -> str:
    """
    Parse a file into plain text content suitable for Claude.
    Returns the extracted text.
    """
    ext = Path(filename).suffix.lower()

    if ext in TEXT_EXTENSIONS:
        return _parse_text(file_bytes)
    elif ext in DOCX_EXTENSIONS:
        return _parse_docx(file_bytes)
    elif ext in PDF_EXTENSIONS:
        return _parse_pdf(file_bytes)
    elif ext in IMAGE_EXTENSIONS:
        return _parse_image_placeholder(filename)
    elif ext in AUDIO_EXTENSIONS:
        return _parse_audio_placeholder(filename)
    else:
        logger.warning("Unsupported file type: %s", ext)
        return f"[不支持的文件类型: {ext}]"


def _parse_text(file_bytes: bytes) -> str:
    """Parse plain text / markdown files."""
    for encoding in ("utf-8", "gbk", "gb2312", "latin-1"):
        try:
            return file_bytes.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return file_bytes.decode("utf-8", errors="replace")


def _parse_docx(file_bytes: bytes) -> str:
    """Extract text from .docx files."""
    try:
        from docx import Document

        doc = Document(io.BytesIO(file_bytes))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs)
    except Exception as e:
        logger.error("Failed to parse DOCX: %s", e)
        return f"[DOCX 解析失败: {e}]"


def _parse_pdf(file_bytes: bytes) -> str:
    """Extract text from .pdf files."""
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(file_bytes))
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
        return "\n\n---\n\n".join(pages)
    except Exception as e:
        logger.error("Failed to parse PDF: %s", e)
        return f"[PDF 解析失败: {e}]"


def _parse_image_placeholder(filename: str) -> str:
    """Placeholder for P3 OCR support."""
    return f"[图片文件: {filename} — OCR 功能将在 P3 阶段启用]"


def _parse_audio_placeholder(filename: str) -> str:
    """Placeholder for P3 Whisper transcription."""
    return f"[音频文件: {filename} — 语音转写功能将在 P3 阶段启用]"
