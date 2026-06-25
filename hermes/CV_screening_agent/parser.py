"""Extract plain text from CV files (PDF, DOCX, DOC, images)."""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
SUPPORTED_EXTENSIONS = DOCUMENT_EXTENSIONS | IMAGE_EXTENSIONS

_IMAGE_MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
}


def extract_cv_text(data: bytes, filename: str) -> str:
    """Extract text from a CV file."""
    ext = Path(filename or "").suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{ext}'. Use PDF, DOC, DOCX, or an image (JPG, PNG, …)."
        )

    if ext == ".pdf":
        text = _extract_pdf(data)
    elif ext == ".docx":
        text = _extract_docx(data)
    elif ext == ".doc":
        text = _extract_doc(data)
    else:
        text = _extract_image(data, ext)

    cleaned = _clean_text(text)
    if len(cleaned) < 20:
        raise ValueError("Could not extract enough text from the file. Try a different format.")
    return cleaned


def _clean_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    parts: list[str] = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts)


def _extract_docx(data: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _extract_doc(data: bytes) -> str:
    """Legacy Word .doc via antiword if installed, else clear error."""
    antiword = shutil.which("antiword")
    if not antiword:
        raise ValueError(
            "Legacy .doc files need the 'antiword' tool installed, "
            "or save the CV as PDF or DOCX."
        )
    with tempfile.NamedTemporaryFile(suffix=".doc", delete=False) as tmp:
        tmp.write(data)
        path = tmp.name
    try:
        result = subprocess.run(
            [antiword, "-m", "UTF-8.txt", path],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            raise ValueError("Failed to read .doc file. Save as PDF or DOCX instead.")
        return result.stdout
    finally:
        os.unlink(path)


def _extract_image(data: bytes, ext: str) -> str:
    """OCR from image CV; falls back to OpenAI vision when local OCR is weak."""
    text = _ocr_image(data)
    if len(_clean_text(text)) >= 20:
        return text

    mime = _IMAGE_MIME.get(ext, "image/jpeg")
    try:
        from hermes.llm import LLMClient

        llm = LLMClient()
        if llm.available:
            return llm.extract_text_from_image(data, mime)
    except Exception:
        pass

    if text.strip():
        return text
    raise ValueError(
        "Could not read text from the image. Use a clearer photo/scan, or upload PDF/DOCX."
    )


def _ocr_image(data: bytes) -> str:
    from PIL import Image
    import pytesseract

    if not shutil.which("tesseract"):
        return ""
    img = Image.open(io.BytesIO(data))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    return pytesseract.image_to_string(img)
