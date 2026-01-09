import os
import re
import shutil
import subprocess
import tempfile
from fastapi.responses import Response
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="NNewtonians PDF Backend")


class LatexInput(BaseModel):
    latex: str
    filename: str | None = None  # optional hint


def safe_filename(name: str) -> str:
    # keep it simple and safe
    name = name.strip()
    name = re.sub(r"[^a-zA-Z0-9._-]+", "_", name)
    if not name:
        name = "report"
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return name


@app.get("/")
def read_root():
    return {"status": "ok", "message": "NNewtonians PDF backend is running"}


@app.post("/compile")
def compile_latex(payload: LatexInput):
    latex = payload.latex
    if not latex or len(latex) < 50:
        raise HTTPException(status_code=400, detail="LaTeX content is too short or missing.")

    out_name = safe_filename(payload.filename or "nnewtonians_report.pdf")

    # Work in a temp directory to avoid clutter
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        tex_path = tmp / "main.tex"
        pdf_path = tmp / "main.pdf"
        tex_path.write_text(latex, encoding="utf-8")

        # pdflatex command (twice for references)
        cmd = ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "main.tex"]

        try:
            subprocess.run(cmd, cwd=tmp, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
            subprocess.run(cmd, cwd=tmp, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
        except FileNotFoundError:
            raise HTTPException(status_code=500, detail="pdflatex not found on server.")
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=500, detail="LaTeX compilation timed out.")
        except subprocess.CalledProcessError as e:
            log = e.stdout.decode("utf-8", errors="replace") if e.stdout else "Compilation failed."
            # Return a short log excerpt to help debugging
            raise HTTPException(status_code=400, detail=f"LaTeX compilation error:\n{log[:2000]}")

        if not pdf_path.exists():
            raise HTTPException(status_code=500, detail="PDF was not produced.")

        # Return the PDF directly as a downloadable file
        # Copy it to a stable temp file location for FileResponse
        final_path = tmp / out_name
        shutil.copyfile(pdf_path, final_path)
        return FileResponse(
            path=str(final_path),
            media_type="application/pdf",
            filename=out_name
        )
