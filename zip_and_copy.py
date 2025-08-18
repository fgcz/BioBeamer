# Dowload zip utility from:
# https://sourceforge.net/projects/gnuwin32/files/zip/3.0/
#!/usr/bin/env python3
import sys, re, subprocess, argparse
from datetime import datetime
from pathlib import Path

# Configuration
DEFAULT_DATA_PATH = r"D:\Data2San"

def fail(msg: str, code: int = 1):
    print(msg, file=sys.stderr)
    sys.exit(code)

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description="Zip and copy folder to Data2San directory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python zip_and_copy.py "C:\\path\\to\\folder"
  python zip_and_copy.py --data-path "E:\\Data2San" "C:\\path\\to\\folder"
  python zip_and_copy.py --username "john" "C:\\path\\to\\folder"
        """
    )
    
    parser.add_argument(
        "folder",
        nargs="?",
        help="Path to folder to zip and copy (can also be provided via drag&drop)"
    )
    
    parser.add_argument(
        "--data-path",
        default=DEFAULT_DATA_PATH,
        help=f"Base data path (default: {DEFAULT_DATA_PATH})"
    )
    
    parser.add_argument(
        "--username",
        default="analytics",
        help="Username for the destination folder (default: analytics)"
    )
    
    parser.add_argument(
        "--no-prompt",
        action="store_true",
        help="Skip username prompt and use default"
    )
    
    args = parser.parse_args()
    
    # Accept drag&drop path or prompt if not provided as argument
    folder = args.folder
    if not folder:
        fail("No folder provided.")

    folder = Path(folder).resolve()
    if not folder.is_dir():
        fail(f"Not a folder: {folder}")

    parent = folder.parent
    foldername = folder.name

    # Expect: pNNNNN_oNNNNN_<suffix...>
    m = re.match(r'^(?P<p>p\d+?)_(?P<o>o\d+?)_(?P<suffix>.+)$', foldername)
    if not m:
        fail(f'Folder name must match: pNNNNN_oNNNNN_<suffix...>\nGot: {foldername}')

    o_part  = m.group("o")          # e.g. o38561
    p_id    = "p" + o_part[1:]      # -> p38561
    suffix  = m.group("suffix")     # full suffix

    # Username prompt (unless --no-prompt is used)
    username = args.username
    if not args.no_prompt:
        try:
            user_input = input(f"Enter username (default '{username}'): ").strip()
            if user_input:
                username = user_input
        except EOFError:
            pass

    now = datetime.now()
    ymd = now.strftime("%Y%m%d")
    hms = now.strftime("%H%M%S")

    # Use the configurable data path
    data_path = Path(args.data_path).expanduser()
    dest = data_path / p_id / "Metabolomics" / "Analysis" / "CompoundDiscoV1" / f"{username}_{ymd}_{suffix}_{hms}"
    
    try:
        dest.mkdir(parents=True, exist_ok=True)
        # Verify the directory was actually created
        if not dest.is_dir():
            fail(f"Failed to create destination directory: {dest}")
    except Exception as e:
        fail(f"Error creating destination directory {dest}: {e}")

    zip_path = parent / f"{foldername}.zip"
    if zip_path.exists():
        try:
            zip_path.unlink()
        except Exception as e:
            fail(f"Cannot overwrite existing zip: {zip_path}\n{e}")

    print(f"Running zip: {folder} -> {zip_path}")
    try:
        subprocess.run(
            ["zip", "-0", "-r", str(zip_path), foldername],
            cwd=parent,
            check=True
        )
    except subprocess.CalledProcessError as e:
        fail(f"zip command failed with exit code {e.returncode}")

    try:
        # Copy the zip file to destination
        dest_file = dest / zip_path.name
        zip_path.copy(dest_file)
        zip_path.unlink()  # Delete the original
    except Exception as e:
        fail(f"Copy failed to {dest}: {e}")

    print("\nDone.")
    print(f"Zipped: {zip_path}")
    print(f"Copied to: {dest}")
    
if __name__ == "__main__":
    main()
