"""
Adaptador concreto de `IPDFProcessor` sobre PyMuPDF (fitz) + pymupdf4llm.

Vive en `app/infrastructure` para que la capa de aplicación (servicios) nunca
dependa de una librería de parsing específica (Hexagonal / Ports & Adapters).
Las excepciones de infraestructura se mapean a errores de dominio en este
borde, y las operaciones CPU-intensivas se descargan a un thread pool
(`asyncio.to_thread`) para no bloquear el event loop del framework.
"""

import asyncio
import hashlib

import fitz
import pymupdf4llm

from app.domain.exceptions import InvalidPDFFormatError, PDFProcessingError
from app.services.ports import IPDFProcessor

PDF_MAGIC_BYTES = b"%PDF"


def compute_checksum(file_bytes: bytes) -> str:
    """Calcula el hash SHA-256 de los bytes dados para evitar duplicados en BD."""
    return hashlib.sha256(file_bytes).hexdigest()


def validate_pdf_format(file_bytes: bytes) -> None:
    """
    Valida que los bytes correspondan a un PDF legible.

    1. Comprueba magic bytes (`%PDF`).
    2. Intenta abrirlo con PyMuPDF para descartar corrupción estructural.

    Los errores de la librería (`fitz.FileDataError`) se mapean aquí a
    `InvalidPDFFormatError` (error de dominio) para no filtrar infraestructura.
    """
    if not file_bytes.startswith(PDF_MAGIC_BYTES):
        raise InvalidPDFFormatError("El archivo no es un PDF válido.")

    doc = None
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except fitz.FileDataError:
        raise InvalidPDFFormatError("El PDF está corrupto o no se puede procesar.")
    finally:
        if doc is not None:
            doc.close()


def extract_text(file_bytes: bytes) -> str:
    """
    Extrae el texto de un PDF en memoria usando pymupdf4llm.
    El archivo nunca se escribe en disco.

    El manejador de `fitz.Document` se libera en `finally` aunque `to_markdown`
    lance excepción, y cualquier fallo de la librería se convierte en
    `PDFProcessingError` (error de dominio).
    """
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        try:
            text = pymupdf4llm.to_markdown(
                doc,
                pages=list(range(len(doc))),
                page_chunks=False,
                write_images=False,
                embed_images=False,
                graphics_limit=0,
                plain_text=True,
            )
        finally:
            doc.close()
    except Exception as exc:
        raise PDFProcessingError() from exc
    return text.strip()


class PyMuPDFProcessor(IPDFProcessor):
    """Adaptador concreto del puerto `IPDFProcessor` sobre PyMuPDF.

    Cada método es `async` y delega en un thread pool: PyMuPDF es
    CPU-intensivo y bloquearía el event loop si se invocara en línea.
    """

    async def validate_format(self, file_bytes: bytes) -> None:
        await asyncio.to_thread(validate_pdf_format, file_bytes)

    async def compute_checksum(self, file_bytes: bytes) -> str:
        return await asyncio.to_thread(compute_checksum, file_bytes)

    async def extract_text(self, file_bytes: bytes) -> str:
        return await asyncio.to_thread(extract_text, file_bytes)