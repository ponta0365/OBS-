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
        if not markers:
            logging.warning("No markers to generate SRT")
            return False

        try:
            with open(output_path, "w", encoding="utf-8") as f:
                for i, marker in enumerate(markers):
                    start_time = marker["time"]
                    # If it's the last marker, display for 'duration' seconds.
                    # Otherwise, display until the next marker or 'duration' seconds, whichever is shorter.
                    if i < len(markers) - 1:
                        end_time = min(start_time + duration, markers[i+1]["time"])
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
