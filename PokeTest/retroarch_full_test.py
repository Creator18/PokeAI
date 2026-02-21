"""
RetroArch Full Integration Test for Pokemon FireRed
Tests memory reading and input commands with the game running.
"""

import socket
import time

RETROARCH_HOST = "127.0.0.1"
RETROARCH_PORT = 55355

# Pokemon FireRed Memory Addresses (GBA)
ADDRESSES = {
    'player_x':   0x02036E48,
    'player_y':   0x02036E4A,
    'map_id':     0x02036E44,
    'direction':  0x02036E50,  # Raw: DOWN=17, UP=34, LEFT=51, RIGHT=68
    'battle':     0x0202000A,  # 0=no battle, 1=in battle
    'game_state': 0x020204C2,  # 0=overworld, 1=menu, 35=battle
}

DIRECTION_NAMES = {17: "DOWN", 34: "UP", 51: "LEFT", 68: "RIGHT"}

class RetroArchBridge:
    def __init__(self, host=RETROARCH_HOST, port=RETROARCH_PORT):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(0.5)
    
    def send(self, command):
        """Send command and return response."""
        try:
            self.sock.sendto(command.encode(), (self.host, self.port))
            try:
                response, _ = self.sock.recvfrom(4096)
                return response.decode().strip()
            except socket.timeout:
                return None
        except Exception as e:
            return f"ERROR: {e}"
    
    def read_memory(self, address, length=1):
        """Read bytes from GBA memory using READ_CORE_MEMORY."""
        # Format address without 0x prefix
        addr_str = f"{address:08X}"
        cmd = f"READ_CORE_MEMORY {addr_str} {length}"
        response = self.send(cmd)
        
        if response and "READ_CORE_MEMORY" in response:
            # Response format: "READ_CORE_MEMORY address XX XX XX..."
            parts = response.split()
            if len(parts) >= 3:
                # Get hex bytes after address
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
        """Read unsigned 8-bit value."""
        return self.read_memory(address, 1)
    
    def read_u16(self, address):
        """Read unsigned 16-bit value (little-endian)."""
        bytes_read = self.read_memory(address, 2)
        if bytes_read and len(bytes_read) == 2:
            return bytes_read[0] | (bytes_read[1] << 8)
        return None
    
    def get_status(self):
        """Get emulator status."""
        response = self.send("GET_STATUS")
        if response:
            if "PLAYING" in response:
                return "playing"
            elif "PAUSED" in response:
                return "paused"
            elif "CONTENTLESS" in response:
                return "no_game"
        return "unknown"
    
    def pause(self):
        """Pause emulation."""
        self.send("PAUSE_TOGGLE")
        time.sleep(0.1)
        if self.get_status() != "paused":
            self.send("PAUSE_TOGGLE")
    
    def unpause(self):
        """Unpause emulation."""
        status = self.get_status()
        if status == "paused":
            self.send("PAUSE_TOGGLE")
            time.sleep(0.1)
    
    def press_button(self, button, duration=0.1):
        """
        Press a button for a duration.
        Buttons: A, B, UP, DOWN, LEFT, RIGHT, START, SELECT, L, R
        """
        button = button.upper()
        # Try multiple command formats
        self.send(f"{button}")
        time.sleep(duration)
    
    def close(self):
        self.sock.close()


def get_game_state(bridge):
    """Read all relevant game state."""
    state = {}
    
    state['x'] = bridge.read_u8(ADDRESSES['player_x'])
    state['y'] = bridge.read_u8(ADDRESSES['player_y'])
    state['map_id'] = bridge.read_u8(ADDRESSES['map_id'])
    state['direction_raw'] = bridge.read_u8(ADDRESSES['direction'])
    state['battle'] = bridge.read_u8(ADDRESSES['battle'])
    state['game_state'] = bridge.read_u8(ADDRESSES['game_state'])
    
    # Decode direction
    if state['direction_raw'] in DIRECTION_NAMES:
        state['direction'] = DIRECTION_NAMES[state['direction_raw']]
    else:
        state['direction'] = f"?({state['direction_raw']})"
    
    return state


def print_state(state, label=""):
    """Pretty print game state."""
    if label:
        print(f"\n{label}")
    print(f"  Position: ({state['x']}, {state['y']})")
    print(f"  Map ID: {state['map_id']}")
    print(f"  Direction: {state['direction']}")
    print(f"  Battle: {state['battle']}")
    print(f"  Game State: {state['game_state']}")


def test_memory_reading(bridge):
    """Test that we can read game memory."""
    print("\n" + "=" * 50)
    print("TEST 1: Memory Reading")
    print("=" * 50)
    
    state = get_game_state(bridge)
    
    if state['x'] is not None:
        print("✓ Memory reading works!")
        print_state(state)
        return True
    else:
        print("✗ Memory reading failed")
        return False


def test_input_commands(bridge):
    """Test that input commands work."""
    print("\n" + "=" * 50)
    print("TEST 2: Input Commands")
    print("=" * 50)
    
    # Make sure game is running
    status = bridge.get_status()
    print(f"Current status: {status}")
    
    if status == "paused":
        print("Unpausing game...")
        bridge.unpause()
        time.sleep(0.3)
        status = bridge.get_status()
        print(f"New status: {status}")
    
    if status != "playing":
        print("⚠️  Game is not playing. Please:")
        print("   1. Make sure a game is loaded")
        print("   2. Unpause if needed (press P in RetroArch)")
        return False
    
    # Read initial position
    state_before = get_game_state(bridge)
    print_state(state_before, "Before movement:")
    
    # Try to move
    print("\nSending movement commands...")
    print("Trying DOWN...")
    
    # Send multiple frames of input
    for _ in range(30):  # ~0.5 seconds of input
        bridge.send("DOWN")
        time.sleep(0.016)  # ~60fps
    
    time.sleep(0.2)
    
    # Read new position
    state_after = get_game_state(bridge)
    print_state(state_after, "After movement:")
    
    # Check if position changed
    if state_before['x'] != state_after['x'] or state_before['y'] != state_after['y']:
        print("\n✓ Input commands work! Position changed.")
        return True
    elif state_before['direction'] != state_after['direction']:
        print("\n✓ Input commands work! Direction changed (may be blocked).")
        return True
    else:
        print("\n⚠️  Position didn't change. Trying alternative input format...")
        
        # Try alternative format
        for _ in range(30):
            bridge.send("INPUT_PLAYER1_DOWN")
            time.sleep(0.016)
        
        time.sleep(0.2)
        state_after2 = get_game_state(bridge)
        
        if state_after['y'] != state_after2['y']:
            print("✓ Alternative format works!")
            return True
        
        print("\n❓ Input may not be working via network commands.")
        print("   We may need to use a different approach.")
        return False


def interactive_control(bridge):
    """Let user manually control the game via network commands."""
    print("\n" + "=" * 50)
    print("Interactive Control Mode")
    print("=" * 50)
    print("Commands: W/A/S/D = movement, J = A, K = B")
    print("          I = Start, O = Select, Q = quit")
    print("          P = print state, U = unpause")
    print("")
    
    import sys
    import termios
    import tty

    # Set up non-blocking input
    old_settings = termios.tcgetattr(sys.stdin)
    
    try:
        tty.setcbreak(sys.stdin.fileno())
        
        key_map = {
            'w': 'UP', 'a': 'LEFT', 's': 'DOWN', 'd': 'RIGHT',
            'j': 'A', 'k': 'B', 'i': 'START', 'o': 'SELECT',
        }
        
        print("Ready! Use WASD to move, J/K for A/B")
        
        while True:
            char = sys.stdin.read(1).lower()
            
            if char == 'q':
                print("\nExiting...")
                break
            elif char == 'p':
                state = get_game_state(bridge)
                print_state(state)
            elif char == 'u':
                bridge.unpause()
                print("Unpaused")
            elif char in key_map:
                button = key_map[char]
                bridge.send(button)
                # Also try holding for a few frames
                for _ in range(5):
                    bridge.send(button)
                    time.sleep(0.016)
                print(f"  → {button}")
            else:
                print(f"  ? Unknown key: {repr(char)}")
                
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)


def main():
    print("=" * 50)
    print("RetroArch Pokemon FireRed Integration Test")
    print("=" * 50)
    
    bridge = RetroArchBridge()
    
    # Check connection
    status = bridge.get_status()
    print(f"\nRetroArch status: {status}")
    
    if status == "no_game":
        print("⚠️  No game loaded! Please load Pokemon FireRed.")
        bridge.close()
        return
    
    # Run tests
    memory_ok = test_memory_reading(bridge)
    
    if memory_ok:
        input_ok = test_input_commands(bridge)
        
        if input_ok:
            print("\n" + "=" * 50)
            print("All tests passed! Ready for AI control.")
            print("=" * 50)
        else:
            print("\n⚠️  Input via network may not work.")
            print("Alternative approaches:")
            print("1. Use keyboard simulation (pyautogui)")
            print("2. Use mGBA standalone with Lua scripting")
    
    # Offer interactive mode
    print("\nWould you like to try interactive control? (y/n)")
    if input().lower() == 'y':
        interactive_control(bridge)
    
    bridge.close()


if __name__ == "__main__":
    main()