import pandas as pd
import numpy as np

def clean_numeric(x):
    """
    Cleans Japanese numeric strings (full-width to half-width) and converts to float.
    """
    if isinstance(x, str):
        x = x.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
        x = ''.join(c for c in x if c.isdigit() or c == '.')
    try:
        return float(x)
    except:
        return np.nan

def process_features(df):
    """
    Applies the exact feature engineering logic used in the winning model (Pattern C).
    Includes:
    - n-1 Lag Features (Prev_PCI, Prev_3F, Prev_Rank)
    - Current Race Conditions (Odds, Pop, Weight, etc.)
    """
    # 1. Date Construction (if not already datetime)
    if 'Date' not in df.columns:
        if {'年', '月', '日'}.issubset(df.columns):
            df['Date'] = pd.to_datetime(df['年'].astype(str).str.zfill(2) + 
                                        df['月'].astype(str).str.zfill(2) + 
                                        df['日'].astype(str).str.zfill(2), format='%y%m%d')
        else:
            # Assume 'Timestamp' or similar if coming from API, but for CSV flow:
            pass

    # 2. Clean Raw Columns (Numeric Conversion)
    raw_cols = {
        'PCI': 'PCI', 
        '上り3F': '上がり3Fタイム', 
        '着順': '確定着順'
    }
    for alias, orig in raw_cols.items():
        if orig in df.columns:
            df[alias] = df[orig].apply(clean_numeric)

    # 3. Valid Horse ID Check
    if '血統登録番号' not in df.columns:
        raise ValueError("Horse ID '血統登録番号' missing. Cannot calculate lag features.")

    # 4. Sort for Shift (Time-Series)
    # Ensure stable sort
    df = df.sort_values(['血統登録番号', 'Date'])

    # 5. Create Lag Features (Shift 1 -> n-1)
    # This assumes the dataframe contains PAST history for the horses.
    # For a "Single Race Prediction" in production, we must fetch history first.
    df['Prev_PCI'] = df.groupby('血統登録番号')['PCI'].shift(1)
    df['Prev_3F'] = df.groupby('血統登録番号')['上り3F'].shift(1)
    df['Prev_Rank'] = df.groupby('血統登録番号')['着順'].shift(1)

    # 6. Current info (Known before race)
    feature_mapping = {
        '人気': '人気順',
        '単勝オッズ': '単勝オッズ',
        '頭数': '頭数',
        '馬番': '馬番',
        '斤量': '斤量'
    }
    current_features = []
    for alias, original in feature_mapping.items():
        if original in df.columns:
            df[alias] = df[original].apply(clean_numeric)
            current_features.append(alias)
    
    # 7. Define Final Feature Set
    feature_cols = ['Prev_PCI', 'Prev_3F', 'Prev_Rank'] + current_features
    
    return df, feature_cols
