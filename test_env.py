#!/usr/bin/env python3
"""Test environment variables before Django loads"""
import os
import sys

print("=" * 50)
print("ENVIRONMENT VARIABLE CHECK")
print("=" * 50)

# Check critical variables
required_vars = ['DATABASE_URL', 'DJANGO_SECRET_KEY']
optional_vars = ['FIREBASE_PROJECT_ID', 'FIREBASE_PRIVATE_KEY', 'FIREBASE_CLIENT_EMAIL']

print("\nREQUIRED VARIABLES:")
for var in required_vars:
    value = os.environ.get(var)
    if value:
        print(f"✓ {var}: {value[:30]}...")
    else:
        print(f"✗ {var}: NOT SET")
        sys.exit(1)

print("\nOPTIONAL VARIABLES (Firebase):")
for var in optional_vars:
    value = os.environ.get(var)
    if value:
        if var == 'FIREBASE_PRIVATE_KEY':
            # Check if it has actual newlines vs \n
            if '\n' in value and not value.startswith('-----BEGIN'):
                print(f"✗ {var}: HAS ACTUAL NEWLINES - THIS WILL FAIL!")
                print(f"   First 50 chars: {repr(value[:50])}")
                print("   FIX: Make it ONE LINE with \\n as literal text")
            else:
                print(f"✓ {var}: {value[:40]}...")
        else:
            print(f"✓ {var}: {value}")
    else:
        print(f"- {var}: NOT SET (optional)")

print("\n" + "=" * 50)
print("Environment check complete!")
print("=" * 50)

