import sys
import os
import time
import unittest
from unittest.mock import MagicMock, patch

# プロジェクトルートをパスに追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.config_manager import ConfigManager
from src.srt_generator import SrtGenerator
from src.hotkey_manager import HotkeyManager
from src.obs_controller import ObsController

class AutomatedSystemTest(unittest.TestCase):
    def setUp(self):
        with patch('src.config_manager.ConfigManager.load_config') as mock_load, \
             patch('src.config_manager.ConfigManager.save_config') as mock_save:
            mock_load.return_value = {
                "current_preset": "Default",
                "presets": {
                    "Default": {
                        "obs": {
                            "host": "localhost",
                            "port": 4455,
                            "password": "",
                            "path": "C:\\Program Files\\obs-studio\\bin\\64bit\\obs64.exe",
                            "profile": "",
                            "scene_collection": ""
                        },
                        "hotkeys": {
                            "text": "設定字幕"
                        },
                        "subtitles": {
                            "duration": 3.0
                        }
                    }
                }
            }
            self.config = ConfigManager("data/test_config_temp.json")
        self.srt = SrtGenerator()

    def test_config_retrieval(self):
        """設定が正しく読み込めるかテスト"""
        self.assertEqual(self.config.get("obs.host"), "localhost")
        self.assertEqual(self.config.get("hotkeys.text"), "設定字幕")
        self.assertEqual(self.config.get("subtitles.duration"), 3.0)

    def test_srt_formatting(self):
        """SRTの時刻フォーマットが正しいかテスト"""
        self.assertEqual(self.srt.format_time(0), "00:00:00,000")
        self.assertEqual(self.srt.format_time(3661.5), "01:01:01,500")

    @patch('keyboard.add_hotkey')
    @patch('keyboard.remove_hotkey')
    def test_hotkey_recording(self, mock_remove, mock_add):
        """ホットキーの記録プロセスをテスト"""
        hotkey_config = {"text": "Test Setting Subtitle"}
        
        # モックのコールバック
        mock_get_text = MagicMock(return_value="Test Setting Subtitle")
        mock_show_window = MagicMock()
        
        manager = HotkeyManager(
            hotkey_config,
            get_setting_text_callback=mock_get_text,
            show_input_window_callback=mock_show_window
        )
        
        # モニタリング開始
        manager.start_monitoring()
        manager.start_time = time.time() - 10  # 10秒前に開始したことにする
        
        # 1. 設定字幕(Ctrl+Alt+T)記録をシミュレート
        manager._record_setting_text()
        markers = manager.get_markers()
        self.assertEqual(len(markers), 1)
        self.assertEqual(markers[0]["text"], "Test Setting Subtitle")
        self.assertGreaterEqual(markers[0]["time"], 10)
        
        # 2. 小窓表示トリガー(Ctrl+Alt+G)をシミュレート
        manager._trigger_input_window()
        mock_show_window.assert_called_once()
        
        # 3. チャプター記録をシミュレート
        manager._record_chapter()
        self.assertEqual(len(markers), 2)
        self.assertEqual(markers[1]["text"], "チャプター 1")
        
        # 4. 手動マーカー追加（小窓からの確定）をシミュレート
        manager.add_manual_marker("Manual Typed Subtitle", 15.5)
        self.assertEqual(len(markers), 3)
        self.assertEqual(markers[2]["text"], "Manual Typed Subtitle")
        self.assertEqual(markers[2]["time"], 15.5)
        
        manager.stop_monitoring()
        self.assertEqual(mock_remove.call_count, 4)

    def test_obs_controller_interface(self):
        """OBSコントローラーのインターフェース（モック）テスト"""
        with patch('obsws_python.ReqClient') as mock_client:
            obs = ObsController("localhost", 4455, "password")
            
            # Start Recording
            mock_client.return_value.start_record = MagicMock()
            self.assertTrue(obs.start_recording())
            
            # Get Status
            mock_client.return_value.get_record_status.return_value.output_active = True
            self.assertTrue(obs.get_record_status())
            
            # Stop Recording
            mock_response = MagicMock()
            mock_response.output_path = "C:/videos/test.mp4"
            mock_client.return_value.stop_record.return_value = mock_response
            
            path = obs.stop_recording()
            self.assertEqual(path, "C:/videos/test.mp4")

    def test_srt_chapter_separation(self):
        """SRT生成時にチャプターが除外され、別ファイルに正しく生成されるかテスト"""
        markers = [
            {"time": 2.5, "text": "字幕テスト1", "type": "subtitle"},
            {"time": 5.0, "text": "チャプター1", "type": "chapter"},
            {"time": 10.0, "text": "字幕テスト2", "type": "subtitle"}
        ]
        
        srt_path = "data/test_output_temp.srt"
        chap_path = "data/test_output_temp_chapters.txt"
        
        # Ensure output dir exists
        os.makedirs("data", exist_ok=True)
        
        # Clean up any old files
        for p in [srt_path, chap_path]:
            if os.path.exists(p):
                os.remove(p)
                
        # Generate SRT
        self.assertTrue(self.srt.generate(markers, srt_path, duration=3.0))
        # Generate Chapters
        self.assertTrue(self.srt.generate_chapters(markers, chap_path))
        
        # Verify SRT contents: should contain "字幕テスト1" and "字幕テスト2", but NOT "チャプター1"
        self.assertTrue(os.path.exists(srt_path))
        with open(srt_path, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("字幕テスト1", content)
            self.assertIn("字幕テスト2", content)
            self.assertNotIn("チャプター1", content)
            
        # Verify Chapter file contents: should contain "00:00 開始" (automatically prepended because no chapter at 0.0) and "00:05 チャプター1"
        self.assertTrue(os.path.exists(chap_path))
        with open(chap_path, "r", encoding="utf-8") as f:
            content = f.read()
            lines = content.strip().split("\n")
            self.assertEqual(len(lines), 2)
            self.assertEqual(lines[0], "00:00 開始")
            self.assertEqual(lines[1], "00:05 チャプター1")
            
        # Clean up
        for p in [srt_path, chap_path]:
            if os.path.exists(p):
                os.remove(p)

    @patch('subprocess.run')
    def test_ffmpeg_chapters_embed(self, mock_run):
        """FFmpegによるチャプター埋め込み処理が正しく動作するかテスト"""
        markers = [
            {"time": 5.0, "text": "チャプター1", "type": "chapter"}
        ]
        
        # Test case 1: Non-mkv files should return False immediately
        self.assertFalse(self.srt.embed_chapters("video.mp4", markers, "ffmpeg.exe"))
        
        # Test case 2: Empty chapters should return False
        self.assertFalse(self.srt.embed_chapters("video.mkv", [], "ffmpeg.exe"))
        
        # Test case 3: Valid call should run subprocess and return True
        with patch('os.path.exists') as mock_exists, \
             patch('os.remove') as mock_remove, \
             patch('os.rename') as mock_rename:
            # We mock exists to return True for the exe path
            mock_exists.side_effect = lambda path: True if "ffmpeg" in path or "temp_meta" in path or "temp_out" in path or "video.mkv" in path else False
            
            # Run
            result = self.srt.embed_chapters("video.mkv", markers, "ffmpeg.exe", total_duration=10.0)
            
            # Assertions
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            self.assertEqual(args[0], "ffmpeg.exe")
            self.assertEqual(args[1], "-y")
            self.assertEqual(args[2], "-i")
            self.assertEqual(args[3], "video.mkv")
            self.assertEqual(args[4], "-i")
            self.assertTrue(args[5].endswith(".temp_meta.txt"))
            self.assertEqual(args[6], "-map_metadata")
            self.assertEqual(args[7], "1")
            self.assertEqual(args[8], "-map_chapters")
            self.assertEqual(args[9], "1")
            self.assertEqual(args[10], "-codec")
            self.assertEqual(args[11], "copy")
            self.assertTrue(args[12].endswith(".temp_out.mkv"))

if __name__ == "__main__":
    print("Running Automated System Tests...")
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
