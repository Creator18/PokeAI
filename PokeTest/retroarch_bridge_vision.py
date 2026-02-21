"""
RetroArch AI Bridge with Frame Capture
Reads game memory + captures frames for visual learning.

Usage:
1. Start RetroArch with Pokemon FireRed
2. Run this script: python3 retroarch_bridge_vision.py
3. Run the AI notebook in another terminal
"""

import json
import socket
import time
from pathlib import Path

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.005
except ImportError:
    print("ERROR: pip3 install pyautogui")
    exit(1)

try:
    import mss
    import mss.tools
except ImportError:
    print("ERROR: pip3 install mss")
    exit(1)

try:
    import cv2
    import numpy as np
except ImportError:
    print("ERROR: pip3 install opencv-python numpy")
    exit(1)

# =============================================================================
# CONFIGURATION
# =============================================================================

BASE_PATH = Path("/Users/achal/Downloads/PokeTest")
ACTION_FILE = BASE_PATH / "action.json"
STATE_FILE = BASE_PATH / "game_state.json"

RETROARCH_HOST = "127.0.0.1"
RETROARCH_PORT = 55355

# Game window region (from your test results)
GAME_REGION = {"left": 6, "top": 71, "width": 705, "height": 456}

# Frame capture settings
FRAME_WIDTH = 60
FRAME_HEIGHT = 40
USE_GRAYSCALE = False  # Set True for 2,400 values, False for 7,200 values

# Pokemon FireRed Memory Addresses
ADDR_PLAYER_X = 0x02036E48
ADDR_PLAYER_Y = 0x02036E4A
ADDR_MAP_ID = 0x02036E44
ADDR_DIRECTION = 0x02036E50
ADDR_BATTLE = 0x0202000A
ADDR_GAME_STATE = 0x020204C2

# RetroArch keyboard bindings
RETROARCH_KEYS = {
    'UP': 'up', 'DOWN': 'down', 'LEFT': 'left', 'RIGHT': 'right',
    'A': 'x', 'B': 'z', 'START': 'return', 'SELECT': 'shift',
}

DIRECTION_MAP = {17: 0, 34: 1, 51: 2, 68: 3}

# =============================================================================
# BRIDGE CLASS
# =============================================================================

class RetroArchVisionBridge:
    def __init__(self):
        # Network socket for memory reading
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(0.1)
        
        # Screen capture
        self.sct = mss.mss()
        self.game_region = GAME_REGION.copy()
        
        # Frame counter
        self.frame_count = 0
        
        # Ensure output directory exists
        BASE_PATH.mkdir(parents=True, exist_ok=True)
        
        # Performance tracking
        self.capture_times = []
        self.memory_times = []
    
    def send_command(self, command):
        """Send network command to RetroArch."""
        try:
            self.sock.sendto(command.encode(), (RETROARCH_HOST, RETROARCH_PORT))
            try:
                response, _ = self.sock.recvfrom(4096)
                return response.decode().strip()
            except socket.timeout:
                return None
        except:
            return None
    
    def read_memory(self, address, length=1):
        """Read bytes from memory."""
        addr_str = f"{address:08X}"
        response = self.send_command(f"READ_CORE_MEMORY {addr_str} {length}")
        
        if response and "READ_CORE_MEMORY" in response:
            parts = response.split()
            if len(parts) >= 3:
                try:
                    return [int(b, 16) for b in parts[2:2+length]]
                except:
                    pass
        return None
    
    def read_u8(self, address):
        result = self.read_memory(address, 1)
        return result[0] if result else 0
    
    def get_status(self):
        response = self.send_command("GET_STATUS")
        if response:
            if "PLAYING" in response:
                return "playing"
            elif "PAUSED" in response:
                return "paused"
        return "unknown"
    
    def press_button(self, button, duration=0.08):
        """Press a GBA button via keyboard."""
        button = button.upper()
        if button in RETROARCH_KEYS:
            key = RETROARCH_KEYS[button]
            pyautogui.keyDown(key)
            time.sleep(duration)
            pyautogui.keyUp(key)
    
    # =========================================================================
    # FRAME CAPTURE
    # =========================================================================
    
    def capture_frame(self):
        """Capture and process game frame."""
        start = time.time()
        
        # Grab screen region
        img = self.sct.grab(self.game_region)
        frame = np.array(img)
        
        # Convert BGRA to RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
        
        # Resize to target resolution
        frame_small = cv2.resize(frame_rgb, (FRAME_WIDTH, FRAME_HEIGHT), 
                                  interpolation=cv2.INTER_AREA)
        
        # Convert to grayscale if configured
        if USE_GRAYSCALE:
            frame_small = cv2.cvtColor(frame_small, cv2.COLOR_RGB2GRAY)
        
        # Normalize to 0-1 range and flatten
        frame_normalized = frame_small.astype(np.float32) / 255.0
        frame_flat = frame_normalized.flatten().tolist()
        
        self.capture_times.append(time.time() - start)
        
        return frame_flat
    
    def capture_frame_raw(self):
        """Return raw frame for visualization (not flattened)."""
        img = self.sct.grab(self.game_region)
        frame = np.array(img)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
        return cv2.resize(frame_rgb, (FRAME_WIDTH, FRAME_HEIGHT))
    
    # =========================================================================
    # GAME STATE
    # =========================================================================
    
    def read_game_state(self):
        """Read game state from memory - optimized batch read."""
        start = time.time()
        
        # Read player data in one batch (X, Y at 0x02036E48-4B, map at 0x44, dir at 0x50)
        # These are close together, read a chunk
        player_data = self.read_memory(ADDR_MAP_ID, 16)  # Read 16 bytes from map_id
        
        if player_data and len(player_data) >= 16:
            # Offsets from ADDR_MAP_ID (0x02036E44):
            # map_id = offset 0
            # x = offset 4 (0x48 - 0x44)
            # y = offset 6 (0x4A - 0x44)
            # direction = offset 12 (0x50 - 0x44)
            map_id = player_data[0]
            x = player_data[4]
            y = player_data[6]
            direction_raw = player_data[12]
        else:
            # Fallback to individual reads
            x = self.read_u8(ADDR_PLAYER_X)
            y = self.read_u8(ADDR_PLAYER_Y)
            map_id = self.read_u8(ADDR_MAP_ID)
            direction_raw = self.read_u8(ADDR_DIRECTION)
        
        # These are far away, read separately but cache
        if self.frame_count % 5 == 0:  # Only read every 5 frames
            self._cached_battle = self.read_u8(ADDR_BATTLE)
            self._cached_game_state = self.read_u8(ADDR_GAME_STATE)
        
        battle_flag = getattr(self, '_cached_battle', 0)
        game_state = getattr(self, '_cached_game_state', 0)
        
        direction = DIRECTION_MAP.get(direction_raw, direction_raw % 4)
        in_battle = 1 if battle_flag == 1 else 0
        menu_flag = 1 if game_state == 1 else 0
        
        self.memory_times.append(time.time() - start)
        
        return {
            'x': x, 'y': y, 'map_id': map_id,
            'direction': direction, 'in_battle': in_battle,
            'menu_flag': menu_flag
        }
    
    # =========================================================================
    # FILE I/O
    # =========================================================================
    
    def write_state(self, state, frame_data):
        """Write state + frame to JSON for AI to read."""
        data = {
            'state': [
                state['x'], state['y'], state['map_id'],
                state['in_battle'], state['menu_flag'], state['direction']
            ],
            'frame': frame_data,  # New: actual frame data
            'frame_shape': [FRAME_HEIGHT, FRAME_WIDTH, 1 if USE_GRAYSCALE else 3],
            'palette': [],  # Deprecated but kept for compatibility
            'tiles': [],    # Deprecated but kept for compatibility
            'dead': False
        }
        
        try:
            with open(STATE_FILE, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Error writing state: {e}")
    
    def read_action(self):
        """Read action from AI."""
        if not ACTION_FILE.exists():
            return None
        try:
            with open(ACTION_FILE, 'r') as f:
                data = json.load(f)
            return data.get('action')
        except:
            return None
    
    # =========================================================================
    # CALIBRATION
    # =========================================================================
    
    def calibrate_window(self):
        """Interactive calibration for game window region."""
        print("\n" + "=" * 50)
        print("Window Calibration")
        print("=" * 50)
        print("Current region:", self.game_region)
        print("\nOptions:")
        print("  1. Use current region")
        print("  2. Enter coordinates manually")
        print("  3. Interactive (move mouse to corners)")
        
        choice = input("\nChoice [1]: ").strip() or "1"
        
        if choice == "2":
            try:
                self.game_region["left"] = int(input("  Left X [6]: ") or 6)
                self.game_region["top"] = int(input("  Top Y [71]: ") or 71)
                self.game_region["width"] = int(input("  Width [705]: ") or 705)
                self.game_region["height"] = int(input("  Height [456]: ") or 456)
            except ValueError:
                print("Invalid input, using defaults")
        
        elif choice == "3":
            print("\nMove mouse to TOP-LEFT corner of game, press Enter...")
            input()
            x1, y1 = pyautogui.position()
            print(f"  Got: ({x1}, {y1})")
            
            print("Move mouse to BOTTOM-RIGHT corner, press Enter...")
            input()
            x2, y2 = pyautogui.position()
            print(f"  Got: ({x2}, {y2})")
            
            self.game_region = {
                "left": x1, "top": y1,
                "width": x2 - x1, "height": y2 - y1
            }
        
        print(f"\n✓ Using region: {self.game_region}")
        
        # Save a test capture
        frame = self.capture_frame_raw()
        from PIL import Image
        img = Image.fromarray(frame)
        test_path = BASE_PATH / "calibration_test.png"
        img.save(test_path)
        print(f"✓ Test capture saved: {test_path}")
        print("  Check this image to verify the region is correct!")
    
    # =========================================================================
    # MAIN LOOP
    # =========================================================================
    
    def run(self):
        """Main loop."""
        print("=" * 60)
        print("RetroArch Vision Bridge")
        print("=" * 60)
        print(f"Frame size: {FRAME_WIDTH}x{FRAME_HEIGHT} {'grayscale' if USE_GRAYSCALE else 'RGB'}")
        print(f"Frame values: {FRAME_WIDTH * FRAME_HEIGHT * (1 if USE_GRAYSCALE else 3)}")
        print(f"State file: {STATE_FILE}")
        print("=" * 60)
        
        # Check connection
        status = self.get_status()
        print(f"\nRetroArch status: {status}")
        
        if status != "playing":
            print("\n⚠️  Game not playing! Load Pokemon FireRed and unpause.")
            return
        
        # Calibrate
        self.calibrate_window()
        
        print("\n" + "=" * 60)
        print("Starting bridge loop... (Ctrl+C to stop)")
        print("⚠️  Keep RetroArch window visible and focused!")
        print("=" * 60 + "\n")
        
        last_action = None
        
        try:
            while True:
                loop_start = time.time()
                
                # Read memory state
                state = self.read_game_state()
                
                # Capture frame
                frame_data = self.capture_frame()
                
                # Write to file
                self.write_state(state, frame_data)
                
                # Read and execute action
                action = self.read_action()
                if action and action != "NONE":
                    self.press_button(action, duration=0.06)
                    last_action = action
                
                # Logging every 60 frames
                if self.frame_count % 60 == 0:
                    dir_names = {0: "DOWN", 1: "UP", 2: "LEFT", 3: "RIGHT"}
                    dir_str = dir_names.get(state['direction'], '?')
                    
                    avg_capture = np.mean(self.capture_times[-60:]) * 1000 if self.capture_times else 0
                    avg_memory = np.mean(self.memory_times[-60:]) * 1000 if self.memory_times else 0
                    
                    print(f"[{self.frame_count:5d}] Pos:({state['x']:3d},{state['y']:3d}) "
                          f"Map:{state['map_id']:3d} Dir:{dir_str:5s} "
                          f"| Capture:{avg_capture:.1f}ms Mem:{avg_memory:.1f}ms "
                          f"| Act:{last_action or '-'}")
                
                self.frame_count += 1
                
                # Maintain ~50 FPS
                elapsed = time.time() - loop_start
                sleep_time = max(0, 0.02 - elapsed)
                time.sleep(sleep_time)
                
        except KeyboardInterrupt:
            print("\n\nStopping...")
        finally:
            self.sct.close()
            self.sock.close()
            
            # Print performance summary
            if self.capture_times:
                print(f"\nPerformance Summary:")
                print(f"  Avg capture time: {np.mean(self.capture_times)*1000:.2f}ms")
                print(f"  Avg memory read:  {np.mean(self.memory_times)*1000:.2f}ms")
                print(f"  Total frames: {self.frame_count}")


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    print("\n🎮 Pokemon FireRed Vision Bridge\n")
    
    bridge = RetroArchVisionBridge()
    bridge.run()