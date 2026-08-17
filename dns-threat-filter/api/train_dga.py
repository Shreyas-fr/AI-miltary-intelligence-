import logging
from pathlib import Path
from dga_classifier import classifier

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_domains(file_path: Path, max_lines: int = 10000) -> list[str]:
    domains = []
    if not file_path.exists():
        logger.warning(f"File not found: {file_path}")
        return domains
        
    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                # We want to train on just the primary domain part (without TLD)
                # This makes the lexical features independent of the TLD
                parts = line.split(".")
                target = parts[0] if len(parts) > 1 else line
                domains.append(target)
                if len(domains) >= max_lines:
                    break
    return domains

def main():
    data_dir = Path(__file__).parent / "data"
    benign_path = data_dir / "benign_domains.txt"
    malicious_path = data_dir / "malicious_domains.txt"
    
    logger.info("Loading datasets...")
    benign_domains = load_domains(benign_path)
    malicious_domains = load_domains(malicious_path)
    
    logger.info(f"Loaded {len(benign_domains)} benign domains and {len(malicious_domains)} malicious domains.")
    
    if not benign_domains or not malicious_domains:
        logger.error("Missing training data. Please ensure data/benign_domains.txt and data/malicious_domains.txt exist.")
        return
        
    logger.info("Training DGA classifier...")
    model = classifier.train(benign_domains, malicious_domains)
    
    logger.info("Training complete. Model saved to data/dga_model.joblib.")
    
    # Test a few domains
    test_domains = ["google.com", "microsoft.com", "22jwr0yslh8wvqlo3fn.cn", "ld1usi43uxoq0xn95.org"]
    for d in test_domains:
        score = classifier.predict(d)
        logger.info(f"Prediction for {d}: {score:.4f}")

if __name__ == "__main__":
    main()
