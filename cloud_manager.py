import streamlit as st
import datetime
from supabase import create_client
import os

# Wrapper for reading/writing system config to Supabase
# Table: system_config (key: text PK, value: text, updated_at: timestamp)

class CloudManager:
    def __init__(self, supabase):
        self.client = supabase

    def get_config(self, key, default_value):
        try:
            # st.cache_data removed here to ensure real-time toggle response for critical switches
            # or use logic to force refresh. For now, direct DB hit is safer for "Stop Button".
            response = self.client.table("system_config").select("value").eq("key", key).execute()
            if response.data:
                return response.data[0]['value']
            else:
                return default_value
        except Exception as e:
            print(f"[CloudManager] Error fetching {key}: {e}")
            return default_value

    def set_config(self, key, value):
        try:
            now = datetime.datetime.now().isoformat()
            data = {"key": key, "value": str(value), "updated_at": now}
            self.client.table("system_config").upsert(data).execute()
            return True
        except Exception as e:
             print(f"[CloudManager] Error setting {key}: {e}")
             return False

    # Helpers for specific keys
    def is_auto_bet_active(self):
        # User defined key: 'AUTO_BET' ('true'/'false')
        val = self.get_config("AUTO_BET", "false")
        return val.lower() == "true"

    def set_auto_bet_active(self, is_active: bool):
        val = "true" if is_active else "false"
        return self.set_config("AUTO_BET", val)

    def get_daily_cap(self):
        val = self.get_config("daily_cap", "10000") # Keep lower for now unless user specified otherwise, or unify. User didn't specify daily cap key in prompt, just AUTO_BET.
        try:
            return int(val)
        except:
            return 10000
    
    def set_daily_cap(self, amount: int):
        return self.set_config("daily_cap", str(amount))

    def check_admin_pass(self, input_pass):
        # User defined key: 'ADMIN_PASSWORD'
        if not input_pass: return False
        stored = self.get_config("ADMIN_PASSWORD", "")
        if not stored:
            # Fallback to Env if DB entry missing
            return input_pass == os.getenv("ADMIN_PASS")
        return input_pass == stored

    def log_system_event(self, level, message, details=""):
        try:
            data = {
                "level": level,
                "message": message,
                "details": str(details),
                # timestamp defaults to now() in DB
            }
            self.client.table("system_logs").insert(data).execute()
        except Exception as e:
            print(f"[CloudManager] Log failed: {e}")
