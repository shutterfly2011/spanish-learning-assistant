#!/usr/bin/env python3
"""
Simple test script for the BuenoSpanish MCP server.
This script demonstrates how to test the MCP server tools.
"""

import requests
import json
import sys

SERVER_URL = "http://localhost:8000"

def test_health():
    """Test server health endpoint."""
    try:
        response = requests.get(f"{SERVER_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Server health check passed")
            return True
        else:
            print(f"❌ Server health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Server health check failed: {e}")
        return False

def test_lookup(word):
    """Test the REST lookup endpoint."""
    try:
        response = requests.get(
            f"{SERVER_URL}/lookup/{word}",
            timeout=15,
        )
        if response.status_code == 200:
            result = response.json()
            print(f"✅ /lookup/{word} succeeded")
            return result
        else:
            print(f"❌ /lookup/{word} failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ /lookup/{word} failed: {e}")
        return None


def main():
    """Run all tests."""
    print("Testing BuenoSpanish MCP Server")
    print("=" * 40)

    # Test server health
    if not test_health():
        print("Server is not running. Please start it first:")
        print("  cd buenospanish_mcp && docker-compose up --build")
        sys.exit(1)

    print()

    # Test REST lookup endpoint
    test_word = "casa"
    print(f"Testing REST lookup for '{test_word}'...")
    result = test_lookup(test_word)
    if result:
        meanings = result.get("meanings", [])
        print(f"  Meanings  : {len(meanings)} found")
        for m in meanings[:2]:
            print(f"    - {m.get('definition', 'N/A')}")
        etymology = result.get("etymology", "")
        if etymology:
            preview = etymology[:120] + "..." if len(etymology) > 120 else etymology
            print(f"  Etymology : {preview}")
        cognates = result.get("english_cognates", [])
        if cognates:
            print(f"  Cognates  : {', '.join(cognates)}")

    print()
    print("✅ All tests completed!")

if __name__ == "__main__":
    main()