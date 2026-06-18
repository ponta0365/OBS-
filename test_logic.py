import sys
import os
import time

# プロジェクトルートをパスに追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.config_manager import ConfigManager
from src.srt_generator import SrtGenerator
from src.hotkey_manager import HotkeyManager

def test_srt_generation():
    print("Testing SRT generation...")
    config = ConfigManager()
    hotkeys = HotkeyManager(config.get("hotkeys"))
    srt = SrtGenerator()

    # 擬似的なマーカーデータを作成
    markers = [
        {"time": 1.5, "text": "Start Point"},
        {"time": 5.0, "text": "Mid Point"},
        {"time": 12.3, "text": "End Point"}
    ]
    
    output_path = os.path.join("data", "test_output.srt")
    if srt.generate(markers, output_path):
        print(f"SUCCESS: SRT generated at {output_path}")
        with open(output_path, "r", encoding="utf-8") as f:
            print("--- SRT Content ---")
            print(f.read())
            print("-------------------")
    else:
        print("FAILED: SRT generation failed")

if __name__ == "__main__":
    test_srt_generation()
