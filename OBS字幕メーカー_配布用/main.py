import argparse
import sys
import logging
from logging.handlers import RotatingFileHandler
import os
import ctypes

# Mutex handle storage to prevent garbage collection
_single_instance_mutex = None

def main():
    # Single instance check using Windows Named Mutex
    MUTEX_NAME = "Local\\OBS_Subtitle_Maker_Single_Instance_Mutex"
    kernel32 = ctypes.windll.kernel32
    global _single_instance_mutex
    _single_instance_mutex = kernel32.CreateMutexW(None, True, MUTEX_NAME)
    last_error = kernel32.GetLastError()
    
    if last_error == 183: # ERROR_ALREADY_EXISTS
        ctypes.windll.user32.MessageBoxW(
            0, 
            "OBS字幕メーカーは既に起動しています。\n二重起動はできません。", 
            "二重起動エラー", 
            0x10 | 0x0  # MB_ICONERROR | MB_OK
        )
        sys.exit(0)

    # Setup logging to file with rotation (max 5MB, keep 3 backups)
    log_path = os.path.join("data", "app.log")
    os.makedirs("data", exist_ok=True)
    
    file_handler = RotatingFileHandler(
        log_path, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            file_handler,
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    try:
        parser = argparse.ArgumentParser(description="OBS Subtitle Maker")
        parser.add_argument("--cli", action="store_true", help="Run in CLI mode")
        args = parser.parse_args()

        if args.cli:
            from src.cli import CLIController
            controller = CLIController()
            controller.run()
        else:
            from src.gui.main_window import MainWindow
            app = MainWindow()
            app.mainloop()
    except Exception as e:
        import traceback
        print("\n--- CRITICAL ERROR ---")
        traceback.print_exc()
        print("----------------------")
        input("\nPress Enter to exit...")

if __name__ == "__main__":
    main()
