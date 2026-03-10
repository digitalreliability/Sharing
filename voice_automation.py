"""
Voice-Controlled PC Automation - FAST & RELIABLE
Wake word: "Aakaash" (Telugu for Sky)
- Instant app launch via subprocess
- Always-on wake word detection (works even when minimised)
- LM Studio with fallback pattern matching
Designed for PyInstaller packaging.
"""

import tkinter as tk
from tkinter import messagebox, scrolledtext
import threading
import time
import re
import sys
import os
import subprocess
import webbrowser
from datetime import datetime
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, TimeoutError

# Core automation libraries
import lmstudio as lms
import pyautogui
import speech_recognition as sr
import pyttsx3

# Global hotkey library
import keyboard

# PyAutoGUI safety
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.2  # Reduced pause for faster actions


class VoiceAutomation:
    """Handles all voice recognition, LM Studio communication, and PC control."""

    def __init__(self, status_callback=None, wake_callback=None, log_callback=None):
        self.status_callback = status_callback
        self.wake_callback = wake_callback
        self.log_callback = log_callback

        # Text-to-speech
        self.engine = pyttsx3.init()
        self.engine.setProperty('rate', 175)
        self.engine.setProperty('volume', 0.9)

        # Speech recognizer (shared, but used carefully)
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()

        # LM Studio
        self.model = None
        self.lm_studio_available = False

        # Wake word settings
        self.wake_word = "aakaash"
        self.wake_word_enabled = False
        self.wake_thread = None
        self.stop_wake_flag = threading.Event()
        self.is_listening_command = False  # Prevents overlapping

        # Quick app launch mapping (for instant execution)
        self.app_map = {
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "calc": "calc.exe",
            "chrome": "chrome.exe",
            "firefox": "firefox.exe",
            "edge": "msedge.exe",
            "explorer": "explorer.exe",
            "file explorer": "explorer.exe",
            "word": "winword.exe",
            "excel": "excel.exe",
            "powerpoint": "powerpnt.exe",
            "paint": "mspaint.exe",
            "cmd": "cmd.exe",
            "command prompt": "cmd.exe",
            "powershell": "powershell.exe",
        }

        # Screenshot folder
        self.pictures_folder = os.path.join(os.path.expanduser("~"), "Pictures")
        if not os.path.exists(self.pictures_folder):
            self.pictures_folder = os.path.dirname(os.path.abspath(__file__))

        # Fallback command patterns (same as before, but with close pattern already there)
        self.fallback_patterns = [
            (r"(open|launch|start)\s+(.+)", self._handle_open_fallback),
            (r"type\s+(.+)$", lambda m: self.type_text(m.group(1))),
            (r"(write|enter)\s+(.+)$", lambda m: self.type_text(m.group(2))),
            (r"say\s+(.+)$", lambda m: self.type_text(m.group(1))),
            (r"press\s+(enter|return)", lambda m: self.press_key("enter")),
            (r"press\s+(space|spacebar)", lambda m: self.press_key("space")),
            (r"press\s+(tab)", lambda m: self.press_key("tab")),
            (r"press\s+(escape|esc)", lambda m: self.press_key("esc")),
            (r"press\s+(backspace|delete)", lambda m: self.press_key("backspace")),
            (r"(volume|sound)\s+(up|increase)", lambda m: self.press_key("volumeup")),
            (r"(volume|sound)\s+(down|decrease)", lambda m: self.press_key("volumedown")),
            (r"mute", lambda m: self.press_key("volumemute")),
            (r"scroll\s+up", lambda m: self.scroll(3)),
            (r"scroll\s+down", lambda m: self.scroll(-3)),
            (r"scroll\s+a little\s+up", lambda m: self.scroll(1)),
            (r"scroll\s+a little\s+down", lambda m: self.scroll(-1)),
            (r"mouse\s+position|where (is|am) i", lambda m: self.get_mouse_position()),
            (r"click", lambda m: self.move_and_click()),
            (r"right[-\s]*click", lambda m: self.move_and_click(button='right')),
            (r"double[-\s]*click", lambda m: pyautogui.doubleClick() or "✅ Double-clicked"),
            (r"(take|make)\s+a?\s*screen(shot)?", lambda m: self.take_screenshot()),
            (r"(minimize|hide)\s+(all )?windows|show desktop", lambda m: self.minimize_all_windows()),
            (r"copy", lambda m: self.hotkey("ctrl", "c")),
            (r"paste", lambda m: self.hotkey("ctrl", "v")),
            (r"select all", lambda m: self.hotkey("ctrl", "a")),
            (r"cut", lambda m: self.hotkey("ctrl", "x")),
            (r"undo", lambda m: self.hotkey("ctrl", "z")),
            (r"redo", lambda m: self.hotkey("ctrl", "y")),
            (r"save", lambda m: self.hotkey("ctrl", "s")),
            (r"close|exit", lambda m: self.close_window()),
        ]

        # Initial LM Studio check
        self.check_lm_studio()

    def _handle_open_fallback(self, match):
        """Extract app name from 'open ...' command and launch it."""
        app = match.group(2).strip().lower()
        return self.open_application(app)

    # ---------- Logging ----------
    def log(self, message, level="INFO"):
        if self.log_callback:
            self.log_callback(f"[{level}] {message}")
        else:
            print(f"[{level}] {message}")

    def update_status(self, message):
        if self.status_callback:
            self.status_callback(message)
        else:
            print(f"[STATUS] {message}")

    # ---------- Text-to-Speech ----------
    def speak(self, text):
        self.update_status(f"Speaking: {text[:50]}...")
        self.log(f"Speaking: {text}")
        self.engine.say(text)
        self.engine.runAndWait()

    # ---------- LM Studio ----------
    def check_lm_studio(self):
        try:
            self.model = lms.llm()
            self.lm_studio_available = True
            self.update_status("✅ LM Studio connected")
            self.log("LM Studio connected successfully")
            return True
        except Exception as e:
            self.lm_studio_available = False
            self.update_status(f"⚠️ LM Studio not available: {e}")
            self.log(f"LM Studio connection failed: {e}", "WARNING")
            return False

    # ---------- FAST APP LAUNCH ----------
    def open_application(self, app_name: str) -> str:
        """Launch application instantly using subprocess."""
        app_key = app_name.lower().strip()
        # Check our mapping first
        if app_key in self.app_map:
            executable = self.app_map[app_key]
        else:
            # Assume it's a command that might be in PATH (like "notepad")
            executable = app_key

        try:
            # Use subprocess to launch without waiting
            subprocess.Popen(executable, shell=True)
            msg = f"✅ Launched {app_name}"
            self.log(msg)
            return msg
        except Exception as e:
            msg = f"❌ Failed to launch {app_name}: {e}"
            self.log(msg, "ERROR")
            return msg

    # ---------- Voice Input (for commands) ----------
    def listen_for_command(self, timeout=3, phrase_limit=5) -> Optional[str]:
        """Shorter timeout for quicker response."""
        try:
            with self.microphone as source:
                self.update_status("🎤 Listening for command...")
                self.recognizer.adjust_for_ambient_noise(source, duration=0.3)
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)

            self.update_status("🔄 Processing speech...")
            command = self.recognizer.recognize_google(audio).lower()
            self.update_status(f"📝 You said: '{command}'")
            self.log(f"Recognized: '{command}'")
            return command
        except sr.WaitTimeoutError:
            self.update_status("⏰ No speech detected")
            return None
        except sr.UnknownValueError:
            self.update_status("❌ Could not understand audio")
            self.speak("Sorry, I didn't catch that.")
            return None
        except Exception as e:
            self.update_status(f"❌ Error: {e}")
            self.log(f"Speech recognition error: {e}", "ERROR")
            return None

    # ---------- Wake Word Detection (Always On) ----------
    def wake_word_listener(self):
        """Runs in a background thread, continuously listening for wake word."""
        self.update_status(f"👂 Wake word '{self.wake_word}' enabled")
        self.log(f"Wake word '{self.wake_word}' enabled")

        while self.wake_word_enabled and not self.stop_wake_flag.is_set():
            # If a command is already being processed, skip listening to avoid conflicts
            if self.is_listening_command:
                time.sleep(0.1)
                continue

            try:
                # Listen for a short chunk (max 2 seconds)
                with self.microphone as source:
                    # No need to adjust noise every time; do it occasionally
                    audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=2)

                # Quick recognition attempt
                try:
                    text = self.recognizer.recognize_google(audio, show_all=False)
                    if text and self.wake_word in text.lower():
                        self.update_status(f"✅ Wake word detected")
                        self.log("Wake word detected!")
                        if self.wake_callback:
                            self.wake_callback()
                        # Trigger command listening in a separate thread
                        threading.Thread(target=self._wake_triggered_command, daemon=True).start()
                        # Wait a moment to avoid re-triggering
                        time.sleep(1.5)
                except sr.UnknownValueError:
                    pass
                except sr.RequestError as e:
                    self.log(f"Wake word recognition error: {e}", "ERROR")
                    time.sleep(1)
            except sr.WaitTimeoutError:
                continue  # No speech, just loop
            except Exception as e:
                self.log(f"Wake thread error: {e}", "ERROR")
                time.sleep(0.5)

    def _wake_triggered_command(self):
        """Handles command listening after wake word."""
        if self.is_listening_command:
            return
        self.is_listening_command = True
        was_enabled = self.wake_word_enabled
        if was_enabled:
            self.set_wake_word_enabled(False)  # Pause wake detection

        self.speak("Yes?")
        command = self.listen_for_command()
        if command:
            self.update_status("🤔 Processing...")
            response = self.process_with_lmstudio(command)
            if response.startswith("✅"):
                self.speak("Done.")
            elif response.startswith("❌"):
                self.speak("Sorry, I couldn't do that.")
            else:
                self.speak(response)

        if was_enabled:
            self.set_wake_word_enabled(True)  # Resume wake detection
        self.is_listening_command = False

    def set_wake_word_enabled(self, enabled: bool):
        if enabled == self.wake_word_enabled:
            return
        self.wake_word_enabled = enabled
        if enabled:
            self.stop_wake_flag.clear()
            self.wake_thread = threading.Thread(target=self.wake_word_listener, daemon=True)
            self.wake_thread.start()
        else:
            self.stop_wake_flag.set()
            if self.wake_thread and self.wake_thread.is_alive():
                self.wake_thread.join(timeout=2)
            self.update_status("👂 Wake word disabled")
            self.log("Wake word disabled")

    # ---------- Tool Functions (unchanged, but faster) ----------
    # (All tool functions remain exactly as before, with docstrings)
    # I'll keep them concise here; they are identical to previous version.

    def type_text(self, text: str) -> str:
        try:
            pyautogui.write(text, interval=0.02)  # faster typing
            msg = f"✅ Typed: {text[:30]}..."
            self.log(msg)
            return msg
        except Exception as e:
            msg = f"❌ Failed to type text: {e}"
            self.log(msg, "ERROR")
            return msg

    def press_key(self, key: str) -> str:
        try:
            pyautogui.press(key)
            msg = f"✅ Pressed {key}"
            self.log(msg)
            return msg
        except Exception as e:
            msg = f"❌ Failed to press key {key}: {e}"
            self.log(msg, "ERROR")
            return msg

    def hotkey(self, *keys) -> str:
        try:
            pyautogui.hotkey(*keys)
            msg = f"✅ Pressed {'+'.join(keys)}"
            self.log(msg)
            return msg
        except Exception as e:
            msg = f"❌ Failed to press hotkey: {e}"
            self.log(msg, "ERROR")
            return msg

    def move_and_click(self, x=None, y=None, button='left') -> str:
        try:
            if x is not None and y is not None:
                pyautogui.moveTo(int(x), int(y), duration=0.2)
                msg = f"✅ Moved to ({x},{y}) and clicked {button}"
            else:
                pyautogui.click(button=button)
                msg = f"✅ Clicked {button} at current position"
            self.log(msg)
            return msg
        except Exception as e:
            msg = f"❌ Failed to click: {e}"
            self.log(msg, "ERROR")
            return msg

    def scroll(self, amount: int) -> str:
        try:
            pyautogui.scroll(int(amount))
            direction = "up" if amount > 0 else "down"
            msg = f"✅ Scrolled {direction}"
            self.log(msg)
            return msg
        except Exception as e:
            msg = f"❌ Failed to scroll: {e}"
            self.log(msg, "ERROR")
            return msg

    def take_screenshot(self) -> str:
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"
            filepath = os.path.join(self.pictures_folder, filename)
            pyautogui.screenshot().save(filepath)
            msg = f"✅ Screenshot saved as {filepath}"
            self.log(msg)
            return msg
        except Exception as e:
            msg = f"❌ Failed to take screenshot: {e}"
            self.log(msg, "ERROR")
            return msg

    def get_mouse_position(self) -> str:
        try:
            x, y = pyautogui.position()
            msg = f"✅ Mouse at ({x}, {y})"
            self.log(msg)
            return msg
        except Exception as e:
            msg = f"❌ Failed to get mouse position: {e}"
            self.log(msg, "ERROR")
            return msg

    def minimize_all_windows(self) -> str:
        try:
            pyautogui.hotkey('win', 'd')
            msg = "✅ Windows minimized"
            self.log(msg)
            return msg
        except Exception as e:
            msg = f"❌ Failed to minimize windows: {e}"
            self.log(msg, "ERROR")
            return msg

    def open_file_explorer(self) -> str:
        try:
            subprocess.Popen("explorer.exe")
            msg = "✅ Opened File Explorer"
            self.log(msg)
            return msg
        except Exception as e:
            msg = f"❌ Failed to open File Explorer: {e}"
            self.log(msg, "ERROR")
            return msg

    def close_window(self) -> str:
        try:
            pyautogui.hotkey('alt', 'f4')
            msg = "✅ Closed active window"
            self.log(msg)
            return msg
        except Exception as e:
            msg = f"❌ Failed to close window: {e}"
            self.log(msg, "ERROR")
            return msg

    # ---------- Fallback & LM Studio Processing ----------
    def process_fallback(self, command: str) -> str:
        for pattern, action in self.fallback_patterns:
            match = re.search(pattern, command, re.IGNORECASE)
            if match:
                try:
                    return action(match)
                except Exception as e:
                    err_msg = f"❌ Error executing fallback: {e}"
                    self.log(err_msg, "ERROR")
                    return err_msg
        # Conversational help
        if any(word in command for word in ["how", "what", "why", "can you", "are you", "hello", "hi"]):
            msg = ("I'm your voice automation assistant. To control your PC, try commands like "
                   "'open notepad', 'type hello', 'scroll down', 'take a screenshot', or 'close window'. "
                   "For general conversation, please load a model in LM Studio.")
            self.log(msg)
            return msg
        else:
            msg = ("Sorry, I don't know how to do that. Say 'help' for examples, or "
                   "load a model in LM Studio for more natural conversation.")
            self.log(msg, "WARNING")
            return msg

    def process_with_lmstudio(self, command: str) -> str:
        if not self.lm_studio_available:
            return self.process_fallback(command)
        tools = [
            self.open_application,
            self.type_text,
            self.press_key,
            self.hotkey,
            self.move_and_click,
            self.scroll,
            self.take_screenshot,
            self.get_mouse_position,
            self.minimize_all_windows,
            self.open_file_explorer,
            self.close_window,
        ]
        try:
            self.log(f"Sending command to LM Studio: '{command}'")
            def lm_task():
                return self.model.act(
                    command,
                    tools,
                    on_message=lambda m: self.log(f"🧠 LM: {m}", "DEBUG") if m else None
                )
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(lm_task)
                result = future.result(timeout=15)  # seconds
            self.log(f"LM Studio raw result: {result}")
            result_str = str(result)
            if "Cannot find tool" in result_str or "tool_name" in result_str:
                self.log("LM Studio returned invalid tool call – falling back", "WARNING")
                return self.process_fallback(command)
            return result_str
        except TimeoutError:
            self.log("⏰ LM Studio call timed out – falling back", "ERROR")
            return self.process_fallback(command)
        except Exception as e:
            self.log(f"❌ LM Studio error: {e}, falling back", "ERROR")
            return self.process_fallback(command)

    # ---------- Manual trigger ----------
    def trigger_command_listening(self):
        if self.is_listening_command:
            self.update_status("Already listening...")
            self.log("Already listening, ignoring trigger")
            return
        self.is_listening_command = True
        was_enabled = self.wake_word_enabled
        if was_enabled:
            self.set_wake_word_enabled(False)

        command = self.listen_for_command()
        if command:
            self.update_status("🤔 Processing...")
            response = self.process_with_lmstudio(command)
            if response.startswith("✅"):
                self.speak("Done.")
            elif response.startswith("❌"):
                self.speak("Sorry, I couldn't do that.")
            else:
                self.speak(response)

        if was_enabled:
            self.set_wake_word_enabled(True)
        self.is_listening_command = False

    # ---------- Microphone test ----------
    def test_microphone(self):
        try:
            with self.microphone as source:
                self.update_status("🎤 Testing microphone...")
                self.log("Testing microphone...")
                self.recognizer.adjust_for_ambient_noise(source, duration=0.3)
                audio = self.recognizer.listen(source, timeout=3, phrase_time_limit=2)
            self.update_status("✅ Microphone working")
            self.log("Microphone test successful")
            return True
        except Exception as e:
            self.update_status(f"❌ Microphone test failed: {e}")
            self.log(f"Microphone test failed: {e}", "ERROR")
            return False


# ---------- StatusOverlay (unchanged) ----------
class StatusOverlay:
    # ... (exactly as before, omitted for brevity; include from previous version)
    def __init__(self, root):
        self.root = root
        self.window = tk.Toplevel(root)
        self.window.title("Status")
        self.window.geometry("300x70+50+50")
        self.window.attributes('-topmost', True)
        self.window.overrideredirect(True)
        self.window.configure(bg='lightyellow')
        self.window.bind('<Button-1>', self.start_move)
        self.window.bind('<B1-Motion>', self.on_move)
        self.label = tk.Label(self.window, text="Ready", font=("Arial", 12),
                              bg='lightyellow', wraplength=280)
        self.label.pack(expand=True, fill='both', padx=5, pady=5)
        close_btn = tk.Button(self.window, text="✕", command=self.hide,
                              bg='red', fg='white', bd=0, font=('Arial', 8))
        close_btn.place(relx=1.0, x=-5, y=5, anchor='ne')
        self.visible = True
    def start_move(self, event): self.x, self.y = event.x, event.y
    def on_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.window.winfo_x() + deltax
        y = self.window.winfo_y() + deltay
        self.window.geometry(f"+{x}+{y}")
    def update_status(self, message): self.label.config(text=message)
    def hide(self): self.window.withdraw(); self.visible = False
    def show(self): self.window.deiconify(); self.visible = True


# ---------- GUI (unchanged, except we keep the same layout) ----------
class VoiceAutomationGUI:
    # ... (exactly as before, but ensure we use the new VoiceAutomation)
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Voice Automation - Aakaash")
        self.root.geometry("700x600")
        self.root.resizable(True, True)
        branding = "From Ganesh Solutions by Kishore DVR | For more details visit www.parishodana.xyz"
        tk.Label(self.root, text=branding, font=("Arial", 9), fg="blue").pack(pady=5)
        self.current_hotkey = "ctrl+shift+l"
        self.hotkey_registered = False
        self.build_ui()
        self.overlay = StatusOverlay(self.root)
        self.engine = VoiceAutomation(
            status_callback=self.on_status_update,
            wake_callback=self.on_wake_word_detected,
            log_callback=self.on_log_message
        )
        self.register_hotkey(self.current_hotkey)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def build_ui(self):
        # ... (same as before – includes status, listen button, mic test, wake toggle, overlay toggle, LM status, hotkey, log, quit)
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        control_frame = tk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=5)
        self.status_var = tk.StringVar(value="Ready")
        tk.Label(control_frame, textvariable=self.status_var, font=("Arial", 12), fg="blue").pack(side=tk.LEFT, padx=5)
        self.listen_btn = tk.Button(control_frame, text="Listen", command=self.start_listening,
                                    bg="green", fg="white", font=("Arial", 12), width=8)
        self.listen_btn.pack(side=tk.LEFT, padx=5)
        self.test_mic_btn = tk.Button(control_frame, text="Test Mic", command=self.test_microphone,
                                      bg="orange", fg="white", font=("Arial", 12), width=8)
        self.test_mic_btn.pack(side=tk.LEFT, padx=5)

        settings_frame = tk.Frame(main_frame)
        settings_frame.pack(fill=tk.X, pady=5)
        self.wake_var = tk.BooleanVar(value=False)
        self.wake_check = tk.Checkbutton(settings_frame, text="Enable wake word 'Aakaash'",
                                         variable=self.wake_var, command=self.toggle_wake_word)
        self.wake_check.pack(side=tk.LEFT, padx=5)
        self.overlay_var = tk.BooleanVar(value=True)
        self.overlay_check = tk.Checkbutton(settings_frame, text="Show status overlay",
                                            variable=self.overlay_var, command=self.toggle_overlay)
        self.overlay_check.pack(side=tk.LEFT, padx=5)

        lm_frame = tk.Frame(main_frame)
        lm_frame.pack(fill=tk.X, pady=5)
        self.lm_status_label = tk.Label(lm_frame, text="LM Studio: Unknown", fg="gray")
        self.lm_status_label.pack(side=tk.LEFT, padx=5)
        self.retry_lm_btn = tk.Button(lm_frame, text="Retry LM Studio", command=self.retry_lm_studio)
        self.retry_lm_btn.pack(side=tk.LEFT, padx=5)

        hotkey_frame = tk.Frame(main_frame)
        hotkey_frame.pack(fill=tk.X, pady=5)
        tk.Label(hotkey_frame, text="Global Hotkey:").pack(side=tk.LEFT, padx=5)
        self.hotkey_entry = tk.Entry(hotkey_frame, width=15)
        self.hotkey_entry.pack(side=tk.LEFT, padx=5)
        self.hotkey_entry.insert(0, self.current_hotkey)
        self.set_hotkey_btn = tk.Button(hotkey_frame, text="Set Hotkey", command=self.set_hotkey)
        self.set_hotkey_btn.pack(side=tk.LEFT, padx=5)

        log_frame = tk.Frame(main_frame)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        tk.Label(log_frame, text="Command Log:", font=("Arial", 10, "bold")).pack(anchor=tk.W)
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, wrap=tk.WORD, state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        tk.Button(main_frame, text="Quit", command=self.on_close, bg="red", fg="white").pack(pady=5)

    def on_status_update(self, message):
        self.status_var.set(message)
        if self.overlay_var.get() and self.overlay.visible:
            self.overlay.update_status(message)
        if "LM Studio" in message:
            if "connected" in message:
                self.lm_status_label.config(text="LM Studio: Connected", fg="green")
            elif "not available" in message:
                self.lm_status_label.config(text="LM Studio: Disconnected", fg="red")

    def on_log_message(self, message):
        def append():
            self.log_text.config(state=tk.NORMAL)
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)
        self.root.after(0, append)

    def on_wake_word_detected(self):
        self.listen_btn.config(bg="orange")
        self.root.after(500, lambda: self.listen_btn.config(bg="green"))

    def toggle_wake_word(self):
        if self.wake_var.get():
            self.engine.set_wake_word_enabled(True)
        else:
            self.engine.set_wake_word_enabled(False)

    def toggle_overlay(self):
        if self.overlay_var.get():
            self.overlay.show()
        else:
            self.overlay.hide()

    def retry_lm_studio(self):
        self.engine.check_lm_studio()

    def test_microphone(self):
        self.test_mic_btn.config(state=tk.DISABLED, text="Testing...")
        threading.Thread(target=self._test_mic_thread, daemon=True).start()

    def _test_mic_thread(self):
        self.engine.test_microphone()
        self.root.after(0, lambda: self.test_mic_btn.config(state=tk.NORMAL, text="Test Mic"))

    def start_listening(self):
        if self.engine.is_listening_command:
            return
        self.listen_btn.config(state=tk.DISABLED)
        threading.Thread(target=self._listen_thread, daemon=True).start()

    def _listen_thread(self):
        self.engine.trigger_command_listening()
        self.root.after(0, lambda: self.listen_btn.config(state=tk.NORMAL))

    def register_hotkey(self, hotkey):
        try:
            if self.hotkey_registered:
                keyboard.remove_hotkey(self.hotkey_registered)
            self.hotkey_registered = keyboard.add_hotkey(hotkey, self.hotkey_callback)
            self.on_log_message(f"Hotkey '{hotkey}' registered")
        except Exception as e:
            messagebox.showerror("Hotkey Error", f"Failed to register hotkey:\n{e}")
            self.hotkey_registered = False

    def hotkey_callback(self):
        threading.Thread(target=self.start_listening_from_hotkey, daemon=True).start()

    def start_listening_from_hotkey(self):
        self.root.after(0, lambda: self.listen_btn.config(state=tk.DISABLED))
        self.engine.trigger_command_listening()
        self.root.after(0, lambda: self.listen_btn.config(state=tk.NORMAL))

    def set_hotkey(self):
        new_hotkey = self.hotkey_entry.get().strip()
        if new_hotkey:
            self.current_hotkey = new_hotkey
            self.register_hotkey(new_hotkey)

    def on_close(self):
        if self.hotkey_registered:
            try:
                keyboard.remove_hotkey(self.hotkey_registered)
            except:
                pass
        self.engine.set_wake_word_enabled(False)
        self.overlay.window.destroy()
        self.root.destroy()
        sys.exit(0)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = VoiceAutomationGUI()
    app.run()