import streamlit as st
import rsa
import time

from utils.auth import require_auth
from utils.audit_log import log_commander_action

# Guard page so only Commander can access
require_auth(['Commander'])

st.set_page_config(page_title="Commander Secure Entry", page_icon="🔐", layout="wide")

st.title("🔐 Commander Data Entry & Transmission")
st.markdown("Use this portal to encrypt sensitive tactical intelligence before transmission.")
st.info("🔐 **Encryption Standard:** RSA-2048 (PKCS#1). Keypairs are ephemeral and never stored. Maximum payload: 245 bytes.")

# Validate form input
with st.form("secure_entry_form"):
    st.subheader("Tactical Payload")
    target_id = st.text_input("Target ID / Operation Code", max_chars=20)
    intel_type = st.selectbox("Intelligence Type", ["SIGINT", "HUMINT", "GEOINT", "MASINT"])
    coordinates = st.text_input("Coordinates (Lat, Long)")
    details = st.text_area("Detailed Assessment", max_chars=150,
                           help="Maximum 150 characters to stay within RSA-2048 encryption limits.")
    
    st.markdown("---")
    submitted = st.form_submit_button("Encrypt & Preview Ciphertext")

if submitted:
    errors = []
    if not target_id:
        errors.append("Target ID / Operation Code is required.")
    if not coordinates:
        errors.append("Coordinates are required.")
    elif not all(part.strip().lstrip('-').replace('.', '', 1).isdigit() for part in coordinates.split(',')):
        errors.append("Coordinates must be in decimal format (e.g. 28.6139, 77.2090).")
    if not details:
        errors.append("Detailed Assessment is required.")
    
    if errors:
        for err in errors:
            st.error(f"❌ {err}")
    else:
        payload = f"OP_CODE:{target_id}|TYPE:{intel_type}|COORD:{coordinates}|DETAILS:{details}"
        payload_bytes = payload.encode('utf-8')
        
        # RSA-2048 PKCS#1 v1.5 hard limit is (2048/8) - 11 = 245 bytes
        if len(payload_bytes) > 245:
            st.error(f"❌ Payload too large: {len(payload_bytes)} bytes (max 245 for RSA-2048). Shorten the assessment.")
        else:
            with st.spinner("Generating ephemeral 2048-bit RSA keypair..."):
                public_key, private_key = rsa.newkeys(2048)
                
            with st.spinner("Encrypting payload..."):
                try:
                    encrypted_data = rsa.encrypt(payload_bytes, public_key)
                except rsa.pkcs1.OverflowError as e:
                    st.error(f"❌ Encryption failed: payload too large. {e}")
                    st.stop()
                    
            st.success("✅ Encryption Successful. Keypair will be destroyed when this session ends.")

            # Audit log — record the action without the payload or keys
            log_commander_action(
                username=st.session_state.get("username", "unknown"),
                action="COMMANDER_ENCRYPT",
                metadata={
                    "intel_type": intel_type,
                    "payload_size_bytes": len(payload_bytes),
                    "target_id": target_id,  # operation code only, not details
                },
            )
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Payload Size", f"{len(payload_bytes)} bytes")
            with col2:
                st.metric("Ciphertext Size", f"{len(encrypted_data)} bytes")
            
            st.markdown("### 📤 Transmission Preview")
            st.info("The following ciphertext represents the data as it would be transmitted over the wire. The private key is held only in process memory and is never displayed or logged.")
            st.code(encrypted_data.hex(), language="text")
            
            with st.expander("Public Key (Encryption Only)"):
                st.markdown("**Public Key (RSA-2048, PKCS#1 PEM):**")
                st.code(public_key.save_pkcs1().decode('utf-8'))
                st.caption("⚠️ The private key is ephemeral and is NOT displayed here for security reasons.")

