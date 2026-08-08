import streamlit as st

def require_auth(allowed_roles=None):
    """
    Enforces authentication and role-based access control (RBAC).
    Must be called at the very top of every page script.
    
    Args:
        allowed_roles (list, optional): List of role strings allowed to access the page.
                                        If None, any authenticated user can access.
    """
    # 1. Check if authenticated
    if not st.session_state.get("authentication_status"):
        st.error("🔒 Unauthorized. Please log in from the Home page.")
        st.stop()
        
    # 2. Check Role Authorization
    if allowed_roles is not None:
        roles = st.session_state.get("roles")
        role = roles[0] if roles and isinstance(roles, list) else "Viewer"
        
        if role not in allowed_roles and role != "Commander": # Commander overrides
            st.error(f"🛑 Access Denied. Your role ({role}) does not have permission to view this module.")
            st.stop()
