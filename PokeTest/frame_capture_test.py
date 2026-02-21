"""
Frame Capture Test for RetroArch
Tests different methods of capturing gameplay frames.

Install dependencies:
    pip3 install mss pillow numpy opencv-python
"""

import time
from pathlib import Path

import numpy as np

# Optional imports - we'll check what's available
MSS_AVAILABLE = False
CV2_AVAILABLE = False
PIL_AVAILABLE = False

try:
    import mss
    MSS_AVAILABLE = True
except ImportError:
    print("mss not installed: pip3 install mss")

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    print("opencv not installed: pip3 install opencv-python")

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    print("pillow not installed: pip3 install pillow")

BASE_PATH = Path("/Users/achal/Downloads/PokeTest")

# GBA native resolution
GBA_WIDTH = 240
GBA_HEIGHT = 160


def test_mss_capture():
    """Test screen capture using mss library."""
    if not MSS_AVAILABLE:
        print("❌ mss not available")
        return None
    
    print("\n" + "=" * 50)
    print("TEST: mss Screen Capture")
    print("=" * 50)
    
    with mss.mss() as sct:
        # List all monitors
        print("\nAvailable monitors:")
        for i, mon in enumerate(sct.monitors):
            print(f"  {i}: {mon}")
        
        print("\n⚠️  Position RetroArch window and note its location!")
        print("   We need to capture just the game area.")
        
        # For now, capture a region - user will need to adjust
        # Default: assume RetroArch is near top-left, 720x480 window
        print("\nEnter RetroArch window coordinates (or press Enter for defaults):")
        
        try:
            x = input("  Left X position [100]: ").strip()
            x = int(x) if x else 100
            
            y = input("  Top Y position [100]: ").strip()
            y = int(y) if y else 100
            
            w = input("  Width [720]: ").strip()
            w = int(w) if w else 720
            
            h = input("  Height [480]: ").strip()
            h = int(h) if h else 480
        except ValueError:
            x, y, w, h = 100, 100, 720, 480
        
        monitor = {"left": x, "top": y, "width": w, "height": h}
        print(f"\nCapturing region: {monitor}")
        
        # Benchmark capture speed
        print("\nBenchmarking capture speed (100 frames)...")
        
        frames = []
        start = time.time()
        
        for i in range(100):
            img = sct.grab(monitor)
            frame = np.array(img)
            frames.append(frame)
        
        elapsed = time.time() - start
        fps = 100 / elapsed
        
        print(f"  ✓ Captured 100 frames in {elapsed:.2f}s")
        print(f"  ✓ Speed: {fps:.1f} FPS")
        print(f"  ✓ Frame shape: {frames[0].shape}")
        
        # Save a sample frame
        if PIL_AVAILABLE:
            sample = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
            sample_path = BASE_PATH / "sample_frame.png"
            sample.save(sample_path)
            print(f"  ✓ Sample saved: {sample_path}")
        
        return frames[0], monitor


def test_downsampling(frame):
    """Test downsampling to various resolutions."""
    if not CV2_AVAILABLE:
        print("❌ opencv not available for downsampling test")
        return
    
    print("\n" + "=" * 50)
    print("TEST: Downsampling Performance")
    print("=" * 50)
    
    # Convert BGRA to RGB
    if frame.shape[2] == 4:
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
    else:
        frame_rgb = frame
    
    resolutions = [
        (240, 160, "Native GBA"),
        (120, 80, "Half"),
        (60, 40, "Quarter"),
        (48, 32, "Tiny"),
    ]
    
    print(f"\nOriginal frame: {frame_rgb.shape}")
    
    for w, h, name in resolutions:
        start = time.time()
        
        for _ in range(1000):
            resized = cv2.resize(frame_rgb, (w, h), interpolation=cv2.INTER_AREA)
        
        elapsed = time.time() - start
        fps = 1000 / elapsed
        flat_size = w * h * 3
        
        print(f"  {name:12s} ({w}x{h}): {fps:.0f} FPS, {flat_size:,} values")
        
        # Save sample
        if PIL_AVAILABLE:
            img = Image.fromarray(resized)
            img.save(BASE_PATH / f"sample_{w}x{h}.png")


def test_grayscale(frame):
    """Test grayscale conversion."""
    if not CV2_AVAILABLE:
        return
    
    print("\n" + "=" * 50)
    print("TEST: Grayscale Conversion")
    print("=" * 50)
    
    # Convert to grayscale
    if frame.shape[2] == 4:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
    else:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    start = time.time()
    for _ in range(1000):
        if frame.shape[2] == 4:
            g = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
        else:
            g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(g, (60, 40))
    
    elapsed = time.time() - start
    print(f"  Grayscale 60x40: {1000/elapsed:.0f} FPS, {60*40:,} values")
    
    if PIL_AVAILABLE:
        img = Image.fromarray(cv2.resize(gray, (60, 40)))
        img.save(BASE_PATH / "sample_gray_60x40.png")


def test_feature_extraction(frame):
    """Test simple feature extraction."""
    if not CV2_AVAILABLE:
        return
    
    print("\n" + "=" * 50)
    print("TEST: Feature Extraction")
    print("=" * 50)
    
    if frame.shape[2] == 4:
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
    else:
        frame_rgb = frame
    
    def extract_features(img):
        """Extract compact features from frame."""
        features = []
        
        # Resize to GBA resolution first
        small = cv2.resize(img, (240, 160))
        
        # 1. Color histogram (simplified: 8 bins per channel)
        for c in range(3):
            hist = cv2.calcHist([small], [c], None, [8], [0, 256])
            features.extend(hist.flatten() / hist.sum())
        
        # 2. Grid-based color averages (4x4 grid = 16 regions × 3 colors)
        h, w = small.shape[:2]
        for i in range(4):
            for j in range(4):
                region = small[i*h//4:(i+1)*h//4, j*w//4:(j+1)*w//4]
                features.extend(region.mean(axis=(0, 1)) / 255.0)
        
        # 3. Edge density
        gray = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        features.append(edges.mean() / 255.0)
        
        return np.array(features)
    
    # Benchmark
    start = time.time()
    for _ in range(100):
        feat = extract_features(frame_rgb)
    elapsed = time.time() - start
    
    print(f"  Feature vector size: {len(feat)}")
    print(f"  Extraction speed: {100/elapsed:.0f} FPS")
    print(f"  Features: color_hist(24) + grid_colors(48) + edges(1) = {len(feat)}")


def interactive_window_finder():
    """Help user find RetroArch window coordinates."""
    if not MSS_AVAILABLE:
        return None
    
    print("\n" + "=" * 50)
    print("Interactive Window Finder")
    print("=" * 50)
    print("\nThis will help you find the exact RetroArch game area.")
    print("Move your mouse to the corners of the game and press Enter.")
    
    try:
        import pyautogui
        
        input("\n1. Move mouse to TOP-LEFT corner of game area, press Enter...")
        x1, y1 = pyautogui.position()
        print(f"   Got: ({x1}, {y1})")
        
        input("2. Move mouse to BOTTOM-RIGHT corner of game area, press Enter...")
        x2, y2 = pyautogui.position()
        print(f"   Got: ({x2}, {y2})")
        
        width = x2 - x1
        height = y2 - y1
        
        print(f"\n✓ Game region: left={x1}, top={y1}, width={width}, height={height}")
        
        return {"left": x1, "top": y1, "width": width, "height": height}
        
    except ImportError:
        print("pyautogui not available for mouse position")
        return None


def main():
    print("=" * 50)
    print("RetroArch Frame Capture Test")
    print("=" * 50)
    
    print("\nThis will test different frame capture methods.")
    print("Make sure RetroArch is running with the game visible.\n")
    
    # Check dependencies
    print("Dependencies:")
    print(f"  mss: {'✓' if MSS_AVAILABLE else '✗ pip3 install mss'}")
    print(f"  opencv: {'✓' if CV2_AVAILABLE else '✗ pip3 install opencv-python'}")
    print(f"  pillow: {'✓' if PIL_AVAILABLE else '✗ pip3 install pillow'}")
    
    if not MSS_AVAILABLE:
        print("\n❌ Need mss for screen capture. Install and retry.")
        return
    
    # Find window
    print("\n" + "-" * 50)
    resp = input("Use interactive window finder? (y/n): ")
    
    if resp.lower() == 'y':
        monitor = interactive_window_finder()
        if monitor:
            frame, _ = None, monitor
            with mss.mss() as sct:
                img = sct.grab(monitor)
                frame = np.array(img)
    else:
        result = test_mss_capture()
        if result:
            frame, monitor = result
        else:
            return
    
    if frame is None:
        print("No frame captured")
        return
    
    # Run other tests
    if CV2_AVAILABLE:
        test_downsampling(frame)
        test_grayscale(frame)
        test_feature_extraction(frame)
    
    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"\nRecommended capture region:")
    print(f"  {monitor}")
    print(f"\nSample images saved to: {BASE_PATH}")
    print("\nFor the AI, recommended options:")
    print("  1. 60x40 RGB = 7,200 values (good balance)")
    print("  2. 60x40 grayscale = 2,400 values (faster)")
    print("  3. Feature extraction = ~73 values (fastest)")


if __name__ == "__main__":
    main()