import os
import base64
import re
import subprocess
import tempfile
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="NNewtonians PDF Backend")

FILES_DIR = os.environ.get("FILES_DIR", "/tmp/generated_pdfs")
os.makedirs(FILES_DIR, exist_ok=True)
app.mount("/files", StaticFiles(directory=FILES_DIR), name="files")


class LatexInput(BaseModel):
    latex: str
    filename: str | None = None


def safe_filename(name: str) -> str:
    name = (name or "").strip()
    name = re.sub(r"[^a-zA-Z0-9._-]+", "_", name)
    if not name:
        name = "report"
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return name


def run_pdflatex(latex: str) -> bytes:
    if not latex or len(latex) < 50:
        raise HTTPException(status_code=400, detail="LaTeX content is too short or missing.")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        (tmp / "main.tex").write_text(latex, encoding="utf-8")
        pdf_path = tmp / "main.pdf"

        cmd = ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "main.tex"]

        try:
            subprocess.run(cmd, cwd=tmp, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
            subprocess.run(cmd, cwd=tmp, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
        except FileNotFoundError:
            raise HTTPException(status_code=500, detail="pdflatex not found on server.")
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=500, detail="LaTeX compilation timed out.")
        except subprocess.CalledProcessError as e:
            log = e.stdout.decode("utf-8", errors="replace") if e.stdout else "Compilation failed."
            raise HTTPException(status_code=400, detail=f"LaTeX compilation error:\n{log[:2000]}")

        if not pdf_path.exists():
            raise HTTPException(status_code=500, detail="PDF was not produced.")

        return pdf_path.read_bytes()


@app.get("/")
def read_root():
    return {"status": "ok", "message": "NNewtonians PDF backend is running"}


@app.post("/compile")
def compile_latex(payload: LatexInput):
    out_name = safe_filename(payload.filename or "nnewtonians_report.pdf")
    pdf_bytes = run_pdflatex(payload.latex)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{out_name}"'},
    )


@app.post("/compile_base64")
def compile_latex_base64(payload: LatexInput):
    out_name = safe_filename(payload.filename or "nnewtonians_report.pdf")
    pdf_bytes = run_pdflatex(payload.latex)
    pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")
    return {"filename": out_name, "mime_type": "application/pdf", "pdf_base64": pdf_b64}


@app.post("/compile_url")
def compile_latex_url(payload: LatexInput):
    pdf_bytes = run_pdflatex(payload.latex)

    safe_name = safe_filename(payload.filename or "NNewtonians_AI_Adoption_Report.pdf")
    unique = uuid.uuid4().hex[:10]
    stored_name = f"{unique}_{safe_name}"
    out_path = os.path.join(FILES_DIR, stored_name)

    with open(out_path, "wb") as f:
        f.write(pdf_bytes)

    download_url = f"https://nnewtonians-pdf-backend.onrender.com/files/{stored_name}"
    return {"filename": safe_name, "download_url": download_url}
