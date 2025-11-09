#!/usr/bin/env python3
"""
Generate Content Manager-compatible car packs for ac-server-wrapper.

This script creates car pack zip files and generates a content.json manifest
that ac-server-wrapper can serve to Content Manager clients. The wrapper will
serve these files from the cm_content directory, allowing clients to download
car packs directly from the server.

Usage:
    python generate_cm_pack.py <car_dir> --output <output_dir>
    
Example:
    python generate_cm_pack.py ./cars/ks_audi_r8_lms --output ./cm_content/cars
"""

import argparse
import json
import os
import zipfile
from pathlib import Path
from typing import Dict, List


def calculate_directory_size(directory: Path) -> int:
    """Calculate total size of a directory in bytes."""
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(directory):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            if os.path.isfile(filepath):
                total_size += os.path.getsize(filepath)
    return total_size


def create_car_zip(car_dir: Path, output_dir: Path) -> Dict[str, any]:
    """
    Create a zip file for a car directory.
    
    Args:
        car_dir: Path to the car directory
        output_dir: Path to the output directory for the zip file
        
    Returns:
        Dictionary with car pack metadata
    """
    car_name = car_dir.name
    zip_filename = f"{car_name}.zip"
    zip_path = output_dir / zip_filename
    
    print(f"Creating zip file for {car_name}...")
    
    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create zip file
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(car_dir):
            for file in files:
                file_path = Path(root) / file
                # Store with relative path from car directory
                arcname = str(file_path.relative_to(car_dir.parent))
                zipf.write(file_path, arcname)
    
    # Get file size
    file_size = os.path.getsize(zip_path)
    
    # Try to read car metadata from ui_car.json
    ui_car_json = car_dir / "ui" / "ui_car.json"
    car_metadata = {
        "name": car_name,
        "brand": "",
        "description": "",
    }
    
    if ui_car_json.exists():
        try:
            with open(ui_car_json, 'r', encoding='utf-8') as f:
                ui_data = json.load(f)
                car_metadata["brand"] = ui_data.get("brand", "")
                car_metadata["name"] = ui_data.get("name", car_name)
                car_metadata["description"] = ui_data.get("description", "")
        except Exception as e:
            print(f"Warning: Could not read ui_car.json: {e}")
    
    return {
        "id": car_name,
        "name": car_metadata["name"],
        "brand": car_metadata["brand"],
        "description": car_metadata["description"],
        "url": f"/cm_content/cars/{zip_filename}",
        "size": file_size,
        "type": "car"
    }


def generate_content_json(pack_entries: List[Dict], output_path: Path) -> None:
    """
    Generate content.json file for ac-server-wrapper.
    
    Args:
        pack_entries: List of pack metadata dictionaries
        output_path: Path to save content.json
    """
    content = {
        "version": "1.0",
        "content": pack_entries
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(content, f, indent=2, ensure_ascii=False)
    
    print(f"\nGenerated content.json at {output_path}")
    print(f"Total packs: {len(pack_entries)}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate Content Manager-compatible car packs for ac-server-wrapper"
    )
    parser.add_argument(
        "car_dir",
        type=Path,
        help="Path to car directory (or parent directory containing multiple cars)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("./cm_content/cars"),
        help="Output directory for car pack zips (default: ./cm_content/cars)",
    )
    parser.add_argument(
        "--content-json",
        "-c",
        type=Path,
        default=Path("./cm_content/content.json"),
        help="Path for content.json output (default: ./cm_content/content.json)",
    )
    parser.add_argument(
        "--batch",
        "-b",
        action="store_true",
        help="Process all subdirectories as individual cars",
    )
    
    args = parser.parse_args()
    
    if not args.car_dir.exists():
        print(f"Error: Directory {args.car_dir} does not exist")
        return 1
    
    pack_entries = []
    
    if args.batch:
        # Process all subdirectories
        print(f"Processing all subdirectories in {args.car_dir}...")
        for subdir in args.car_dir.iterdir():
            if subdir.is_dir():
                try:
                    entry = create_car_zip(subdir, args.output)
                    pack_entries.append(entry)
                except Exception as e:
                    print(f"Error processing {subdir.name}: {e}")
    else:
        # Process single directory
        try:
            entry = create_car_zip(args.car_dir, args.output)
            pack_entries.append(entry)
        except Exception as e:
            print(f"Error processing {args.car_dir.name}: {e}")
            return 1
    
    if pack_entries:
        # Ensure content.json parent directory exists
        args.content_json.parent.mkdir(parents=True, exist_ok=True)
        
        # Generate content.json
        generate_content_json(pack_entries, args.content_json)
        print("\n✓ Car pack generation complete!")
        print(f"\nNext steps:")
        print(f"1. Copy the contents of {args.output.parent} to your server preset's cm_content directory")
        print(f"2. Deploy the server with ac-server-manager")
        print(f"3. Content Manager clients will be able to download cars from the server")
    else:
        print("No car packs were generated")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
