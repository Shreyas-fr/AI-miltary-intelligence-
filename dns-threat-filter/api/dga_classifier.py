"""
dga_classifier.py — Domain Generation Algorithm classifier.

Improved feature set:
  - Shannon entropy
  - Vowel / consonant / digit ratios  
  - Unique character ratio
  - Bigram frequency flatness (DGA hallmark: uniform bigram distribution)
  - Max consonant cluster length (DGA hallmark: unpronounceable consonant runs)
  - Domain label length

Block threshold raised from 0.75 → 0.80 to reduce false positives on
short, single-syllable legitimate domains.
"""

import math
import collections
import numpy as np
import joblib
from pathlib import Path

from sklearn.ensemble import RandomForestClassifier

MODEL_PATH = Path(__file__).parent / "data" / "dga_model.joblib"

# ---------------------------------------------------------------------------
# Feature engineering helpers
# ---------------------------------------------------------------------------

def calculate_entropy(s: str) -> float:
    """Calculate Shannon entropy of a string."""
    if not s:
        return 0.0
    counter = collections.Counter(s)
    length = len(s)
    return -sum((c / length) * math.log2(c / length) for c in counter.values())


def bigram_flatness(s: str) -> float:
    """
    Measure how uniform the bigram frequency distribution is.

    Legitimate domains have skewed bigram distributions (e.g., "th", "er"
    are very frequent in English). DGA domains generated from random
    characters have near-flat bigram distributions.

    Returns a value 0–1 where 1.0 = perfectly flat (highly suspicious).
    """
    if len(s) < 2:
        return 0.0
    bigrams = [s[i:i+2] for i in range(len(s) - 1)]
    counts = collections.Counter(bigrams)
    n = len(bigrams)
    # Normalised entropy of bigram distribution
    entropy = -sum((v / n) * math.log2(v / n) for v in counts.values())
    max_entropy = math.log2(n) if n > 1 else 1.0
    return entropy / max_entropy if max_entropy > 0 else 0.0


def max_consonant_cluster(s: str) -> int:
    """
    Return the length of the longest consecutive consonant run.

    DGA strings commonly have clusters like "xprfzqk" that are
    unpronounceable in any natural language.
    """
    consonants = set("bcdfghjklmnpqrstvwxyz")
    max_run, current_run = 0, 0
    for c in s.lower():
        if c in consonants:
            current_run += 1
            max_run = max(max_run, current_run)
        else:
            current_run = 0
    return max_run


def extract_features(domain: str) -> np.ndarray:
    """
    Extract lexical features from a domain label (first part before TLD).

    Features (9 total):
      1.  length
      2.  Shannon entropy
      3.  vowel ratio
      4.  consonant ratio
      5.  digit ratio
      6.  unique character ratio
      7.  bigram flatness score (0–1)
      8.  max consonant cluster length
      9.  digit count (absolute)
    """
    if not domain:
        return np.zeros(9)

    length = len(domain)
    entropy = calculate_entropy(domain)

    vowels = set("aeiou")
    consonants = set("bcdfghjklmnpqrstvwxyz")

    vowel_count = sum(1 for c in domain if c in vowels)
    consonant_count = sum(1 for c in domain if c in consonants)
    digit_count = sum(1 for c in domain if c.isdigit())
    unique_chars = len(set(domain))

    return np.array([
        length,
        entropy,
        vowel_count / length,
        consonant_count / length,
        digit_count / length,
        unique_chars / length,
        bigram_flatness(domain),
        max_consonant_cluster(domain),
        digit_count,
    ])


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------

class DGAClassifier:
    # Raised from 0.75 → 0.80 to reduce false positives on short domains
    BLOCK_THRESHOLD = 0.80

    def __init__(self):
        self.model = None

    def train(self, benign_domains: list[str], malicious_domains: list[str]):
        """Train the model and save to disk."""
        X, y = [], []
        for d in benign_domains:
            X.append(extract_features(d.split(".")[0]))
            y.append(0)
        for d in malicious_domains:
            X.append(extract_features(d.split(".")[0]))
            y.append(1)

        self.model = RandomForestClassifier(
            n_estimators=200,       # up from 100
            max_depth=12,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1,
        )
        self.model.fit(np.array(X), np.array(y))
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model, MODEL_PATH)
        return self.model

    def load(self) -> bool:
        if MODEL_PATH.exists():
            self.model = joblib.load(MODEL_PATH)
        return self.model is not None

    def predict(self, domain: str) -> float:
        """
        Predict the probability that a domain is DGA-generated.
        Returns 0.0–1.0.
        """
        if self.model is None:
            if not self.load():
                return 0.0  # Failsafe: no model → assume clean

        # Classify only the first label (excludes TLD noise)
        parts = domain.split(".")
        target = parts[0] if len(parts) > 1 else domain

        features = extract_features(target)
        return float(self.model.predict_proba([features])[0][1])


# Singleton instance used by main.py
classifier = DGAClassifier()
