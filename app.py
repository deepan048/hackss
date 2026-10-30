"""
Brand Shield Guardian - Streamlit Multi-Organization Dashboard, Diff Engine & Creative Visual Verifier
Interactive Pre-Publication Brand Governance, Per-Org Reference Logo Management & Visual Compliance Verification
"""

import streamlit as st
import requests
import json
import os
import base64
from typing import Dict, Any, List, Optional

st.set_page_config(
    page_title="Brand Shield Guardian",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

BACKEND_URL = "http://127.0.0.1:8000"

# ----------------- Modern Dark Theme Styling -----------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 3rem;
        max-width: 1240px;
    }

    .brand-header {
        background: linear-gradient(135deg, #090d16 0%, #1e1b4b 50%, #0f172a 100%);
        border: 1px solid #312e81;
        border-radius: 16px;
        padding: 22px 26px;
        margin-bottom: 22px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4);
    }

    .brand-title {
        font-size: 2.1rem;
        font-weight: 800;
        background: linear-gradient(90deg, #60a5fa, #a78bfa, #f472b6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
        display: flex;
        align-items: center;
        gap: 12px;
    }

    .brand-subtitle {
        color: #94a3b8;
        font-size: 0.92rem;
        margin-top: 4px;
        margin-bottom: 0;
    }

    .ruleset-pill {
        display: inline-flex;
        align-items: center;
        gap: 12px;
        background: rgba(99, 102, 241, 0.15);
        border: 1px solid #4f46e5;
        border-radius: 12px;
        padding: 8px 18px;
        font-size: 0.9rem;
        color: #c7d2fe;
        font-weight: 600;
        margin-bottom: 18px;
    }

    .metric-card {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 16px 18px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
    }

    .metric-label {
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #94a3b8;
        font-weight: 600;
        margin-bottom: 4px;
    }

    .metric-value {
        font-size: 1.6rem;
        font-weight: 800;
        color: #f8fafc;
    }

    .status-banner-fail {
        background: linear-gradient(90deg, rgba(239, 68, 68, 0.18), rgba(185, 28, 28, 0.06));
        border-left: 5px solid #ef4444;
        border-radius: 10px;
        padding: 16px 20px;
        margin-bottom: 20px;
    }

    .status-banner-pass {
        background: linear-gradient(90deg, rgba(16, 185, 129, 0.18), rgba(4, 120, 87, 0.06));
        border-left: 5px solid #10b981;
        border-radius: 10px;
        padding: 16px 20px;
        margin-bottom: 20px;
    }

    .status-banner-review {
        background: linear-gradient(90deg, rgba(245, 158, 11, 0.18), rgba(180, 83, 9, 0.06));
        border-left: 5px solid #f59e0b;
        border-radius: 10px;
        padding: 16px 20px;
        margin-bottom: 20px;
    }

    .badge-critical {
        background-color: #ef4444;
        color: #ffffff;
        font-size: 0.72rem;
        font-weight: 700;
        padding: 3px 8px;
        border-radius: 9999px;
        text-transform: uppercase;
        display: inline-block;
    }

    .badge-revision {
        background-color: #f59e0b;
        color: #0f172a;
        font-size: 0.72rem;
        font-weight: 700;
        padding: 3px 8px;
        border-radius: 9999px;
        text-transform: uppercase;
        display: inline-block;
    }

    .badge-advisory {
        background-color: #3b82f6;
        color: #ffffff;
        font-size: 0.72rem;
        font-weight: 700;
        padding: 3px 8px;
        border-radius: 9999px;
        text-transform: uppercase;
        display: inline-block;
    }

    .diff-box {
        background-color: #1e293b;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 18px 20px;
        min-height: 140px;
        font-size: 1.02rem;
        line-height: 1.65;
        color: #f1f5f9;
    }

    .diff-box-original {
        border-left: 4px solid #ef4444;
    }

    .diff-box-corrected {
        border-left: 4px solid #10b981;
    }

    .violation-highlight {
        background-color: rgba(239, 68, 68, 0.25);
        color: #fca5a5;
        padding: 2px 6px;
        border-radius: 4px;
        font-weight: 600;
    }

    .color-chip {
        display: inline-block;
        width: 18px;
        height: 18px;
        border-radius: 4px;
        border: 1px solid #475569;
        vertical-align: middle;
        margin-right: 4px;
    }

    .creative-card {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 18px;
        margin-top: 14px;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

def check_backend_alive() -> bool:
    try:
        r = requests.get(f"{BACKEND_URL}/health", timeout=1.0)
        return r.status_code == 200
    except Exception:
        return False

def api_get_organizations() -> List[Dict[str, Any]]:
    if check_backend_alive():
        try:
            res = requests.get(f"{BACKEND_URL}/organizations", timeout=5)
            if res.status_code == 200:
                return res.json()
        except Exception:
            pass

    try:
        from database import get_all_organizations
        return get_all_organizations()
    except Exception:
        return []

def api_create_organization(org_id: str, name: str, description: str, guidelines: str, brand_colors_hex: str, logo_bytes: Optional[bytes] = None, logo_name: Optional[str] = None) -> bool:
    success = False
    if check_backend_alive():
        try:
            payload = {
                "id": org_id,
                "name": name,
                "description": description,
                "guidelines": guidelines,
                "brand_colors_hex": brand_colors_hex
            }
            res = requests.post(f"{BACKEND_URL}/organizations", json=payload, timeout=10)
            if res.status_code in (200, 201):
                success = True
                if logo_bytes and logo_name:
                    files = {"file": (logo_name, logo_bytes, "image/png")}
                    requests.post(f"{BACKEND_URL}/organizations/{org_id}/logo", files=files, timeout=10)
                return True
        except Exception:
            pass

    try:
        from database import create_organization, save_organization_logo
        from vector_store import build_or_update_org_index
        create_organization(org_id, name, description, guidelines, brand_colors_hex=brand_colors_hex)
        build_or_update_org_index(org_id, guidelines)
        if logo_bytes and logo_name:
            save_organization_logo(org_id, logo_bytes, logo_name)
        return True
    except Exception:
        return False

def api_update_organization(org_id: str, name: str, description: str, guidelines: str, brand_colors_hex: str, logo_bytes: Optional[bytes] = None, logo_name: Optional[str] = None) -> bool:
    if check_backend_alive():
        try:
            payload = {
                "name": name,
                "description": description,
                "guidelines": guidelines,
                "brand_colors_hex": brand_colors_hex
            }
            res = requests.put(f"{BACKEND_URL}/organizations/{org_id}", json=payload, timeout=10)
            if res.status_code == 200:
                if logo_bytes and logo_name:
                    files = {"file": (logo_name, logo_bytes, "image/png")}
                    requests.post(f"{BACKEND_URL}/organizations/{org_id}/logo", files=files, timeout=10)
                return True
        except Exception:
            pass

    try:
        from database import update_organization, save_organization_logo
        from vector_store import build_or_update_org_index
        update_organization(org_id, name, description, guidelines, brand_colors_hex=brand_colors_hex)
        build_or_update_org_index(org_id, guidelines)
        if logo_bytes and logo_name:
            save_organization_logo(org_id, logo_bytes, logo_name)
        return True
    except Exception:
        return False

def api_upload_reference_logo(org_id: str, filename: str, file_bytes: bytes) -> bool:
    if check_backend_alive():
        try:
            files = {"file": (filename, file_bytes, "image/png")}
            res = requests.post(f"{BACKEND_URL}/organizations/{org_id}/logo", files=files, timeout=10)
            return res.status_code == 200
        except Exception:
            pass

    try:
        from database import save_organization_logo
        save_organization_logo(org_id, file_bytes, filename)
        return True
    except Exception:
        return False

def api_delete_organization(org_id: str) -> bool:
    if check_backend_alive():
        try:
            res = requests.delete(f"{BACKEND_URL}/organizations/{org_id}", timeout=5)
            return res.status_code == 200
        except Exception:
            pass

    try:
        from database import delete_organization
        from vector_store import delete_org_index
        delete_organization(org_id)
        delete_org_index(org_id)
        return True
    except Exception:
        return False

def execute_evaluate_text(organization_id: str, content: str) -> Dict[str, Any]:
    if check_backend_alive():
        try:
            payload = {"content": content, "organization_id": organization_id}
            res = requests.post(f"{BACKEND_URL}/evaluate", json=payload, timeout=60)
            if res.status_code == 200:
                return res.json()
            else:
                try:
                    err = res.json().get("detail", res.text)
                except Exception:
                    err = res.text
                return {"error": f"API Error (HTTP {res.status_code}): {err}"}
        except Exception:
            pass

    try:
        import asyncio
        from engine import evaluate_content_rag
        loop = asyncio.new_event_loop()
        res = loop.run_until_complete(evaluate_content_rag(content=content, organization_id=organization_id))
        loop.close()
        res["extracted_text"] = content
        return res
    except Exception as e:
        return {"error": f"Text evaluation failed: {e}"}

def execute_evaluate_creative(organization_id: str, filename: str, file_bytes: bytes, mime_type: str) -> Dict[str, Any]:
    """Calls POST /evaluate-creative on FastAPI backend or in-process engine."""
    if check_backend_alive():
        try:
            files = {"file": (filename, file_bytes, mime_type)}
            data = {"organization_id": organization_id}
            res = requests.post(f"{BACKEND_URL}/evaluate-creative", data=data, files=files, timeout=60)
            if res.status_code == 200:
                return res.json()
            else:
                try:
                    err = res.json().get("detail", res.text)
                except Exception:
                    err = res.text
                return {"error": f"Creative Verification Error (HTTP {res.status_code}): {err}"}
        except Exception:
            pass

    try:
        import asyncio
        from engine import evaluate_creative_visual
        from backend import extract_text_from_pdf

        if filename.lower().endswith(".pdf") or "pdf" in mime_type:
            pdf_res = extract_text_from_pdf(file_bytes)
            if pdf_res.get("rendered_image_b64"):
                file_bytes = base64.b64decode(pdf_res["rendered_image_b64"])
                mime_type = "image/png"

        loop = asyncio.new_event_loop()
        res = loop.run_until_complete(evaluate_creative_visual(
            ad_image_bytes=file_bytes,
            organization_id=organization_id,
            ad_mime_type=mime_type
        ))
        loop.close()
        return res
    except Exception as e:
        return {"error": f"Visual creative verification failed: {e}"}

# ----------------- Sidebar: Organization Ruleset Switcher -----------------
with st.sidebar:
    st.markdown("### 🏢 Multi-Org Brand Kits")

    orgs = api_get_organizations()
    if not orgs:
        from database import init_db
        init_db()
        orgs = api_get_organizations()

    org_options = {f"{o['name']} ({o['id']})": o['id'] for o in orgs}
    org_display_names = list(org_options.keys())

    selected_display = st.selectbox(
        "Active Brand Ruleset",
        options=org_display_names,
        index=0 if org_display_names else 0,
        help="Select which Organization's brand kit & reference logo to evaluate against."
    )
    active_org_id = org_options.get(selected_display) if selected_display else (orgs[0]["id"] if orgs else "org_default")
    active_org = next((o for o in orgs if o["id"] == active_org_id), orgs[0] if orgs else None)

    if active_org:
        st.caption(f"**Description:** {active_org.get('description', 'Standard guidelines')}")

        # Prominently Display Reference Logo
        logo_path = active_org.get("logo_path")
        if not logo_path or not os.path.exists(logo_path):
            std_path = os.path.join("data", "orgs", active_org_id, "reference_logo.png")
            if os.path.exists(std_path):
                logo_path = std_path

        if logo_path and os.path.exists(logo_path):
            st.markdown("**Official Reference Logo:**")
            st.image(logo_path, caption=f"{active_org['name']} Reference Logo", width=170)
        else:
            st.warning("⚠️ No reference logo uploaded yet.")

        # Display Brand Colors
        brand_colors = [c.strip() for c in (active_org.get("brand_colors_hex") or "#1E3A8A, #FFFFFF").split(",") if c.strip()]
        st.markdown("**Approved Brand Palette:**")
        chips_html = "".join([f"<span class='color-chip' style='background-color: {c};'></span><code>{c}</code> " for c in brand_colors])
        st.markdown(chips_html, unsafe_allow_html=True)

        with st.expander("📖 View Brand Guidelines", expanded=False):
            st.text_area("Rules", active_org["guidelines"], height=130, disabled=True)

    st.divider()

    # 1. Upload / Replace Reference Logo
    if active_org:
        with st.expander("🎨 Upload / Replace Reference Logo"):
            logo_up = st.file_uploader("Select Logo Image (PNG, JPG, SVG)", type=["png", "jpg", "jpeg", "svg"], key="side_logo_up")
            if logo_up and st.button("Save Reference Logo", type="primary"):
                if api_upload_reference_logo(active_org_id, logo_up.name, logo_up.getvalue()):
                    st.success("Reference logo saved in data/orgs/{org_id}/reference_logo.png!")
                    st.rerun()
                else:
                    st.error("Failed to upload reference logo.")

    # 2. Create New Brand Ruleset (with Logo upload)
    with st.expander("➕ Create New Brand Kit"):
        new_name = st.text_input("Brand / Org Name", placeholder="e.g. Apex Health - EMEA Social")
        new_id = st.text_input("Ruleset ID (slug)", placeholder="e.g. org_apex_emea")
        new_desc = st.text_input("Description", placeholder="e.g. B2C social media rules for European markets")
        new_colors = st.text_input("Approved HEX Colors", value="#1E3A8A, #06B6D4, #FFFFFF")
        new_guide = st.text_area("Brand Rules & Terminology", placeholder="Rule 1: Never use...\nRule 2: Nomenclature...", height=110)
        new_logo_file = st.file_uploader("Upload Reference Logo (PNG/JPG)", type=["png", "jpg", "jpeg", "svg"], key="new_org_logo")

        if st.button("Save & Index Brand Kit"):
            if not new_name.strip() or not new_guide.strip():
                st.error("Name and Guidelines cannot be empty.")
            else:
                slug = new_id.strip() if new_id.strip() else f"org_{new_name.lower().replace(' ', '_')[:12]}"
                l_bytes = new_logo_file.getvalue() if new_logo_file else None
                l_name = new_logo_file.name if new_logo_file else None
                if api_create_organization(slug, new_name, new_desc, new_guide, new_colors, l_bytes, l_name):
                    st.success(f"Brand Kit '{new_name}' created with FAISS vector store and reference logo!")
                    st.rerun()
                else:
                    st.error("Failed to create brand kit.")

    # 3. Edit Active Ruleset
    if active_org:
        with st.expander("✏️ Edit Active Ruleset"):
            edit_name = st.text_input("Edit Name", value=active_org["name"], key="edit_name")
            edit_desc = st.text_input("Edit Description", value=active_org.get("description", ""), key="edit_desc")
            edit_colors = st.text_input("Approved HEX Colors", value=active_org.get("brand_colors_hex", "#1E3A8A, #FFFFFF"), key="edit_colors")
            edit_guide = st.text_area("Edit Guidelines", value=active_org["guidelines"], height=120, key="edit_guide")
            edit_logo_file = st.file_uploader("Replace Reference Logo (Optional)", type=["png", "jpg", "jpeg"], key="edit_logo_up")

            if st.button("Update Brand Kit"):
                el_bytes = edit_logo_file.getvalue() if edit_logo_file else None
                el_name = edit_logo_file.name if edit_logo_file else None
                if api_update_organization(active_org_id, edit_name, edit_desc, edit_guide, edit_colors, el_bytes, el_name):
                    st.success("Brand kit updated!")
                    st.rerun()
                else:
                    st.error("Update failed.")

        with st.expander("🗑️ Delete Ruleset"):
            st.warning(f"Delete '{active_org['name']}'?")
            if st.button("Confirm Delete", key="btn_del"):
                if len(orgs) <= 1:
                    st.error("Cannot delete the only remaining organization ruleset.")
                else:
                    if api_delete_organization(active_org_id):
                        st.success("Ruleset deleted.")
                        st.rerun()

    st.divider()
    backend_status = check_backend_alive()
    if backend_status:
        st.success("🟢 FastAPI Backend: **Connected (Port 8000)**")
    else:
        st.info("🟡 Engine: **Standalone Local RAG Mode**")

# ----------------- Main Dashboard -----------------
st.markdown("""
<div class="brand-header">
    <div class="brand-title">
        🛡️ Brand Shield Guardian
    </div>
    <p class="brand-subtitle">
        Automated Pre-Publication AI Brand Governance, Reference Logo Verifier & Real-Time Diff Engine
    </p>
</div>
""", unsafe_allow_html=True)

# Active Organization Header Badge with Logo
if active_org:
    col_pill1, col_pill2 = st.columns([3, 1])
    with col_pill1:
        st.markdown(f"""
        <div class="ruleset-pill">
            <span>🏢 Active Organization: <b>{active_org['name']}</b></span>
            <span>|</span>
            <span>🔍 FAISS Vector Store: <b>Active</b></span>
        </div>
        """, unsafe_allow_html=True)
    with col_pill2:
        logo_path = active_org.get("logo_path")
        if logo_path and os.path.exists(logo_path):
            st.image(logo_path, width=120, caption="Active Reference Logo")

# Main Modes: 1. Visual Creative Compliance (/evaluate-creative) | 2. Marketing Copy & Diff Engine (/evaluate)
main_tab1, main_tab2 = st.tabs([
    "🖼️ Visual Creative & Logo Verification (POST /evaluate-creative)",
    "📝 Marketing Copy & Diff Engine (POST /evaluate)"
])

# ==============================================================================
# TAB 1: Visual Creative & Logo Compliance Evaluation (POST /evaluate-creative)
# ==============================================================================
with main_tab1:
    st.markdown("### 🎨 Visual Creative Compliance & Logo Integrity Audit")
    st.caption("Upload a marketing flyer, social banner, or ad image. The engine loads the active organization's `reference_logo.png`, inspects placement, accurate variant, aspect ratio distortion, and cross-references visual guidelines from FAISS.")

    col_c_in1, col_c_in2 = st.columns([2, 1], gap="medium")

    with col_c_in1:
        creative_upload = st.file_uploader(
            "Upload Marketing Asset (PNG, JPG, PDF)",
            type=["png", "jpg", "jpeg", "pdf"],
            key="creative_eval_file"
        )
        if creative_upload and creative_upload.name.lower().endswith((".png", ".jpg", ".jpeg")):
            st.image(creative_upload, caption="Uploaded Marketing Creative Asset", width=360)

    with col_c_in2:
        st.markdown("#### 🎯 Active Verification Kit")
        if active_org and active_org.get("logo_path") and os.path.exists(active_org["logo_path"]):
            st.image(active_org["logo_path"], caption=f"Master Reference Logo ({active_org['name']})", width=180)
        else:
            st.info("No master logo uploaded yet for this organization. You can upload one in the sidebar.")

        st.markdown(f"**Target Organization:** `{active_org['name']}`")
        st.markdown(f"**FAISS Visual Identity Index:** `Loaded & Ready`")

    btn_eval_creative = st.button("🚀 Evaluate Creative Visual Compliance", type="primary", use_container_width=True, key="btn_eval_creative")

    if btn_eval_creative:
        if not creative_upload:
            st.warning("Please upload a marketing creative image or PDF.")
        else:
            with st.spinner("🔍 Comparing creative asset against reference_logo.png and grounding visual rules via FAISS..."):
                creative_res = execute_evaluate_creative(
                    organization_id=active_org_id,
                    filename=creative_upload.name,
                    file_bytes=creative_upload.getvalue(),
                    mime_type=creative_upload.type
                )

            if "error" in creative_res:
                st.error(f"❌ {creative_res['error']}")
            else:
                st.session_state["creative_result"] = creative_res

    # Display Creative Verification Results
    if "creative_result" in st.session_state:
        c_res = st.session_state["creative_result"]
        c_status = str(c_res.get("overall_status", "FAIL")).upper()
        logo_found = c_res.get("logo_found", False)
        placement = c_res.get("placement", "not_found")
        ar_valid = c_res.get("aspect_ratio_valid", False)
        variant_valid = c_res.get("accurate_variant", False)
        conf_score = int(c_res.get("confidence_score", 0.9) * 100)
        feedback_list = c_res.get("visual_feedback", [])
        c_issues = c_res.get("issues", [])
        ref_b64 = c_res.get("reference_logo_b64", "")
        crop_b64 = c_res.get("cropped_logo_b64", "")
        logo_audit_data = c_res.get("logo_audit", {})

        st.divider()

        # Status Banner
        if c_status == "PASS" and logo_found and ar_valid:
            st.markdown(f"""
            <div class="status-banner-pass">
                <h3 style="margin: 0; color: #10b981;">🟢 VISUAL COMPLIANCE: PASS (Confidence: {conf_score}%)</h3>
                <p style="margin: 4px 0 0 0; color: #cbd5e1;">The marketing creative properly displays the official reference logo for <b>{c_res.get('organization_name')}</b> without distortion or unapproved alterations.</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="status-banner-fail">
                <h3 style="margin: 0; color: #ef4444;">🔴 VISUAL COMPLIANCE: FAIL / VIOLATION DETECTED</h3>
                <p style="margin: 4px 0 0 0; color: #cbd5e1;">Visual identity violations detected against <b>{c_res.get('organization_name')}</b>. Review logo placement, distortion, or unapproved alterations below.</p>
            </div>
            """, unsafe_allow_html=True)

        # Visual Comparison Grid
        st.markdown("#### 🔍 Visual Asset Comparison")
        col_v1, col_v2, col_v3, col_v4 = st.columns([1.2, 1.2, 1.3, 1.3], gap="medium")

        with col_v1:
            st.markdown("**Official Reference Logo:**")
            if ref_b64:
                st.markdown(f'<img src="data:image/png;base64,{ref_b64}" width="150" style="border: 1px solid #475569; border-radius: 8px; padding: 6px; background: #0f172a;" />', unsafe_allow_html=True)
            elif active_org and active_org.get("logo_path") and os.path.exists(active_org["logo_path"]):
                st.image(active_org["logo_path"], width=150)
            st.caption(f"Target Ratio: **{logo_audit_data.get('master_aspect_ratio', 'N/A')}:1**")

        with col_v2:
            st.markdown("**Detected Logo in Creative:**")
            if crop_b64:
                st.markdown(f'<img src="data:image/png;base64,{crop_b64}" width="150" style="border: 1px solid #475569; border-radius: 8px; padding: 6px; background: #0f172a;" />', unsafe_allow_html=True)
            else:
                st.caption("No logo crop available.")
            st.caption(f"Detected Ratio: **{logo_audit_data.get('detected_aspect_ratio', 'N/A')}:1**")

        with col_v3:
            st.markdown("**Placement & Presence:**")
            if logo_found:
                st.success(f"✅ Logo Present (`{placement}`)")
            else:
                st.error("❌ Logo Missing / Unrecognized")

            if ar_valid:
                st.success("✅ Aspect Ratio Preserved")
            else:
                dev = logo_audit_data.get('aspect_ratio_deviation_pct', 0)
                st.error(f"❌ Distorted ({dev}% deviation)")

        with col_v4:
            st.markdown("**Variant & Palette:**")
            if variant_valid:
                st.success("✅ Authentic Approved Variant")
            else:
                st.warning("⚠️ Unapproved Variant / Color")

            col_val = logo_audit_data.get("color_valid", True)
            if col_val:
                st.success("✅ Brand Colors Matched")
            else:
                st.error("❌ Palette Deviation")

        # Visual Feedback Observations
        if feedback_list:
            st.markdown("#### 📋 Vision Model Feedback & Observations")
            with st.container():
                st.markdown('<div class="creative-card">', unsafe_allow_html=True)
                for fb in feedback_list:
                    st.markdown(f"- {fb}")
                st.markdown('</div>', unsafe_allow_html=True)

        # Flagged Visual Issues
        if c_issues:
            st.markdown("#### ⚠️ Flagged Visual Violations")
            for i_idx, c_issue in enumerate(c_issues):
                with st.expander(f"Visual Violation #{i_idx+1}: {c_issue.get('rule_violated', 'Visual Mismatch')}", expanded=True):
                    st.markdown(f"<span class='badge-critical'>CRITICAL VISUAL MISMATCH</span>", unsafe_allow_html=True)
                    st.markdown(f"**Non-Compliant Item:** `{c_issue.get('detected_text', 'N/A')}`")
                    st.markdown(f"**Explanation:** {c_issue.get('explanation', 'N/A')}")
                    st.markdown(f"**Suggested Fix:** {c_issue.get('suggested_fix', 'N/A')}")

        # Retrieved Visual Guidelines from FAISS
        ret_visual_rules = c_res.get("retrieved_visual_rules", [])
        with st.expander("🔍 View Visual Guidelines Grounded from FAISS"):
            if ret_visual_rules:
                for vr in ret_visual_rules:
                    st.markdown(f"- `{vr}`")
            else:
                st.caption("Active brand guidelines verified directly.")

# ==============================================================================
# TAB 2: Marketing Copy & Diff Engine (POST /evaluate)
# ==============================================================================
with main_tab2:
    st.markdown("### 📝 Marketing Text Governance & Interactive Diff Engine")
    st.caption("Evaluate ad copy against active guidelines, calculate compliance score, and generate One-Click Auto-Fixed copy with color-coded diff.")

    col_txt1, col_txt2 = st.columns([3, 1], gap="medium")

    with col_txt1:
        default_test_copy = "Get instant 1-day results with our miracle product! Order now before stock runs out."
        ad_text_input = st.text_area(
            "Draft Marketing Copy",
            value=st.session_state.get("draft_text", default_test_copy),
            height=130,
            placeholder="Paste marketing copy, headline, or email draft..."
        )

    with col_txt2:
        st.markdown("#### ⚡ Presets")
        if st.button("Cosmetics Ad Sample", use_container_width=True):
            st.session_state["draft_text"] = "Get guaranteed results in 1 day with our miracle product! Order now before stock runs out."
            st.rerun()

        if st.button("Enterprise Healthcare Sample", use_container_width=True):
            st.session_state["draft_text"] = "Complete cure guaranteed overnight with Lumina Tech! Contact our sales team now for discount."
            st.rerun()

        if st.button("Compliant Draft Sample", use_container_width=True):
            st.session_state["draft_text"] = "Lumina Health Enterprise: Clinical trials demonstrate visible improvement over 4 weeks of daily use."
            st.rerun()

    btn_eval_text = st.button("🚀 Evaluate Text & Generate Diff", type="primary", use_container_width=True, key="btn_eval_text")

    if btn_eval_text:
        if not ad_text_input.strip():
            st.warning("Please provide marketing copy.")
        else:
            with st.spinner(f"🔍 Grounding against '{active_org['name']}' ruleset and computing diff..."):
                txt_result = execute_evaluate_text(
                    organization_id=active_org_id,
                    content=ad_text_input
                )

            if "error" in txt_result:
                st.error(f"❌ {txt_result['error']}")
            else:
                st.session_state["text_result"] = txt_result

    # Display Text Audit Results
    if "text_result" in st.session_state:
        t_res = st.session_state["text_result"]
        t_violations = t_res.get("total_violations", 0)
        t_score = t_res.get("compliance_score", 100)
        t_status = str(t_res.get("overall_status", "FAIL")).upper()
        t_breakdown = t_res.get("severity_breakdown", {})
        t_high = t_breakdown.get("high", 0)
        t_med = t_breakdown.get("medium", 0)
        t_low = t_breakdown.get("low", 0)
        t_issues = t_res.get("issues", [])
        corrected_text = t_res.get("corrected_text", "")
        diff_html = t_res.get("diff_html", "")
        changes_exp = t_res.get("explanation_of_changes", [])

        st.divider()

        # Status Banner
        if "PASS" in t_status and t_violations == 0:
            st.markdown(f"""
            <div class="status-banner-pass">
                <h3 style="margin: 0; color: #10b981;">🟢 AUDIT RESULT: FULLY COMPLIANT (Score: {t_score}/100)</h3>
                <p style="margin: 4px 0 0 0; color: #cbd5e1;">Content strictly complies with <b>{t_res.get('organization_name')}</b> policies.</p>
            </div>
            """, unsafe_allow_html=True)
        elif t_high > 0:
            st.markdown(f"""
            <div class="status-banner-fail">
                <h3 style="margin: 0; color: #ef4444;">🔴 AUDIT RESULT: CRITICAL VIOLATIONS DETECTED (Score: {t_score}/100)</h3>
                <p style="margin: 4px 0 0 0; color: #cbd5e1;">Found {t_high} critical violation(s) against <b>{t_res.get('organization_name')}</b>.</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="status-banner-review">
                <h3 style="margin: 0; color: #f59e0b;">🟡 AUDIT RESULT: REQUIRES REVISION (Score: {t_score}/100)</h3>
                <p style="margin: 4px 0 0 0; color: #cbd5e1;">Identified {t_violations} guideline deviations against <b>{t_res.get('organization_name')}</b>.</p>
            </div>
            """, unsafe_allow_html=True)

        # Metric Grid
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        with col_m1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Total Violations</div>
                <div class="metric-value" style="color: {'#10b981' if t_violations == 0 else '#ef4444'};">{t_violations}</div>
            </div>
            """, unsafe_allow_html=True)
        with col_m2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Compliance Health</div>
                <div class="metric-value" style="color: {'#10b981' if t_score >= 85 else ('#ef4444' if t_score < 50 else '#f59e0b')};">{t_score} / 100</div>
            </div>
            """, unsafe_allow_html=True)
        with col_m3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Critical / High</div>
                <div class="metric-value" style="color: {'#10b981' if t_high == 0 else '#ef4444'};">{t_high}</div>
            </div>
            """, unsafe_allow_html=True)
        with col_m4:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Moderate / Advisory</div>
                <div class="metric-value" style="color: {'#10b981' if (t_med + t_low) == 0 else '#f59e0b'};">{t_med + t_low}</div>
            </div>
            """, unsafe_allow_html=True)

        # Diff View
        st.markdown("### 🔄 Interactive AI Content Fixer & Diff Engine")
        diff_tab1, diff_tab2 = st.tabs(["⚡ Side-by-Side Comparison", "🔍 Unified Color-Coded Diff View"])

        with diff_tab1:
            col_orig, col_fixed = st.columns(2, gap="large")
            with col_orig:
                st.markdown("#### ❌ Original Submitted Draft")
                st.markdown(f"""<div class="diff-box diff-box-original">{ad_text_input}</div>""", unsafe_allow_html=True)
            with col_fixed:
                st.markdown("#### ✨ One-Click Auto-Fixed Copy")
                st.markdown(f"""<div class="diff-box diff-box-corrected">{corrected_text}</div>""", unsafe_allow_html=True)

        with diff_tab2:
            st.markdown("#### 🔍 Word-Level Additions & Deletions")
            st.markdown(f"""<div class="diff-box">{diff_html}</div>""", unsafe_allow_html=True)

        col_act1, col_act2 = st.columns([1, 2], gap="small")
        with col_act1:
            st.download_button(
                label="📥 Download Audit Report (JSON)",
                data=json.dumps(t_res, indent=2),
                file_name=f"brand_shield_audit_{t_res.get('organization_id')}.json",
                mime="application/json",
                use_container_width=True
            )
        with col_act2:
            with st.expander("📋 View Copy-Ready Text Block"):
                st.code(corrected_text, language="text")

        if changes_exp:
            with st.expander("💡 View Explanation of Auto-Fix Changes", expanded=True):
                for exp in changes_exp:
                    st.markdown(f"- {exp}")

        # Granular Issues Breakdown
        if t_issues:
            st.markdown("### 📋 Granular Rule Violations & Citations")
            for idx, issue in enumerate(t_issues):
                sev = str(issue.get("severity", "medium")).lower()
                b_class = "badge-critical" if sev == "high" else ("badge-revision" if sev == "medium" else "badge-advisory")
                b_lbl = "CRITICAL VIOLATION" if sev == "high" else ("REQUIRES REVISION" if sev == "medium" else "ADVISORY")

                with st.expander(f"Violation #{idx+1}: {issue.get('rule_violated', 'Rule Violation')}", expanded=True):
                    st.markdown(f"<span class='{b_class}'>{b_lbl}</span> &nbsp; <b>Category:</b> <code>{issue.get('issue_type', 'General')}</code>", unsafe_allow_html=True)
                    st.markdown(f"**Non-Compliant Text Found:** <span class='violation-highlight'>{issue.get('detected_text', 'N/A')}</span>", unsafe_allow_html=True)
                    st.markdown(f"**Source Citation:** `{issue.get('rule_violated', 'Active Brand Policy')}`")
                    st.markdown(f"**Explanation:** {issue.get('explanation', 'N/A')}")
                    st.markdown(f"""
                    <div style="background-color: rgba(16, 185, 129, 0.15); border-left: 3px solid #10b981; border-radius: 6px; padding: 10px 14px; margin-top: 8px;">
                        <b style="color: #6ee7b7;">Suggested Compliant Reword:</b><br/>
                        <span style="color: #f1f5f9;">{issue.get('suggested_fix', 'No fix suggested')}</span>
                    </div>
                    """, unsafe_allow_html=True)
