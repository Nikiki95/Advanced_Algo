#!/usr/bin/env python3
"""
API Key Manager for TheOddsAPI
Monitors usage and switches to backup key when primary is exhausted
"""

import os
import requests
from datetime import datetime
from pathlib import Path

ENV_PATH = Path('secrets/.env')
USAGE_LOG = Path('logs/api_usage.log')

def log_usage(key_type, status, message):
    """Log API usage"""
    USAGE_LOG.parent.mkdir(exist_ok=True)
    with open(USAGE_LOG, 'a') as f:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        f.write(f"{timestamp} | {key_type} | {status} | {message}\n")

def check_key_status(api_key):
    """Check if API key is valid and has quota"""
    try:
        url = "https://api.the-odds-api.com/v4/sports"
        resp = requests.get(url, params={'apiKey': api_key}, timeout=10)
        
        if resp.status_code == 200:
            return True, "Active"
        elif resp.status_code == 401:
            data = resp.json()
            if 'quota' in data.get('message', '').lower() or 'usage' in data.get('message', '').lower():
                return False, "Quota exceeded"
            return False, "Invalid key"
        else:
            return False, f"Error {resp.status_code}"
    except Exception as e:
        return False, f"Exception: {e}"

def get_active_key():
    """Get the active API key, switching if necessary"""
    # Load current env
    env_vars = {}
    if ENV_PATH.exists():
        with open(ENV_PATH) as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    env_vars[key] = value
    
    primary_key = env_vars.get('THEODDS_API_KEY', '')
    backup_key = env_vars.get('THEODDS_API_KEY_BACKUP', '')
    
    # Check primary key
    primary_ok, primary_status = check_key_status(primary_key)
    
    if primary_ok:
        log_usage("PRIMARY", "OK", "Using primary key")
        return primary_key, "primary"
    else:
        log_usage("PRIMARY", "FAIL", primary_status)
        print(f"⚠️  Primary key failed: {primary_status}")
        
        # Try backup key
        if backup_key:
            backup_ok, backup_status = check_key_status(backup_key)
            
            if backup_ok:
                log_usage("BACKUP", "OK", "Switched to backup key")
                print(f"✅ Switched to backup key")
                
                # Swap keys in env file
                swap_keys()
                
                return backup_key, "backup"
            else:
                log_usage("BACKUP", "FAIL", backup_status)
                print(f"❌ Backup key also failed: {backup_status}")
                return None, "none"
        else:
            print("❌ No backup key configured")
            return None, "none"

def swap_keys():
    """Swap primary and backup keys in .env file"""
    if not ENV_PATH.exists():
        return
    
    with open(ENV_PATH) as f:
        content = f.read()
    
    # Read current values
    lines = content.split('\n')
    new_lines = []
    
    primary_val = None
    backup_val = None
    
    for line in lines:
        if line.startswith('THEODDS_API_KEY=') and not line.startswith('THEODDS_API_KEY_BACKUP='):
            primary_val = line.split('=', 1)[1]
        elif line.startswith('THEODDS_API_KEY_BACKUP='):
            backup_val = line.split('=', 1)[1]
    
    # Swap values
    for line in lines:
        if line.startswith('THEODDS_API_KEY=') and not line.startswith('THEODDS_API_KEY_BACKUP='):
            new_lines.append(f'THEODDS_API_KEY={backup_val}  # Was backup, now primary')
        elif line.startswith('THEODDS_API_KEY_BACKUP='):
            new_lines.append(f'THEODDS_API_KEY_BACKUP={primary_val}  # Was primary, now backup')
        else:
            new_lines.append(line)
    
    with open(ENV_PATH, 'w') as f:
        f.write('\n'.join(new_lines))
    
    print("📝 Keys swapped in .env file")

def main():
    print("🔑 API Key Manager")
    print("="*60)
    
    key, key_type = get_active_key()
    
    if key:
        print(f"\n✅ Active key: {key_type.upper()}")
        print(f"   Key: {key[:10]}...{key[-4:]}")
        return key
    else:
        print("\n❌ No valid API key available")
        return None

if __name__ == "__main__":
    main()
