import io
from pypdf import PdfReader
from docx import Document

def extract_text_from_pdf(file_bytes: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        text = ""
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
        return text.strip()
    except Exception as e:
        raise ValueError(f"Failed to parse PDF document: {str(e)}")

def extract_text_from_docx(file_bytes: bytes) -> str:
    try:
        doc = Document(io.BytesIO(file_bytes))
        text = []
        for p in doc.paragraphs:
            if p.text:
                text.append(p.text)
        return "\n".join(text).strip()
    except Exception as e:
        raise ValueError(f"Failed to parse DOCX document: {str(e)}")

def extract_document_text(filename: str, content: bytes) -> str:
    lower_name = filename.lower()
    if lower_name.endswith(".pdf"):
        return extract_text_from_pdf(content)
    elif lower_name.endswith(".docx"):
        return extract_text_from_docx(content)
    elif lower_name.endswith(".txt"):
        return content.decode("utf-8", errors="ignore")
    else:
        raise ValueError("Unsupported document format. Please upload PDF, DOCX, or TXT.")
