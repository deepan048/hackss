"""
Brand Shield Guardian - AI Evaluation & Diff Engine
RAG Compliance Auditor, Diff Generator, One-Click Auto-Fix & Automated Visual Creative Verifier
"""

import os
import re
import json
import base64
import logging
import difflib
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv

from openai import OpenAI
from database import get_organization
from vector_store import retrieve_relevant_rules
from logo_checker import verify_ad_logo

load_dotenv()
logger = logging.getLogger("brand_shield_guardian.engine")

def generate_html_diff(original_text: str, corrected_text: str) -> str:
    orig_words = original_text.split()
    corr_words = corrected_text.split()
    matcher = difflib.SequenceMatcher(None, orig_words, corr_words)
    diff_html_parts = []

    for opcode, a0, a1, b0, b1 in matcher.get_opcodes():
        if opcode == "equal":
            diff_html_parts.append(" ".join(orig_words[a0:a1]))
        elif opcode == "delete":
            deleted_text = " ".join(orig_words[a0:a1])
            diff_html_parts.append(
                f'<del style="background-color: rgba(239, 68, 68, 0.25); color: #fca5a5; text-decoration: line-through; padding: 2px 6px; border-radius: 4px; font-weight: 500;">{deleted_text}</del>'
            )
        elif opcode == "insert":
            inserted_text = " ".join(corr_words[b0:b1])
            diff_html_parts.append(
                f'<ins style="background-color: rgba(16, 185, 129, 0.25); color: #6ee7b7; text-decoration: none; padding: 2px 6px; border-radius: 4px; font-weight: 600;">{inserted_text}</ins>'
            )
        elif opcode == "replace":
            deleted_text = " ".join(orig_words[a0:a1])
            inserted_text = " ".join(corr_words[b0:b1])
            diff_html_parts.append(
                f'<del style="background-color: rgba(239, 68, 68, 0.25); color: #fca5a5; text-decoration: line-through; padding: 2px 6px; font-weight: 500;">{deleted_text}</del> '
                f'<ins style="background-color: rgba(16, 185, 129, 0.25); color: #6ee7b7; text-decoration: none; padding: 2px 6px; font-weight: 600;">{inserted_text}</ins>'
            )

    return " ".join(diff_html_parts)

def calculate_compliance_score(issues: List[Dict[str, Any]]) -> int:
    score = 100
    for issue in issues:
        sev = str(issue.get("severity", "medium")).lower()
        if sev == "high":
            score -= 25
        elif sev == "medium":
            score -= 12
        else:
            score -= 5
    return max(0, score)

def evaluate_locally_fallback(
    content: str,
    org: Dict[str, Any],
    retrieved_rules: List[str],
    image_bytes: Optional[bytes] = None
) -> Dict[str, Any]:
    guidelines = org.get("guidelines", "")
    content_lower = content.lower()
    guidelines_lower = guidelines.lower()
    issues = []
    changes_explanation = []
    corrected = content

    # 1. Timeline claims check
    time_triggers = ["1-day", "1 day", "instant", "overnight", "24-hour", "24 hour"]
    if any(t in content_lower for t in time_triggers) and any(t in guidelines_lower for t in ["instant", "1-day", "overnight", "24-hour"]):
        match = re.search(r"\b(get\s+)?(instant|1-day|1 day|overnight|24-hour)\b[^\.\!\?]*", content, re.IGNORECASE)
        snippet = match.group(0) if match else "instant / 1-day results"
        fix = "visible improvements over verified trial periods"
        issues.append({
            "issue_type": "factual_contradiction",
            "severity": "high",
            "detected_text": snippet.strip(),
            "rule_violated": "Clinical/Timeline Policy: Unverified instant or overnight results are prohibited.",
            "explanation": "Guarantees of instant or overnight results contradict verified brand timelines.",
            "evidence": "Guidelines mandate validated multi-week trial timelines.",
            "suggested_fix": fix,
            "confidence": 0.98
        })
        corrected = re.sub(re.escape(snippet), fix, corrected, flags=re.IGNORECASE)
        changes_explanation.append(f"Replaced unapproved timeline claim '{snippet.strip()}' with compliant trial period wording.")

    # 2. Prohibited terms check
    prohibited_candidates = ["miracle", "overnight results", "complete elimination", "100% cure", "filters in a bottle"]
    for term in prohibited_candidates:
        if term in content_lower and (term in guidelines_lower or "prohibit" in guidelines_lower):
            match = re.search(re.escape(term), content, re.IGNORECASE)
            snippet = match.group(0) if match else term
            fix = "clinically tested formula"
            issues.append({
                "issue_type": "forbidden_term",
                "severity": "high",
                "detected_text": snippet,
                "rule_violated": f"Blacklisted Terminology: '{snippet}' is explicitly prohibited.",
                "explanation": f"The term '{snippet}' violates advertising compliance standards.",
                "evidence": f"Guidelines strictly forbid sensationalist terms like '{term}'.",
                "suggested_fix": fix,
                "confidence": 0.99
            })
            corrected = re.sub(re.escape(snippet), fix, corrected, flags=re.IGNORECASE)
            changes_explanation.append(f"Removed blacklisted buzzword '{snippet}' and substituted with compliant description '{fix}'.")

    # 3. Product Nomenclature
    names = re.findall(r"['\"]([A-Z][A-Za-z0-9 ]+)['\"]", guidelines)
    approved_names = [n for n in names if len(n.split()) >= 2 and not n.startswith("Rule")]
    if approved_names and not any(name.lower() in content_lower for name in approved_names):
        target_name = approved_names[0]
        issues.append({
            "issue_type": "forbidden_term",
            "severity": "medium",
            "detected_text": "Missing official product nomenclature",
            "rule_violated": f"Nomenclature Standard: Must use official name '{target_name}'.",
            "explanation": f"Official product designation '{target_name}' must be referenced.",
            "evidence": f"Mandatory nomenclature: '{target_name}'.",
            "suggested_fix": f"Prepend official product name '{target_name}'.",
            "confidence": 0.92
        })
        corrected = f"{target_name}: {corrected}"
        changes_explanation.append(f"Standardized brand identity by adding official nomenclature '{target_name}'.")

    # 4. Sales urgency
    if any(u in content_lower for u in ["order now", "buy now", "stock runs out", "hurry"]):
        if "tone" in guidelines_lower or "sales jargon" in guidelines_lower or "scarcity" in guidelines_lower:
            match = re.search(r"\b(order now|buy now|before stock runs out|hurry)[^\.\!\?]*", content, re.IGNORECASE)
            snippet = match.group(0) if match else "Sales urgency jargon"
            fix = "Discover how our formula elevates your routine today."
            issues.append({
                "issue_type": "tone_violation",
                "severity": "medium",
                "detected_text": snippet.strip(),
                "rule_violated": "Tone Policy: Avoid aggressive high-pressure sales jargon.",
                "explanation": "High-pressure urgency language contradicts the approved brand voice.",
                "evidence": "Brand tone policy mandates professional, encouraging communication.",
                "suggested_fix": fix,
                "confidence": 0.91
            })
            corrected = re.sub(re.escape(snippet), fix, corrected, flags=re.IGNORECASE)
            changes_explanation.append("Replaced high-pressure sales urgency with engaging, compliant call-to-action.")

    # 5. Automated Logo Verification
    logo_audit = None
    if image_bytes and org.get("logo_path"):
        approved_colors = [c.strip() for c in (org.get("brand_colors_hex") or "").split(",") if c.strip()]
        logo_audit = verify_ad_logo(
            ad_image_bytes=image_bytes,
            master_logo_path=org["logo_path"],
            approved_hex_colors=approved_colors
        )
        if logo_audit and logo_audit.get("violations"):
            issues.extend(logo_audit["violations"])
            for lv in logo_audit["violations"]:
                changes_explanation.append(f"Visual Logo Alert: {lv['explanation']}")

    high_count = sum(1 for i in issues if i["severity"] == "high")
    med_count = sum(1 for i in issues if i["severity"] == "medium")
    low_count = sum(1 for i in issues if i["severity"] == "low")
    score = calculate_compliance_score(issues)

    if high_count > 0 or score < 50:
        compliance_status = "Critical Violation"
        overall_status = "FAIL"
    elif issues:
        compliance_status = "Requires Revision"
        overall_status = "FAIL"
    else:
        compliance_status = "Pass"
        overall_status = "PASS"

    diff_html = generate_html_diff(content, corrected)

    return {
        "organization_id": org["id"],
        "organization_name": org["name"],
        "total_violations": len(issues),
        "compliance_score": score,
        "compliance_status": compliance_status,
        "overall_status": overall_status,
        "severity_breakdown": {"high": high_count, "medium": med_count, "low": low_count},
        "issues": issues,
        "corrected_text": corrected.strip(),
        "diff_html": diff_html,
        "explanation_of_changes": changes_explanation if changes_explanation else ["No changes required; text is fully compliant."],
        "retrieved_evidence": retrieved_rules,
        "logo_audit": logo_audit
    }

async def evaluate_content_rag(
    content: str,
    organization_id: str,
    image_bytes: Optional[bytes] = None,
    mime_type: Optional[str] = None
) -> Dict[str, Any]:
    org = get_organization(organization_id)
    if not org:
        raise ValueError(f"Organization '{organization_id}' not found.")

    retrieved_rules = retrieve_relevant_rules(organization_id, content, top_k=4)
    retrieved_context = "\n".join([f"- {r}" for r in retrieved_rules]) if retrieved_rules else org["guidelines"]

    logo_audit = None
    if image_bytes and org.get("logo_path"):
        approved_colors = [c.strip() for c in (org.get("brand_colors_hex") or "").split(",") if c.strip()]
        logo_audit = verify_ad_logo(
            ad_image_bytes=image_bytes,
            master_logo_path=org["logo_path"],
            approved_hex_colors=approved_colors
        )

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key.startswith("your-"):
        logger.info(f"OpenAI API key not set. Running local RAG heuristic audit for '{org['name']}'.")
        return evaluate_locally_fallback(content, org, retrieved_rules, image_bytes=image_bytes)

    client = OpenAI(api_key=api_key)

    system_prompt = f"""
You are Brand Shield Guardian, an expert evidence-based brand compliance officer and content auto-fixer.
You are evaluating marketing content specifically for: '{org['name']}'.

CORE PRINCIPLES:
1. RETRIEVE FIRST, COMPARE SECOND: Use only the retrieved brand rules for this organization.
2. CITATION DISCIPLINE: Cite the specific rule title or section for every flagged violation.
3. ONE-CLICK AUTO-FIX: Generate a complete, polished 'corrected_text' that is 100% compliant with the organization's rules while preserving the creator's core message and engaging marketing tone.
4. EXPLAIN CHANGES: Provide clear bulleted points in 'explanation_of_changes' explaining why specific phrases were altered.

OUTPUT MUST BE VALID JSON:
{{
  "total_violations": <int>,
  "compliance_score": <int between 0 and 100>,
  "compliance_status": "Pass | Requires Revision | Critical Violation",
  "overall_status": "PASS | FAIL | NEEDS_REVIEW",
  "severity_breakdown": {{"high": <int>, "medium": <int>, "low": <int>}},
  "issues": [
    {{
      "issue_type": "forbidden_term | factual_contradiction | unsupported_claim | tone_violation | visual_mismatch",
      "severity": "high | medium | low",
      "detected_text": "Exact snippet from submitted content",
      "rule_violated": "Specific rule citation from active brand ruleset",
      "explanation": "Why this snippet violates the active organization policy",
      "evidence": "Supporting guideline evidence retrieved from FAISS",
      "suggested_fix": "Compliant wording alternative",
      "confidence": 0.95
    }}
  ],
  "corrected_text": "Complete compliant version of the marketing text with all fixes applied",
  "explanation_of_changes": [
    "Replaced prohibited term X with compliant description Y to adhere to Rule Z."
  ]
}}
"""

    user_text = f"""
[ACTIVE ORGANIZATION BRAND KIT]
Organization: {org['name']}
Description: {org.get('description', '')}

[RELEVANT BRAND RULES RETRIEVED BY FAISS]
{retrieved_context}

[FULL GUIDELINES REFERENCE]
{org['guidelines']}

[SUBMITTED MARKETING CONTENT]
{content if content else "[Visual Creative attached for evaluation]"}
"""

    try:
        messages = [{"role": "system", "content": system_prompt}]

        if image_bytes:
            b64_img = base64.b64encode(image_bytes).decode("utf-8")
            img_mime = mime_type or "image/png"
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": user_text},
                    {"type": "image_url", "image_url": {"url": f"data:{img_mime};base64,{b64_img}"}}
                ]
            })
        else:
            messages.append({"role": "user", "content": user_text})

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.1
        )

        res_data = json.loads(response.choices[0].message.content)
        res_data["organization_id"] = org["id"]
        res_data["organization_name"] = org["name"]
        res_data["retrieved_evidence"] = retrieved_rules

        if logo_audit and logo_audit.get("violations"):
            res_data["issues"].extend(logo_audit["violations"])
            res_data["total_violations"] = len(res_data["issues"])
            res_data["compliance_score"] = calculate_compliance_score(res_data["issues"])
            high_c = sum(1 for i in res_data["issues"] if i["severity"] == "high")
            if high_c > 0:
                res_data["compliance_status"] = "Critical Violation"
                res_data["overall_status"] = "FAIL"

            for lv in logo_audit["violations"]:
                res_data.setdefault("explanation_of_changes", []).append(f"Visual Logo Alert: {lv['explanation']}")

        res_data["logo_audit"] = logo_audit
        corrected = res_data.get("corrected_text", content)
        res_data["diff_html"] = generate_html_diff(content, corrected)

        if not res_data.get("explanation_of_changes"):
            res_data["explanation_of_changes"] = [
                f"Updated copy to adhere to {org['name']} compliance rules while maintaining creator tone."
            ]

        return res_data

    except Exception as e:
        logger.error(f"OpenAI evaluation failed: {e}. Falling back to local heuristic audit.")
        return evaluate_locally_fallback(content, org, retrieved_rules, image_bytes=image_bytes)

# ----------------- Dedicated POST /evaluate-creative Engine -----------------
async def evaluate_creative_visual(
    ad_image_bytes: bytes,
    organization_id: str,
    ad_mime_type: str = "image/png"
) -> Dict[str, Any]:
    """
    Dedicated Visual Creative Compliance Evaluator:
    1. Loads the organization's stored reference_logo.png.
    2. Retrieves visual guidelines from FAISS vector store.
    3. Runs mathematical logo detection, aspect ratio & color analysis.
    4. Submits both images (master logo + marketing ad) to Vision Model API.
    5. Returns unified pass/fail and visual feedback.
    """
    org = get_organization(organization_id)
    if not org:
        raise ValueError(f"Organization '{organization_id}' not found.")

    logo_path = org.get("logo_path")
    if not logo_path or not os.path.exists(logo_path):
        standard_path = os.path.join("data", "orgs", organization_id, "reference_logo.png")
        if os.path.exists(standard_path):
            logo_path = standard_path
        else:
            raise ValueError(f"No reference logo registered for organization '{org['name']}'. Please upload reference_logo.png first.")

    with open(logo_path, "rb") as f:
        ref_logo_bytes = f.read()

    ref_logo_b64 = base64.b64encode(ref_logo_bytes).decode("utf-8")
    ad_b64 = base64.b64encode(ad_image_bytes).decode("utf-8")

    visual_rules = retrieve_relevant_rules(
        organization_id,
        "logo placement clearspace visual identity aspect ratio colors distortion header footer",
        top_k=4
    )
    rules_text = "\n".join([f"- {r}" for r in visual_rules]) if visual_rules else org.get("guidelines", "")

    approved_colors = [c.strip() for c in (org.get("brand_colors_hex") or "#1E3A8A, #06B6D4, #FFFFFF").split(",") if c.strip()]
    cv_logo_audit = verify_ad_logo(
        ad_image_bytes=ad_image_bytes,
        master_logo_path=logo_path,
        approved_hex_colors=approved_colors
    )

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key.startswith("your-"):
        logo_detected = cv_logo_audit.get("logo_detected", False)
        ar_valid = cv_logo_audit.get("aspect_ratio_valid", False)
        col_valid = cv_logo_audit.get("color_valid", False)

        feedback = []
        if logo_detected:
            feedback.append(f"Brand logo detected in creative (confidence: {int(cv_logo_audit.get('match_confidence', 0.8) * 100)}%).")
            if ar_valid:
                feedback.append(f"Aspect ratio is correct ({cv_logo_audit.get('detected_aspect_ratio')}:1). No stretching.")
            else:
                feedback.append(f"Logo aspect ratio is distorted ({cv_logo_audit.get('aspect_ratio_deviation_pct')}% deviation).")
            if col_valid:
                feedback.append("Logo colors conform to approved brand palette.")
            else:
                feedback.append(f"Unapproved colors found: {', '.join(cv_logo_audit.get('detected_hex_colors', []))}.")
        else:
            feedback.append("Master reference logo was not detected in the creative image.")

        has_high_issue = any(v.get("severity") == "high" for v in cv_logo_audit.get("violations", []))
        status = "FAIL" if (has_high_issue or not logo_detected or not ar_valid) else "PASS"

        return {
            "organization_id": org["id"],
            "organization_name": org["name"],
            "overall_status": status,
            "logo_found": logo_detected,
            "placement": "header / top section" if logo_detected else "not_found",
            "aspect_ratio_valid": ar_valid,
            "accurate_variant": logo_detected and col_valid,
            "color_valid": col_valid,
            "confidence_score": cv_logo_audit.get("match_confidence", 0.85),
            "visual_feedback": feedback,
            "issues": cv_logo_audit.get("violations", []),
            "retrieved_visual_rules": visual_rules,
            "cropped_logo_b64": cv_logo_audit.get("cropped_logo_b64", ""),
            "reference_logo_b64": ref_logo_b64,
            "logo_audit": cv_logo_audit
        }

    client = OpenAI(api_key=api_key)

    system_prompt = f"""
You are Brand Shield Guardian's Chief Visual Identity & Logo Compliance Officer.
Your task is to compare an official reference logo against a submitted marketing creative image for organization: '{org['name']}'.

You are provided with:
1. Image 1: The official approved reference logo.
2. Image 2: The submitted marketing creative asset.

Check and verify:
1. Logo Presence & Placement: Is Image 1 present in Image 2? Where is it placed (e.g. top-left, top-right, bottom-center)?
2. Accurate Variant: Is it the authentic approved variant? Has it been recolored, outlined, modified, or missing trademark elements?
3. Aspect Ratio & Distortion: Is the logo stretched, squashed, rotated, skewed, or low-resolution?
4. Clearspace & Background: Is there sufficient breathing room, or is it crowded by text/elements?

Cross-reference with these Brand Rules:
{rules_text}

OUTPUT MUST BE VALID JSON:
{{
  "overall_status": "PASS | FAIL | NEEDS_REVIEW",
  "logo_found": <bool>,
  "placement": "top-right | top-left | bottom-center | header | footer | not_found",
  "aspect_ratio_valid": <bool>,
  "accurate_variant": <bool>,
  "color_valid": <bool>,
  "confidence_score": <float between 0.0 and 1.0>,
  "visual_feedback": [
    "Clear bullet point explaining observation..."
  ],
  "issues": [
    {{
      "issue_type": "visual_mismatch",
      "severity": "high | medium | low",
      "detected_text": "Visual item or snippet",
      "rule_violated": "Specific visual rule citation",
      "explanation": "Why this violates visual compliance",
      "suggested_fix": "Recommended correction"
    }}
  ]
}}
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Here is the official reference logo (Image 1) and the marketing creative (Image 2). Evaluate visual compliance strictly:"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{ref_logo_b64}"}},
                {"type": "image_url", "image_url": {"url": f"data:{ad_mime_type};base64,{ad_b64}"}}
            ]
        }
    ]

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.1
        )
        res_data = json.loads(response.choices[0].message.content)
        res_data["organization_id"] = org["id"]
        res_data["organization_name"] = org["name"]
        res_data["retrieved_visual_rules"] = visual_rules
        res_data["cropped_logo_b64"] = cv_logo_audit.get("cropped_logo_b64", "")
        res_data["reference_logo_b64"] = ref_logo_b64
        res_data["logo_audit"] = cv_logo_audit

        if cv_logo_audit.get("violations"):
            existing_explanations = [i.get("explanation") for i in res_data.get("issues", [])]
            for v in cv_logo_audit["violations"]:
                if v.get("explanation") not in existing_explanations:
                    res_data["issues"].append(v)
            if any(v.get("severity") == "high" for v in cv_logo_audit["violations"]):
                res_data["overall_status"] = "FAIL"

        return res_data
    except Exception as e:
        logger.error(f"Vision model evaluation failed: {e}. Falling back to computer vision logo checker.")
        return evaluate_locally_fallback(
            content="[Visual Creative Image Evaluation]",
            org=org,
            retrieved_rules=visual_rules,
            image_bytes=ad_image_bytes
        )