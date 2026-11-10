"""
Semantic product matcher using sentence-transformers (all-MiniLM-L6-v2).
Pre-computes embeddings for every Neo4j product at startup; cosine similarity
is used to find the closest match to free-text user input.
"""
from __future__ import annotations

import numpy as np

# Confidence thresholds (kept in sync with config/settings.py)
HIGH_THRESHOLD   = 0.80   # strong match → auto-assign
MEDIUM_THRESHOLD = 0.60   # moderate match → user confirmation
LOW_THRESHOLD    = 0.50   # weak match → still surface, but flag LOW
                           # below LOW_THRESHOLD → INSUFFICIENT, return product=None

try:
    from sentence_transformers import SentenceTransformer
    _ST_AVAILABLE = True
except ImportError:
    _ST_AVAILABLE = False


class SemanticMatcher:
    """
    Load the embedding model once, pre-embed all product names from Neo4j,
    then answer find_closest_product() calls in microseconds.
    """

    def __init__(self) -> None:
        self._ready = False
        self._products: list[dict] = []
        self._embeddings: np.ndarray = np.array([])

        if not _ST_AVAILABLE:
            self._error = (
                "sentence_transformers not installed. "
                "Run: pip install sentence-transformers==2.2.0"
            )
            return

        try:
            from agent.graph_client import get_all_products
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
            self._products = get_all_products()
            if self._products:
                names = [p["name"] for p in self._products]
                self._embeddings = self._model.encode(
                    names, normalize_embeddings=True, show_progress_bar=False
                )
            self._ready = True
        except Exception as exc:
            self._error = str(exc)

    # ── Public API ─────────────────────────────────────────────────────────────

    def find_closest_product(self, user_input: str) -> dict:
        """
        Encode *user_input* and return the closest product by cosine similarity.

        Returns
        -------
        {
            "product":          str | None,
            "product_id":       str | None,
            "similarity_score": float,          # 0.0 – 1.0
            "confidence_level": "HIGH" | "MEDIUM" | "LOW" | "INSUFFICIENT",
            "explanation":      str,
        }
        """
        if not self._ready or not self._products:
            return {
                "product":          None,
                "product_id":       None,
                "similarity_score": 0.0,
                "confidence_level": "INSUFFICIENT",
                "explanation":      getattr(self, "_error", "Semantic matcher not available."),
            }

        query_emb   = self._model.encode([user_input], normalize_embeddings=True)
        similarities = np.dot(self._embeddings, query_emb.T).flatten()
        best_idx    = int(np.argmax(similarities))
        score       = float(similarities[best_idx])
        product     = self._products[best_idx]

        if score < LOW_THRESHOLD:
            return {
                "product":          None,
                "product_id":       None,
                "similarity_score": score,
                "confidence_level": "INSUFFICIENT",
                "explanation": (
                    f"No product matched above the 50% threshold "
                    f"(best: {score:.0%} similarity to '{product['name']}')"
                ),
            }

        if score >= HIGH_THRESHOLD:
            level       = "HIGH"
            explanation = (
                f"Strong semantic match ({score:.0%}) to '{product['name']}'"
            )
        elif score >= MEDIUM_THRESHOLD:
            level       = "MEDIUM"
            explanation = (
                f"Moderate semantic match ({score:.0%}) to '{product['name']}'"
            )
        else:
            level       = "LOW"
            explanation = (
                f"Weak semantic match ({score:.0%}) to '{product['name']}' — "
                "please confirm before proceeding"
            )

        return {
            "product":          product["name"],
            "product_id":       product["product_id"],
            "similarity_score": score,
            "confidence_level": level,
            "explanation":      explanation,
        }

    @property
    def ready(self) -> bool:
        return self._ready

    @property
    def product_count(self) -> int:
        return len(self._products)


# Module-level singleton (loaded once per process).
# app.py wraps this in @st.cache_resource so it only initialises once per
# Streamlit server restart and its loading progress appears in the Streamlit UI.
semantic_matcher = SemanticMatcher()
