#!/usr/bin/env python3
import re

with open('medsync-backend/api/tests/test_phase7_password_recovery.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find and remove the settings method, fix class definition
output = []
i = 0
while i < len(lines):
    line = lines[i]
    
    # Check if this is the problematic settings method
    if 'def settings(self, **kwargs):' in line:
        # Skip this method and the following lines until we reach a new top-level item
        while i < len(lines) and not (lines[i].startswith('class ') or (lines[i].startswith('    """') and i > 0 and lines[i-1].strip() == '')):
            i += 1
        continue
    
    # Fix the broken class definition
    if '"""Test comprehensive audit logging' in line and i > 0 and not lines[i].startswith('class'):
        output.append('\nclass TestAuditLogging(TestCase):\n')
        output.append('    ' + line)
        i += 1
        continue
    
    output.append(line)
    i += 1

with open('medsync-backend/api/tests/test_phase7_password_recovery.py', 'w', encoding='utf-8') as f:
    f.writelines(output)

print("File fixed!")
