import os
import time
import datetime
import sys
import json
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import smtplib
from email.mime.text import MIMEText
from supabase import create_client

# --- Configuration ---
load_dotenv()

# IPAT Credentials (Rakuten Bank)
IPAT_INET_ID = os.getenv("IPAT_INET_ID")
IPAT_SUBSCRIBER_ID = os.getenv("IPAT_SUBSCRIBER_ID")
IPAT_PARS_NUM = os.getenv("IPAT_PARS_NUM")
IPAT_PIN = os.getenv("IPAT_PIN")

# Safety Caps
DAILY_BUDGET_CAP = int(os.getenv("DAILY_CAP", "10000")) # Default 10,000 JPY
SEMI_AUTO_MODE = os.getenv("SEMI_AUTO_MODE", "True").lower() == "true"

# Mail Config
MAIL_SENDER = os.getenv("MAIL_SENDER")
MAIL_APP_PASS = os.getenv("MAIL_APP_PASS")
MAIL_RECEIVER = os.getenv("MAIL_RECEIVER")

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

class Shopper:
    def __init__(self):
        print(f"[SHOPPER] Initializing... Daily Cap: ¥{DAILY_BUDGET_CAP:,}, Semi-Auto: {SEMI_AUTO_MODE}")
        self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        self.driver = None
        self.total_spent = 0
        self.mail_user = MAIL_SENDER
        self.mail_pass = MAIL_APP_PASS
        self.mail_to = MAIL_RECEIVER
        
        # Verify Env
        if not all([IPAT_INET_ID, IPAT_SUBSCRIBER_ID, IPAT_PARS_NUM, IPAT_PIN]):
            print("[ERROR] Missing IPAT Credentials in .env")
            sys.exit(1)

    def start_browser(self):
        options = webdriver.ChromeOptions()
        # options.add_argument("--headless") # Headless off for visual confirmation
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        
    def login_ipat(self):
        print("[SHOPPER] Logging in to IPAT (Rakuten)...")
        # Access Top Page
        self.driver.get("https://www.ipat.jra.go.jp/")
        
        wait = WebDriverWait(self.driver, 10)
        
        # 1. INET-ID
        try:
            wait.until(EC.presence_of_element_located((By.NAME, "inetid")))
            self.driver.find_element(By.NAME, "inetid").send_keys(IPAT_INET_ID)
            self.driver.find_element(By.CSS_SELECTOR, "a[onclick*='DoLogin']").click()
        except:
            print("[ERROR] Login Step 1 Failed.")
            return False

        # 2. Part 2 Auth (Subscriber, P-ARS, PIN)
        try:
            wait.until(EC.presence_of_element_located((By.NAME, "i")))
            self.driver.find_element(By.NAME, "i").send_keys(IPAT_SUBSCRIBER_ID)
            self.driver.find_element(By.NAME, "p").send_keys(IPAT_PARS_NUM)
            self.driver.find_element(By.NAME, "f").send_keys(IPAT_PIN)
            self.driver.find_element(By.CSS_SELECTOR, "a[onclick*='DoLogin']").click()
            print("[SHOPPER] Login Success.")
            return True
        except:
            print("[ERROR] Login Step 2 Failed.")
            return False

    def send_mail(self, subject, body):
        if not all([self.mail_user, self.mail_pass, self.mail_to]):
            print("[MAIL] Credentials missing. Skipping email.")
            return

        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = self.mail_user
        msg['To'] = self.mail_to

        try:
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(self.mail_user, self.mail_pass)
            server.send_message(msg)
            server.quit()
            print("[MAIL] Sent successfully.")
        except Exception as e:
            print(f"[MAIL] Failed: {e}")

    def check_and_buy(self):
        # 1. Check Safety Cap
        if self.total_spent >= DAILY_BUDGET_CAP:
            print(f"[SAFETY] Daily Cap Reached (¥{self.total_spent:,} / ¥{DAILY_BUDGET_CAP:,}). Stopping.")
            return False

        # 2. Fetch 'Approved' Bets from Supabase
        res = self.supabase.table("bet_queue").select("*").eq("status", "approved").execute()
        bets = res.data if hasattr(res, 'data') else []
        
        if not bets:
            return True # Continue polling

        if not self.driver:
            self.start_browser()
            if not self.login_ipat():
                return True # Retry login later

        purchased_items = []

        for bet in bets:
            print(f"\n[BUY ALERT] Race: {bet['race_id']} Horse: {bet['horse_num']} Amount: ¥{bet['amount']}")
            
            # Update Spending Check
            if self.total_spent + int(bet['amount']) > DAILY_BUDGET_CAP:
                print("[SAFETY] Bet exceeds cap. Skipping.")
                continue

            # --- Manual Confirmation (Semi-Auto) ---
            if SEMI_AUTO_MODE:
                text = input(f"Permission to buy ¥{bet['amount']}? (y/n): ")
                if text.lower() != 'y':
                    print("Skipped.")
                    continue
            
            print("Buying... (Development Mode: Not clicking final button yet)")
            # self.driver.find_element(...) 
            
            # Post-Buy Update
            self.total_spent += int(bet['amount'])
            self.supabase.table("bet_queue").update({"status": "purchased"}).eq("id", bet['id']).execute()
            print(f"[DONE] Purchased. Total Spent: ¥{self.total_spent:,}")
            purchased_items.append(bet)
            
        # Send Summary Mail
        if purchased_items:
            params = {
               'count': len(purchased_items),
               'total': sum(b['amount'] for b in purchased_items),
               'cap': DAILY_BUDGET_CAP,
               'spent': self.total_spent
            }
            body = f"Purchased {params['count']} bets.\nTotal Cost: ¥{params['total']:,}\n\nCurrent Daily Spend: ¥{params['spent']:,} / ¥{params['cap']:,}"
            self.send_mail("JRA Auto-Bet Execution Report", body)

        return True

    def run_loop(self):
        print("[SHOPPER] Searching for approved bets...")
        while True:
            keep_running = self.check_and_buy()
            if not keep_running:
                break
            time.sleep(60) # 1 min Interval

if __name__ == "__main__":
    shopper = Shopper()
    shopper.run_loop()
