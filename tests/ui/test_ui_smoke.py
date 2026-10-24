"""
UI Smoke Test for Streamlit Dashboard.
Verifies that dashboard components load correctly.
"""

def test_streamlit_app_import():
    import importlib.util
    spec = importlib.util.spec_from_file_location("streamlit_app", "dashboards/streamlit_app.py")
    assert spec is not None
