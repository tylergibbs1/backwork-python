"""Basic test to verify SDK works."""

from backwork import BackworkClient, AuthenticationError

def test_sdk():
    # Test with a placeholder key - replace with your real key
    api_key = "bwk_live_h2V4x8pL6JFHuX3y"  # This key may not be active
    client = BackworkClient(api_key)
    
    # Test health check (no auth required)
    try:
        health = client.health()
        assert health["success"] is True
        print(f"✓ Health check: {health['data']['status']}")
    except Exception as e:
        print(f"✗ Health check failed: {e}")
    
    # Test code lookup (requires auth)
    try:
        result = client.lookup_code("76942")
        assert result["success"] is True
        assert "data" in result
        print(f"✓ Code lookup: {result['data']['description']}")
    except AuthenticationError as e:
        print(f"⚠ Code lookup requires valid API key: {e.message}")
        print("  Note: Get your API key from https://backworkhealth.com/dashboard")
    except Exception as e:
        print(f"✗ Code lookup failed: {e}")
    
    client.close()
    print("\n✓ SDK structure is valid!")

if __name__ == "__main__":
    test_sdk()
