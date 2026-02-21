"""
RetroArch Input via PyAutoGUI (Keyboard Simulation)
This simulates actual keyboard presses that RetroArch will receive.

Prerequisites:
1. pip3 install pyautogui
2. Grant Accessibility permissions to Terminal/IDE on macOS:
   System Preferences → Security & Privacy → Privacy → Accessibility
"""

import socket
import time

# Check for pyautogui
try:
    import pyautogui
    pyautogui.FAILSAFE = True  # Move mouse to corner to abort
    pyautogui.PAUSE = 0.01  # Reduce delay between actions
except ImportError:
    print("Please install pyautogui: pip3 install pyautogui")
    exit(1)

RETROARCH_HOST = "127.0.0.1"
RETROARCH_PORT = 55355

# Default RetroArch keyboard bindings for GBA
# You may need to adjust these based on your RetroArch config
RETROARCH_KEYS = {
    'UP': 'up',
    'DOWN': 'down', 
    'LEFT': 'left',
    'RIGHT': 'right',
    'A': 'x',        # Default RetroArch: X = A button
    'B': 'z',        # Default RetroArch: Z = B button
    'START': 'return',  # Enter = Start
    'SELECT': 'shift',  # Right Shift = Select (may vary)
    'L': 'a',        # A = L shoulder
    'R': 's',        # S = R shoulder
}

# Pokemon FireRed Memory Addresses
ADDRESSES = {
    'player_x':   0x02036E48,
    'player_y':   0x02036E4A,
    'map_id':     0x02036E44,
    'direction':  0x02036E50,
    'battle':     0x0202000A,
    'game_state': 0x020204C2,
}

DIRECTION_NAMES = {17: "DOWN", 34: "UP", 51: "LEFT", 68: "RIGHT"}


class RetroArchBridge:
    """Handles memory reading via network and input via keyboard simulation."""
    
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(0.5)
    
    def send_network(self, command):
        """Send network command to RetroArch."""
        try:
            self.sock.sendto(command.encode(), (RETROARCH_HOST, RETROARCH_PORT))
            try:
                response, _ = self.sock.recvfrom(4096)
                return response.decode().strip()
            except socket.timeout:
                return None
        except Exception as e:
            return f"ERROR: {e}"
    
    def read_memory(self, address, length=1):
        """Read bytes from GBA memory."""
        addr_str = f"{address:08X}"
        cmd = f"READ_CORE_MEMORY {addr_str} {length}"
        response = self.send_network(cmd)
        
        if response and "READ_CORE_MEMORY" in response:
            parts = response.split()
            if len(parts) >= 3:
                hex_bytes = parts[2:]
                try:
                    if length == 1:
                        return int(hex_bytes[0], 16)
                    else:
                        return [int(b, 16) for b in hex_bytes[:length]]
                except (ValueError, IndexError):
                    pass
        return None
    
    def read_u8(self, address):
        return self.read_memory(address, 1)
    
    def get_status(self):
        response = self.send_network("GET_STATUS")
        if response:
            if "PLAYING" in response:
                return "playing"
            elif "PAUSED" in response:
                return "paused"
        return "unknown"
    
    def press_button(self, button, duration=0.08):
        """Press a GBA button using keyboard simulation."""
        button = button.upper()
        if button not in RETROARCH_KEYS:
            print(f"Unknown button: {button}")
            return
        
        key = RETROARCH_KEYS[button]
        pyautogui.keyDown(key)
        time.sleep(duration)
        pyautogui.keyUp(key)
    
    def hold_button(self, button, duration=0.3):
        """Hold a button for longer duration."""
        self.press_button(button, duration)
    
    def close(self):
        self.sock.close()


def get_game_state(bridge):
    """Read all game state."""
    state = {}
    state['x'] = bridge.read_u8(ADDRESSES['player_x'])
    state['y'] = bridge.read_u8(ADDRESSES['player_y'])
    state['map_id'] = bridge.read_u8(ADDRESSES['map_id'])
    state['direction_raw'] = bridge.read_u8(ADDRESSES['direction'])
    state['battle'] = bridge.read_u8(ADDRESSES['battle'])
    state['game_state'] = bridge.read_u8(ADDRESSES['game_state'])
    
    if state['direction_raw'] in DIRECTION_NAMES:
        state['direction'] = DIRECTION_NAMES[state['direction_raw']]
    else:
        state['direction'] = f"?({state['direction_raw']})"
    
    return state


def print_state(state, label=""):
    if label:
        print(f"\n{label}")
    print(f"  Position: ({state['x']}, {state['y']})")
    print(f"  Map: {state['map_id']} | Dir: {state['direction']} | Battle: {state['battle']}")


def test_keyboard_input():
    """Test keyboard-based input."""
    print("=" * 55)
    print("RetroArch Input Test via Keyboard Simulation")
    print("=" * 55)
    
    bridge = RetroArchBridge()
    
    # Check status
    status = bridge.get_status()
    print(f"\nRetroArch status: {status}")
    
    if status == "paused":
        print("⚠️  Game is paused! Unpause it first (press P in RetroArch)")
        bridge.close()
        return False
    
    if status != "playing":
        print("⚠️  Game not detected. Make sure Pokemon FireRed is running.")
        bridge.close()
        return False
    
    # Read initial state
    state_before = get_game_state(bridge)
    print_state(state_before, "Before movement:")
    
    # Instructions
    print("\n" + "-" * 55)
    print("IMPORTANT: Click on RetroArch window NOW!")
    print("You have 3 seconds...")
    print("-" * 55)
    
    for i in range(3, 0, -1):
        print(f"  {i}...")
        time.sleep(1)
    
    print("\nSending DOWN button presses...")
    
    # Send multiple DOWN presses
    for i in range(5):
        bridge.press_button('DOWN', duration=0.15)
        time.sleep(0.05)
        print(f"  Press {i+1}/5")
    
    time.sleep(0.3)
    
    # Read new state
    state_after = get_game_state(bridge)
    print_state(state_after, "After movement:")
    
    # Check results
    if state_before['y'] != state_after['y']:
        print("\n✅ SUCCESS! Y position changed (moved down).")
        return True
    elif state_before['x'] != state_after['x']:
        print("\n✅ SUCCESS! X position changed.")
        return True
    elif state_before['direction'] != state_after['direction']:
        print("\n✅ PARTIAL: Direction changed (might be blocked by obstacle).")
        return True
    else:
        print("\n❌ Position didn't change.")
        print("\nTroubleshooting:")
        print("1. Was RetroArch the focused window?")
        print("2. Check your RetroArch key bindings:")
        print("   Settings → Input → Port 1 Controls")
        print("3. Try running this script from Terminal (not IDE)")
        print("4. Grant Accessibility permissions:")
        print("   System Preferences → Security & Privacy → Privacy → Accessibility")
        return False
    
    bridge.close()


def interactive_mode():
    """Interactive control mode."""
    print("\n" + "=" * 55)
    print("Interactive Mode - WASD to move, J=A, K=B, Q=quit")
    print("=" * 55)
    print("\n⚠️  Make sure RetroArch is visible and focused!")
    print("    This window will send keys that RetroArch receives.\n")
    
    bridge = RetroArchBridge()
    
    key_map = {
        'w': 'UP', 's': 'DOWN', 'a': 'LEFT', 'd': 'RIGHT',
        'j': 'A', 'k': 'B', 'i': 'START', 'o': 'SELECT',
    }
    
    import sys
    import termios
    import tty
    
    old_settings = termios.tcgetattr(sys.stdin)
    
    try:
        tty.setcbreak(sys.stdin.fileno())
        print("Ready! Press keys (q to quit, p for position):")
        
        while True:
            char = sys.stdin.read(1).lower()
            
            if char == 'q':
                print("\nExiting...")
                break
            elif char == 'p':
                state = get_game_state(bridge)
                print_state(state)
            elif char in key_map:
                button = key_map[char]
                print(f"  → {button}")
                bridge.press_button(button, duration=0.12)
            
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
    
    bridge.close()


def check_retroarch_keybinds():
    """Show what keys RetroArch should be using."""
    print("\n" + "=" * 55)
    print("Expected RetroArch Key Bindings")
    print("=" * 55)
    print("\nThis script expects these default bindings:")
    print("  D-Pad:   Arrow keys (↑↓←→)")
    print("  A:       X")
    print("  B:       Z") 
    print("  Start:   Enter")
    print("  Select:  Right Shift")
    print("\nTo check/change in RetroArch:")
    print("  Settings → Input → Port 1 Controls")
    print("\nIf your bindings differ, edit RETROARCH_KEYS in this script.")


if __name__ == "__main__":
    print("\n🎮 RetroArch PyAutoGUI Input Test\n")
    
    check_retroarch_keybinds()
    
    print("\n" + "-" * 55)
    input("Press Enter to start the test...")
    
    success = test_keyboard_input()
    
    if success:
        print("\n" + "-" * 55)
        resp = input("Try interactive mode? (y/n): ")
        if resp.lower() == 'y':
            interactive_mode()
    else:
        print("\n" + "-" * 55)
        print("If keys aren't working, check Accessibility permissions on macOS!")