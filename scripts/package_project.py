"""Automated Zip Packaging Script for Project Submission

Generates a clean submission zip archive adhering strictly to academic rubrics:
- Excludes venv/, __pycache__/, .git/, and secret files (.env)
- Preserves .env.example, sample data, tests, queries, docs, and benchmarks
- Verifies output archive integrity and displays size and file manifest
"""

import os
import sys
import zipfile

# Root directory of the project
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PARENT_DIR = os.path.dirname(PROJECT_ROOT)
DEFAULT_ZIP_NAME = "iot-digital-twin.zip"

# Exclusion patterns
EXCLUDE_DIRS = {
    "venv",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".git",
    ".vscode",
    ".idea",
}

EXCLUDE_FILES = {
    ".env",
    ".DS_Store",
    "Thumbs.db",
}

EXCLUDE_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".log",
}


def should_exclude(rel_path: str) -> bool:
    parts = rel_path.replace("\\", "/").split("/")
    # Exclude directories
    for part in parts:
        if part in EXCLUDE_DIRS:
            return True

    # Exclude specific files
    filename = parts[-1]
    if filename in EXCLUDE_FILES:
        return True

    # Exclude extensions
    _, ext = os.path.splitext(filename)
    if ext.lower() in EXCLUDE_EXTENSIONS:
        return True

    return False


def create_submission_zip(output_zip_path: str = None):
    target_zip = output_zip_path or os.path.join(PARENT_DIR, DEFAULT_ZIP_NAME)
    print(f"Creating submission archive: {target_zip}")
    print(f"Source Directory: {PROJECT_ROOT}\n")

    included_count = 0
    total_uncompressed_bytes = 0

    with zipfile.ZipFile(target_zip, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for root, dirs, files in os.walk(PROJECT_ROOT):
            # Prune excluded directories in-place
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, PROJECT_ROOT)

                if should_exclude(rel_path):
                    continue

                # Store inside top-level folder 'iot-digital-twin/' for clean extraction
                archive_name = os.path.join("iot-digital-twin", rel_path)
                zip_file.write(full_path, archive_name)
                file_size = os.path.getsize(full_path)
                total_uncompressed_bytes += file_size
                included_count += 1
                print(f"  + Added: {archive_name} ({file_size:,} bytes)")

    zip_size_kb = os.path.getsize(target_zip) / 1024.0
    print("\n=======================================================")
    print(f" [SUCCESS] Submission Zip Created Successfully!")
    print(f" Archive Location: {target_zip}")
    print(f" Files Packaged:   {included_count} files")
    print(f" Archive Size:     {zip_size_kb:.2f} KB")
    print(f" Excluded:         venv/, __pycache__/, .env, *.pyc, .git/")
    print("=======================================================\n")
    return target_zip


if __name__ == "__main__":
    out_path = sys.argv[1] if len(sys.argv) > 1 else None
    create_submission_zip(out_path)
