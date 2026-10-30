"""
Brand Shield Guardian - FastAPI Modular Backend
REST API with Multi-Organization CRUD, Isolated FAISS Vector Stores, Logo Checker & RAG Diff Evaluator
"""

import os
import json
import base64
import logging
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Path
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import pymupdf  # PyMuPDF
from database import (
    get_all_organizations,
    get_organization,
    create_organization,
    update_organization,
    delete_organization
)
from vector_store import (
    build_or_update_org_index,
    delete_org_index
)
from engine import evaluate_content_rag

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("brand_shield_guardian.api")

app = FastAPI(
    title="Brand Shield Guardian API",
    description="Multi-Organization AI Brand Governance, FAISS Vector Grounding, Automated Logo Checker & Diff Engine",
    version="3.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

LOGOS_DIR = os.path.join(os.path.dirname(__file__), "data", "logos")
os.makedirs(LOGOS_DIR, exist_ok=True)

# ----------------- Request / Response Models -----------------
class OrganizationCreateRequest(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., example="Brand Kit - Social Media")
    description: Optional[str] = Field("", example="Guidelines for influencer and social media posts")
    guidelines: str = Field(..., example="Rule 1: Never use unverified claims...")
    brand_colors_hex: Optional[str] = Field("#1E3A8A, #06B6D4, #FFFFFF", example="#1E3A8A, #06B6D4, #FFFFFF")

class OrganizationUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    guidelines: Optional[str] = None
    brand_colors_hex: Optional[str] = None

class OrganizationResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = ""
    guidelines: str
    logo_path: Optional[str] = None
    brand_colors_hex: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class EvaluateRequest(BaseModel):
    content: str = Field(..., example="Get instant 1-day results with our miracle product!")
    organization_id: str = Field(..., example="org_b2b_clinical")

class Issue(BaseModel):
    issue_type: str
    severity: str
    detected_text: str
    rule_violated: str
    explanation: str
    evidence: str
    suggested_fix: str
    confidence: float = 0.95

class SeverityBreakdown(BaseModel):
    high: int = 0
    medium: int = 0
    low: int = 0

class EvaluateResponse(BaseModel):
    organization_id: str
    organization_name: str
    total_violations: int
    compliance_score: int
    compliance_status: str
    overall_status: str
    severity_breakdown: SeverityBreakdown
    issues: List[Issue] = []
    corrected_text: str
    diff_html: str
    explanation_of_changes: List[str] = []
    retrieved_evidence: List[str] = []
    extracted_text: Optional[str] = ""
    logo_audit: Optional[Dict[str, Any]] = None

def extract_text_from_pdf(pdf_bytes: bytes) -> Dict[str, Any]:
    extracted_text = ""
    rendered_image_b64 = None
    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        for page in doc:
            page_text = page.get_text("text")
            if page_text:
                extracted_text += page_text + "\n"

        if len(doc) > 0:
            pix = doc[0].get_pixmap(dpi=150)
            img_bytes = pix.tobytes("png")
            rendered_image_b64 = base64.b64encode(img_bytes).decode("utf-8")
            if not extracted_text.strip():
                extracted_text = "[Scanned / Image-Based PDF: First page converted for Multimodal Vision Review]"

        return {"text": extracted_text.strip(), "rendered_image_b64": rendered_image_b64}
    except Exception as e:
        logger.error(f"PyMuPDF error: {e}")
        return {"text": "", "rendered_image_b64": None}

# ----------------- Organization CRUD Routes -----------------
@app.get("/organizations", response_model=List[OrganizationResponse])
def list_organizations():
    return get_all_organizations()

@app.post("/organizations", response_model=OrganizationResponse, status_code=201)
def create_new_organization(req: OrganizationCreateRequest):
    import uuid
    org_id = req.id.strip() if req.id and req.id.strip() else f"org_{uuid.uuid4().hex[:8]}"

    existing = get_organization(org_id)
    if existing:
        raise HTTPException(status_code=409, detail=f"Organization with id '{org_id}' already exists.")

    org = create_organization(
        org_id=org_id,
        name=req.name.strip(),
        description=req.description.strip() if req.description else "",
        guidelines=req.guidelines.strip(),
        brand_colors_hex=req.brand_colors_hex
    )
    build_or_update_org_index(org_id, org["guidelines"])
    return org

@app.get("/organizations/{org_id}", response_model=OrganizationResponse)
def get_organization_detail(org_id: str = Path(...)):
    org = get_organization(org_id)
    if not org:
        raise HTTPException(status_code=404, detail=f"Organization '{org_id}' not found.")
    return org

@app.put("/organizations/{org_id}", response_model=OrganizationResponse)
def update_organization_detail(org_id: str, req: OrganizationUpdateRequest):
    org = update_organization(
        org_id=org_id,
        name=req.name,
        description=req.description,
        guidelines=req.guidelines,
        brand_colors_hex=req.brand_colors_hex
    )
    if not org:
        raise HTTPException(status_code=404, detail=f"Organization '{org_id}' not found.")

    if req.guidelines:
        build_or_update_org_index(org_id, org["guidelines"])

    return org

@app.delete("/organizations/{org_id}", status_code=200)
def delete_organization_profile(org_id: str):
    org = get_organization(org_id)
    if not org:
        raise HTTPException(status_code=404, detail=f"Organization '{org_id}' not found.")

    delete_organization(org_id)
    delete_org_index(org_id)
    return {"message": f"Organization '{org_id}' and its FAISS index were successfully deleted."}

# ----------------- Master Logo Asset Upload Route -----------------
@app.post("/organizations/{org_id}/logo")
async def upload_organization_master_logo(
    org_id: str,
    file: UploadFile = File(...)
):
    """Uploads and registers an approved master reference logo (.png, .jpg, .svg) for an organization."""
    org = get_organization(org_id)
    if not org:
        raise HTTPException(status_code=404, detail=f"Organization '{org_id}' not found.")

    ext = (file.filename or "").split(".")[-1].lower()
    if ext not in ["png", "jpg", "jpeg", "svg", "webp"]:
        raise HTTPException(status_code=400, detail="Logo file must be an image (PNG, JPG, SVG, or WEBP).")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded logo file is empty.")

    saved_filename = f"{org_id}_master.{ext}"
    saved_path = os.path.join(LOGOS_DIR, saved_filename)
    with open(saved_path, "wb") as f:
        f.write(file_bytes)

    update_organization(org_id, logo_path=saved_path)
    logger.info(f"Master logo saved for '{org_id}' at {saved_path}.")
    return {"message": "Master logo uploaded and registered successfully.", "logo_path": saved_path}

@app.get("/organizations/{org_id}/logo")
def get_organization_master_logo(org_id: str):
    """Retrieves the master reference logo image for an organization."""
    org = get_organization(org_id)
    if not org or not org.get("logo_path") or not os.path.exists(org["logo_path"]):
        raise HTTPException(status_code=404, detail=f"Master logo not found for organization '{org_id}'.")
    return FileResponse(org["logo_path"])

# ----------------- Evaluation Routes -----------------
@app.post("/evaluate", response_model=EvaluateResponse)
async def evaluate_text(req: EvaluateRequest):
    if not req.content.strip():
        raise HTTPException(status_code=400, detail="Marketing content cannot be empty.")
    if not req.organization_id.strip():
        raise HTTPException(status_code=400, detail="Organization ID is required.")

    org = get_organization(req.organization_id)
    if not org:
        raise HTTPException(status_code=404, detail=f"Organization '{req.organization_id}' not found.")

    res = await evaluate_content_rag(
        content=req.content,
        organization_id=req.organization_id
    )
    res["extracted_text"] = req.content
    return res

@app.post("/evaluate/upload", response_model=EvaluateResponse)
async def evaluate_upload(
    organization_id: str = Form(...),
    file: UploadFile = File(...)
):
    org = get_organization(organization_id)
    if not org:
        raise HTTPException(status_code=404, detail=f"Organization '{organization_id}' not found.")

    filename = (file.filename or "").lower()
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    extracted_text = ""
    image_bytes = None
    mime_type = file.content_type or "image/png"

    if filename.endswith(".pdf") or "pdf" in mime_type:
        pdf_res = extract_text_from_pdf(file_bytes)
        extracted_text = pdf_res["text"]
        if pdf_res["rendered_image_b64"]:
            image_bytes = base64.b64decode(pdf_res["rendered_image_b64"])
            mime_type = "image/png"

    elif any(filename.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp"]) or "image" in mime_type:
        image_bytes = file_bytes
        extracted_text = f"[Visual Creative Ad '{file.filename}' processed via Multimodal Vision & Logo Checker]"
    else:
        raise HTTPException(status_code=400, detail="Unsupported file format. Please upload PDF, PNG, or JPG.")

    res = await evaluate_content_rag(
        content=extracted_text,
        organization_id=organization_id,
        image_bytes=image_bytes,
        mime_type=mime_type
    )
    res["extracted_text"] = extracted_text
    return res

@app.get("/health")
def health_check():
    orgs = get_all_organizations()
    return {
        "status": "healthy",
        "service": "Brand Shield Guardian API",
        "active_organizations_count": len(orgs),
        "organizations": [o["name"] for o in orgs]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend:app", host="127.0.0.1", port=8000, reload=True)
