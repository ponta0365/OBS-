import sys
import os
import time
import logging

# プロジェクトルートをパスに追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.config_manager import ConfigManager
from src.obs_controller import ObsController
from src.browser_manager import BrowserManager
from src.hotkey_manager import HotkeyManager
from src.srt_generator import SrtGenerator

def run_integration_test():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    print("=== OBS Subtitle Maker Integration Test ===")
    print("This test will briefly launch the browser and check key components.")
    print("Ensure OBS is running if you want to test OBS connection.\n")

    config = ConfigManager()
    
    # 1. Browser Test
    print("[1/4] Testing BrowserManager (Playwright)...")
    browser = BrowserManager(
        config.get("browser.url"),
        config.get("browser.width"),
        config.get("browser.height")
    )
    if browser.launch():
        print("SUCCESS: Browser launched.")
        time.sleep(2)  # Wait a bit to see the browser
        browser.close()
        print("SUCCESS: Browser closed.")
    else:
        print("FAILED: Browser launch failed.")

    # 2. OBS Connection Test (Optional/Soft failure)
    print("\n[2/4] Testing ObsController connection...")
    obs = ObsController(
        config.get("obs.host"),
        config.get("obs.port"),
        config.get("obs.password")
    )
    if obs.connect():
        print("SUCCESS: Connected to OBS.")
        status = obs.get_record_status()
        print(f"Current OBS Recording Status: {'Recording' if status else 'Idle'}")
        obs.disconnect()
    else:
        print("SKIPPED/FAILED: Could not connect to OBS. (Make sure OBS is running with WebSocket enabled)")

    # 3. Hotkey Test
    print("\n[3/4] Testing HotkeyManager...")
    print("PLEASE NOTE: This part requires 5 seconds of your time.")
    print("Action: Try pressing 'Ctrl+F1' or 'Ctrl+F2' within the next 5 seconds...")
    
    hotkeys = HotkeyManager(config.get("hotkeys"))
    hotkeys.start_monitoring()
    
    for i in range(5, 0, -1):
        print(f"{i}...")
        time.sleep(1)
    
    markers = hotkeys.get_markers()
    hotkeys.stop_monitoring()
    
    if markers:
        print(f"SUCCESS: Recorded {len(markers)} markers:")
        for m in markers:
            print(f"  - {m['text']} at {m['time']:.2f}s")
    else:
        print("INFO: No markers recorded. (Did you press the hotkeys? Some environments need Admin privileges)")

    # 4. SRT Export Test
    print("\n[4/4] Testing SRT generation from recorded markers...")
    if not markers:
        print("Using dummy markers for SRT test since no hotkeys were pressed.")
        markers = [{"time": 1.0, "text": "Dummy Marker"}]
    
    srt = SrtGenerator()
    test_srt_path = os.path.join("data", "integration_test.srt")
    if srt.generate(markers, test_srt_path):
        print(f"SUCCESS: SRT file generated at {test_srt_path}")
    else:
        print("FAILED: SRT generation failed.")

    print("\n=== Integration Test Finished ===")

if __name__ == "__main__":
    run_integration_test()
