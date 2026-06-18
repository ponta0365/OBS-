from playwright.sync_api import sync_playwright
import logging

class BrowserManager:
    def __init__(self, url, width, height):
        self.url = url
        self.width = width
        self.height = height
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def launch(self):
        try:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=False)
            self.context = self.browser.new_context(
                viewport={"width": self.width, "height": self.height}
            )
            self.page = self.context.new_page()
            self.page.goto(self.url)
            logging.info(f"Launched browser at {self.url} with size {self.width}x{self.height}")
            return True
        except Exception as e:
            logging.error(f"Failed to launch browser: {e}")
            return False

    def close(self):
        try:
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
            logging.info("Browser closed")
        except Exception as e:
            logging.error(f"Error closing browser: {e}")

    def get_page(self):
        return self.page
