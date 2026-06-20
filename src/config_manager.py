import json
import os

class ConfigManager:
    DEFAULT_CONFIG_PATH = os.path.join("data", "config.json")
    DEFAULT_PRESET_NAME = "Default"
    
    BASE_CONFIG_TEMPLATE = {
        "obs": {
            "host": "localhost",
            "port": 4455,
            "password": "",
            "path": "C:\\Program Files\\obs-studio\\bin\\64bit\\obs64.exe",
            "ffmpeg_path": "",
            "profile": "",
            "scene_collection": ""
        },
        "hotkeys": {
            "text": "設定字幕",
            "key_record_toggle": "ctrl+alt+r",
            "key_record_subtitle": "ctrl+alt+t",
            "key_open_window": "alt+g",
            "key_open_chapter_window": "alt+v",
            "key_add_chapter": "alt+c"
        },
        "subtitles": {
            "duration": 3.0
        }
    }

    DEFAULT_CONFIG = {
        "current_preset": DEFAULT_PRESET_NAME,
        "presets": {
            DEFAULT_PRESET_NAME: BASE_CONFIG_TEMPLATE
        },
        "output": {
            "base_dir": "data",
            "dir": "data/output"
        }
    }

    def __init__(self, config_path=None):
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self.config = self.load_config()
        self._ensure_compatibility()

    def _ensure_compatibility(self):
        """Migrate old config format to new preset-based format if necessary."""
        if "presets" not in self.config:
            old_config = self.config.copy()
            # If it's an old format, wrap it in a preset
            obs = old_config.get("obs", self.BASE_CONFIG_TEMPLATE["obs"])
            hotkeys = old_config.get("hotkeys", self.BASE_CONFIG_TEMPLATE["hotkeys"])
            
            self.config = {
                "current_preset": self.DEFAULT_PRESET_NAME,
                "presets": {
                    self.DEFAULT_PRESET_NAME: {
                        "obs": obs,
                        "hotkeys": hotkeys
                    }
                },
                "output": old_config.get("output", {"dir": "data/output"})
            }

        # Ensure new configuration keys exist and old keys are removed
        updated = False
        for preset_name, preset in self.config.get("presets", {}).items():
            if "hotkeys" in preset:
                # Remove obsolete fields if they exist
                if "keys" in preset["hotkeys"]:
                    del preset["hotkeys"]["keys"]
                    updated = True
                if "modifier" in preset["hotkeys"]:
                    del preset["hotkeys"]["modifier"]
                    updated = True
                # Add hotkeys.text if missing
                if "text" not in preset["hotkeys"]:
                    preset["hotkeys"]["text"] = "設定字幕"
                    updated = True
                # Add default keybindings if missing
                if "key_record_toggle" not in preset["hotkeys"]:
                    preset["hotkeys"]["key_record_toggle"] = "ctrl+alt+r"
                    updated = True
                if "key_record_subtitle" not in preset["hotkeys"]:
                    preset["hotkeys"]["key_record_subtitle"] = "ctrl+alt+t"
                    updated = True
                if "key_open_window" not in preset["hotkeys"]:
                    preset["hotkeys"]["key_open_window"] = "alt+g"
                    updated = True
                if "key_open_chapter_window" not in preset["hotkeys"]:
                    preset["hotkeys"]["key_open_chapter_window"] = "alt+v"
                    updated = True
                if "key_add_chapter" not in preset["hotkeys"]:
                    preset["hotkeys"]["key_add_chapter"] = "alt+c"
                    updated = True
            else:
                preset["hotkeys"] = {
                    "text": "設定字幕",
                    "key_record_toggle": "ctrl+alt+r",
                    "key_record_subtitle": "ctrl+alt+t",
                    "key_open_window": "alt+g",
                    "key_open_chapter_window": "alt+v",
                    "key_add_chapter": "alt+c"
                }
                updated = True
            
            # Add ffmpeg_path if missing and remove mkvpropedit_path
            if "obs" not in preset:
                preset["obs"] = self.BASE_CONFIG_TEMPLATE["obs"].copy()
                updated = True
            else:
                if "mkvpropedit_path" in preset["obs"]:
                    del preset["obs"]["mkvpropedit_path"]
                    updated = True
                if "ffmpeg_path" not in preset["obs"]:
                    preset["obs"]["ffmpeg_path"] = ""
                    updated = True

            # Add subtitles.duration if missing
            if "subtitles" not in preset:
                preset["subtitles"] = {"duration": 3.0}
                updated = True
            elif "duration" not in preset["subtitles"]:
                preset["subtitles"]["duration"] = 3.0
                updated = True

        # Ensure output config has base_dir
        if "output" not in self.config:
            self.config["output"] = {"base_dir": "data", "dir": "data/output"}
            updated = True
        else:
            import os
            if "base_dir" not in self.config["output"]:
                current_dir = self.config["output"].get("dir", "data/output")
                parent_dir = os.path.dirname(current_dir) if current_dir else "data"
                self.config["output"]["base_dir"] = parent_dir if parent_dir else "data"
                updated = True
            if "dir" not in self.config["output"]:
                self.config["output"]["dir"] = "data/output"
                updated = True

        if updated:
            self.save_config()

    def load_config(self):
        if not os.path.exists(self.config_path):
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            self.save_config(self.DEFAULT_CONFIG)
            return self.DEFAULT_CONFIG
        
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return self.DEFAULT_CONFIG

    def save_config(self, config_data=None):
        if config_data:
            self.config = config_data
        
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=4, ensure_ascii=False)

    def get_preset_names(self):
        return list(self.config.get("presets", {}).keys())

    def get_current_preset_name(self):
        return self.config.get("current_preset", self.DEFAULT_PRESET_NAME)

    def set_current_preset(self, name):
        if name in self.config.get("presets", {}):
            self.config["current_preset"] = name
            self.save_config()
            return True
        return False

    def save_preset(self, name, preset_data):
        if "presets" not in self.config:
            self.config["presets"] = {}
        self.config["presets"][name] = preset_data
        self.config["current_preset"] = name
        self.save_config()

    def delete_preset(self, name):
        if name == self.DEFAULT_PRESET_NAME:
            return False # Cannot delete default
        if name in self.config.get("presets", {}):
            del self.config["presets"][name]
            if self.config["current_preset"] == name:
                self.config["current_preset"] = self.DEFAULT_PRESET_NAME
            self.save_config()
            return True
        return False

    def get(self, key, default=None):
        # Current logic: If the key starts with 'obs.' or 'hotkeys.' or 'subtitles.', 
        # it refers to the CURRENT preset.
        current_name = self.get_current_preset_name()
        current_preset = self.config.get("presets", {}).get(current_name, {})
        
        keys = key.split(".")
        
        # Check if it's a global config or preset-specific
        if keys[0] in ["obs", "hotkeys", "subtitles"]:
            val = current_preset
        else:
            val = self.config

        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return default
        return val

    def set(self, key, value):
        current_name = self.get_current_preset_name()
        
        keys = key.split(".")
        if keys[0] in ["obs", "hotkeys", "subtitles"]:
            # Set in current preset
            if "presets" not in self.config: self.config["presets"] = {}
            if current_name not in self.config["presets"]: 
                self.config["presets"][current_name] = self.BASE_CONFIG_TEMPLATE.copy()
            
            val = self.config["presets"][current_name]
        else:
            val = self.config

        for k in keys[:-1]:
            if k not in val:
                val[k] = {}
            val = val[k]
        val[keys[-1]] = value
        self.save_config()
