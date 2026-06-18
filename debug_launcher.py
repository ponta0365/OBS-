import sys
import os
import logging
import traceback

# ログの設定
LOG_FILE = "debug_launcher.log"
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

def run_diagnostic():
    logging.info("=== OBS Subtitle Maker Diagnostic Startup ===")
    logging.info(f"Python version: {sys.version}")
    logging.info(f"Working directory: {os.getcwd()}")

    try:
        # 1. Path check
        logging.info("[Step 1] Checking project structure...")
        src_path = os.path.join(os.getcwd(), "src")
        if not os.path.exists(src_path):
            logging.error("src directory not found!")
        else:
            logging.info("src directory found.")
        sys.path.append(os.getcwd())

        # 2. Dependency check
        logging.info("[Step 2] Checking core dependencies...")
        try:
            import customtkinter as ctk
            logging.info(f"customtkinter imported successfully. Version: {ctk.__version__}")
        except ImportError as e:
            logging.error(f"Failed to import customtkinter: {e}")
        
        try:
            import obsws_python as obs
            logging.info("obsws-python imported successfully.")
        except ImportError as e:
            logging.error(f"Failed to import obsws-python: {e}")

        try:
            from playwright.sync_api import sync_playwright
            logging.info("playwright imported successfully.")
        except ImportError as e:
            logging.error(f"Failed to import playwright: {e}")

        # 3. ConfigManager check
        logging.info("[Step 3] Initializing ConfigManager...")
        try:
            from src.config_manager import ConfigManager
            config = ConfigManager()
            logging.info(f"Config loaded: {config.config_path}")
            logging.debug(f"Current Config Data: {config.config}")
        except Exception as e:
            logging.error(f"ConfigManager initialization failed: {e}")
            logging.error(traceback.format_exc())

        # 4. GUI Initialization (The most likely crash point)
        logging.info("[Step 4] Attempting to initialize GUI (MainWindow)...")
        logging.info("If it crashes here, the issue is likely with Tcl/Tk or CustomTkinter appearance settings.")
        try:
            from src.gui.main_window import MainWindow
            # We don't call mainloop() yet, just instantiation
            app = MainWindow()
            logging.info("MainWindow instantiated successfully.")
            
            logging.info("Diagnostic finished successfully. No immediate crashes found.")
            logging.info("Starting mainloop in 2 seconds... (Close the window to end test)")
            import time
            time.sleep(2)
            app.mainloop()
            
        except Exception as e:
            logging.error(f"GUI Initialization failed: {e}")
            logging.error(traceback.format_exc())

    except Exception as e:
        logging.critical(f"Unexpected diagnostic failure: {e}")
        logging.critical(traceback.format_exc())

    print(f"\nDiagnostic log saved to: {LOG_FILE}")
    input("Press Enter to exit...")

if __name__ == "__main__":
    run_diagnostic()
