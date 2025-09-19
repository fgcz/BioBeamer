import os
import random
import string
import argparse
from pathlib import Path

def generate_random_string(pattern):
    """Generate a random string based on pattern specifications"""
    if pattern == "[A-Z]{5-6}":
        length = random.randint(5, 6)
        return ''.join(random.choices(string.ascii_uppercase, k=length))
    elif pattern == "[1-9]{1,1}":
        return str(random.randint(1, 9))
    elif pattern == "[a-z]{3,9}":
        length = random.randint(3, 9)
        return ''.join(random.choices(string.ascii_lowercase, k=length))
    elif pattern == "[0-9]{8,8}":
        return ''.join(random.choices(string.digits, k=8))
    elif pattern == "[0-9a-zA-Z]{3-15}":
        length = random.randint(3, 15)
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))
    elif pattern == "[0-9]{6,6}":
        return ''.join(random.choices(string.digits, k=6))
    elif pattern == "[0-9]{3,3}":
        return ''.join(random.choices(string.digits, k=3))
    elif pattern == "[a-z]{3,10}":
        length = random.randint(3, 10)
        return ''.join(random.choices(string.ascii_lowercase, k=length))

def generate_project_id():
    """Generate p + 6 digits"""
    return f"p{generate_random_string('[0-9]{6,6}')}"

def generate_analysis_type():
    """Generate either Metabolomics or Proteomics"""
    return random.choice(["Metabolomics", "Proteomics"])

def generate_instrument():
    """Generate instrument type: EXPLORIS_5, ASTRAL_1, or LUMOS_3"""
    return random.choice(["EXPLORIS_5", "ASTRAL_1", "LUMOS_3"])

def generate_user_prefix():
    """Generate user prefix: wolski, grossmann, cpanse, dummy, or analytics"""
    return random.choice(["wolski", "grossmann", "cpanse", "dummy", "analytics"])

def generate_experiment_id():
    """Generate experiment ID: [user]_*[0-9]{8,8}_[0-9a-zA-Z]{3-15}"""
    user_prefix = generate_user_prefix()
    # The "*" in the pattern suggests a wildcard - using a random separator
    part1 = generate_random_string("[0-9]{8,8}")
    part2 = generate_random_string("[0-9a-zA-Z]{3-15}")
    return f"{user_prefix}_{part1}_{part2}"

def generate_filename():
    """Generate filename: [0-9]{8,8}_[0-9]{3,3}_[a-z]{3,10}.raw"""
    part1 = generate_random_string("[0-9]{8,8}")
    part2 = generate_random_string("[0-9]{3,3}")
    part3 = generate_random_string("[a-z]{3,10}")
    return f"{part1}_{part2}_{part3}.raw"

def get_existing_paths(base_dir):
    """Get all existing directory paths to avoid duplicates"""
    existing_paths = set()
    if os.path.exists(base_dir):
        for root, dirs, files in os.walk(base_dir):
            # Convert to relative path from base_dir
            rel_path = os.path.relpath(root, base_dir)
            if rel_path != '.':
                existing_paths.add(rel_path)
    return existing_paths

def create_directory_structure(base_dir, num_directories):
    """Create the specified directory structure with files"""
    base_path = Path(base_dir)
    base_path.mkdir(exist_ok=True)
    
    existing_paths = get_existing_paths(base_dir)
    created_dirs = []
    
    attempts = 0
    max_attempts = num_directories * 10  # Avoid infinite loops
    
    while len(created_dirs) < num_directories and attempts < max_attempts:
        attempts += 1
        
        # Generate directory path components
        project_id = generate_project_id()
        analysis_type = generate_analysis_type()
        instrument = generate_instrument()
        experiment_id = generate_experiment_id()
        
        # Create full directory path
        dir_path = f"{project_id}/{analysis_type}/{instrument}/{experiment_id}"
        
        # Check if this path already exists
        if dir_path in existing_paths or dir_path in [d[0] for d in created_dirs]:
            continue
            
        # Create the directory
        full_dir_path = base_path / dir_path
        full_dir_path.mkdir(parents=True, exist_ok=True)
        
        # Generate random number of files (3-10)
        num_files = random.randint(3, 10)
        file_names = set()
        
        # Create files in the directory
        for _ in range(num_files):
            file_attempts = 0
            while file_attempts < 50:  # Avoid infinite loop for file generation
                filename = generate_filename()
                if filename not in file_names:
                    file_names.add(filename)
                    file_path = full_dir_path / filename
                    file_path.touch()  # Create empty file
                    break
                file_attempts += 1
        
        created_dirs.append((dir_path, num_files))
        print(f"Created: {dir_path} with {num_files} files")
    
    if attempts >= max_attempts and len(created_dirs) < num_directories:
        print(f"Warning: Could only create {len(created_dirs)} unique directories out of {num_directories} requested")
        print("This might indicate that you need to increase the randomness ranges or clear existing directories")
    
    return created_dirs

def main():
    parser = argparse.ArgumentParser(description='Create directory structure with specified pattern')
    parser.add_argument('num_dirs', type=int, help='Number of directories to create')
    parser.add_argument('--base-dir', default='/Users/witoldwolski/Data2San', 
                       help='Base directory to create structure in (default: /Users/witoldwolski/Data2San)')
    
    args = parser.parse_args()
    
    if args.num_dirs <= 0:
        print("Error: Number of directories must be positive")
        return
    
    print(f"Creating {args.num_dirs} directories in '{args.base_dir}'...")
    created = create_directory_structure(args.base_dir, args.num_dirs)
    print(f"Successfully created {len(created)} directories")

if __name__ == "__main__":
    main()