import fitz
import pymupdf4llm


def extract_text(file_bytes: bytes) -> str:
    """
    Extrae el texto de un PDF en memoria usando pymupdf4llm.
    El archivo nunca se escribe en disco.
    """
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    text = pymupdf4llm.to_markdown(
        doc,
        pages=list(range(len(doc))),
        page_chunks=False,
        write_images=False,
        embed_images=False,
        graphics_limit=0,
        plain_text=True,
    )
    doc.close()
    return text.strip()