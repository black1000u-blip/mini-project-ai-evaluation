"""OCR Worker — Standalone script for OCR text extraction.

This script runs as a subprocess to isolate PaddleOCR's heavy memory usage.
It handles both PDF and image files.

Usage:
    python ocr_worker.py <file_path>

Output:
    Extracted text is printed to stdout.
"""

import sys
import os


def ocr_with_paddleocr(image_or_path):
    """Run PaddleOCR on an image (numpy array or file path)."""
    try:
        from paddleocr import PaddleOCR
        ocr = PaddleOCR(lang="en", use_angle_cls=True, show_log=False)
        result = ocr.ocr(image_or_path)

        words = []
        if result:
            for line in result:
                if line:
                    for word in line:
                        if word and len(word) > 1:
                            words.append(word[1][0])

        return " ".join(words)
    except ImportError:
        print("[OCR WORKER] PaddleOCR not installed. Install with: pip install paddleocr", file=sys.stderr)
        return ""
    except Exception as e:
        print(f"[OCR WORKER] Error: {e}", file=sys.stderr)
        return ""


def ocr_pdf(path):
    """Extract text from a PDF using PyMuPDF + PaddleOCR fallback."""
    import fitz  # PyMuPDF
    import numpy as np

    doc = fitz.open(path)
    full_text = []

    for page_num, page in enumerate(doc):
        # First try direct text extraction
        text = page.get_text().strip()

        # If very little text found, try OCR
        if len(text) < 10:
            try:
                pix = page.get_pixmap(dpi=200)
                img = np.frombuffer(
                    pix.samples, dtype=np.uint8
                ).reshape(pix.h, pix.w, pix.n)

                if pix.n == 4:
                    img = img[:, :, :3]

                text = ocr_with_paddleocr(img)

                del pix, img
            except Exception as e:
                print(f"[OCR WORKER] OCR failed on page {page_num + 1}: {e}", file=sys.stderr)

        if text:
            full_text.append(text)

    doc.close()
    print("\n".join(full_text))


def ocr_image(path):
    """Extract text from an image file using PaddleOCR."""
    text = ocr_with_paddleocr(path)
    if text:
        print(text)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ocr_worker.py <file_path>", file=sys.stderr)
        sys.exit(1)

    file_path = sys.argv[1]

    if not os.path.exists(file_path):
        print(f"[OCR WORKER] File not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    ext = file_path.rsplit(".", 1)[-1].lower()

    if ext == "pdf":
        ocr_pdf(file_path)
    elif ext in ("png", "jpg", "jpeg"):
        ocr_image(file_path)
    else:
        print(f"[OCR WORKER] Unsupported file type: {ext}", file=sys.stderr)
        sys.exit(1)
