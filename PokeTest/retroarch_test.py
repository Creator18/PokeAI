"""
RetroArch Network Commands - Connection Test
Run this while RetroArch is open with a game loaded.

Prerequisites:
1. RetroArch → Settings → Network → Network Commands = ON
2. RetroArch → Settings → Network → Network Command Port = 55355
"""

import socket
import time

RETROARCH_HOST = "127.0.0.1"
RETROARCH_PORT = 55355

def send_command(sock, command):
    """Send a command to RetroArch and optionally get response."""
    try:
        sock.sendto(command.encode(), (RETROARCH_HOST, RETROARCH_PORT))
        sock.settimeout(0.1)
        try:
            response, _ = sock.recvfrom(4096)
            return response.decode().strip()
        except socket.timeout:
            return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def test_connection():
    """Test basic RetroArch connectivity."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    print("=" * 50)
    print("RetroArch Network Command Test")
    print("=" * 50)
    
    # Test 1: Get version
    print("\n[TEST 1] Getting RetroArch version...")
    response = send_command(sock, "VERSION")
    if response:
        print(f"  ✓ Connected! Version: {response}")
    else:
        print("  ✗ No response. Check:")
        print("    - Is RetroArch running?")
        print("    - Is Network Commands enabled?")
        print("    - Is a game loaded?")
        return False
    
    # Test 2: Get status
    print("\n[TEST 2] Getting emulator status...")
    response = send_command(sock, "GET_STATUS")
    if response:
        print(f"  ✓ Status: {response}")
    else:
        print("  ? No status response (may be normal)")
    
    # Test 3: Read memory (GBA WRAM starts at 0x02000000)
    print("\n[TEST 3] Testing memory read...")
    # Try to read player X position (FireRed address)
    response = send_command(sock, "READ_CORE_RAM 02036E48 1")
    if response:
        print(f"  ✓ Memory read response: {response}")
    else:
        print("  ? Memory read not supported or no response")
        print("    (This is okay - we may need alternative methods)")
    
    # Test 4: Send a test input
    print("\n[TEST 4] Testing input command...")
    print("  Sending DOWN press for 5 frames...")
    for i in range(5):
        send_command(sock, "INPUT_DOWN")
        time.sleep(0.016)  # ~60fps
    send_command(sock, "INPUT_UP")  # Release
    print("  ✓ Input commands sent (check if character moved)")
    
    # Test 5: List available commands
    print("\n[TEST 5] Checking available commands...")
    test_commands = [
        "PAUSE_TOGGLE",
        "READ_CORE_MEMORY 0x02036E48 1",  # Alternative syntax
        "GET_CONFIG_PARAM input_driver",
    ]
    for cmd in test_commands:
        response = send_command(sock, cmd)
        print(f"  {cmd}: {response if response else 'no response'}")
    
    sock.close()
    print("\n" + "=" * 50)
    print("Test complete!")
    print("=" * 50)
    return True

def test_input_commands():
    """Test all GBA input commands."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    print("\n" + "=" * 50)
    print("Input Command Test")
    print("=" * 50)
    
    # RetroArch uses "INPUT PRESSED/RELEASED" format
    # or direct button commands depending on version
    
    button_tests = [
        # Format: (press_cmd, release_cmd, name)
        ("INPUT PRESSED A", "INPUT RELEASED A", "A Button"),
        ("INPUT PRESSED B", "INPUT RELEASED B", "B Button"),
        ("INPUT PRESSED UP", "INPUT RELEASED UP", "D-Pad Up"),
        ("INPUT PRESSED DOWN", "INPUT RELEASED DOWN", "D-Pad Down"),
        ("INPUT PRESSED LEFT", "INPUT RELEASED LEFT", "D-Pad Left"),
        ("INPUT PRESSED RIGHT", "INPUT RELEASED RIGHT", "D-Pad Right"),
        ("INPUT PRESSED START", "INPUT RELEASED START", "Start"),
        ("INPUT PRESSED SELECT", "INPUT RELEASED SELECT", "Select"),
    ]
    
    print("\nTesting each button (watch the game)...")
    print("Press Ctrl+C to stop\n")
    
    try:
        for press_cmd, release_cmd, name in button_tests:
            print(f"  Testing {name}...")
            send_command(sock, press_cmd)
            time.sleep(0.1)
            send_command(sock, release_cmd)
            time.sleep(0.3)
    except KeyboardInterrupt:
        print("\nStopped by user")
    
    sock.close()

if __name__ == "__main__":
    if test_connection():
        print("\nWould you like to test input commands? (y/n)")
        if input().lower() == 'y':
            test_input_commands()