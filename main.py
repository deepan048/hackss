import os
import json
import base64
import logging
import pymupdf
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai_brand_guardian")

app = FastAPI(
    title="AI Brand Guardian API",
    description="Evidence-based marketing compliance engine",
    version="1.0.0"
)

# Enable CORS for browser access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize OpenAI client from environment variable
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key) if api_key else None

SYSTEM_PROMPT = """
You are AI Brand Guardian, an evidence-based brand governance assistant.
Your mission is to evaluate submitted marketing content against approved brand guidelines, policies, terminology, visual requirements, and verified reference facts.

CORE PRINCIPLE — RETRIEVE FIRST, COMPARE SECOND:
1. Examine retrieved guidelines and approved reference facts.
2. Compare submitted content against that evidence.
3. Cite the specific source, section, rule, or reference supporting every flagged issue.
4. Flag any violations in tone, terminology, unsupported claims, or factual errors.

Return ONLY valid JSON matching this exact structure:
{
  "issues": [
    {
      "issue_type": "unsupported_claim | tone_violation | forbidden_term | factual_contradiction | visual_mismatch",
      "severity": "low | medium | high",
      "detected_text": "Exact snippet from submitted content",
      "explanation": "Why the content was flagged based on retrieved evidence",
      "reference": "Specific source document, section, rule, or approved reference",
      "evidence": "Relevant retrieved evidence supporting the decision",
      "suggested_fix": "Compliant alternative that preserves creator intent",
      "confidence": 0.95,
      "status": "requires_review"
    }
  ],
  "overall_status": "PASS | FAIL | NEEDS_REVIEW"
}

Rule for overall_status:
- Set to "FAIL" if any high or medium severity compliance issues/violations exist.
- Set to "PASS" if zero violations or issues exist.
- Set to "NEEDS_REVIEW" if content is ambiguous, claims cannot be fully assessed, or text couldn't be extracted properly.
"""

class ReviewRequest(BaseModel):
    content: str
    guidelines: str

def check_client():
    if not client:
        raise HTTPException(
            status_code=500,
            detail="OPENAI_API_KEY environment variable is not configured. Please set it in your environment or .env file."
        )

@app.get("/health")
def health_check():
    return {"status": "ok", "api_key_configured": client is not None}

@app.post("/reviews")
async def review_content(request: ReviewRequest):
    check_client()
    if not request.content.strip():
        raise HTTPException(status_code=400, detail="Marketing content cannot be empty.")
    if not request.guidelines.strip():
        raise HTTPException(status_code=400, detail="Brand guidelines cannot be empty.")

    user_payload = f"""
    [RETRIEVED BRAND GUIDELINES]
    {request.guidelines}

    [SUBMITTED MARKETING CONTENT]
    {request.content}
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_payload}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        res_data = json.loads(response.choices[0].message.content)
        res_data["extracted_text"] = request.content
        return res_data
    except Exception as e:
        logger.error(f"Error in review_content: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/reviews/upload")
async def review_file(guidelines: str = Form(...), file: UploadFile = File(...)):
    check_client()
    if not guidelines.strip():
        raise HTTPException(status_code=400, detail="Brand guidelines cannot be empty.")

    filename = file.filename or "upload"
    file_extension = filename.split(".")[-1].lower()
    file_bytes = await file.read()
    
    extracted_text = ""
    image_base64 = None
    mime_type = file.content_type or "image/png"

    try:
        # 1. Process PDF files
        if file_extension == "pdf":
            doc = pymupdf.open(stream=file_bytes, filetype="pdf")
            for page in doc:
                page_text = page.get_text("text")
                if page_text:
                    extracted_text += page_text + "\n"
            
            # If PDF has no text layer (scanned/graphic PDF), render page 1 to image for vision
            if not extracted_text.strip() and len(doc) > 0:
                pix = doc[0].get_pixmap()
                img_bytes = pix.tobytes("png")
                image_base64 = base64.b64encode(img_bytes).decode("utf-8")
                mime_type = "image/png"
                extracted_text = "[Scanned/Graphic PDF: Analyzed visually using Multimodal Vision]"
                
        # 2. Process Image files (PNG, JPG, JPEG, WEBP)
        elif file_extension in ["png", "jpg", "jpeg", "webp"]:
            image_base64 = base64.b64encode(file_bytes).decode("utf-8")
            if not file.content_type:
                mime_type = f"image/{file_extension if file_extension != 'jpg' else 'jpeg'}"
            extracted_text = f"[Image File '{filename}': Analyzed visually with Multimodal Vision]"
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file format '.{file_extension}'. Use PDF, PNG, or JPG.")

        # Prepare messages for OpenAI
        if image_base64:
            # Multimodal Vision Request
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"[RETRIEVED BRAND GUIDELINES]\n{guidelines}\n\nPlease evaluate the marketing creative and copy in the attached image against these guidelines."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_base64}"
                            }
                        }
                    ]
                }
            ]
        else:
            if not extracted_text.strip():
                extracted_text = f"[WARNING: No readable text found in '{filename}']"
                
            user_payload = f"""
            [RETRIEVED BRAND GUIDELINES]
            {guidelines}

            [SUBMITTED MARKETING CONTENT EXTRACTED FROM FILE ({filename})]
            {extracted_text}
            """
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_payload}
            ]

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.1
        )
        
        res_data = json.loads(response.choices[0].message.content)
        res_data["extracted_text"] = extracted_text
        return res_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in review_file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)