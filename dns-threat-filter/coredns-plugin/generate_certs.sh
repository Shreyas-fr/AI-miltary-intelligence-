#!/bin/bash

# WARNING: This script generates self-signed certificates for LOCAL DEVELOPMENT and DEMONSTRATION purposes only.
# It does NOT provide production-grade trusted encryption.
# Ensure that private keys (*.key, *.pem) are NEVER committed to version control.

echo "=========================================================================="
echo "WARNING: Generating a self-signed RSA certificate for local DoT testing."
echo "This is NOT a production-trusted certificate."
echo "Private keys should NEVER be committed to Git. Ensure .gitignore is active."
echo "=========================================================================="

# Generate a 2048-bit RSA private key and self-signed certificate (valid for 365 days)
openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/CN=localhost"

echo "Certificates generated:"
echo " - cert.pem (Public Certificate)"
echo " - key.pem (Private Key)"
