"""
utils/similarity.py — Event Similarity Engine
===============================================
TF-IDF + cosine similarity over GTD incidents to find historically
similar events given a new incident description.

Algorithm
---------
1. Concatenate categorical features (country, attack type, weapon type,
   target type, group name) into a text document per incident.
2. Append normalised numerical features (nkill, nwound, success) as
   repeated tokens for weighting.
3. Build a TF-IDF matrix over the corpus.
4. For a query incident, transform it into the same TF-IDF space and
   compute cosine similarity against all historical incidents.
5. Return the top-K most similar incidents.

Why TF-IDF + Cosine?
--------------------
- TF-IDF captures the relative importance of rare attack/weapon/target
  combinations (e.g., "Chemical" weapon is rarer and more distinctive
  than "Explosives").
- Cosine similarity is scale-invariant and works well in high-dimensional
  sparse spaces like TF-IDF vectors.
- Much faster than embedding-based approaches for structured categorical
  data — no GPU or API calls required.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def _build_document(row: pd.Series) -> str:
    """Convert one incident row into a pseudo-document for TF-IDF."""
    parts = []

    # Categorical features — repeated for emphasis
    for col in ["country_txt", "region_txt", "attacktype1_txt",
                "weaptype1_txt", "targtype1_txt", "gname"]:
        val = str(row.get(col, "")).strip()
        if val and val.lower() not in ("", "nan", "unknown"):
            parts.append(val)
            parts.append(val)  # double-weight categorical terms

    # Numerical features as binned tokens
    nkill = max(0, float(row.get("nkill", 0) or 0))
    nwound = max(0, float(row.get("nwound", 0) or 0))

    if nkill == 0:
        parts.append("no_fatalities")
    elif nkill <= 5:
        parts.append("low_fatalities")
    elif nkill <= 20:
        parts.append("medium_fatalities")
    else:
        parts.append("high_fatalities")

    if nwound == 0:
        parts.append("no_injuries")
    elif nwound <= 10:
        parts.append("low_injuries")
    elif nwound <= 50:
        parts.append("medium_injuries")
    else:
        parts.append("high_injuries")

    success = int(row.get("success", 1) or 1)
    parts.append("attack_successful" if success == 1 else "attack_failed")

    return " ".join(parts)


class SimilarityEngine:
    """Precomputed TF-IDF index over GTD incidents."""

    def __init__(self, df: pd.DataFrame):
        self.df = df.reset_index(drop=True).copy()
        self.documents = self.df.apply(_build_document, axis=1).tolist()
        self.vectorizer = TfidfVectorizer(
            max_features=3000,   # safe for up to 200k rows in ~500MB RAM
            min_df=5,            # ignore terms appearing in fewer than 5 incidents
            ngram_range=(1, 2),
            sublinear_tf=True,
        )
        self.tfidf_matrix = self.vectorizer.fit_transform(self.documents)

    def find_similar(
        self,
        query: dict,
        top_k: int = 10,
    ) -> pd.DataFrame:
        """Find the top-K most similar historical incidents to a query.

        Parameters
        ----------
        query : dict
            Keys matching GTD column names (country_txt, attacktype1_txt, etc.)
        top_k : int
            Number of similar incidents to return.

        Returns
        -------
        pd.DataFrame with columns from the original data plus 'similarity_score'.
        """
        query_series = pd.Series(query)
        query_doc = _build_document(query_series)
        query_vec = self.vectorizer.transform([query_doc])

        similarities = cosine_similarity(query_vec, self.tfidf_matrix).flatten()

        top_indices = similarities.argsort()[::-1][:top_k]
        results = self.df.iloc[top_indices].copy()
        results["similarity_score"] = similarities[top_indices]
        results["similarity_pct"] = (results["similarity_score"] * 100).round(1)

        return results.reset_index(drop=True)
