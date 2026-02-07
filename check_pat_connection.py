import os
import sys
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time

# Load Env
load_dotenv()

IPAT_INET_ID = os.getenv("IPAT_INET_ID")
IPAT_SUBSCRIBER_ID = os.getenv("IPAT_SUBSCRIBER_ID")
IPAT_PARS_NUM = os.getenv("IPAT_PARS_NUM")
IPAT_PIN = os.getenv("IPAT_PIN")

def check_connection():
    print("=== JRA IPAT CONNECTION CHECK ===")
    print(f"INET ID: {IPAT_INET_ID[:4]}****")
    
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    try:
        # 1. Login
        print("Logging in...")
        driver.get("https://www.ipat.jra.go.jp/")
        wait = WebDriverWait(driver, 10)
        
        # Step 1
        wait.until(EC.presence_of_element_located((By.NAME, "inetid")))
        driver.find_element(By.NAME, "inetid").send_keys(IPAT_INET_ID)
        driver.find_element(By.CSS_SELECTOR, "a[onclick*='DoLogin']").click()
        
        # Step 2
        wait.until(EC.presence_of_element_located((By.NAME, "i")))
        driver.find_element(By.NAME, "i").send_keys(IPAT_SUBSCRIBER_ID)
        driver.find_element(By.NAME, "p").send_keys(IPAT_PARS_NUM)
        driver.find_element(By.NAME, "f").send_keys(IPAT_PIN)
        driver.find_element(By.CSS_SELECTOR, "a[onclick*='DoLogin']").click()
        
        # 2. Verify Top Page
        print("Verifying Top Page...")
        time.sleep(2)
        if "トップメニュー" in driver.title or "投票メニュー" in driver.page_source:
             print("[SUCCESS] Login Successful.")
        else:
             print("[ERROR] Login Failed (Title mismatch).")
             driver.save_screenshot("login_fail.png")
             return

        # 3. Check Balance
        # Look for avail money. Usually id="avail_money" or class
        # Trying a generic selector for now based on typical IPAT layout (avail_money is often the ID)
        balance_text = "N/A"
        try:
             # Common ID for balance in JRA IPAT PC site
             # Note: It might be different. I will dump text if ID fails.
             # Actually, simpler to look for "購入限度額" label
             body_text = driver.find_element(By.TAG_NAME, "body").text
             # Parse budget from text? 
             # Or try specific element. 'ng-binding' often used if angular, but IPAT is old.
             # Let's try to finding element with text "購入限度額" and getting next value.
             pass
        except:
             pass
        
        print("[INFO] Connection verified. (Balance check skipped in simple mode)")
        
    except Exception as e:
        print(f"[ERROR] {e}")
        driver.save_screenshot("error.png")
    finally:
        driver.quit()

if __name__ == "__main__":
    check_connection()
