from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="NNewtonians PDF Backend")


class LatexInput(BaseModel):
    latex: str


@app.get("/")
def read_root():
    return {"status": "ok", "message": "NNewtonians PDF backend is running"}


@app.post("/compile")
def compile_latex(payload: LatexInput):
    # Per ora non compiliamo nulla: verifichiamo solo che il server riceva il LaTeX
    latex_length = len(payload.latex)
    return {
        "status": "received",
        "latex_characters": latex_length
    }
