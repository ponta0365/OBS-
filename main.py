import argparse
import sys
import logging
import os

def main():
    # Setup logging to file
    log_path = os.path.join("data", "app.log")
    os.makedirs("data", exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(log_path, encoding='utf-8'),
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
