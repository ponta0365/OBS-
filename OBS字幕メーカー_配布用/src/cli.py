import time
import os
import logging
from src.config_manager import ConfigManager
from src.obs_controller import ObsController
from src.hotkey_manager import HotkeyManager
from src.srt_generator import SrtGenerator

class CLIController:
    def __init__(self):
        self.config = ConfigManager()
        self.obs = ObsController(
            self.config.get("obs.host"),
            self.config.get("obs.port"),
            self.config.get("obs.password"),
            self.config.get("obs.path")
        )
        self.hotkeys = HotkeyManager(self.config.get("hotkeys"))
        self.srt = SrtGenerator()

    def run(self):
        logging.basicConfig(level=logging.INFO)
        
        print("Starting Recording Session (CLI Mode)...")
        print("Ensuring OBS is running...")
        
        if not self.obs.launch_obs():
            print("Error: Could not launch or connect to OBS. Please check the path and if OBS WebSocket is enabled.")
            return

        # Apply Profile and Scene Collection
        print("Applying OBS Settings...")
        self.obs.set_profile(self.config.get("obs.profile"))
        self.obs.set_scene_collection(self.config.get("obs.scene_collection"))

        print("Press Ctrl+C to stop recording.")

        if not self.obs.start_recording():
            print("Error: Could not start OBS recording.")
            return

        self.hotkeys.start_monitoring()

        try:
            while True:
                time.sleep(1)
                if not self.obs.get_record_status():
                    print("Recording stopped from OBS.")
                    break
        except KeyboardInterrupt:
            print("\nStopping session...")

        self.hotkeys.stop_monitoring()
        video_path = self.obs.stop_recording()

        duration = self.config.get("subtitles.duration", 3.0)
        if video_path:
            srt_path = os.path.splitext(video_path)[0] + ".srt"
            self.srt.generate(self.hotkeys.get_markers(), srt_path, duration=duration)
            
            chapters_path = os.path.splitext(video_path)[0] + "_chapters.txt"
            self.srt.generate_chapters(self.hotkeys.get_markers(), chapters_path)
            
            # Embed chapters to MKV in-place using mkvpropedit
            mkvprop_path = self.config.get("obs.mkvpropedit_path")
            self.srt.embed_chapters(video_path, self.hotkeys.get_markers(), mkvpropedit_path=mkvprop_path)
            
            print(f"Session finished. Video: {video_path}, SRT: {srt_path}, Chapters: {chapters_path}")
        else:
            # Fallback if video path is unknown
            output_dir = self.config.get("output.dir", "data/output")
            os.makedirs(output_dir, exist_ok=True)
            timestamp = int(time.time())
            srt_path = os.path.join(output_dir, f"recording_{timestamp}.srt")
            self.srt.generate(self.hotkeys.get_markers(), srt_path, duration=duration)
            
            chapters_path = os.path.join(output_dir, f"recording_{timestamp}_chapters.txt")
            self.srt.generate_chapters(self.hotkeys.get_markers(), chapters_path)
            
            print(f"Session finished. SRT saved to: {srt_path}, Chapters to: {chapters_path} (Video path unknown)")
