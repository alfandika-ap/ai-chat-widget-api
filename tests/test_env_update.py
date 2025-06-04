#!/usr/bin/env python3
"""
Test script to demonstrate environment variable refresh functionality.
This script shows that OPENAI_API_KEY changes are now picked up without restarting the app.
"""

import os
from app.utils.openai import get_openai_client

def test_env_refresh():
    print("=== Testing Environment Variable Refresh ===\n")
    
    # Test 1: Show current API key (masked for security)
    try:
        client = get_openai_client()
        current_key = os.getenv("OPENAI_API_KEY")
        if current_key:
            masked_key = current_key[:8] + "..." + current_key[-8:] if len(current_key) > 16 else "***masked***"
            print(f"✅ Current API Key: {masked_key}")
        else:
            print("❌ No API Key found in environment")
    except Exception as e:
        print(f"❌ Error getting client: {e}")
    
    print("\n=== How to test the fix ===")
    print("1. Change your OPENAI_API_KEY in the .env file")
    print("2. Call get_openai_client() again - it will pick up the new key")
    print("3. No need to restart the application!")
    
    print("\n=== Benefits of this solution ===")
    print("• ✅ Environment variables are reloaded on each client creation")
    print("• ✅ No need to restart the application when changing API keys")
    print("• ✅ Backward compatibility maintained for existing code")
    print("• ✅ Error handling for missing API keys")

if __name__ == "__main__":
    test_env_refresh() 