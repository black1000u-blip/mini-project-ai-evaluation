"""Text Extraction Module optimized for low-memory environments.

Strategy:
- PDFs: Use PyMuPDF direct text extraction; optionally fall back to OCR worker
- Images: Lightweight image loading + optional OCR worker
- DOCX: Use python-docx
- TXT: Direct file read

The module avoids heavy in-process OCR dependencies to keep Colab/Render stable.
"""

import gc
import time
import os
import sys
import subprocess
import logging

import numpy as np
from PIL import Image


try:
    import docx
except ImportError:
    docx = None

logging.info("[TEXT] Using lightweight text extraction (optimized for 512MB RAM)")


def extract_text_from_docx(file_path):
    """Extract text from .docx file."""
    if not docx:
        logging.warning("[TEXT] python-docx not installed, cannot read .docx")
        return ""
    try:
        doc = docx.Document(file_path)
        full_text = []
        for para in doc.paragraphs:
            full_text.append(para.text)
        return '\n'.join(full_text)
    except Exception as e:
        logging.error(f"[TEXT] DOCX extraction failed: {e}")
        return ""


def extract_text(image):
    """
    Extract text from a preprocessed image (numpy array).
    Uses PyMuPDF's built-in capabilities.
    """
    import fitz  # PyMuPDF
    
    if not isinstance(image, np.ndarray):
        raise ValueError("Expected numpy array image")
    
    try:
        # Convert numpy array to PIL Image
        if len(image.shape) == 2:
            pil_img = Image.fromarray(image)
        else:
            if image.shape[2] == 4:
                pil_img = Image.fromarray(image[:, :, :3], mode="RGB")
            else:
                pil_img = Image.fromarray(image[:, :, :3], mode="RGB")
        
        # Resize large images to save memory
        max_dim = 1200
        if max(pil_img.size) > max_dim:
            ratio = max_dim / max(pil_img.size)
            new_size = (int(pil_img.size[0] * ratio), int(pil_img.size[1] * ratio))
            pil_img = pil_img.resize(new_size, Image.Resampling.LANCZOS)
        
        # Convert the image into an in-memory PDF page and try direct text extraction.
        img_bytes = pil_img.tobytes("raw", "RGB")
        img_doc = fitz.open()
        img_page = img_doc.new_page(width=pil_img.size[0], height=pil_img.size[1])
        img_page.insert_image(img_page.rect, stream=img_bytes, keep_proportion=True)
        
        # Try to extract any embedded text
        text = img_page.get_text().strip()
        img_doc.close()
        
        # Clean up
        del pil_img, img_bytes
        gc.collect()
        
        return text
        
    except Exception as e:
        logging.error(f"[TEXT] Image extraction failed: {e}")
        gc.collect()
        return ""


def _get_python_command():
    """Get the correct Python command for the current platform."""
    if sys.platform == 'win32':
        # Try py launcher first (Windows-specific)
        for cmd in ["py -3.10", "py -3", "python"]:
            try:
                parts = cmd.split()
                result = subprocess.run(
                    parts + ["--version"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    return parts
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
    
    # Unix / fallback
    for cmd in ["python3", "python"]:
        try:
            result = subprocess.run(
                [cmd, "--version"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return [cmd]
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    
    return [sys.executable]


def extract_text_from_file(file_path):
    """Extract text from a file based on its extension."""
    ext = file_path.rsplit(".", 1)[1].lower()

    # -------- PDF --------
    if ext == "pdf":
        return _extract_pdf_text(file_path)

    # -------- TXT --------
    if ext == "txt":
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
            logging.info(f"[TEXT] TXT file read: {len(text)} chars")
            return text.strip()
        except Exception as e:
            logging.error(f"[TXT READ ERROR] {e}")
            return ""

    # -------- DOCX --------
    if ext == "docx":
        return extract_text_from_docx(file_path)

    # -------- DOC (legacy, limited support) --------
    if ext == "doc":
        logging.warning("[TEXT] .doc format has limited support. Consider using .docx.")
        return extract_text_from_docx(file_path)  # python-docx may handle some .doc files

    # -------- IMAGE --------
    if ext in ["png", "jpg", "jpeg"]:
        return _extract_image_text(file_path)

    logging.warning(f"[TEXT] Unsupported file extension: {ext}")
    return ""


def _extract_pdf_text(pdf_path):
    """Extract text from a PDF using PyMuPDF direct text extraction."""
    import fitz  # PyMuPDF

    doc = None
    try:
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        logging.info(f"[TEXT] Processing PDF: {total_pages} pages")

        from config import Config
        max_pages = min(total_pages, Config.MAX_PDF_PAGES)

        all_text = []
        for page_num in range(max_pages):
            t0 = time.time()
            page = doc[page_num]

            # Direct text extraction (works for digital/typed PDFs)
            text = page.get_text().strip()
            elapsed = time.time() - t0

            logging.info(
                f"[TEXT] Page {page_num + 1}/{max_pages}: {len(text)} chars in {elapsed:.2f}s"
            )

            if text:
                all_text.append(text)

            gc.collect()

        if total_pages > max_pages:
            logging.warning(
                f"[TEXT] Truncated: processed {max_pages}/{total_pages} pages (limit: MAX_PDF_PAGES)"
            )

        combined = "\n\n".join(all_text).strip()
        if combined:
            return combined

        logging.warning("[TEXT] PDF had no directly extractable text, trying OCR worker fallback")
        return _extract_with_worker(pdf_path)

    except Exception as e:
        logging.error(f"[TEXT] PDF extraction failed: {e}")
        return ""
    finally:
        if doc:
            doc.close()
        gc.collect()


def _extract_image_text(image_path):
    """Extract text from an image using OCR worker subprocess."""
    return _extract_with_worker(image_path)


def _extract_with_worker(file_path):
    """Use the standalone OCR worker when available."""
    worker_path = os.path.join(os.path.dirname(__file__), "ocr_worker.py")
    
    if not os.path.exists(worker_path):
        logging.warning("[TEXT] OCR worker not found, falling back to PyMuPDF extraction")
        return ""

    try:
        python_cmd = _get_python_command()
        logging.info(f"[OCR] Running OCR worker with: {' '.join(python_cmd)}")

        result = subprocess.run(
            python_cmd + [worker_path, file_path],
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode != 0:
            logging.error(f"[OCR ERROR] {result.stderr}")
            return ""

        return result.stdout.strip()

    except subprocess.TimeoutExpired:
        logging.error("[OCR] Worker timed out after 120s")
        return ""
    except Exception as e:
        logging.error(f"[OCR SERVICE ERROR] {e}")
        return ""
