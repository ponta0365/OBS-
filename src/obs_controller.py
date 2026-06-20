import obsws_python as obs
import logging
import subprocess
import os
import time
import threading

class ObsController:
    def __init__(self, host, port, password, exe_path=None):
        self.host = host
        self.port = port
        self.password = password
        self.exe_path = exe_path
        self.client = None
        self.event_client = None
        
        # Event-driven recording state
        self._recording_active = False
        self._recording_stopped_event = threading.Event()
        self._on_recording_stopped_callback = None
        
        # Heartbeat keep-alive
        self._heartbeat_thread = None
        self._heartbeat_stop = threading.Event()

    def is_obs_running(self):
        try:
            # tasklist command to check if obs64.exe is running
            output = subprocess.check_output('tasklist /FI "IMAGENAME eq obs64.exe"', shell=True).decode('cp932')
            return "obs64.exe" in output
        except Exception:
            return False

    def launch_obs(self):
        if self.is_obs_running():
            logging.info("OBS is already running.")
            if not self.client:
                self.connect()
            return self.client is not None
        
        if not self.exe_path or not os.path.exists(self.exe_path):
            logging.error(f"OBS executable not found at: {self.exe_path}")
            return False

        try:
            # Launch OBS and don't wait for it to close
            # Using start_in directory to ensure OBS finds its plugins
            start_in = os.path.dirname(self.exe_path)
            subprocess.Popen([self.exe_path], cwd=start_in)
            logging.info(f"Launching OBS: {self.exe_path}")
            
            # Wait for OBS to start and WebSocket to be ready
            for i in range(10):
                time.sleep(2)
                if self.connect():
                    return True
            return False
        except Exception as e:
            logging.error(f"Failed to launch OBS: {e}")
            return False

    def set_profile(self, profile_name):
        if not self.client or not profile_name:
            return
        try:
            self.client.set_current_profile(profile_name)
            logging.info(f"Set OBS profile to: {profile_name}")
            time.sleep(1) # Wait for UI to settle
        except Exception as e:
            logging.error(f"Failed to set profile: {e}")

    def set_scene_collection(self, collection_name):
        if not self.client or not collection_name:
            return
        try:
            self.client.set_current_scene_collection(collection_name)
            logging.info(f"Set OBS scene collection to: {collection_name}")
            time.sleep(1) # Wait for UI to settle
        except Exception as e:
            logging.error(f"Failed to set scene collection: {e}")

    def get_profiles(self):
        if not self.client: return []
        try:
            return self.client.get_profile_list().profiles
        except Exception: return []

    def get_scene_collections(self):
        if not self.client: return []
        try:
            return self.client.get_scene_collection_list().scene_collections
        except Exception: return []

    def get_scenes(self):
        if not self.client: return []
        try:
            # get_scene_list().scenes returns a list of dict-like objects
            scenes = self.client.get_scene_list().scenes
            return [s['sceneName'] if isinstance(s, dict) else s.scene_name for s in scenes]
        except Exception: return []

    def reconnect(self):
        """WebSocket接続が切断された場合に自動再接続を試みます。"""
        logging.info("Attempting to reconnect to OBS WebSocket...")
        self.client = None
        for attempt in range(3):
            try:
                self.client = obs.ReqClient(host=self.host, port=self.port, password=self.password, timeout=30)
                logging.info(f"Reconnected to OBS WebSocket (attempt {attempt + 1})")
                return True
            except Exception as e:
                logging.warning(f"Reconnect attempt {attempt + 1}/3 failed: {e}")
                time.sleep(2)
        logging.error("Failed to reconnect to OBS WebSocket after 3 attempts")
        return False

    def connect(self):
        try:
            if not self.password:
                logging.warning("OBS connection attempted without a password, but authentication is enabled on OBS.")
            
            self.client = obs.ReqClient(host=self.host, port=self.port, password=self.password, timeout=30)
            logging.info("Connected to OBS WebSocket")
            return True
        except Exception as e:
            logging.error(f"Failed to connect to OBS: {e}")
            return False

    def _start_event_client(self):
        """イベントクライアントを起動し、録画状態変更を監視します。"""
        try:
            self.event_client = obs.EventClient(host=self.host, port=self.port, password=self.password)
            self.event_client.callback.register(self._on_record_state_changed)
            logging.info("OBS EventClient started - listening for recording state changes")
        except Exception as e:
            logging.warning(f"Failed to start EventClient (falling back to polling): {e}")
            self.event_client = None

    def _stop_event_client(self):
        """イベントクライアントを停止します。"""
        if self.event_client:
            try:
                self.event_client.disconnect()
            except Exception:
                pass
            self.event_client = None
            logging.info("OBS EventClient stopped")

    def _on_record_state_changed(self, data):
        """OBSから録画状態変更イベントを受信した際のコールバック。"""
        try:
            output_state = getattr(data, 'output_state', '')
            output_active = getattr(data, 'output_active', None)
            logging.info(f"OBS RecordStateChanged event: state={output_state}, active={output_active}")
            
            self._recording_active = bool(output_active)
            
            if not output_active:
                logging.info("Recording stopped (detected via EventClient)")
                self._recording_stopped_event.set()
                if self._on_recording_stopped_callback:
                    self._on_recording_stopped_callback()
        except Exception as e:
            logging.error(f"Error handling RecordStateChanged event: {e}")

    def start_heartbeat(self):
        """WebSocket接続を維持するためのハートビートスレッドを開始します。"""
        self._heartbeat_stop.clear()
        
        def heartbeat_loop():
            while not self._heartbeat_stop.is_set():
                self._heartbeat_stop.wait(30)  # 30秒間隔
                if self._heartbeat_stop.is_set():
                    break
                try:
                    if self.client:
                        self.client.get_version()
                        # ログは出さない（30秒ごとに出ると煩い）
                except Exception as e:
                    logging.warning(f"Heartbeat failed, attempting reconnect: {e}")
                    self.reconnect()
        
        self._heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True, name="OBS-Heartbeat")
        self._heartbeat_thread.start()
        logging.info("OBS WebSocket heartbeat started (30s interval)")

    def stop_heartbeat(self):
        """ハートビートスレッドを停止します。"""
        self._heartbeat_stop.set()
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=5)
            self._heartbeat_thread = None
        logging.info("OBS WebSocket heartbeat stopped")

    def start_monitoring(self, on_stopped_callback=None):
        """録画状態の監視を開始します（EventClient + ハートビート）。"""
        self._recording_active = True
        self._recording_stopped_event.clear()
        self._on_recording_stopped_callback = on_stopped_callback
        self._start_event_client()
        self.start_heartbeat()

    def stop_monitoring(self):
        """録画状態の監視を停止します。"""
        self._on_recording_stopped_callback = None
        self.stop_heartbeat()
        self._stop_event_client()

    def wait_for_recording_stop(self, timeout=None):
        """録画停止イベントを待機します。Trueなら録画停止、Falseならタイムアウト。"""
        return self._recording_stopped_event.wait(timeout=timeout)

    def is_recording_active(self):
        """現在の録画状態を返します（イベント駆動で更新）。"""
        return self._recording_active

    def disconnect(self):
        self.stop_monitoring()
        if self.client:
            self.client = None
            logging.info("Disconnected from OBS WebSocket")

    def start_recording(self):
        if not self.client:
            if not self.connect():
                return False
        try:
            self.client.start_record()
            self._recording_active = True
            logging.info("Started OBS recording")
            return True
        except Exception as e:
            logging.error(f"Failed to start recording: {e}")
            return False

    def stop_recording(self):
        if not self.client:
            # Try reconnecting before giving up
            if not self.reconnect():
                return None
        try:
            response = self.client.stop_record()
            self._recording_active = False
            logging.info(f"Stopped OBS recording. Response: {response}")
            
            # Extract output path from response
            output_path = None
            if hasattr(response, 'output_path'):
                output_path = response.output_path
            elif isinstance(response, dict) and 'outputPath' in response:
                output_path = response['outputPath']
            elif hasattr(response, 'output_active') and not response.output_active:
                logging.warning("Recording stopped but output_path not found in response attributes.")
            
            if output_path:
                logging.info(f"Recording saved to: {output_path}")
            return output_path
        except Exception as e:
            logging.error(f"Failed to stop recording: {e}")
            # One more attempt after reconnect
            if self.reconnect():
                try:
                    response = self.client.stop_record()
                    self._recording_active = False
                    output_path = getattr(response, 'output_path', None)
                    logging.info(f"Stopped OBS recording after reconnect. Path: {output_path}")
                    return output_path
                except Exception as e2:
                    logging.error(f"Failed to stop recording even after reconnect: {e2}")
            return None

    def get_record_status(self):
        if not self.client:
            return False
        try:
            response = self.client.get_record_status()
            return response.output_active
        except Exception as e:
            logging.warning(f"get_record_status failed, attempting reconnect: {e}")
            # Attempt reconnect and retry once
            if self.reconnect():
                try:
                    response = self.client.get_record_status()
                    return response.output_active
                except Exception as e2:
                    logging.error(f"get_record_status failed even after reconnect: {e2}")
            return None  # None means "unknown" - distinct from False ("not recording")

    def set_record_directory(self, path):
        if not self.client:
            return False
        try:
            # Replace backslashes with forward slashes for cross-platform safety
            normalized_path = path.replace("\\", "/")
            
            # 1. Prioritize native SetRecordDirectory request (v5.3.0+)
            try:
                self.client.set_record_directory(recordDirectory=normalized_path)
                logging.info(f"Set OBS record directory using SetRecordDirectory to: {normalized_path}")
            except Exception as e:
                logging.warning(f"SetRecordDirectory failed, attempting profile parameter override: {e}")

            # 2. Fallback: Simple Output Mode configuration change
            try:
                self.client.set_profile_parameter(
                    category="SimpleOutput",
                    name="FilePath",
                    value=normalized_path
                )
                logging.info(f"Set OBS simple record directory parameter to: {normalized_path}")
            except Exception as e:
                logging.warning(f"Could not set SimpleOutput FilePath: {e}")

            # 3. Fallback: Advanced Output Mode configuration change
            try:
                self.client.set_profile_parameter(
                    category="AdvOut",
                    name="RecFilePath",
                    value=normalized_path
                )
                logging.info(f"Set OBS advanced record directory parameter to: {normalized_path}")
            except Exception as e:
                logging.warning(f"Could not set AdvOut RecFilePath: {e}")

            # Verify the set directory
            try:
                current_dir = self.client.get_record_directory()
                if hasattr(current_dir, 'record_directory'):
                    logging.info(f"OBS reports current record directory is: {current_dir.record_directory}")
                elif hasattr(current_dir, 'recordDirectory'):
                    logging.info(f"OBS reports current record directory is: {current_dir.recordDirectory}")
                else:
                    logging.info(f"OBS reports current record directory is: {current_dir}")
            except Exception as e:
                logging.debug(f"Could not verify current record directory: {e}")
                
            return True
        except Exception as e:
            logging.error(f"Failed to set OBS record directory: {e}")
            return False


