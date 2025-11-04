#!/usr/bin/env python3
"""
Simple PCK inspector - reads the file table from a Godot PCK file
"""

import struct
import sys

def read_pck_info(pck_path):
    """Read and display PCK file information"""
    with open(pck_path, 'rb') as f:
        # Read header
        magic = f.read(4)
        if magic != b'GDPC':
            print(f"Error: Not a valid PCK file (magic: {magic})")
            return
        
        print(f"✓ Valid Godot PCK file")
        print(f"Magic: {magic.decode('ascii')}")
        
        # Read version info
        format_version = struct.unpack('<I', f.read(4))[0]
        godot_major = struct.unpack('<I', f.read(4))[0]
        godot_minor = struct.unpack('<I', f.read(4))[0]
        godot_patch = struct.unpack('<I', f.read(4))[0]
        
        print(f"PCK Format Version: {format_version}")
        print(f"Godot Version: {godot_major}.{godot_minor}.{godot_patch}")
        
        # Read flags and file_base
        flags = struct.unpack('<I', f.read(4))[0]
        file_base = struct.unpack('<Q', f.read(8))[0]
        
        print(f"Flags: {flags}")
        print(f"File Base: 0x{file_base:x}")
        
        # Skip reserved bytes (adjust for what we already read)
        f.read(44)  # Remaining reserved space
        
        # Read file count
        file_count = struct.unpack('<I', f.read(4))[0]
        print(f"\n📦 Files in PCK: {file_count}\n")
        
        # If file_count is 0, the index might be at the end
        if file_count == 0:
            print("File count is 0, checking if index is at EOF...")
            # Jump to near the end to find index
            f.seek(-8, 2)
            potential_count = struct.unpack('<Q', f.read(8))[0]
            if potential_count > 0 and potential_count < 1000:
                file_count = potential_count
                print(f"Found file count at EOF: {file_count}")
        
        # Read file entries
        for i in range(min(file_count, 50)):  # Limit to 50 for safety
            try:
                # Read path length
                path_len = struct.unpack('<I', f.read(4))[0]
                if path_len > 1000:  # Sanity check
                    print(f"Warning: Unusual path length: {path_len}")
                    break
                # Read path
                path = f.read(path_len).decode('utf-8', errors='ignore')
                # Read offset and size
                offset = struct.unpack('<Q', f.read(8))[0]
                size = struct.unpack('<Q', f.read(8))[0]
                # Read MD5
                md5 = f.read(16)
                # Read flags
                entry_flags = struct.unpack('<I', f.read(4))[0]
                
                print(f"  {i+1}. {path}")
                print(f"     Size: {size} bytes, Offset: 0x{offset:x}")
                
                # Check if it's a scene file
                if path.endswith('.tscn'):
                    print(f"     ⭐ SCENE FILE")
                elif path.endswith('.tres'):
                    print(f"     📄 RESOURCE")
                elif path.endswith('.gd'):
                    print(f"     📜 SCRIPT")
                print()
            except Exception as e:
                print(f"Error reading entry {i}: {e}")
                break

if __name__ == "__main__":
    pck_file = sys.argv[1] if len(sys.argv) > 1 else "characters/player-robin-hood.pck"
    print(f"Inspecting: {pck_file}\n")
    read_pck_info(pck_file)
