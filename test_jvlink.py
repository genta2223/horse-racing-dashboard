"""
JRA JV-Link Connection Test
============================
Tests the connection to JV-Link and basic data retrieval.

Usage:
    python test_jvlink.py
"""

import sys
import datetime

# Check platform
if sys.platform != "win32":
    print("[ERROR] This script requires Windows.")
    sys.exit(1)

print("=" * 50)
print("JV-Link Connection Test")
print("=" * 50)

# Test 1: JV-Link COM registration
print("\n[TEST 1] Checking JV-Link COM registration...")
try:
    import win32com.client
    jv = win32com.client.Dispatch("JVDTLab.JVLink")
    print("   ✓ JVLink COM object created successfully")
except Exception as e:
    print(f"   ✗ Failed: {e}")
    print("\n[HELP] Make sure JV-Link SDK is installed and registered.")
    print("       Download from: https://jra-van.jp/")
    sys.exit(1)

# Test 2: JVInit
print("\n[TEST 2] Initializing JV-Link...")
try:
    res = jv.JVInit("UNKNOWN")
    if res == 0:
        print("   ✓ JVInit successful (code: 0)")
    elif res == -100:
        print("   ✗ JVInit failed: Not registered (need TARGET login)")
    elif res == -101:
        print("   ✗ JVInit failed: Authentication error")
    elif res == -102:
        print("   ✗ JVInit failed: Another instance running")
    else:
        print(f"   ? JVInit returned: {res}")
except Exception as e:
    print(f"   ✗ Exception: {e}")
    sys.exit(1)

# Test 3: Check for today's data
print("\n[TEST 3] Checking for available data...")
today = datetime.date.today()
date_str = today.strftime("%Y%m%d")

try:
    # Try to open 0B31 (Odds) for today
    res = jv.JVOpen("0B31", f"{date_str}000000", 4, 0, 0, "")
    
    if res == 0:
        print(f"   ✓ Data found for {date_str}")
        
        # Count records
        count = 0
        while True:
            read_res = jv.JVRead("", 200000, "")
            if isinstance(read_res, tuple):
                ret = read_res[0]
            else:
                ret = read_res
            
            if ret <= 0:
                break
            count += 1
        
        print(f"   ✓ Read {count} records")
        jv.JVClose()
    else:
        print(f"   ✗ No data for today ({date_str})")
        print("   [INFO] This is normal if:")
        print("          - Today is not a race day")
        print("          - Data hasn't been downloaded in TARGET yet")
        
        # Try yesterday
        yesterday = today - datetime.timedelta(days=1)
        date_str2 = yesterday.strftime("%Y%m%d")
        res2 = jv.JVOpen("0B31", f"{date_str2}000000", 4, 0, 0, "")
        if res2 == 0:
            print(f"   ✓ But found data for yesterday ({date_str2})")
            jv.JVClose()

except Exception as e:
    print(f"   ✗ Exception: {e}")

# Test 4: Supabase connection
print("\n[TEST 4] Testing Supabase connection...")
try:
    from dotenv import load_dotenv
    import os
    load_dotenv()
    
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    
    if not url or not key:
        print("   ✗ Missing SUPABASE_URL or SUPABASE_KEY in .env")
    else:
        from supabase import create_client
        sb = create_client(url, key)
        
        # Test insert
        res = sb.table("system_logs").insert({
            "level": "INFO",
            "message": "JV-Link Test",
            "details": f"Connection test at {datetime.datetime.now().isoformat()}",
            "timestamp": datetime.datetime.now().isoformat()
        }).execute()
        
        print("   ✓ Supabase connection successful")
        print("   ✓ Test log inserted")

except Exception as e:
    print(f"   ✗ Supabase error: {e}")

print("\n" + "=" * 50)
print("Test Complete")
print("=" * 50)
