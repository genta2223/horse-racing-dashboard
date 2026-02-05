import win32com.client
import sys

def main():
    print(f"Python Version: {sys.version}")
    print("--- JV-Link 接続テスト開始 ---")
    try:
        # JV-Linkを呼び出す
        jv_link = win32com.client.Dispatch("JVDTLab.JVLink")
        
        print("[OK] JV-Link Success")
        
        # 初期化処理 ("UNKNOWN"はテスト用のキー)
        ret = jv_link.JVInit("UNKNOWN")
        
        if ret == 0:
            print("[OK] Init Success (JVInit)")
            print("Press OK on the Setup Screen...")
            
            # 設定画面を呼び出す
            jv_link.JVSetUIProperties()
            
            # 終了処理
            jv_link.JVClose()
            print("[OK] Test Complete!")
        else:
            print(f"[ERROR] Init Failed. Code: {ret}")
            
    except Exception as e:
        print("❌ エラーが発生しました")
        print(e)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
