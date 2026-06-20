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

    def embed_chapters(self, video_path, markers, ffmpeg_path=None, total_duration=0.0):
        if not video_path or not video_path.lower().endswith(".mkv"):
            return False
            
        # Find ffmpeg executable
        import shutil
        ffmpeg_exe = None
        
        # 1. Check custom path if specified
        if ffmpeg_path:
            if os.path.isdir(ffmpeg_path):
                exe_path = os.path.join(ffmpeg_path, "ffmpeg.exe")
                if os.path.exists(exe_path):
                    ffmpeg_exe = exe_path
            elif os.path.exists(ffmpeg_path):
                ffmpeg_exe = ffmpeg_path
                
        # 2. Check system PATH
        if not ffmpeg_exe:
            ffmpeg_exe = shutil.which("ffmpeg")
            
        # 3. Check common paths
        if not ffmpeg_exe:
            default_paths = [
                r"C:\ffmpeg\bin\ffmpeg.exe",
                r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
                r"C:\ffmpeg\ffmpeg.exe",
            ]
            for p in default_paths:
                if os.path.exists(p):
                    ffmpeg_exe = p
                    break
                    
        if not ffmpeg_exe or not os.path.exists(ffmpeg_exe):
            logging.warning("ffmpeg executable not found. Skipping embedding chapters to MKV.")
            return False

        chapter_markers = [m for m in markers if m.get("type") == "chapter"]
        if not chapter_markers:
            return False
            
        chapter_markers = sorted(chapter_markers, key=lambda x: x["time"])
        if not chapter_markers or chapter_markers[0]["time"] >= 1.0:
            chapter_markers.insert(0, {"time": 0.0, "text": "開始"})

        # Paths
        temp_meta_path = video_path + ".temp_meta.txt"
        temp_out_path = video_path + ".temp_out.mkv"

        try:
            # Generate FFMETADATA file
            with open(temp_meta_path, "w", encoding="utf-8") as f:
                f.write(";FFMETADATA1\n")
                for i, marker in enumerate(chapter_markers):
                    start_ms = int(marker["time"] * 1000)
                    if i < len(chapter_markers) - 1:
                        end_ms = int(chapter_markers[i+1]["time"] * 1000)
                    else:
                        end_ms = int(max(total_duration * 1000, start_ms + 5000))
                        
                    f.write("[CHAPTER]\n")
                    f.write("TIMEBASE=1/1000\n")
                    f.write(f"START={start_ms}\n")
                    f.write(f"END={end_ms}\n")
                    # Escape metadata characters
                    escaped_title = marker["text"].replace("\\", "\\\\").replace(";", "\\;").replace("#", "\\#").replace("=", "\\=")
                    f.write(f"title={escaped_title}\n\n")

            # Run ffmpeg
            import subprocess
            import time
            cmd = [
                ffmpeg_exe,
                "-y",
                "-i", video_path,
                "-i", temp_meta_path,
                "-map_metadata", "1",
                "-map_chapters", "1",
                "-codec", "copy",
                temp_out_path
            ]
            logging.info(f"Running FFmpeg to embed chapters: {' '.join(cmd)}")
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logging.info("FFmpeg successfully created MKV with embedded chapters.")

            # Replace original file with the new file
            # Wait for any file locks to release (try up to 5 times)
            success = False
            for attempt in range(5):
                try:
                    if os.path.exists(video_path):
                        os.remove(video_path)
                    os.rename(temp_out_path, video_path)
                    success = True
                    logging.info("Successfully replaced video file with chapter-embedded version.")
                    break
                except Exception as ex:
                    logging.warning(f"File replacement attempt {attempt+1}/5 failed: {ex}")
                    time.sleep(1)
            
            if not success:
                raise OSError("Could not replace video file (possibly locked by OBS or other process).")
            return True
            
        except Exception as e:
            logging.error(f"Failed to embed chapters in MKV using FFmpeg: {e}")
            if os.path.exists(temp_out_path):
                try:
                    os.remove(temp_out_path)
                except Exception:
                    pass
            return False
        finally:
            if os.path.exists(temp_meta_path):
                try:
                    os.remove(temp_meta_path)
                except Exception:
                    pass
