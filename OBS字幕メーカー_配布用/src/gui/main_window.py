import customtkinter as ctk
import threading
import os
import time
import logging
import gc
import keyboard
from win11toast import toast
from src.config_manager import ConfigManager
from src.obs_controller import ObsController
from src.browser_manager import BrowserManager
from src.hotkey_manager import HotkeyManager
from src.srt_generator import SrtGenerator

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("OBS Subtitle Maker")
        self.geometry("800x600")

        self.config = ConfigManager()
        self.obs = None
        self.browser = None
        self.hotkeys = None
        self.srt = SrtGenerator()
        
        self.is_recording = False
        self.last_video_dir = None
        self._global_hotkey_handle = None  # Track individual global hotkey handle
        
        self._setup_ui()
        self._setup_global_hotkeys()
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _is_admin(self):
        import ctypes
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False

    def _setup_global_hotkeys(self):
        # Remove only the previous global hotkey (not recording session hotkeys)
        if self._global_hotkey_handle is not None:
            try:
                keyboard.remove_hotkey(self._global_hotkey_handle)
            except Exception:
                pass
            self._global_hotkey_handle = None

        # Register global hotkey for start/stop recording from config
        toggle_key = self.config.get("hotkeys.key_record_toggle", "ctrl+alt+r")
        try:
            self._global_hotkey_handle = keyboard.add_hotkey(toggle_key, self._toggle_recording_safe)
            logging.info(f"Global hotkey '{toggle_key}' registered for recording toggle")
        except Exception as e:
            logging.error(f"Failed to register global hotkey '{toggle_key}': {e}")

    def _toggle_recording_safe(self):
        # Called from keyboard thread, needs to be safe with Tkinter
        self.after(0, self._toggle_recording)

    def _notify(self, title, message, on_click=None):
        def show_toast():
            try:
                # Use win11toast for modern Windows 10/11 notifications
                # on_click can be a file path or a web URL
                toast(title, message, on_click=on_click)
                logging.info(f"Notification sent: {title}")
            except Exception as e:
                logging.error(f"Notification failed: {e}")
            finally:
                # WinRT COMオブジェクトの蓄積を防止
                gc.collect()
        
        # Run in separate thread to prevent blocking
        threading.Thread(target=show_toast, daemon=True).start()

    def _setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Left Sidebar (Navigation/Status)
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        self.status_label = ctk.CTkLabel(self.sidebar, text="Status: Idle", font=ctk.CTkFont(size=14, weight="bold"))
        self.status_label.pack(pady=20, padx=10)

        self.start_obs_button = ctk.CTkButton(self.sidebar, text="Start OBS", command=self._launch_obs_from_gui)
        self.start_obs_button.pack(pady=10, padx=10)

        self.start_button = ctk.CTkButton(self.sidebar, text="Start Recording", command=self._toggle_recording)
        self.start_button.pack(pady=10, padx=10)

        self.open_folder_button = ctk.CTkButton(self.sidebar, text="Open Output Folder", command=self._open_output_directory)
        self.open_folder_button.pack(pady=10, padx=10)

        self.reset_hotkeys_button = ctk.CTkButton(self.sidebar, text="Reset Hotkeys", command=self._reset_hotkeys_action)
        self.reset_hotkeys_button.pack(pady=10, padx=10)

        # Admin privilege check warning label
        self.admin_warning_label = None
        if not self._is_admin():
            self.admin_warning_label = ctk.CTkLabel(
                self.sidebar, 
                text="⚠️管理者未実行\n(キーが効かない事があります)", 
                font=ctk.CTkFont(size=11),
                text_color="orange"
            )
            self.admin_warning_label.pack(pady=(20, 10), padx=10, side="bottom")

        # Main Content
        self.main_frame = ctk.CTkScrollableFrame(self)
        self.main_frame.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")

        # Preset Management
        self.preset_label = ctk.CTkLabel(self.main_frame, text="Preset Management", font=ctk.CTkFont(size=16, weight="bold"))
        self.preset_label.pack(pady=(0, 10), anchor="w")

        preset_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        preset_frame.pack(fill="x", pady=2)
        
        self.preset_var = ctk.StringVar(value=self.config.get_current_preset_name())
        self.preset_menu = ctk.CTkOptionMenu(preset_frame, variable=self.preset_var, values=self.config.get_preset_names(), command=self._on_preset_change)
        self.preset_menu.pack(side="left", padx=(0, 10))

        self.new_preset_button = ctk.CTkButton(preset_frame, text="New", width=60, command=self._create_new_preset)
        self.new_preset_button.pack(side="left", padx=2)
        
        self.delete_preset_button = ctk.CTkButton(preset_frame, text="Delete", width=60, fg_color="red", hover_color="#8B0000", command=self._delete_current_preset)
        self.delete_preset_button.pack(side="left", padx=2)

        self.save_preset_button = ctk.CTkButton(preset_frame, text="Save", width=60, command=self._save_settings)
        self.save_preset_button.pack(side="left", padx=2)

        ctk.CTkLabel(self.main_frame, text="").pack(pady=5) # Spacer

        # OBS Config
        self.obs_label = ctk.CTkLabel(self.main_frame, text="OBS WebSocket Settings", font=ctk.CTkFont(size=16, weight="bold"))
        self.obs_label.pack(pady=(0, 10), anchor="w")

        self.obs_host = self._create_input("Host:", self.config.get("obs.host"))
        self.obs_port = self._create_input("Port:", str(self.config.get("obs.port")))
        self.obs_password = self._create_input("Password:", self.config.get("obs.password"), show="*")
        self.obs_path = self._create_input("OBS Path:", self.config.get("obs.path"))
        
        # FFmpeg configuration (input + Browse button)
        ffmpeg_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        ffmpeg_frame.pack(fill="x", pady=2)
        ffmpeg_label = ctk.CTkLabel(ffmpeg_frame, text="FFmpeg Path:", width=100, anchor="w")
        ffmpeg_label.pack(side="left")
        self.ffmpeg_path_input = ctk.CTkEntry(ffmpeg_frame)
        self.ffmpeg_path_input.insert(0, self.config.get("obs.ffmpeg_path", ""))
        self.ffmpeg_path_input.pack(side="left", fill="x", expand=True, padx=(10, 0))
        self.browse_ffmpeg_button = ctk.CTkButton(ffmpeg_frame, text="Browse", width=60, command=self._browse_ffmpeg_directory)
        self.browse_ffmpeg_button.pack(side="left", padx=(5, 0))
        
        # OptionMenus for Profile and Scene Collection
        self.obs_profile_var = ctk.StringVar(value=self.config.get("obs.profile", ""))
        self.obs_profile_menu = self._create_option_menu("Profile:", self.obs_profile_var, ["Fetching..."])
        
        self.obs_scene_col_var = ctk.StringVar(value=self.config.get("obs.scene_collection", ""))
        self.obs_scene_col_menu = self._create_option_menu("Scene Collection:", self.obs_scene_col_var, [self.obs_scene_col_var.get()] if self.obs_scene_col_var.get() else ["Fetching..."])

        button_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        button_frame.pack(pady=10)

        self.fetch_button = ctk.CTkButton(button_frame, text="Fetch OBS Lists", command=self._fetch_obs_lists)
        self.fetch_button.pack(side="left", padx=5)

        self.apply_button = ctk.CTkButton(button_frame, text="Apply to OBS", command=self._apply_settings_to_obs)
        self.apply_button.pack(side="left", padx=5)

        # Output Directory Settings
        self.output_label = ctk.CTkLabel(self.main_frame, text="Output Directory Settings", font=ctk.CTkFont(size=16, weight="bold"))
        self.output_label.pack(pady=(20, 10), anchor="w")

        # 1. 基準フォルダ
        base_dir_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        base_dir_frame.pack(fill="x", pady=2)
        base_dir_label = ctk.CTkLabel(base_dir_frame, text="Base Folder:", width=100, anchor="w")
        base_dir_label.pack(side="left")
        
        self.base_dir_input = ctk.CTkEntry(base_dir_frame)
        self.base_dir_input.insert(0, self.config.get("output.base_dir", "data"))
        self.base_dir_input.pack(side="left", fill="x", expand=True, padx=(10, 0))
        
        self.browse_base_button = ctk.CTkButton(base_dir_frame, text="Browse", width=60, command=self._browse_base_directory)
        self.browse_base_button.pack(side="left", padx=(5, 0))

        # 2. 保存先フォルダ
        output_dir_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        output_dir_frame.pack(fill="x", pady=2)
        output_dir_label = ctk.CTkLabel(output_dir_frame, text="Output Folder:", width=100, anchor="w")
        output_dir_label.pack(side="left")
        
        self.output_dir_input = ctk.CTkEntry(output_dir_frame)
        self.output_dir_input.insert(0, self.config.get("output.dir", "data/output"))
        self.output_dir_input.pack(side="left", fill="x", expand=True, padx=(10, 0))
        
        self.browse_output_button = ctk.CTkButton(output_dir_frame, text="Browse", width=60, command=self._browse_output_directory_ui)
        self.browse_output_button.pack(side="left", padx=(5, 0))

        # 3. 日付フォルダ作成ボタン & OBS反映ボタン
        date_folder_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        date_folder_frame.pack(fill="x", pady=2)
        self.create_date_folder_button = ctk.CTkButton(date_folder_frame, text="Create Date Folder", command=self._create_date_folder_action)
        self.create_date_folder_button.pack(side="left", padx=(110, 0))
        
        self.apply_folder_button = ctk.CTkButton(date_folder_frame, text="Apply Folder to OBS", command=self._apply_folder_to_obs_action)
        self.apply_folder_button.pack(side="left", padx=(10, 0))

        # Hotkey & Subtitle Config
        self.hotkey_label = ctk.CTkLabel(self.main_frame, text="Subtitle & Hotkey Settings", font=ctk.CTkFont(size=16, weight="bold"))
        self.hotkey_label.pack(pady=(20, 10), anchor="w")

        self.setting_text_input = self._create_input("Setting Subtitle Text:", self.config.get("hotkeys.text"))
        self.subtitle_duration_input = self._create_input("Display Duration (sec):", str(self.config.get("subtitles.duration")))

        # Keybindings inputs
        self.key_record_toggle_input = self._create_input("Start/Stop Rec Hotkey:", self.config.get("hotkeys.key_record_toggle", "ctrl+alt+r"))
        self.key_record_subtitle_input = self._create_input("Record Subtitle Hotkey:", self.config.get("hotkeys.key_record_subtitle", "ctrl+alt+t"))
        self.key_open_window_input = self._create_input("Open Input Window Hotkey:", self.config.get("hotkeys.key_open_window", "alt+g"))
        self.key_open_chapter_window_input = self._create_input("Open Chapter Window Hotkey:", self.config.get("hotkeys.key_open_chapter_window", "alt+v"))
        self.key_add_chapter_input = self._create_input("Add Chapter Hotkey:", self.config.get("hotkeys.key_add_chapter", "alt+c"))

        help_text = (
            "【ショートカットキーについて】\n"
            "・キーが動作しなくなった時は、左側の「Reset Hotkeys」ボタンをお試しください。\n"
            "・ゲーム画面等でショートカットを反応させるには、本アプリを\n"
            "  「管理者として実行」で起動する必要があります。"
        )
        self.help_label = ctk.CTkLabel(self.main_frame, text=help_text, justify="left", font=ctk.CTkFont(size=12))
        self.help_label.pack(pady=(10, 0), anchor="w", padx=10)

        self.save_button = ctk.CTkButton(self.main_frame, text="Save Settings", command=self._save_settings)
        self.save_button.pack(pady=20)

        # Auto-fetch OBS lists on startup
        self.after(1000, self._fetch_obs_lists)

    def _on_preset_change(self, selected_preset):
        self.config.set_current_preset(selected_preset)
        self._update_ui_from_config()
        self.after(500, self._fetch_obs_lists)

    def _create_new_preset(self):
        dialog = ctk.CTkInputDialog(text="Enter new preset name:", title="New Preset")
        name = dialog.get_input()
        if name and name not in self.config.get_preset_names():
            # Save current settings to the new preset
            self.config.set_current_preset(self.config.get_current_preset_name()) # Just to ensure current is saved
            preset_data = {
                "obs": {
                    "host": self.obs_host.get(),
                    "port": int(self.obs_port.get()) if self.obs_port.get().isdigit() else 4455,
                    "password": self.obs_password.get(),
                    "path": self.obs_path.get(),
                    "ffmpeg_path": self.ffmpeg_path_input.get(),
                    "profile": self.obs_profile_var.get(),
                    "scene_collection": self.obs_scene_col_var.get()
                },
                "hotkeys": {
                    "text": self.setting_text_input.get(),
                    "key_record_toggle": self.key_record_toggle_input.get().strip().lower(),
                    "key_record_subtitle": self.key_record_subtitle_input.get().strip().lower(),
                    "key_open_window": self.key_open_window_input.get().strip().lower(),
                    "key_open_chapter_window": self.key_open_chapter_window_input.get().strip().lower(),
                    "key_add_chapter": self.key_add_chapter_input.get().strip().lower()
                },
                "subtitles": {
                    "duration": float(self.subtitle_duration_input.get()) if self.subtitle_duration_input.get() else 3.0
                }
            }
            self.config.save_preset(name, preset_data)
            self.preset_menu.configure(values=self.config.get_preset_names())
            self.preset_var.set(name)
            self._update_ui_from_config()

    def _delete_current_preset(self):
        name = self.preset_var.get()
        if name == "Default":
            return
        if self.config.delete_preset(name):
            self.preset_menu.configure(values=self.config.get_preset_names())
            self.preset_var.set(self.config.get_current_preset_name())
            self._update_ui_from_config()

    def _update_ui_from_config(self):
        # Update OBS fields
        self._update_entry(self.obs_host, self.config.get("obs.host"))
        self._update_entry(self.obs_port, str(self.config.get("obs.port")))
        self._update_entry(self.obs_password, self.config.get("obs.password"))
        self._update_entry(self.obs_path, self.config.get("obs.path"))
        self._update_entry(self.ffmpeg_path_input, self.config.get("obs.ffmpeg_path", ""))
        
        self.obs_profile_var.set(self.config.get("obs.profile", ""))
        self.obs_scene_col_var.set(self.config.get("obs.scene_collection", ""))
        
        # Update Hotkeys & Subtitles
        self._update_entry(self.setting_text_input, self.config.get("hotkeys.text"))
        self._update_entry(self.subtitle_duration_input, str(self.config.get("subtitles.duration")))

        # Update Keybindings
        self._update_entry(self.key_record_toggle_input, self.config.get("hotkeys.key_record_toggle", "ctrl+alt+r"))
        self._update_entry(self.key_record_subtitle_input, self.config.get("hotkeys.key_record_subtitle", "ctrl+alt+t"))
        self._update_entry(self.key_open_window_input, self.config.get("hotkeys.key_open_window", "alt+g"))
        self._update_entry(self.key_open_chapter_window_input, self.config.get("hotkeys.key_open_chapter_window", "alt+v"))
        self._update_entry(self.key_add_chapter_input, self.config.get("hotkeys.key_add_chapter", "alt+c"))

        # Update Output settings
        self._update_entry(self.base_dir_input, self.config.get("output.base_dir", "data"))
        self._update_entry(self.output_dir_input, self.config.get("output.dir", "data/output"))

    def _update_entry(self, entry, value):
        entry.delete(0, "end")
        entry.insert(0, value if value is not None else "")

    def _create_input(self, label_text, initial_value, **kwargs):
        frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        frame.pack(fill="x", pady=2)
        label = ctk.CTkLabel(frame, text=label_text, width=100, anchor="w")
        label.pack(side="left")
        entry = ctk.CTkEntry(frame, **kwargs)
        # Ensure initial_value is not None to avoid Tcl errors
        entry.insert(0, initial_value if initial_value is not None else "")
        entry.pack(side="left", fill="x", expand=True, padx=(10, 0))
        return entry

    def _create_option_menu(self, label_text, variable, values):
        frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        frame.pack(fill="x", pady=2)
        label = ctk.CTkLabel(frame, text=label_text, width=100, anchor="w")
        label.pack(side="left")
        menu = ctk.CTkOptionMenu(frame, variable=variable, values=values)
        menu.pack(side="left", fill="x", expand=True, padx=(10, 0))
        return menu

    def _fetch_obs_lists(self):
        def task():
            self.after(0, lambda: self.status_label.configure(text="Status: Fetching OBS Lists..."))
            temp_obs = ObsController(
                self.obs_host.get(),
                int(self.obs_port.get()),
                self.obs_password.get()
            )
            if temp_obs.connect():
                profiles = temp_obs.get_profiles()
                collections = temp_obs.get_scene_collections()
                
                self.after(0, lambda: self.obs_profile_menu.configure(values=profiles if profiles else ["No Profiles Found"]))
                self.after(0, lambda: self.obs_scene_col_menu.configure(values=collections if collections else ["No Collections Found"]))
                
                temp_obs.disconnect()
                self.after(0, lambda: self.status_label.configure(text="Status: Idle (Lists Updated)"))
            else:
                self.after(0, lambda: self.status_label.configure(text="Status: Fetch Failed (Check Connection)"))
        
        threading.Thread(target=task, daemon=True).start()

    def _save_settings(self):
        self.config.set("obs.host", self.obs_host.get())
        try:
            self.config.set("obs.port", int(self.obs_port.get()))
        except ValueError:
            self.config.set("obs.port", 4455)
        self.config.set("obs.password", self.obs_password.get())
        self.config.set("obs.path", self.obs_path.get())
        self.config.set("obs.ffmpeg_path", self.ffmpeg_path_input.get())
        self.config.set("obs.profile", self.obs_profile_var.get())
        self.config.set("obs.scene_collection", self.obs_scene_col_var.get())
        
        self.config.set("hotkeys.text", self.setting_text_input.get())
        self.config.set("hotkeys.key_record_toggle", self.key_record_toggle_input.get().strip().lower())
        self.config.set("hotkeys.key_record_subtitle", self.key_record_subtitle_input.get().strip().lower())
        self.config.set("hotkeys.key_open_window", self.key_open_window_input.get().strip().lower())
        self.config.set("hotkeys.key_open_chapter_window", self.key_open_chapter_window_input.get().strip().lower())
        self.config.set("hotkeys.key_add_chapter", self.key_add_chapter_input.get().strip().lower())

        try:
            duration = float(self.subtitle_duration_input.get())
            self.config.set("subtitles.duration", duration)
        except ValueError:
            logging.warning("Invalid duration format, using default 3.0")
            self.config.set("subtitles.duration", 3.0)
        
        self.config.set("output.base_dir", self.base_dir_input.get())
        self.config.set("output.dir", self.output_dir_input.get())
        
        self.config.save_config()
        self._setup_global_hotkeys() # Apply newly saved hotkeys
        print("Settings saved.")

    def _toggle_recording(self):
        if not self.is_recording:
            self._start_recording_thread()
        else:
            self._stop_recording_thread()

    def _start_recording_thread(self):
        self._save_settings()
        self.is_recording = True
        self.start_button.configure(text="Stop Recording", fg_color="red", hover_color="#8B0000")
        self.status_label.configure(text="Status: Launching OBS...")
        
        threading.Thread(target=self._recording_process, daemon=True).start()

    def _recording_process(self):
        try:
            self.obs = ObsController(
                self.config.get("obs.host"),
                self.config.get("obs.port"),
                self.config.get("obs.password"),
                self.config.get("obs.path")
            )
            self.hotkeys = HotkeyManager(
                self.config.get("hotkeys"),
                get_setting_text_callback=self._get_setting_subtitle_text,
                show_input_window_callback=self._show_input_window_safe
            )

            if not self.obs.launch_obs():
                self._on_error("Failed to launch or connect to OBS")
                return

            # Apply Profile and Scene Collection
            self.after(0, lambda: self.status_label.configure(text="Status: Applying OBS Settings..."))
            self.obs.set_profile(self.config.get("obs.profile"))
            self.obs.set_scene_collection(self.config.get("obs.scene_collection"))

            # Apply output directory path to OBS
            output_dir = self.config.get("output.dir")
            logging.info(f"Preparing to set OBS recording directory. Config value: {output_dir}")
            if output_dir:
                absolute_path = os.path.abspath(output_dir)
                os.makedirs(absolute_path, exist_ok=True)
                logging.info(f"Output directory verified: {absolute_path}")
                success = self.obs.set_record_directory(absolute_path)
                logging.info(f"set_record_directory result: {success}")
            else:
                logging.warning("output.dir is not set in config, skipping directory apply.")

            self.after(0, lambda: self.status_label.configure(text="Status: Recording..."))
            if not self.obs.start_recording():
                self._on_error("Failed to start OBS recording")
                return

            self._notify("Recording Started", "OBS recording has begun.")
            self.hotkeys.start_monitoring()
            
            # イベント駆動方式: OBS EventClientで録画停止を監視
            # ポーリングの代わりにOBSからのイベント通知を使用（接続負荷を大幅軽減）
            self.obs.start_monitoring(on_stopped_callback=lambda: self.after(0, self._on_obs_recording_stopped))
            
            # フォールバック: EventClientが失敗した場合のポーリング監視
            # EventClient接続中は60秒間隔の軽量チェックのみ（従来の毎秒→60秒）
            consecutive_failures = 0
            MAX_FAILURES = 5
            while self.is_recording:
                # EventClientが動いていれば60秒間隔、なければ5秒間隔
                check_interval = 60 if self.obs.event_client else 5
                time.sleep(check_interval)
                
                if not self.is_recording:
                    break
                
                # フォールバック: ステータス確認（EventClient障害時の保険）
                status = self.obs.get_record_status()
                if status is True:
                    consecutive_failures = 0
                elif status is False:
                    logging.warning("OBS confirmed recording is not active (detected via polling fallback). Stopping.")
                    break
                else:
                    consecutive_failures += 1
                    logging.warning(f"Recording status check failed ({consecutive_failures}/{MAX_FAILURES})")
                    if consecutive_failures >= MAX_FAILURES:
                        logging.error(f"Recording status check failed {MAX_FAILURES} times consecutively. Stopping.")
                        break
            
            # Cleanup handled by _stop_recording_thread setting is_recording=False
            # but if OBS stops it externally, we catch it here.
            if self.is_recording:
                self.after(0, self._stop_recording_thread)

        except Exception as e:
            self._on_error(str(e))

    def _stop_recording_thread(self):
        if not self.is_recording:
            return
            
        self.is_recording = False
        self.status_label.configure(text="Status: Finalizing...")
        
        def finalize():
            if self.hotkeys:
                self.hotkeys.stop_monitoring()
            if self.obs:
                self.obs.stop_monitoring()
            self.after(0, self._close_input_window)
            
            video_path = None
            if self.obs:
                video_path = self.obs.stop_recording()
                self.obs.disconnect()
            
            duration = self.config.get("subtitles.duration", 3.0)
            if video_path:
                srt_path = os.path.splitext(video_path)[0] + ".srt"
                self.srt.generate(self.hotkeys.get_markers(), srt_path, duration=duration)
                logging.info(f"SRT generated at: {srt_path}")
                
                chapters_path = os.path.splitext(video_path)[0] + "_chapters.txt"
                self.srt.generate_chapters(self.hotkeys.get_markers(), chapters_path)
                
                # Embed chapters to MKV using FFmpeg
                ffmpeg_path = self.config.get("obs.ffmpeg_path")
                total_duration = self.hotkeys.get_elapsed_time() if self.hotkeys else 0.0
                self.srt.embed_chapters(video_path, self.hotkeys.get_markers(), ffmpeg_path=ffmpeg_path, total_duration=total_duration)
                
                self.last_video_dir = os.path.dirname(video_path)
                self._notify("Recording Finished", f"Video and SRT/Chapters saved.\n{os.path.basename(video_path)}")
            else:
                # Fallback: Save to data/output if video path is unknown
                output_dir = "data/output"
                os.makedirs(output_dir, exist_ok=True)
                timestamp = int(time.time())
                srt_path = os.path.join(output_dir, f"markers_{timestamp}.srt")
                self.srt.generate(self.hotkeys.get_markers(), srt_path, duration=duration)
                
                chapters_path = os.path.join(output_dir, f"markers_{timestamp}_chapters.txt")
                self.srt.generate_chapters(self.hotkeys.get_markers(), chapters_path)
                
                self.last_video_dir = os.path.abspath(output_dir)
                logging.warning(f"Video path unknown. SRT/Chapters saved as fallback: {srt_path}")
                self._notify("Recording Finished", "Video path unknown. SRT/Chapters saved to data/output.")
            
            self.after(0, lambda: self.status_label.configure(text="Status: Idle"))
            self.after(0, lambda: self.start_button.configure(text="Start Recording", fg_color=["#3B8ED0", "#1F6AA5"], hover_color=["#367E93", "#144870"]))

        threading.Thread(target=finalize, daemon=True).start()

    def _on_error(self, message):
        self.is_recording = False
        if self.obs:
            self.obs.stop_monitoring()
        self.after(0, lambda: self.status_label.configure(text=f"Error: {message}"))
        self.after(0, lambda: self.start_button.configure(text="Start Recording", fg_color=["#3B8ED0", "#1F6AA5"]))
        logging.error(message)

    def _on_obs_recording_stopped(self):
        """OBS EventClient経由で録画停止が検出された際のコールバック。"""
        if self.is_recording:
            logging.info("Recording stop detected via OBS EventClient callback")
            self._stop_recording_thread()

    def _get_setting_subtitle_text(self):
        return self.setting_text_input.get()

    def _show_input_window_safe(self, focus_field="subtitle"):
        self.after(0, lambda: self._open_input_window(focus_field=focus_field))

    def _force_focus_window(self, window):
        """Windows APIを使用してウィンドウをフォアグラウンドにし、フォーカスを強制します。"""
        if os.name != 'nt':
            window.lift()
            window.focus_force()
            return

        import ctypes
        window.update_idletasks()
        try:
            hwnd = window.winfo_id()
            user32 = ctypes.windll.user32
            
            # 最小化されていたら元に戻す、そうでなければ表示
            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, 9) # SW_RESTORE
            else:
                user32.ShowWindow(hwnd, 5) # SW_SHOW

            # Altキーの空押しでSetForegroundWindowの制限をバイパス
            user32.keybd_event(0x12, 0, 0, 0) # Alt down
            user32.SetForegroundWindow(hwnd)
            user32.keybd_event(0x12, 0, 2, 0) # Alt up
            
            user32.SetActiveWindow(hwnd)
        except Exception as e:
            logging.error(f"Failed to force focus window: {e}")
            
        window.lift()
        window.focus_force()

    def _open_input_window(self, focus_field="subtitle"):
        if hasattr(self, "input_window") and self.input_window and self.input_window.winfo_exists():
            self._force_focus_window(self.input_window)
            self.input_window.attributes("-topmost", True)
            if focus_field == "chapter":
                if hasattr(self, "chapter_entry") and self.chapter_entry:
                    self.chapter_entry.focus_force()
            else:
                if hasattr(self, "input_entry") and self.input_entry:
                    self.input_entry.focus_force()
            return

        self.input_window = ctk.CTkToplevel(self)
        self.input_window.title("字幕・チャプター入力")
        self.input_window.geometry("400x160")
        self.input_window.attributes("-topmost", True)
        self.input_window.resizable(False, False)

        self.input_window.protocol("WM_DELETE_WINDOW", self._close_input_window)

        current_time = self.hotkeys.get_elapsed_time() if self.hotkeys else 0.0
        self.subtitle_input_time = current_time
        self.subtitle_time_needs_update = False
        
        self.chapter_input_time = current_time
        self.chapter_time_needs_update = False

        frame = ctk.CTkFrame(self.input_window, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        label_sub = ctk.CTkLabel(frame, text="字幕テキスト (Enterで確定):")
        label_sub.pack(anchor="w")

        self.input_entry = ctk.CTkEntry(frame, width=380)
        self.input_entry.pack(pady=(2, 8), fill="x")

        label_chap = ctk.CTkLabel(frame, text="チャプター名 (Enterで確定):")
        label_chap.pack(anchor="w")

        self.chapter_entry = ctk.CTkEntry(frame, width=380)
        self.chapter_entry.pack(pady=(2, 0), fill="x")
        
        # Focus both window and entry immediately
        self._force_focus_window(self.input_window)
        if focus_field == "chapter":
            self.chapter_entry.focus_force()
        else:
            self.input_entry.focus_force()

        # Bind events for Subtitle
        self.input_entry.bind("<Return>", self._on_subtitle_submit)
        self.input_entry.bind("<KeyPress>", self._on_subtitle_keypress)
        self.input_entry.bind("<Escape>", lambda e: self._close_input_window())

        # Bind events for Chapter
        self.chapter_entry.bind("<Return>", self._on_chapter_submit)
        self.chapter_entry.bind("<KeyPress>", self._on_chapter_keypress)
        self.chapter_entry.bind("<Escape>", lambda e: self._close_input_window())

    def _on_subtitle_keypress(self, event):
        if self.subtitle_time_needs_update:
            if self.hotkeys:
                self.subtitle_input_time = self.hotkeys.get_elapsed_time()
            self.subtitle_time_needs_update = False
            logging.info(f"Subtitle timestamp preset to {self.subtitle_input_time:.2f}s because typing started.")

    def _on_subtitle_submit(self, event):
        text = self.input_entry.get().strip()
        if text and self.hotkeys:
            self.hotkeys.add_manual_marker(text, self.subtitle_input_time)
            self.input_entry.delete(0, "end")
            self.subtitle_time_needs_update = True
        else:
            self.input_entry.delete(0, "end")
            self.subtitle_time_needs_update = True

    def _on_chapter_keypress(self, event):
        if self.chapter_time_needs_update:
            if self.hotkeys:
                self.chapter_input_time = self.hotkeys.get_elapsed_time()
            self.chapter_time_needs_update = False
            logging.info(f"Chapter timestamp preset to {self.chapter_input_time:.2f}s because typing started.")

    def _on_chapter_submit(self, event):
        text = self.chapter_entry.get().strip()
        if text and self.hotkeys:
            self.hotkeys.add_manual_marker(text, self.chapter_input_time, marker_type="chapter")
            self.chapter_entry.delete(0, "end")
            self.chapter_time_needs_update = True
        else:
            self.chapter_entry.delete(0, "end")
            self.chapter_time_needs_update = True

    def _close_input_window(self):
        if hasattr(self, "input_window") and self.input_window:
            self.input_window.destroy()
            self.input_window = None
            self.chapter_entry = None
            self.input_entry = None

    def _launch_obs_from_gui(self):
        self._save_settings()
        
        def task():
            self.after(0, lambda: self.status_label.configure(text="Status: Launching OBS..."))
            obs_path = self.config.get("obs.path")
            
            temp_obs = ObsController(
                self.config.get("obs.host"),
                self.config.get("obs.port"),
                self.config.get("obs.password"),
                obs_path
            )
            
            if temp_obs.is_obs_running():
                self.after(0, lambda: self.status_label.configure(text="Status: OBS already running"))
                self._notify("OBS Launch", "OBS is already running.")
                return
                
            if temp_obs.launch_obs():
                self.after(0, lambda: self.status_label.configure(text="Status: OBS Launched"))
                self._notify("OBS Launch", "OBS has been launched successfully.")
                self._fetch_obs_lists()
            else:
                self.after(0, lambda: self.status_label.configure(text="Status: OBS Launch Failed"))
                self._notify("OBS Launch", f"Failed to launch OBS.\nPlease check the path:\n{obs_path}")
        
        threading.Thread(target=task, daemon=True).start()

    def _apply_settings_to_obs(self):
        self._save_settings()
        
        def task():
            self.after(0, lambda: self.status_label.configure(text="Status: Applying to OBS..."))
            
            temp_obs = ObsController(
                self.config.get("obs.host"),
                self.config.get("obs.port"),
                self.config.get("obs.password")
            )
            
            if temp_obs.connect():
                profile = self.config.get("obs.profile")
                scene_col = self.config.get("obs.scene_collection")
                
                if profile:
                    temp_obs.set_profile(profile)
                if scene_col:
                    temp_obs.set_scene_collection(scene_col)
                
                # Apply output directory path to OBS
                output_dir = self.config.get("output.dir")
                dir_set_info = ""
                if output_dir:
                    absolute_path = os.path.abspath(output_dir)
                    os.makedirs(absolute_path, exist_ok=True)
                    if temp_obs.set_record_directory(absolute_path):
                        dir_set_info = "\nRecording directory applied successfully."
                    else:
                        dir_set_info = "\nFailed to apply recording directory."
                
                temp_obs.disconnect()
                self.after(0, lambda: self.status_label.configure(text="Status: Settings Applied"))
                self._notify("OBS Connection Test", f"Successfully applied settings to OBS!{dir_set_info}")
            else:
                self.after(0, lambda: self.status_label.configure(text="Status: Apply Failed (Check Connection)"))
                self._notify("OBS Connection Test", "Failed to connect to OBS. Please check port, password, and if OBS WebSocket is running.")
                
        threading.Thread(target=task, daemon=True).start()

    def _apply_folder_to_obs_action(self):
        self._save_settings()
        
        def task():
            self.after(0, lambda: self.status_label.configure(text="Status: Applying Folder..."))
            
            temp_obs = ObsController(
                self.config.get("obs.host"),
                self.config.get("obs.port"),
                self.config.get("obs.password")
            )
            
            if temp_obs.connect():
                output_dir = self.config.get("output.dir")
                if output_dir:
                    absolute_path = os.path.abspath(output_dir)
                    os.makedirs(absolute_path, exist_ok=True)
                    success = temp_obs.set_record_directory(absolute_path)
                    
                    temp_obs.disconnect()
                    if success:
                        self.after(0, lambda: self.status_label.configure(text="Status: Folder Applied"))
                        self._notify("OBS Connection Test", "Successfully applied output folder to OBS!")
                    else:
                        self.after(0, lambda: self.status_label.configure(text="Status: Apply Folder Failed"))
                        self._notify("OBS Connection Test", "Failed to apply output folder to OBS.")
                else:
                    temp_obs.disconnect()
                    self.after(0, lambda: self.status_label.configure(text="Status: Idle"))
                    self._notify("OBS Connection Test", "Output folder is not set in configuration.")
            else:
                self.after(0, lambda: self.status_label.configure(text="Status: Apply Failed (Check Connection)"))
                self._notify("OBS Connection Test", "Failed to connect to OBS. Please check connection settings.")
                
        threading.Thread(target=task, daemon=True).start()

    def _open_output_directory(self):
        target_dir = None
        if hasattr(self, "last_video_dir") and self.last_video_dir and os.path.exists(self.last_video_dir):
            target_dir = self.last_video_dir
        else:
            config_dir = self.config.get("output.dir", "data/output")
            target_dir = os.path.abspath(config_dir)
            
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)
            
        try:
            os.startfile(target_dir)
            logging.info(f"Opened directory: {target_dir}")
        except Exception as e:
            logging.error(f"Failed to open directory {target_dir}: {e}")

    def _browse_base_directory(self):
        from tkinter import filedialog
        initial = self.base_dir_input.get()
        if not os.path.exists(initial):
            initial = os.path.expanduser("~")
        dir_path = filedialog.askdirectory(initialdir=initial, title="Select Base Folder")
        if dir_path:
            self._update_entry(self.base_dir_input, dir_path)

    def _browse_output_directory_ui(self):
        from tkinter import filedialog
        initial = self.output_dir_input.get()
        if not os.path.exists(initial):
            initial = os.path.expanduser("~")
        dir_path = filedialog.askdirectory(initialdir=initial, title="Select Output Folder")
        if dir_path:
            self._update_entry(self.output_dir_input, dir_path)

    def _browse_ffmpeg_directory(self):
        from tkinter import filedialog
        initial = self.ffmpeg_path_input.get()
        if not os.path.exists(initial):
            initial = os.path.expanduser("~")
        dir_path = filedialog.askdirectory(initialdir=initial, title="Select FFmpeg Folder")
        if dir_path:
            self._update_entry(self.ffmpeg_path_input, dir_path)

    def _create_date_folder_action(self):
        import datetime
        base_dir = self.base_dir_input.get().strip()
        if not base_dir:
            self._notify("Error", "Please specify Base Folder first.")
            return
            
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        new_dir = os.path.join(base_dir, today)
        
        try:
            os.makedirs(new_dir, exist_ok=True)
            self._update_entry(self.output_dir_input, os.path.abspath(new_dir))
            self._save_settings()
            self._notify("Folder Created", f"Created date folder:\n{today}")
        except Exception as e:
            self._notify("Error", f"Failed to create folder: {e}")

    def _reset_hotkeys_action(self):
        try:
            self._setup_global_hotkeys()
            # If currently recording, also reset the recording session hotkeys
            if self.is_recording and self.hotkeys:
                self.hotkeys.stop_monitoring()
                self.hotkeys.start_monitoring()
                logging.info("Reset hotkeys: Re-hooked active recording session hotkeys")
            self._notify("Hotkeys Reset", "ショートカットキーを再登録しました。")
            logging.info("Hotkeys manually reset by user action")
        except Exception as e:
            self._notify("Error", f"Failed to reset hotkeys: {e}")
            logging.error(f"Failed to manually reset hotkeys: {e}")

    def _on_closing(self):
        # Stop recording safely if it's running
        import sys
        if self.is_recording:
            from tkinter import messagebox
            if not messagebox.askyesno("警告", "録画中ですが、アプリを終了しますか？\n(録画は強制停止されます)"):
                return
            
            # Stop hotkeys and disconnect OBS
            if self.hotkeys:
                self.hotkeys.stop_monitoring()
            if self.obs:
                try:
                    self.obs.stop_recording()
                    self.obs.disconnect()
                except Exception:
                    pass
        
        # Unhook all global hotkeys from this process
        try:
            keyboard.unhook_all()
        except Exception:
            pass
            
        logging.info("Application is closing. Cleaned up hotkeys.")
        self.destroy()
        sys.exit(0)
