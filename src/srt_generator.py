import datetime
import os
import logging

class SrtGenerator:
    @staticmethod
    def format_time(seconds):
        td = datetime.timedelta(seconds=seconds)
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        millis = int((td.total_seconds() - total_seconds) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def generate(self, markers, output_path, duration=3.0):
        # Filter out chapters from SRT
        sub_markers = [m for m in markers if m.get("type", "subtitle") != "chapter"]
        
        if not sub_markers:
            logging.warning("No subtitle markers to generate SRT")
            return False

        try:
            with open(output_path, "w", encoding="utf-8") as f:
                for i, marker in enumerate(sub_markers):
                    start_time = marker["time"]
                    # If it's the last marker, display for 'duration' seconds.
                    # Otherwise, display until the next marker or 'duration' seconds, whichever is shorter.
                    if i < len(sub_markers) - 1:
                        end_time = min(start_time + duration, sub_markers[i+1]["time"])
                    else:
                        end_time = start_time + duration
                    
                    f.write(f"{i + 1}\n")
                    f.write(f"{self.format_time(start_time)} --> {self.format_time(end_time)}\n")
                    f.write(f"{marker['text']}\n\n")
            
            logging.info(f"SRT generated: {output_path}")
            return True
        except Exception as e:
            logging.error(f"Failed to generate SRT: {e}")
            return False

    def generate_chapters(self, markers, output_path):
        chapter_markers = [m for m in markers if m.get("type") == "chapter"]
        if not chapter_markers:
            return False
            
        # Ensure we have a chapter at 0.0 (YouTube format requires it)
        chapter_markers = sorted(chapter_markers, key=lambda x: x["time"])
        if not chapter_markers or chapter_markers[0]["time"] >= 1.0:
            # Insert a default start chapter at 0.0
            chapter_markers.insert(0, {"time": 0.0, "text": "開始"})
            
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                for marker in chapter_markers:
                    seconds = marker["time"]
                    hours = int(seconds // 3600)
                    minutes = int((seconds % 3600) // 60)
                    secs = int(seconds % 60)
                    if hours > 0:
                        timestamp_str = f"{hours:02d}:{minutes:02d}:{secs:02d}"
                    else:
                        timestamp_str = f"{minutes:02d}:{secs:02d}"
                    f.write(f"{timestamp_str} {marker['text']}\n")
            logging.info(f"Chapters generated: {output_path}")
            return True
        except Exception as e:
            logging.error(f"Failed to generate chapters file: {e}")
            return False
