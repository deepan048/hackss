# 🛡️ Brand Shield Guardian (v3.0)

**Automated Pre-Publication AI Brand Governance Firewall & Real-Time Diff Engine**

Built with **FastAPI**, **Streamlit**, **LangChain**, **FAISS**, **SQLite**, and **OpenAI GPT-4o-mini (Multimodal Vision)**.

---

## 🌟 Key New Capabilities

1. **Multi-Organization Brand Rulesets**:
   - Save, edit, switch, and delete distinct brand kits / rule profiles for different organizations or sub-brands (e.g. *Lumina Health - B2B Enterprise* vs. *Lumina Glow - D2C Social Media*).
   - Local SQLite database (`data/rulesets.db`) for rule profiles.
   - Isolated FAISS vector store namespaces per organization (`data/faiss_indexes/{org_id}`).
2. **Real-Time Interactive AI Content Fixer & Diff Engine**:
   - RAG grounding: Retrieves only the active organization's specific brand rules from its isolated FAISS index.
   - Side-by-side & Unified word-level diff view highlighting non-compliant deletions (red) and compliant additions (green).
   - **One-Click Auto-Fix**: Generates a 100% compliant, publication-ready version while strictly preserving creator tone and intent.
   - **Explanation of Changes**: Clear breakdown of why each phrase was modified.
3. **Evidence-Based Governance Metrics**:
   - Total Violations counter & 0-100% Compliance Health Score.
   - Status banners (`PASS`, `REQUIRES REVISION`, `CRITICAL VIOLATION`).
   - Granular violation cards citing exact rule titles, detected text, and supporting evidence.

---

## 📁 Modular Code Structure

```
ai-brand-guardian/
├── data/
│   ├── rulesets.db             # SQLite database storing orgs and rulesets
│   └── faiss_indexes/          # Isolated FAISS vector store namespaces per org
├── database.py                 # SQLite CRUD persistence layer for Organizations
├── vector_store.py             # Isolated FAISS vector store indexer & retriever
├── engine.py                   # RAG evaluation, diff generator, and auto-fix rationale
├── backend.py                  # FastAPI REST API (CRUD /organizations, /evaluate)
├── app.py                      # Modern Streamlit UI (ruleset switcher, diff view, auto-fixer)
├── requirements.txt            # Python dependencies
└── .env                        # Configuration (OPENAI_API_KEY)
```

---

## 🚀 How to Run

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Configure Environment
Copy `.env.example` to `.env` and set your OpenAI API key:
```env
OPENAI_API_KEY=your-api-key-here
```
*(If no API key is provided, the system automatically falls back to an intelligent local heuristic RAG engine with zero crashes).*

### Step 3: Start the Backend (FastAPI)
```bash
python -m uvicorn backend:app --reload --port 8000
```
Interactive API Docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### Step 4: Start the Frontend (Streamlit)
```bash
python -m streamlit run app.py
```
Open your browser at: [http://localhost:8501](http://localhost:8501)
