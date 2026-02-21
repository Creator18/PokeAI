"""
RetroArch Command Discovery Script
Discovers which commands your RetroArch version supports.

Run this with RetroArch open and a GBA game loaded.
"""

import socket
import time

RETROARCH_HOST = "127.0.0.1"
RETROARCH_PORT = 55355

class RetroArchConnection:
    def __init__(self, host=RETROARCH_HOST, port=RETROARCH_PORT):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(0.2)
    
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
    
    def close(self):
        self.sock.close()

def discover_commands():
    """Try various command formats to see what works."""
    ra = RetroArchConnection()
    
    print("=" * 60)
    print("RetroArch Network Command Discovery")
    print("=" * 60)
    
    # ========================================
    # SECTION 1: Basic connectivity
    # ========================================
    print("\n[1] BASIC CONNECTIVITY")
    print("-" * 40)
    
    basic_commands = [
        "VERSION",
        "GET_STATUS", 
        "GET_CONFIG_PARAM version",
        "SHOW_MSG Testing connection",
    ]
    
    connected = False
    for cmd in basic_commands:
        resp = ra.send(cmd)
        status = "✓" if resp and "ERROR" not in str(resp) else "✗"
        print(f"  {status} {cmd}")
        if resp:
            print(f"      → {resp[:80]}")
            connected = True
    
    if not connected:
        print("\n⚠️  No responses received!")
        print("   Please verify:")
        print("   1. RetroArch is running")
        print("   2. A game is loaded (not just the menu)")
        print("   3. Settings → Network → Network Commands = ON")
        print("   4. Port 55355 is correct")
        ra.close()
        return
    
    # ========================================
    # SECTION 2: Memory read commands
    # ========================================
    print("\n[2] MEMORY READ COMMANDS")
    print("-" * 40)
    
    # GBA memory: WRAM at 0x02000000, IRAM at 0x03000000
    # FireRed player X is at 0x02036E48
    memory_commands = [
        # Different syntaxes to try
        "READ_CORE_RAM 02036E48 1",
        "READ_CORE_RAM 0x02036E48 1", 
        "READ_CORE_MEMORY 02036E48 1",
        "READ_CORE_MEMORY 0x02036E48 1",
        "PEEK 0x02036E48",
        "READ_MEMORY 0x02036E48 1",
        # Try reading from start of WRAM
        "READ_CORE_RAM 02000000 16",
    ]
    
    memory_works = False
    working_memory_cmd = None
    
    for cmd in memory_commands:
        resp = ra.send(cmd)
        if resp and "ERROR" not in str(resp) and resp != "-1":
            print(f"  ✓ {cmd}")
            print(f"      → {resp[:80]}")
            memory_works = True
            working_memory_cmd = cmd.split()[0]  # Get command name
        else:
            print(f"  ✗ {cmd}")
    
    # ========================================
    # SECTION 3: Input commands
    # ========================================
    print("\n[3] INPUT COMMANDS")
    print("-" * 40)
    
    # Various input command formats used across RetroArch versions
    input_formats = [
        # Format 1: Direct button names
        ("A", "A button direct"),
        ("B", "B button direct"),
        ("UP", "UP direct"),
        
        # Format 2: INPUT PRESSED/RELEASED
        ("INPUT PRESSED A", "INPUT PRESSED format"),
        ("INPUT RELEASED A", "INPUT RELEASED format"),
        
        # Format 3: PRESS/RELEASE
        ("PRESS A", "PRESS format"),
        ("RELEASE A", "RELEASE format"),
        
        # Format 4: Keyboard-style
        ("KEY_A", "KEY_ format"),
        
        # Format 5: Full path
        ("input_state 0 1 0 0", "input_state format"),
    ]
    
    print("  Testing input formats (watch the game!)...")
    print("  Note: Some may work even without response\n")
    
    for cmd, desc in input_formats:
        resp = ra.send(cmd)
        if resp:
            print(f"  ? {desc}: '{cmd}' → {resp}")
        else:
            print(f"  ? {desc}: '{cmd}' → (no response)")
        time.sleep(0.05)
    
    # ========================================
    # SECTION 4: Frame/state commands
    # ========================================
    print("\n[4] FRAME & STATE COMMANDS")
    print("-" * 40)
    
    frame_commands = [
        "FRAMEADVANCE",
        "FRAME_ADVANCE", 
        "PAUSE_TOGGLE",
        "PAUSE",
        "UNPAUSE",
        "FAST_FORWARD",
        "FAST_FORWARD_HOLD",
        "SLOWMOTION",
        "SCREENSHOT",
        "SAVE_STATE",
        "LOAD_STATE",
        "GET_STATE",
    ]
    
    for cmd in frame_commands:
        resp = ra.send(cmd)
        status = "?" if resp is None else ("✓" if "ERROR" not in str(resp) else "✗")
        print(f"  {status} {cmd}: {resp if resp else '(no response)'}")
    
    # ========================================
    # SECTION 5: Screenshot/video commands
    # ========================================
    print("\n[5] VIDEO/SCREENSHOT COMMANDS")
    print("-" * 40)
    
    video_commands = [
        "SCREENSHOT",
        "GET_FRAMECOUNT",
        "GET_SCREEN",
        "SCREENSHOT_PNG",
    ]
    
    for cmd in video_commands:
        resp = ra.send(cmd)
        print(f"  ? {cmd}: {resp if resp else '(no response)'}")
    
    # ========================================
    # SUMMARY
    # ========================================
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    if memory_works:
        print(f"✓ Memory reading works! Use: {working_memory_cmd}")
    else:
        print("✗ Memory reading via network doesn't seem supported")
        print("  Alternative: Use mGBA's built-in scripting or")
        print("  savestate parsing for memory access")
    
    print("\nNext steps:")
    print("1. Run the input tester to find working button format")
    print("2. If memory read works, we can read game state directly")
    print("3. If not, we'll need alternative approaches")
    
    ra.close()

def interactive_input_test():
    """Interactively test input commands."""
    ra = RetroArchConnection()
    
    print("\n" + "=" * 60)
    print("Interactive Input Test")
    print("=" * 60)
    print("Type commands to send. Try:")
    print("  - A, B, UP, DOWN, LEFT, RIGHT, START, SELECT")
    print("  - INPUT PRESSED A / INPUT RELEASED A")  
    print("  - Or any raw command")
    print("Type 'quit' to exit\n")
    
    while True:
        try:
            cmd = input("Command> ").strip()
            if cmd.lower() == 'quit':
                break
            if cmd:
                resp = ra.send(cmd)
                print(f"  Response: {resp if resp else '(none)'}\n")
        except KeyboardInterrupt:
            break
    
    ra.close()

if __name__ == "__main__":
    discover_commands()
    
    print("\n" + "-" * 60)
    resp = input("Run interactive input test? (y/n): ")
    if resp.lower() == 'y':
        interactive_input_test()