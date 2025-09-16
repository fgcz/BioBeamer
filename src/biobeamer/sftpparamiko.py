import os
import subprocess
from typing import Callable
import paramiko
from pathlib import PurePosixPath

def mkdir_p(remote_directory: str, sftp: paramiko.SFTPClient) -> None:
    """Recursively create remote directories like `mkdir -p`."""
    path = PurePosixPath(remote_directory)
    cur = PurePosixPath(path.root)  # usually "/"

    for part in path.parts[1:]:
        cur = cur / part
        try:
            sftp.stat(str(cur))
        except IOError:
            sftp.mkdir(str(cur))



def copy_with_sftp_paramiko(source: str, target: str):
    if ":" in target:
        host_part, remote_path = target.split(":", 1)
        remote_dir = os.path.dirname(remote_path)
        
    else:
        # Local target - create directory locally then use sftp to localhost
        host_part = "localhost"
        remote_path = target
        remote_dir = os.path.dirname(target)
        

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host_part)  # add password=... if needed

    sftp = client.open_sftp()
    mkdir_p(remote_dir, sftp)

    # Upload a file
    sftp.put(source, remote_path)

    sftp.close()
    client.close()


def noop_subprocess(*args, **kwargs):
    """Mock subprocess that does nothing"""
    pass



def mkdir_p_sub(remote_directory: str, host: str, 
                subprocess_fn: Callable = subprocess.run, logger = None) -> str:
    """Emulate `mkdir -p` using sftp -b - (ignore errors with -mkdir)."""
    path = PurePosixPath(remote_directory)
    cur = PurePosixPath(path.root)

    batch_lines = []
    for part in path.parts[1:]:
        cur = cur / part
        batch_lines.append(f'-mkdir "{cur}"')
    batch_lines.append("quit")

    batch = "\n".join(batch_lines) + "\n"
    if logger is not None:
        logger.info(f"Running Command: [{batch}]")
    
    cmd_str = f"sftp -b - {host} << 'EOF'\n{batch.rstrip()}\nEOF"
    
    subprocess_fn(
        ["sftp", "-b", "-", host],
        input=batch.encode(),
        check=True,
    )
    
    return cmd_str

def copy_with_sftp_sub(source: str, target: str, 
                       subprocess_fn: Callable = subprocess.run, logger = None) -> str:
    if ":" in target:
        host_part, remote_path = target.split(":", 1)
        remote_dir = os.path.dirname(remote_path)
    else:
        host_part = "localhost"
        remote_path = target
        remote_dir = os.path.dirname(target)

    mkdir_cmd = mkdir_p_sub(remote_dir, host_part, subprocess_fn, logger)
    
    batch = f'put "{source}" "{remote_path}"\nquit\n'
    copy_cmd = f"sftp -b - {host_part} << 'EOF'\n{batch.rstrip()}\nEOF"
    
    if logger is not None:
        logger.info(f"Running Command: [{batch}]")


    subprocess_fn(
        ["sftp", "-b", "-", host_part],
        input=batch.encode(),
        check=True,
    )
    
    return f"{mkdir_cmd}\n\n{copy_cmd}"


# Example usage
if __name__ == "__main__":
    copy_with_sftp_paramiko("/tmp/source_file.txt", "/tmp/hello/world/wolski/dest_file.txt")
    copy_with_sftp_sub("/tmp/source_file.txt", "/tmp/hello/world/wolski/dest_file.txt")