from streamlit.testing.v1 import AppTest

def _get_real_login_state(username, password):
    """
    Executes a real login flow through the Authenticator UI in app.py 
    and returns the resulting realistic session state.
    """
    at = AppTest.from_file("app.py")
    at.run()
    
    # 0 is username, 1 is password
    at.text_input[0].input(username).run()
    at.text_input[1].input(password).run()
    at.button[0].click().run()
    
    # Extract only the keys managed by streamlit-authenticator to avoid SafeSessionState iteration bugs
    keys = ["authentication_status", "username", "roles", "name", "email"]
    real_state = {}
    for key in keys:
        if key in at.session_state:
            real_state[key] = at.session_state[key]
        
    return real_state

def test_unauthorized_access():
    # We do NOT log in. We just hit the page directly.
    at = AppTest.from_file("pages/20_🌍_Global_Threat_Map.py")
    at.run()
    
    assert not at.exception
    
    # Check that "Unauthorized" is present
    error_msg = at.error[0].value if at.error else ""
    assert "Unauthorized" in error_msg
    
    # Verify the page title "Global Threat Map" does NOT render
    assert "Global Threat Map" not in [t.value for t in at.title]

def test_role_restriction():
    # 1. Perform a REAL login as Viewer
    real_state = _get_real_login_state("viewer", "V1ewer#Echo99")
    
    # 2. Hit a protected page (Database) and inject the REAL session state
    at = AppTest.from_file("pages/50_🗄️_Intelligence_Database.py")
    for key in real_state:
        at.session_state[key] = real_state[key]
    
    at.run()
    
    error_msg = at.error[0].value if at.error else ""
    assert "Access Denied" in error_msg
    
    # Verify page content does not render
    assert "Database Health" not in [t.value for t in at.title]

def test_role_allowed():
    # 1. Perform a REAL login as Viewer
    real_state = _get_real_login_state("viewer", "V1ewer#Echo99")
    
    # 2. Hit an allowed page (Global Threat Map) and inject the REAL session state
    at = AppTest.from_file("pages/20_🌍_Global_Threat_Map.py")
    for key in real_state:
        at.session_state[key] = real_state[key]
        
    at.run(timeout=30)
    
    assert not at.error
    assert any("Global Threat Map" in t.value for t in at.title)

if __name__ == "__main__":
    test_unauthorized_access()
    test_role_restriction()
    test_role_allowed()
    print("All security and role restriction tests passed!")
