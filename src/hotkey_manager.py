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
        self.handlers = []

    def start_monitoring(self):
        self.markers = []
        self.start_time = time.time()
        self.is_monitoring = True
        self.chapter_count = 0
        self.handlers = []
        
        key_record_subtitle = self.hotkey_config.get("key_record_subtitle", "ctrl+alt+t")
        key_open_window = self.hotkey_config.get("key_open_window", "alt+g")
        key_open_chapter_window = self.hotkey_config.get("key_open_chapter_window", "alt+v")
        key_add_chapter = self.hotkey_config.get("key_add_chapter", "alt+c")
        
        try:
            h = keyboard.add_hotkey(key_record_subtitle, self._record_setting_text)
            self.handlers.append(h)
            logging.info(f"Hotkey registered: '{key_record_subtitle}' for recording setting text")
        except Exception as e:
            logging.error(f"Failed to register hotkey '{key_record_subtitle}': {e}")
            
        try:
            h = keyboard.add_hotkey(key_open_window, self._trigger_input_window)
            self.handlers.append(h)
            logging.info(f"Hotkey registered: '{key_open_window}' for input window trigger")
        except Exception as e:
            logging.error(f"Failed to register hotkey '{key_open_window}': {e}")

        try:
            h = keyboard.add_hotkey(key_open_chapter_window, self._trigger_chapter_window)
            self.handlers.append(h)
            logging.info(f"Hotkey registered: '{key_open_chapter_window}' for chapter window trigger")
        except Exception as e:
            logging.error(f"Failed to register hotkey '{key_open_chapter_window}': {e}")
            
        try:
            h = keyboard.add_hotkey(key_add_chapter, self._record_chapter)
            self.handlers.append(h)
            logging.info(f"Hotkey registered: '{key_add_chapter}' for auto-chapter")
        except Exception as e:
            logging.error(f"Failed to register hotkey '{key_add_chapter}': {e}")

    def stop_monitoring(self):
        self.is_monitoring = False
        for h in self.handlers:
            try:
                keyboard.remove_hotkey(h)
            except Exception as e:
                logging.debug(f"Failed to remove hotkey handler: {e}")
        self.handlers = []
        logging.info("Hotkey monitoring stopped (individual handlers removed)")

    def _record_setting_text(self):
        if not self.is_monitoring:
            return
        
        text = "設定字幕"
        if self.get_setting_text_callback:
            text = self.get_setting_text_callback()
            
        elapsed_time = self.get_elapsed_time()
        self.markers.append({
            "time": elapsed_time,
            "text": text,
            "type": "subtitle"
        })
        logging.info(f"Setting text marker recorded: {text} at {elapsed_time:.2f}s")

    def _trigger_input_window(self):
        if not self.is_monitoring:
            return
        if self.show_input_window_callback:
            self.show_input_window_callback("subtitle")

    def _trigger_chapter_window(self):
        if not self.is_monitoring:
            return
        if self.show_input_window_callback:
            self.show_input_window_callback("chapter")

    def _record_chapter(self):
        if not self.is_monitoring:
            return
        
        self.chapter_count += 1
        text = f"チャプター {self.chapter_count}"
        elapsed_time = self.get_elapsed_time()
        self.markers.append({
            "time": elapsed_time,
            "text": text,
            "type": "chapter"
        })
        logging.info(f"Chapter recorded: {text} at {elapsed_time:.2f}s")

    def add_manual_marker(self, text, timestamp, marker_type="subtitle"):
        if not self.is_monitoring:
            return
        self.markers.append({
            "time": timestamp,
            "text": text,
            "type": marker_type
        })
        logging.info(f"Manual marker recorded ({marker_type}): {text} at {timestamp:.2f}s")

    def get_elapsed_time(self):
        if not self.is_monitoring or self.start_time is None:
            return 0.0
        return time.time() - self.start_time

    def get_markers(self):
        return self.markers
