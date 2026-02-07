#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Debug script to identify encoding issue location
"""

import os
import sys
import json
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

print("=" * 60)
print("ENCODING DEBUG")
print("=" * 60)

# Check environment variables
print("\n[1] Checking Environment Variables:")
print(f"  SUPABASE_URL type: {type(SUPABASE_URL)}")
print(f"  SUPABASE_URL repr: {repr(SUPABASE_URL[:30] if SUPABASE_URL else None)}...")
print(f"  SUPABASE_KEY type: {type(SUPABASE_KEY)}")
print(f"  SUPABASE_KEY repr: {repr(SUPABASE_KEY[:30] if SUPABASE_KEY else None)}...")

# Check if they're pure ASCII
def check_ascii(name, value):
    if value is None:
        print(f"  {name}: None")
        return
    try:
        value.encode('ascii')
        print(f"  {name}: ASCII OK")
    except UnicodeEncodeError as e:
        print(f"  {name}: NOT ASCII! {e}")
        # Show problematic characters
        for i, c in enumerate(value):
            if ord(c) > 127:
                print(f"    Position {i}: {repr(c)} (ord={ord(c)})")

check_ascii("SUPABASE_URL", SUPABASE_URL)
check_ascii("SUPABASE_KEY", SUPABASE_KEY)

# Test a minimal upload
print("\n[2] Testing Minimal Upload:")

import urllib.request
import urllib.error

# Create absolutely minimal payload
test_payload = {
    "race_id": "TEST_001",
    "data_type": "TEST",
    "race_date": "20260207",
    "content": "{}",
    "raw_string": "dGVzdA==",  # "test" in base64
    "timestamp": "2026-02-07T12:00:00",
    "status": "test"
}

# Serialize
json_data = json.dumps(test_payload, ensure_ascii=True)
print(f"  Payload JSON: {json_data[:100]}...")
print(f"  Payload is ASCII: ", end="")
try:
    json_data.encode('ascii')
    print("YES")
except:
    print("NO!")

# Try to make request
print("\n[3] Building HTTP Request:")
try:
    json_bytes = json_data.encode('ascii')
    print(f"  JSON bytes length: {len(json_bytes)}")
    
    url = f"{SUPABASE_URL}/rest/v1/raw_race_data"
    print(f"  URL: {url}")
    
    headers = {
        "Content-Type": "application/json",
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Prefer": "resolution=merge-duplicates"
    }
    
    # Check headers
    print("\n  Checking headers:")
    for k, v in headers.items():
        try:
            if v:
                v.encode('latin-1')  # HTTP headers use latin-1 encoding
                print(f"    {k}: OK (latin-1)")
        except UnicodeEncodeError as e:
            print(f"    {k}: FAILED! {e}")
            for i, c in enumerate(str(v)):
                if ord(c) > 255:
                    print(f"      Position {i}: {repr(c)} (ord={ord(c)})")
    
    req = urllib.request.Request(
        url,
        data=json_bytes,
        headers=headers,
        method="POST"
    )
    print("\n  Request created successfully!")
    
    # Now try to actually send it
    print("\n[4] Sending Request...")
    with urllib.request.urlopen(req, timeout=30) as resp:
        print(f"  Status: {resp.status}")
        body = resp.read().decode('utf-8')
        print(f"  Response: {body[:200]}")
        
except urllib.error.HTTPError as he:
    print(f"  HTTP Error: {he.code}")
    body = he.read().decode('utf-8', errors='replace')
    print(f"  Body: {body[:300]}")
except Exception as e:
    import traceback
    print(f"  Exception: {type(e).__name__}: {e}")
    traceback.print_exc()

print("\n" + "=" * 60)
print("DEBUG COMPLETE")
