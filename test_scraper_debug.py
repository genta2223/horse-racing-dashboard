
import requests
from bs4 import BeautifulSoup
import datetime

def test_scrape():
    # Target: 2026/02/07 Tokyo 1R (JRA ID: 2026020705010301)
    # Expected Netkeiba ID: 202605010301
    
    jra_id = "2026020705010301"
    nk_id = "202605010301"
    
    url = f"https://race.netkeiba.com/race/result.html?race_id={nk_id}"
    print(f"Testing URL: {url}")
    
    try:
        resp = requests.get(url, timeout=10)
        print(f"Status Code: {resp.status_code}")
        
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.content, "html.parser")
            title = soup.title.string if soup.title else "No Title"
            print(f"Page Title: {title}")
            
            table = soup.find("table", id="All_Result_Table")
            if table:
                print("FOUND 'All_Result_Table'. Parsing seems OK.")
                rows = table.find_all("tr", class_="HorseList")
                print(f"Found {len(rows)} horse rows.")
            else:
                print("NOT FOUND 'All_Result_Table'.")
                # Debug: Print all table IDs
                tables = soup.find_all("table")
                print(f"Found {len(tables)} tables on page.")
                for i, t in enumerate(tables):
                    print(f"Table {i} ID: {t.get('id')}")
        else:
            print("Request failed.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_scrape()
