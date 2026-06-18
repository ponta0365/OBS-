import keyboard
import time
import logging

class HotkeyManager:
    def __init__(self, hotkey_config, get_setting_text_callback=None, show_input_window_callback=None):
        self.hotkey_config = hotkey_config
        self.get_setting_text_callback = get_setting_text_callback
        self.show_input_window_callback = show_input_window_callback
        self.markers = []
        self.start_time = None
        self.is_monitoring = False
        self.chapter_count = 0

    def start_monitoring(self):
        self.markers = []
        self.start_time = time.time()
        self.is_monitoring = True
        self.chapter_count = 0
        
        # 1. Ctrl + Alt + T: 設定した字幕を入力
        keyboard.add_hotkey("ctrl+alt+t", self._record_setting_text)
        
        # 2. Alt + G: 入力用小窓を表示
        keyboard.add_hotkey("alt+g", self._trigger_input_window)
        
        # 3. Alt + C: 自動チャプターの作成
        keyboard.add_hotkey("alt+c", self._record_chapter)
        
        logging.info("Hotkey monitoring started (Ctrl+Alt+T, Ctrl+Alt+G, Alt+C registered)")

    def stop_monitoring(self):
        self.is_monitoring = False
        keyboard.unhook_all()
        logging.info("Hotkey monitoring stopped")

    def _record_setting_text(self):
        if not self.is_monitoring:
            return
        
        text = "設定字幕"
        if self.get_setting_text_callback:
            text = self.get_setting_text_callback()
            
        elapsed_time = self.get_elapsed_time()
        self.markers.append({
            "time": elapsed_time,
            "text": text
        })
        logging.info(f"Setting text marker recorded: {text} at {elapsed_time:.2f}s")

    def _trigger_input_window(self):
        if not self.is_monitoring:
            return
        if self.show_input_window_callback:
            self.show_input_window_callback()

    def _record_chapter(self):
        if not self.is_monitoring:
            return
        
        self.chapter_count += 1
        text = f"チャプター {self.chapter_count}"
        elapsed_time = self.get_elapsed_time()
        self.markers.append({
            "time": elapsed_time,
            "text": text
        })
        logging.info(f"Chapter recorded: {text} at {elapsed_time:.2f}s")

    def add_manual_marker(self, text, timestamp):
        if not self.is_monitoring:
            return
        self.markers.append({
            "time": timestamp,
            "text": text
        })
        logging.info(f"Manual marker recorded: {text} at {timestamp:.2f}s")

    def get_elapsed_time(self):
        if not self.is_monitoring or self.start_time is None:
            return 0.0
        return time.time() - self.start_time

    def get_markers(self):
        return self.markers
