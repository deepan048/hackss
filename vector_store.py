"""
Brand Shield Guardian - Isolated FAISS Vector Store Layer
Per-Organization Namespaced Vector Stores & Semantic Retrieval
"""

import os
import re
import shutil
import hashlib
import logging
from typing import List, Optional, Dict
import numpy as np

from langchain_core.embeddings import Embeddings
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger("brand_shield_guardian.vector_store")

INDEX_ROOT_DIR = os.path.join(os.path.dirname(__file__), "data", "faiss_indexes")
os.makedirs(INDEX_ROOT_DIR, exist_ok=True)

# In-memory index cache for low-latency queries
_vector_store_cache: Dict[str, FAISS] = {}

class DeterministicLocalEmbeddings(Embeddings):
    """
    High-speed deterministic embeddings guaranteeing vector search
    with zero external dependencies or API rate limits.
    """
    def __init__(self, dim: int = 128):
        self.dim = dim

    def _embed_text(self, text: str) -> List[float]:
        vec = np.zeros(self.dim, dtype=np.float32)
        words = re.findall(r"\w+", text.lower())
        if not words:
            return vec.tolist()
        for w in words:
            h = int(hashlib.md5(w.encode("utf-8")).hexdigest(), 16)
            vec[h % self.dim] += 1.0
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec.tolist()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._embed_text(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._embed_text(text)

def get_embeddings_model():
    """Returns OpenAI embeddings if configured, else DeterministicLocalEmbeddings."""
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key and not api_key.startswith("your-"):
        try:
            from langchain_community.embeddings import OpenAIEmbeddings
            return OpenAIEmbeddings(openai_api_key=api_key)
        except Exception as e:
            logger.warning(f"OpenAIEmbeddings failed ({e}), falling back to DeterministicLocalEmbeddings.")
    return DeterministicLocalEmbeddings()

def get_org_index_path(org_id: str) -> str:
    return os.path.join(INDEX_ROOT_DIR, org_id)

def build_or_update_org_index(org_id: str, guidelines: str) -> FAISS:
    """
    Chunks organization guidelines, creates an isolated FAISS vector index,
    saves it to disk, and updates memory cache.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=200,
        chunk_overlap=30,
        separators=["\n\n", "\n", "Rule ", "Section ", "; ", ". "]
    )
    docs = splitter.create_documents([guidelines])
    if not docs:
        docs = splitter.create_documents([f"Default guidelines for {org_id}"])

    embeddings = get_embeddings_model()
    vs = FAISS.from_documents(docs, embeddings)

    # Save to disk
    org_path = get_org_index_path(org_id)
    os.makedirs(org_path, exist_ok=True)
    try:
        vs.save_local(org_path)
    except Exception as e:
        logger.warning(f"Could not persist FAISS index for {org_id}: {e}")

    # Update in-memory cache
    _vector_store_cache[org_id] = vs
    logger.info(f"FAISS index built and cached for organization '{org_id}' ({len(docs)} chunks).")
    return vs

def get_org_index(org_id: str, guidelines: Optional[str] = None) -> Optional[FAISS]:
    """Retrieves an organization's FAISS index from cache or disk."""
    if org_id in _vector_store_cache:
        return _vector_store_cache[org_id]

    org_path = get_org_index_path(org_id)
    embeddings = get_embeddings_model()

    if os.path.exists(os.path.join(org_path, "index.faiss")):
        try:
            vs = FAISS.load_local(org_path, embeddings, allow_dangerous_deserialization=True)
            _vector_store_cache[org_id] = vs
            return vs
        except Exception as e:
            logger.warning(f"Failed loading FAISS from disk for {org_id}: {e}. Rebuilding.")

    # Rebuild if guidelines provided or fetch from DB
    if guidelines:
        return build_or_update_org_index(org_id, guidelines)

    from database import get_organization
    org = get_organization(org_id)
    if org and org.get("guidelines"):
        return build_or_update_org_index(org_id, org["guidelines"])

    return None

def delete_org_index(org_id: str):
    """Deletes the organization's FAISS index from disk and cache."""
    if org_id in _vector_store_cache:
        del _vector_store_cache[org_id]

    org_path = get_org_index_path(org_id)
    if os.path.exists(org_path):
        try:
            shutil.rmtree(org_path)
            logger.info(f"Deleted FAISS index directory for '{org_id}'.")
        except Exception as e:
            logger.error(f"Error removing FAISS dir for {org_id}: {e}")

def retrieve_relevant_rules(org_id: str, query_content: str, top_k: int = 4) -> List[str]:
    """
    RAG retrieval: Queries the organization's specific FAISS index
    for the most relevant guideline rules against the marketing copy.
    """
    vs = get_org_index(org_id)
    if not vs:
        return []

    try:
        query = query_content[:500] if query_content else "Brand guidelines and rules"
        results = vs.similarity_search(query, k=top_k)
        return [doc.page_content.strip() for doc in results if doc.page_content.strip()]
    except Exception as e:
        logger.error(f"Error querying FAISS for {org_id}: {e}")
        return []
