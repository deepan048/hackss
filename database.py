"""
Brand Shield Guardian - Database Layer
SQLite Persistence for Multi-Organization Brand Rulesets, Guidelines & Per-Org Reference Logo Assets
"""

import sqlite3
import os
import shutil
from datetime import datetime
from typing import List, Optional, Dict, Any

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "rulesets.db")
ORGS_DIR = os.path.join(os.path.dirname(__file__), "data", "orgs")
os.makedirs(ORGS_DIR, exist_ok=True)

def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_org_dir(org_id: str) -> str:
    path = os.path.join(ORGS_DIR, org_id)
    os.makedirs(path, exist_ok=True)
    return path

def save_organization_logo(org_id: str, file_bytes: bytes, filename: str = "reference_logo.png") -> str:
    """Saves the uploaded reference logo inside data/orgs/{org_id}/reference_logo.png"""
    org_folder = get_org_dir(org_id)
    ext = filename.split(".")[-1].lower() if "." in filename else "png"
    if ext not in ["png", "jpg", "jpeg", "svg", "webp"]:
        ext = "png"

    target_name = f"reference_logo.{ext}"
    target_path = os.path.join(org_folder, target_name)
    with open(target_path, "wb") as f:
        f.write(file_bytes)

    rel_path = os.path.join("data", "orgs", org_id, target_name).replace("\\", "/")
    update_organization(org_id, logo_path=rel_path)
    return rel_path

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS organizations (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        guidelines TEXT NOT NULL,
        logo_path TEXT,
        brand_colors_hex TEXT,
        created_at TEXT,
        updated_at TEXT
    );
    """)
    conn.commit()

    # Migration check
    cursor.execute("PRAGMA table_info(organizations);")
    cols = [col["name"] for col in cursor.fetchall()]
    if "logo_path" not in cols:
        cursor.execute("ALTER TABLE organizations ADD COLUMN logo_path TEXT;")
    if "brand_colors_hex" not in cols:
        cursor.execute("ALTER TABLE organizations ADD COLUMN brand_colors_hex TEXT;")
    conn.commit()

    # Update or Seed Default Organizations
    cursor.execute("SELECT COUNT(*) as cnt FROM organizations;")
    count = cursor.fetchone()["cnt"]

    if count == 0:
        seed_default_organizations(conn)
    else:
        # Normalize existing logo paths to per-org directory
        cursor.execute("""
        UPDATE organizations
        SET logo_path = 'data/orgs/org_b2b_clinical/reference_logo.png',
            brand_colors_hex = '#1E3A8A, #06B6D4, #FFFFFF'
        WHERE id = 'org_b2b_clinical';
        """)
        cursor.execute("""
        UPDATE organizations
        SET logo_path = 'data/orgs/org_d2c_social/reference_logo.png',
            brand_colors_hex = '#EC4899, #F59E0B, #FFFFFF'
        WHERE id = 'org_d2c_social';
        """)
        conn.commit()

    conn.close()

def seed_default_organizations(conn):
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()

    default_orgs = [
        (
            "org_b2b_clinical",
            "Lumina Health - B2B Enterprise",
            "Strict healthcare, clinical trials, and regulatory compliance standards for enterprise marketing.",
            """Rule 1 (Clinical Validation): All clinical efficacy claims must reference trials spanning at least 4 weeks of daily use. Never claim instant, 1-day, or overnight improvements.
Rule 2 (Prohibited Healthcare Claims): Do not use absolute terms like 'Complete Cure', 'Miracle', 'Guaranteed Reversal', or 'Permanent Elimination'.
Rule 3 (Commercial & Pricing Policy): All commercial pricing proposals must explicitly state billing interval (Annual/Monthly) and currency (USD). Avoid aggressive sales urgency (e.g., 'Buy now before stock runs out').
Rule 4 (Product Nomenclature): The corporate product name must strictly appear as 'Lumina Health Enterprise' or 'Lumina Clinical Tech'. Deviations or shorthand names are forbidden.
Rule 5 (Professional Tone): Maintain a formal, peer-reviewed, scientific, and encouraging brand voice.
Rule 6 (Logo & Visual Standards): Primary corporate logo must be prominently displayed in the header or top-right with exact aspect ratio (3:1) and official colors (#1E3A8A, #06B6D4). Never stretch or recolor.""",
            "data/orgs/org_b2b_clinical/reference_logo.png",
            "#1E3A8A, #06B6D4, #FFFFFF",
            now,
            now
        ),
        (
            "org_d2c_social",
            "Lumina Glow - D2C Social Media",
            "Consumer skincare & social media guidelines balancing engaging marketing with FTC/advertising compliance.",
            """Rule 1 (Timeline & Efficacy): Claim only visible radiance improvement over 14 days of regular application. Strictly prohibit claims of 'Instant 24-Hour Transformation' or 'Overnight Erase'.
Rule 2 (Blacklisted Social Buzzwords): Prohibit misleading sensationalism such as 'Miracle Potion', 'Filters in a Bottle', or 'Erase Wrinkles Overnight'.
Rule 3 (Nomenclature & Tagging): Always refer to the hero product as 'Lumina Glow Radiance Serum'. Never shorten to just 'Glow' or 'Lumina Serum'.
Rule 4 (Tone & Community Voice): Fun, vibrant, and empowering. Avoid aggressive high-pressure scarcity tactics like 'Hurry, closing forever!'
Rule 5 (Customer Guarantees): Do not invent unapproved money-back guarantees or 100% satisfaction warranties unless officially certified.
Rule 6 (Visual Branding): Must display official Lumina Glow hero logo in authorized colors (#EC4899, #F59E0B) without stretching or distortion.""",
            "data/orgs/org_d2c_social/reference_logo.png",
            "#EC4899, #F59E0B, #FFFFFF",
            now,
            now
        )
    ]

    cursor.executemany("""
    INSERT INTO organizations (id, name, description, guidelines, logo_path, brand_colors_hex, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """, default_orgs)
    conn.commit()

def get_all_organizations() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM organizations ORDER BY name ASC;")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_organization(org_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM organizations WHERE id = ?;", (org_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def create_organization(
    org_id: str,
    name: str,
    description: str,
    guidelines: str,
    logo_path: Optional[str] = None,
    brand_colors_hex: Optional[str] = None
) -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    cursor.execute("""
    INSERT INTO organizations (id, name, description, guidelines, logo_path, brand_colors_hex, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """, (org_id, name, description, guidelines, logo_path, brand_colors_hex, now, now))
    conn.commit()
    conn.close()
    return {
        "id": org_id,
        "name": name,
        "description": description,
        "guidelines": guidelines,
        "logo_path": logo_path,
        "brand_colors_hex": brand_colors_hex,
        "created_at": now,
        "updated_at": now
    }

def update_organization(
    org_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    guidelines: Optional[str] = None,
    logo_path: Optional[str] = None,
    brand_colors_hex: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    current = get_organization(org_id)
    if not current:
        return None

    new_name = name if name is not None else current["name"]
    new_desc = description if description is not None else current["description"]
    new_guide = guidelines if guidelines is not None else current["guidelines"]
    new_logo = logo_path if logo_path is not None else current["logo_path"]
    new_colors = brand_colors_hex if brand_colors_hex is not None else current["brand_colors_hex"]
    now = datetime.utcnow().isoformat()

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE organizations
    SET name = ?, description = ?, guidelines = ?, logo_path = ?, brand_colors_hex = ?, updated_at = ?
    WHERE id = ?;
    """, (new_name, new_desc, new_guide, new_logo, new_colors, now, org_id))
    conn.commit()
    conn.close()

    return {
        "id": org_id,
        "name": new_name,
        "description": new_desc,
        "guidelines": new_guide,
        "logo_path": new_logo,
        "brand_colors_hex": new_colors,
        "created_at": current["created_at"],
        "updated_at": now
    }

def delete_organization(org_id: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM organizations WHERE id = ?;", (org_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()

    # Also clean up the organization's dedicated folder
    org_folder = os.path.join(ORGS_DIR, org_id)
    if os.path.exists(org_folder):
        try:
            shutil.rmtree(org_folder)
        except Exception:
            pass

    return deleted

init_db()
