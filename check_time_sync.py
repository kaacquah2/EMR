#!/usr/bin/env python
"""
MFA Time Sync Fix - Automated Windows Time Sync Check
Run this to automatically check and potentially fix time sync issues
"""

import subprocess
import sys
import json
import time
from datetime import datetime

print("=" * 70)
print("MFA TIME SYNC CHECK & FIX")
print("=" * 70)

def run_cmd(cmd, check=False):
    """Run command and return output"""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return -1, "", str(e)

# Check 1: System Time
print("\n[1] SYSTEM TIME CHECK")
print("-" * 70)
now = datetime.now()
print(f"Current system time: {now}")
print(f"ISO format: {now.isoformat()}")
print(f"Unix timestamp: {time.time()}")

# Check 2: Windows Time Service
print("\n[2] WINDOWS TIME SERVICE CHECK")
print("-" * 70)

code, out, err = run_cmd("powershell -Command \"Get-Service w32time | Select-Object -Property Status, StartType | ConvertTo-Json\"")

if code == 0:
    try:
        data = json.loads(out)
        status = data.get('Status', 'Unknown')
        starttype = data.get('StartType', 'Unknown')
        print(f"Service Status: {status}")
        print(f"Startup Type: {starttype}")
        
        if status.lower() != 'running':
            print("\n⚠️  WARNING: Time service is not running")
            print("   Attempting to start...\n")
            code2, _, _ = run_cmd("powershell -Command \"Start-Service w32time -ErrorAction SilentlyContinue; Write-Host 'Time service started'\"")
            if code2 == 0:
                print("   ✅ Time service started")
            else:
                print("   ❌ Failed to start time service (may need admin rights)")
        else:
            print("✅ Time service is running")
            
        if starttype.lower() != 'automatic':
            print("⚠️  Startup type is not Automatic")
    except:
        print("Could not parse service status")
else:
    print("Could not check time service (may need PowerShell)")

# Check 3: Time Sync Status
print("\n[3] TIME SYNC STATUS")
print("-" * 70)

code, out, err = run_cmd("w32tm /query /status")
if code == 0:
    lines = out.split('\n')
    for line in lines[:10]:  # First 10 lines have useful info
        if line.strip():
            print(line)
else:
    print("Could not query time status")

# Check 4: NTP Peers
print("\n[4] NTP PEERS")
print("-" * 70)

code, out, err = run_cmd("w32tm /query /peers")
if code == 0:
    if out.strip():
        print(out)
    else:
        print("No NTP peers configured")
else:
    print("Could not query peers")

# Summary
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)

print("""
Next steps:
1. Run this command to force time sync:
   w32tm /resync
   
2. Restart Django:
   Ctrl+C (stop current server)
   python manage.py runserver
   
3. Try MFA login again

If you're still seeing "Invalid TOTP code":
- Check your authenticator app time
- Make sure it's within 30 seconds of your system time
- Try clearing and re-adding the account in the app
""")

print("=" * 70)
