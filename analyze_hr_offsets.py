
def analyze():
    # Sample 1
    # 2026/02/07 Tokyo 1R (05010301)
    # Win: 11 (2180 yen)
    # Place: 11 (490), 12 (220), 15 (140)
    
    line = "HR12026020720260207050103011616000000000000000000000000000000000000000000000000000000000000000000000001100000218006                          110000004900612000000220051500000014001                          6600000806018                          1112000007620024                                111200000192002211150000012600151215000000420003                                                                                                                1112000013710040                                                                                111215000005780017                                    1112150000827500240"
    
    print(f"Line Length: {len(line)}")
    
    # Target Values
    targets = {
        "Tan_Horse_11": "11",
        "Tan_Pay_2180": "2180",
        "Fuku_Horse_11": "11",
        "Fuku_Pay_490": "490",
        "Fuku_Horse_12": "12",
        "Fuku_Pay_220": "220"
    }
    
    # Search for Tan Horse "11" after header (lines > 50) to avoid catching date/count
    # RaceID ends at 27.
    # 1616... ends at ?
    
    # Let's just find "11000002180" pattern
    pattern_tan = "11000002180"
    idx_tan = line.find(pattern_tan)
    print(f"Tan Pattern '11...2180' found at: {idx_tan}")
    
    if idx_tan != -1:
        # Layout hypothesis based on finding:
        # If idx_tan is start of Tan Horse:
        # Horse: idx_tan ~ idx_tan+2
        # Pay: idx_tan+? ~
        
        # 11 000002180 06
        # H (2) + Pay (9?) + Pop (2)?
        # Let's assume Pay is 7 digits (standard JV).
        # 11 (2 chars)
        # 0000021 (7 chars) -> 21? No, pay is 2180.
        # So "000002180" is 9 chars?
        # Or "00000 2180"? 
        # let's look at substring
        sub = line[idx_tan:idx_tan+20]
        print(f"Tan Substring: '{sub}'")
        # 11 000002180 06
        # 11: Horse (2)
        # 000002180: Pay (9 chars? Or 8?)
        # 06: Pop (2)
        
        # Let's verify standard JV Spec for HR.
        # Usually Pay is 7 digits.
        # Maybe 000002180 is 9 digits?
        # If Pay is 7 digits "0002180"
        # Then there is padding "00" before?
        
    # Fuku Pattern "12...220"
    pattern_fuku_2 = "12000000220"
    idx_fuk2 = line.find(pattern_fuku_2)
    print(f"Fuku 2 Pattern '12...220' found at: {idx_fuk2}")
    
    # Start positions relative to line start
    # We want fixed offsets.

if __name__ == "__main__":
    analyze()
