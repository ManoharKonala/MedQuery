"""
Universal document parser using EasyOCR + PyPDF2 + pdf2image.

Extraction strategy per page:
  1. Try PyPDF2 for native digital text.
  2. ALWAYS render the page to an image via pdf2image and run EasyOCR.
  3. Use whichever output has more text (handles mixed pages: digital text + embedded diagrams).

This guarantees that scanned pages, embedded images with text,
charts with labels, and mixed-content pages are ALL captured.
"""

import os
import io
import tempfile
from PyPDF2 import PdfReader
from PIL import Image

# Lazy-loaded EasyOCR reader
_ocr_reader = None


def _get_ocr_reader():
    """Initialize EasyOCR reader (cached after first call)."""
    global _ocr_reader
    if _ocr_reader is None:
        import easyocr
        print("[OCR] Initializing EasyOCR reader...")
        _ocr_reader = easyocr.Reader(["en"], gpu=False)
        print("[OCR] EasyOCR ready.")
    return _ocr_reader


def _ocr_image(image: Image.Image) -> str:
    """Run EasyOCR on a PIL Image and return extracted text.

    EasyOCR detects text regions in images — this handles:
    - Scanned document pages
    - Photos of documents
    - Diagrams/charts with text labels
    - Embedded figures with captions
    """
    reader = _get_ocr_reader()

    # Convert to RGB if necessary (RGBA/Palette causes issues)
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    # Save to temp file (EasyOCR works best with file paths)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        image.save(tmp, format="PNG")
        tmp_path = tmp.name

    try:
        # detail=0 returns just text strings, paragraph=True merges nearby text
        results = reader.readtext(tmp_path, detail=0, paragraph=True)
        return "\n".join(results)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _extract_text_from_pdf(file_path: str) -> dict:
    """Extract text from a PDF using a dual-path strategy per page.

    For EVERY page:
      Path A: PyPDF2 extracts native digital text.
      Path B: pdf2image renders the page at 300 DPI → EasyOCR extracts all visible text.
      Result: We keep the LONGER output (covers mixed pages with embedded images).

    This means:
      - Pure digital PDFs → Path A wins (fast, accurate).
      - Pure scanned PDFs → Path B wins (OCR catches everything).
      - Mixed PDFs (text + embedded charts) → Path B catches the image text that Path A misses.
    """
    reader = PdfReader(file_path)
    pages = []
    full_text_parts = []

    # Pre-import pdf2image once
    try:
        from pdf2image import convert_from_path
        has_pdf2image = True
    except ImportError:
        print("[OCR] WARNING: pdf2image not installed. Scanned PDFs will not be processed.")
        has_pdf2image = False

    for i, page in enumerate(reader.pages):
        page_num = i + 1

        # Path A: Native digital text extraction
        digital_text = (page.extract_text() or "").strip()

        # Path B: Render page to image and run full OCR
        ocr_text = ""
        if has_pdf2image:
            try:
                rendered_images = convert_from_path(
                    file_path,
                    first_page=page_num,
                    last_page=page_num,
                    dpi=300,  # High DPI for medical documents with fine print
                )
                if rendered_images:
                    ocr_text = _ocr_image(rendered_images[0]).strip()
            except Exception as e:
                print(f"[OCR] Page {page_num}: Render+OCR failed: {e}")

        # Choose the richer output
        if len(ocr_text) > len(digital_text):
            final_text = ocr_text
            source = "OCR"
        else:
            final_text = digital_text
            source = "Digital"

        # If digital text exists but OCR found additional text (embedded images),
        # merge them to capture everything
        if digital_text and ocr_text and len(ocr_text) > 50:
            # Check if OCR found significantly different content
            digital_words = set(digital_text.lower().split())
            ocr_words = set(ocr_text.lower().split())
            extra_words = ocr_words - digital_words
            if len(extra_words) > 10:
                # OCR found text not in digital extraction (likely from embedded images)
                final_text = digital_text + "\n\n[Image/Figure Text]:\n" + ocr_text
                source = "Merged"

        print(f"[Parser] Page {page_num}: {source} ({len(final_text)} chars)")
        pages.append({"page_number": page_num, "text": final_text})
        full_text_parts.append(final_text)

    return {
        "text": "\n\n".join(full_text_parts),
        "page_count": len(reader.pages),
        "pages": pages,
    }


def _extract_text_from_image(file_path: str) -> dict:
    """Extract text from a standalone image file (PNG, JPG, etc.) using EasyOCR."""
    image = Image.open(file_path)
    text = _ocr_image(image)

    return {
        "text": text,
        "page_count": 1,
        "pages": [{"page_number": 1, "text": text}],
    }


def _extract_text_from_text_file(file_path: str) -> dict:
    """Read plain text files directly."""
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()

    return {
        "text": text,
        "page_count": 1,
        "pages": [{"page_number": 1, "text": text}],
    }


def parse_document(file_path: str) -> dict:
    """Universal document parser — routes to the correct extractor based on file type.

    Returns:
        dict with keys: text, page_count, pages
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        print(f"[Parser] Parsing PDF: {file_path}")
        return _extract_text_from_pdf(file_path)
    elif ext in (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"):
        print(f"[Parser] Parsing image: {file_path}")
        return _extract_text_from_image(file_path)
    elif ext in (".txt", ".md", ".csv"):
        print(f"[Parser] Parsing text file: {file_path}")
        return _extract_text_from_text_file(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")
