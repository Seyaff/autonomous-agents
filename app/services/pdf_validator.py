import io
import logging
from typing import Tuple
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

MAX_PDF_SIZE = 5 * 1024 * 1024  # 5MB
MIN_TEXT_LENGTH = 50  # Minimum characters to consider as text-based PDF


class PDFValidationError(Exception):
    pass


def validate_pdf(file_bytes: bytes, filename: str) -> Tuple[bool, str]:
    """
    Validates PDF file:
    1. Size check (max 5MB)
    2. Not image-only (has extractable text)
    3. Valid PDF structure
    
    Returns: (is_valid, error_message)
    """
    if len(file_bytes) > MAX_PDF_SIZE:
        return False, f"File size exceeds 5MB limit ({len(file_bytes) / (1024*1024):.1f}MB)"

    if len(file_bytes) == 0:
        return False, "Empty file"

    try:
        pdf_stream = io.BytesIO(file_bytes)
        doc = fitz.open(stream=pdf_stream, filetype="pdf")

        if doc.page_count == 0:
            doc.close()
            return False, "PDF has no pages"

        total_text_length = 0
        for page_num in range(doc.page_count):
            page = doc[page_num]
            text = page.get_text()
            if text:
                total_text_length += len(text.strip())

        doc.close()

        if total_text_length < MIN_TEXT_LENGTH:
            return False, (
                f"PDF appears to be image-only or scanned (only {total_text_length} characters extracted). "
                f"Please upload a text-based PDF or use OCR first."
            )

        return True, ""

    except Exception as e:
        logger.error(f"PDF validation failed for {filename}: {e}")
        return False, f"Invalid or corrupted PDF: {str(e)}"


async def extract_pdf_text_sample(file_bytes: bytes, max_chars: int = 500) -> str:
    """Extract a text sample from PDF for preview/validation"""
    try:
        pdf_stream = io.BytesIO(file_bytes)
        doc = fitz.open(stream=pdf_stream, filetype="pdf")

        text_parts = []
        for page_num in range(min(doc.page_count, 3)):
            page = doc[page_num]
            text = page.get_text()
            if text:
                text_parts.append(text.strip())

        doc.close()

        full_text = "\n\n".join(text_parts)
        if len(full_text) > max_chars:
            return full_text[:max_chars] + "..."
        return full_text

    except Exception as e:
        logger.error(f"Failed to extract PDF text sample: {e}")
        return ""