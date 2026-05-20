import fitz
import pymupdf4llm
from fastapi import FastAPI, File, UploadFile, HTTPException

app = FastAPI()


@app.post("/extract-text")
async def extract_text(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="El archivo debe ser un PDF.")

    pdf_bytes = await file.read()

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        md_text = pymupdf4llm.to_markdown(
            doc,
            pages=list(range(len(doc))),
            page_chunks=False,
            write_images=False,
            embed_images=False,
            graphics_limit=0,
            plain_text=True,
        )

        doc.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al procesar el PDF: {e}")

    return {"filename": file.filename, "text": md_text}