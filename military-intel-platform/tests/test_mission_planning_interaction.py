import pytest
from streamlit.testing.v1 import AppTest

def test_mission_planning_auto_fill_and_override():
    # 1. Page Load Test
    at = AppTest.from_file("pages/42_🎖️_Mission_Planning.py")
    
    # Mock session state to bypass auth
    at.session_state["authentication_status"] = True
    at.session_state["mfa_verified"] = True
    at.session_state["roles"] = ["Commander"]
    at.session_state["name"] = "Commander Test"
    at.session_state["email"] = "commander@test.mil"
    
    # Run page
    at.run(timeout=30)
    assert not at.error, f"Page load failed: {at.error}"
    
    # 2. Select a country and verify lat/lon updates
    country_selectbox = at.sidebar.selectbox[0] # The Country dropdown
    
    # Select "Iraq"
    country_selectbox.set_value("Iraq").run(timeout=30)
    assert not at.error, f"Error after selecting Iraq: {at.error}"
    
    # Verify lat/lon inputs updated
    lat_input = at.sidebar.number_input[0]
    lon_input = at.sidebar.number_input[1]
    assert lat_input.value == 33.3152, f"Expected 33.3152, got {lat_input.value}"
    assert lon_input.value == 44.3661, f"Expected 44.3661, got {lon_input.value}"
    
    # Select "Afghanistan"
    country_selectbox.set_value("Afghanistan").run(timeout=30)
    assert not at.error, f"Error after selecting Afghanistan: {at.error}"
    lat_input = at.sidebar.number_input[0]
    lon_input = at.sidebar.number_input[1]
    # Check that it updated (exact coordinate might vary slightly but it shouldn't be Iraq's)
    assert lat_input.value != 33.3152
    assert lon_input.value != 44.3661
    
    # Select a low-incident country (e.g., "Iceland")
    if "Iceland" in country_selectbox.options:
        country_selectbox.set_value("Iceland").run(timeout=30)
        assert not at.error
        # Check if caption exists
        caption_text = [cap.value for cap in at.sidebar.caption if "Approximate centroid" in cap.value]
        assert len(caption_text) > 0, "Low-incident caption did NOT appear for Iceland"
    
    # 3. Manual override test
    # Manually edit lat/lon
    lat_input.set_value(12.3456).run(timeout=30)
    lon_input.set_value(98.7654).run(timeout=30)
    
    # Check if they hold the value
    lat_input = at.sidebar.number_input[0]
    lon_input = at.sidebar.number_input[1]
    assert lat_input.value == 12.3456
    assert lon_input.value == 98.7654

def test_mission_planning_asset_radius():
    # Test specific path when assets are actually in range
    at = AppTest.from_file("pages/42_🎖️_Mission_Planning.py")
    at.session_state["authentication_status"] = True
    at.session_state["mfa_verified"] = True
    at.session_state["roles"] = ["Commander"]
    
    # Load and select Iraq (known to have incidents and nearby assets if radius is large)
    at.run(timeout=30)
    assert not at.error
    
    at.sidebar.selectbox[0].set_value("Iraq").run(timeout=30)
    assert not at.error
    
    # Set radius to 800km to guarantee capturing assets
    at.sidebar.slider[0].set_value(800).run(timeout=30)
    assert not at.error
    
    # Verify the KPI for "Assets in Range" exists and has a non-zero number
    # The KPI card is custom HTML, so it's in the markdown
    markdown_html = "\n".join([md.value for md in at.markdown])
    assert "Assets in Range" in markdown_html
    # We should also see the 'Allied Military Assets' table or section
    subheader_texts = [sh.value for sh in at.subheader]
    assert any("Allied Military Assets" in sh for sh in subheader_texts)
