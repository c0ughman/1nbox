#!/usr/bin/env python3
"""
Quick script to verify environment variables are set correctly.
Run this locally or add as a temporary endpoint to test.
"""
import os
import sys

def check_env_vars():
    """Check if required environment variables are set"""
    print("=" * 60)
    print("ENVIRONMENT VARIABLE VERIFICATION")
    print("=" * 60)
    
    required = {
        'DATABASE_URL': {
            'required': True,
            'check': lambda v: v.startswith(('postgresql://', 'postgres://')),
            'error_msg': 'Must start with postgresql:// or postgres://'
        },
        'DJANGO_SECRET_KEY': {
            'required': True,
            'check': lambda v: len(v) >= 50,
            'error_msg': 'Must be at least 50 characters long'
        }
    }
    
    optional = ['GEMINI_KEY', 'OPENAI_KEY', 'SENDGRID_API_KEY']
    
    all_good = True
    
    print("\n🔴 REQUIRED VARIABLES:")
    for var_name, checks in required.items():
        value = os.environ.get(var_name)
        if not value:
            print(f"  ❌ {var_name}: NOT SET")
            all_good = False
        elif not checks['check'](value):
            print(f"  ⚠️  {var_name}: SET but INVALID")
            print(f"     Value: {value[:50]}...")
            print(f"     Issue: {checks['error_msg']}")
            all_good = False
        else:
            # Show first/last few chars for verification
            preview = f"{value[:20]}...{value[-10:]}" if len(value) > 30 else value
            print(f"  ✅ {var_name}: SET ({len(value)} chars)")
            print(f"     Preview: {preview}")
    
    print("\n🟡 OPTIONAL VARIABLES:")
    for var_name in optional:
        value = os.environ.get(var_name)
        if value:
            print(f"  ✅ {var_name}: SET ({len(value)} chars)")
        else:
            print(f"  ⚪ {var_name}: NOT SET (optional)")
    
    print("\n" + "=" * 60)
    if all_good:
        print("✅ ALL REQUIRED VARIABLES ARE SET CORRECTLY")
        print("=" * 60)
        return 0
    else:
        print("❌ SOME REQUIRED VARIABLES ARE MISSING OR INVALID")
        print("=" * 60)
        return 1

if __name__ == '__main__':
    sys.exit(check_env_vars())

