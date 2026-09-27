import os
import re
import hashlib
import io
import zipfile
from typing import List, Dict, Any, Tuple
import pypdf
import docx
import openpyxl
import pypdfium2
import pytesseract
from app.core.logging import logger

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".txt"}

# Magic byte signatures
MAGIC_BYTES = {
    ".pdf": b"%PDF",
    ".docx": b"PK\x03\x04",
    ".xlsx": b"PK\x03\x04"
}
MAX_ARCHIVE_MEMBERS = 10000
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 250 * 1024 * 1024
MAX_ARCHIVE_COMPRESSION_RATIO = 200
MAX_OCR_PAGES = 50

class DocumentValidationError(Exception):
    """Raised when document validation fails."""
    pass

class DocumentSecurityScanError(Exception):
    """Raised when security inspection detects malicious content."""
    pass

def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent directory traversal and illegal characters.
    Handles Windows and Unix path separators and malicious injection payloads.
    """
    if not filename:
        return "unnamed_document.txt"
    # Remove null bytes
    clean = filename.replace("\x00", "")
    # Remove traversal sequences
    clean = re.sub(r"\.\.+[/\\]?", "", clean)
    
    # Check if path separator separates a genuine filename
    clean_norm = clean.replace("\\", "/")
    parts = clean_norm.split("/")
    last_part = parts[-1].strip()
    
    # Check if last component has an alphanumeric base name before extension
    name_part = os.path.splitext(last_part)[0]
    has_valid_name = bool(re.search(r"[a-zA-Z0-9]", name_part))
    
    if has_valid_name:
        basename = last_part
    else:
        # Slash was malicious or part of an injection; flatten parts safely
        basename = "_".join(parts)

    # Sanitize characters: keep alphanumeric, dots, underscores, dashes
    sanitized = re.sub(r"[^a-zA-Z0-9_.-]", "_", basename)
    # Collapse multiple underscores
    sanitized = re.sub(r"_{2,}", "_", sanitized).strip("_")
    if not sanitized or sanitized.startswith("."):
        sanitized = "doc_" + sanitized
    return sanitized

def validate_file_content(filename: str, content: bytes, max_size_mb: int = 50) -> str:
    """
    Validate file extension, size limit, and magic bytes.
    Returns normalized extension.
    """
    ext = os.path.splitext(filename.lower())[1]
    if ext not in ALLOWED_EXTENSIONS:
        raise DocumentValidationError(f"Unsupported file format '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}")

    size_mb = len(content) / (1024 * 1024)
    if size_mb > max_size_mb:
        raise DocumentValidationError(f"File size {size_mb:.2f}MB exceeds maximum limit of {max_size_mb}MB")

    if len(content) == 0:
        raise DocumentValidationError("File is empty (0 bytes)")

    # Validate Magic Bytes
    if ext in MAGIC_BYTES:
        expected = MAGIC_BYTES[ext]
        if not content.startswith(expected):
            raise DocumentValidationError(f"Corrupted or invalid file header for {ext}. Magic bytes mismatch.")

    # Deep format validation
    if ext in {".docx", ".xlsx"}:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                members = zf.infolist()
                namelist = [member.filename for member in members]
                if ext == ".docx" and not any(n.startswith("word/") for n in namelist):
                    raise DocumentValidationError("Invalid DOCX archive: missing word/ directory")
                if ext == ".xlsx" and not any(n.startswith("xl/") for n in namelist):
                    raise DocumentValidationError("Invalid XLSX archive: missing xl/ directory")
                if len(members) > MAX_ARCHIVE_MEMBERS:
                    raise DocumentValidationError("Office archive contains too many entries")
                total_uncompressed = sum(member.file_size for member in members)
                if total_uncompressed > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                    raise DocumentValidationError("Office archive expands beyond the allowed size")
                for member in members:
                    if member.file_size and member.compress_size == 0:
                        raise DocumentValidationError("Office archive contains an invalid compressed entry")
                    if member.compress_size and member.file_size / member.compress_size > MAX_ARCHIVE_COMPRESSION_RATIO:
                        raise DocumentValidationError("Office archive compression ratio exceeds the allowed limit")
        except zipfile.BadZipFile:
            raise DocumentValidationError(f"Malformed or corrupted {ext} archive")

    return ext

def compute_sha256(content: bytes) -> str:
    """Calculate cryptographic SHA-256 hash of file content."""
    return hashlib.sha256(content).hexdigest()

def extract_text_from_pdf(content: bytes) -> Tuple[str, int, bool]:
    """
    Extract text from PDF using pypdf.
    Rasterizes sparse pages and extracts their actual text with Tesseract OCR.
    Returns (extracted_text, total_pages, ocr_applied).
    """
    reader = pypdf.PdfReader(io.BytesIO(content))
    total_pages = len(reader.pages)
    page_texts = []
    sparse_page_indexes = []
    sparse_pages = 0

    for idx, page in enumerate(reader.pages):
        page_text = page.extract_text() or ""
        cleaned = page_text.strip()
        if len(cleaned) < 50:
            sparse_pages += 1
            sparse_page_indexes.append(idx)
        page_texts.append(cleaned)

    ocr_applied = False

    # If at least half the pages are sparse, OCR only those pages.
    if total_pages > 0 and (sparse_pages / total_pages) >= 0.5:
        if len(sparse_page_indexes) > MAX_OCR_PAGES:
            raise DocumentValidationError(
                f"Scanned PDF has {len(sparse_page_indexes)} pages requiring OCR; the limit is {MAX_OCR_PAGES}. Split the document before upload."
            )
        ocr_applied = True
        logger.info("PDF appears scanned (%s/%s sparse pages). Running OCR.", sparse_pages, total_pages)
        pdf = pypdfium2.PdfDocument(content)
        recognized_pages = 0
        try:
            for idx in sparse_page_indexes:
                page = pdf[idx]
                bitmap = page.render(scale=2.0)
                image = bitmap.to_pil()
                try:
                    recognized = pytesseract.image_to_string(image, lang="eng", timeout=30).strip()
                finally:
                    image.close()
                    bitmap.close()
                    page.close()
                if not recognized:
                    continue
                page_texts[idx] = recognized
                recognized_pages += 1
            if recognized_pages == 0:
                raise RuntimeError("OCR found no readable text on any sparse page")
        except Exception as exc:
            logger.warning("OCR failed while processing scanned PDF: %s", exc)
            raise DocumentValidationError("Scanned PDF could not be read by OCR; verify Tesseract is available and the pages are legible.") from exc
        finally:
            pdf.close()

    full_text = "\n\n".join(
        f"--- Page {idx + 1}{' (OCR)' if idx in sparse_page_indexes and ocr_applied else ''} ---\n{text}"
        for idx, text in enumerate(page_texts)
    ).strip()

    return full_text, total_pages, ocr_applied

def extract_text_from_docx(content: bytes) -> Tuple[str, int]:
    """Extract text from DOCX including paragraphs, headings, and tables."""
    doc = docx.Document(io.BytesIO(content))
    text_parts = []
    
    for p in doc.paragraphs:
        if p.text.strip():
            text_parts.append(p.text.strip())

    for t in doc.tables:
        for row in t.rows:
            row_vals = [c.text.strip() for c in row.cells if c.text.strip()]
            if row_vals:
                text_parts.append(" | ".join(row_vals))

    full_text = "\n\n".join(text_parts)
    # Estimate pages (~300 words per page)
    words = len(full_text.split())
    pages = max(1, (words // 300) + 1)
    return full_text, pages

def extract_text_from_xlsx(content: bytes) -> Tuple[str, int]:
    """Extract tabular data from XLSX workbook."""
    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
    text_parts = []
    sheets_count = len(wb.sheetnames)

    for sheet_name in wb.sheetnames:
        sheet = wb[sheet_name]
        text_parts.append(f"=== Sheet: {sheet_name} ===")
        for row in sheet.iter_rows(values_only=True):
            cells = [str(c).strip() for c in row if c is not None and str(c).strip()]
            if cells:
                text_parts.append(" | ".join(cells))

    full_text = "\n\n".join(text_parts)
    return full_text, sheets_count

def extract_text_from_txt(content: bytes) -> Tuple[str, int]:
    """Extract text from TXT with multiple encoding fallbacks."""
    for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            text = content.decode(enc)
            words = len(text.split())
            pages = max(1, (words // 300) + 1)
            return text, pages
        except UnicodeDecodeError:
            continue
    raise DocumentValidationError("Failed to decode text file with standard encodings")

def normalize_text(text: str) -> str:
    """Normalize whitespace, special characters, and formatting."""
    # Replace multiple spaces with a single space
    text = re.sub(r"[ \t]+", " ", text)
    # Replace more than 3 consecutive newlines with 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Strip leading/trailing whitespace
    return text.strip()

def chunk_text(
    text: str,
    document_id: str,
    chunk_size: int = 800,
    chunk_overlap: int = 150
) -> List[Dict[str, Any]]:
    """
    Split text into overlapping chunks with metadata (character offsets, page estimation).
    """
    if not text:
        return []

    chunks = []
    start = 0
    chunk_index = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)
        
        # If not at the end of the text, try to break at a newline or period
        if end < text_len:
            break_pt = text.rfind("\n", start, end)
            if break_pt == -1 or break_pt < start + (chunk_size // 2):
                break_pt = text.rfind(". ", start, end)
            if break_pt != -1 and break_pt >= start + (chunk_size // 2):
                end = break_pt + 1

        chunk_snippet = text[start:end].strip()
        if chunk_snippet:
            # Estimate page number from '--- Page X ---' tags if present
            page_match = re.findall(r"--- Page (\d+) ---", text[:end])
            page_num = int(page_match[-1]) if page_match else 1

            chunks.append({
                "document_id": document_id,
                "chunk_index": chunk_index,
                "text": chunk_snippet,
                "char_start": start,
                "char_end": end,
                "page_number": page_num,
                "word_count": len(chunk_snippet.split())
            })
            chunk_index += 1

        if end >= text_len:
            break
        start = max(start + 1, end - chunk_overlap)

    return chunks
