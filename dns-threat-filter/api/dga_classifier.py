import math
import collections
import numpy as np
import joblib
from pathlib import Path

# Scikit-learn is required for training/inference
from sklearn.ensemble import RandomForestClassifier

MODEL_PATH = Path(__file__).parent / "data" / "dga_model.joblib"

def calculate_entropy(s: str) -> float:
    """Calculate Shannon entropy of a string."""
    if not s:
        return 0.0
    counter = collections.Counter(s)
    entropy = 0.0
    length = len(s)
    for count in counter.values():
        p = count / length
        entropy -= p * math.log2(p)
    return entropy

def extract_features(domain: str) -> np.ndarray:
    """
    Extract lexical features from a domain string.
    Features:
      1. length
      2. entropy
      3. vowel ratio
      4. consonant ratio
      5. digit ratio
      6. unique character ratio
    """
    if not domain:
        return np.zeros(6)
        
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
        unique_chars / length
    ])

class DGAClassifier:
    def __init__(self):
        self.model = None

    def train(self, benign_domains: list[str], malicious_domains: list[str]):
        """Train the model and save to disk."""
        X = []
        y = []
        
        for d in benign_domains:
            X.append(extract_features(d))
            y.append(0)  # 0 = benign
            
        for d in malicious_domains:
            X.append(extract_features(d))
            y.append(1)  # 1 = malicious
            
        X = np.array(X)
        y = np.array(y)
        
        self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.model.fit(X, y)
        
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model, MODEL_PATH)
        return self.model

    def load(self):
        """Load the model from disk."""
        if MODEL_PATH.exists():
            self.model = joblib.load(MODEL_PATH)
        return self.model is not None

    def predict(self, domain: str) -> float:
        """
        Predict the probability that a domain is a DGA.
        Returns a float between 0.0 and 1.0.
        """
        if self.model is None:
            if not self.load():
                return 0.0  # Failsafe: if no model, assume clean
                
        # For prediction, we use only the first part of the domain (excluding TLD)
        # e.g. "google.com" -> "google"
        parts = domain.split(".")
        target = parts[0] if len(parts) > 1 else domain
            
        features = extract_features(target)
        # predict_proba returns [[prob_0, prob_1]]
        prob_malicious = self.model.predict_proba([features])[0][1]
        return float(prob_malicious)

# Singleton instance
classifier = DGAClassifier()
