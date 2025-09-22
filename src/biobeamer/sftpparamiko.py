import os
import subprocess
from typing import Callable, Optional
import paramiko
from pathlib import PurePosixPath


class SFTPManager:
    """Manages SFTP connection and operations"""
    
    def __init__(self):
        self.client: Optional[paramiko.SSHClient] = None
        self.sftp: Optional[paramiko.SFTPClient] = None
        self.current_host = None
        self.current_username = None
    
    def connect(self, target: str):
        """Connect to SFTP server if not already connected"""
        if ":" not in target:
            # Local target - no connection needed
            return
            
        host_part, _ = target.split(":", 1)
        
        # Parse username from host_part if present
        if "@" in host_part:
            username, hostname = host_part.split("@", 1)
        else:
            username = None
            hostname = host_part
        
        # Check if already connected to the same host
        if (self.client and self.current_host == hostname and 
            self.current_username == username):
            return  # Already connected
        
        # Close existing connection if different host
        self.close()
        
        # Create new connection
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        if username:
            self.client.connect(hostname, username=username)
        else:
            self.client.connect(hostname)
        
        self.sftp = self.client.open_sftp()
        self.current_host = hostname
        self.current_username = username
    
    def mkdir_p(self, remote_directory: str) -> str:
        """Recursively create remote directories like `mkdir -p`."""
        if not self.sftp:
            return f"sftpparamiko.mkdir_p: {remote_directory} (local)"
            
        path = PurePosixPath(remote_directory)
        cur = PurePosixPath(path.root)  # usually "/"

        for part in path.parts:
            cur = cur / part
            try:
                self.sftp.stat(str(cur))  # Check if directory exists
            except IOError:  # If directory doesn't exist (stat fails)
                self.sftp.mkdir(str(cur))  # Create the directory
        
        return f"sftpparamiko.mkdir_p: {str(path)}"
    
    def put_file(self, source: str, remote_path: str):
        """Upload file via SFTP"""
        if not self.sftp:
            raise RuntimeError("Not connected to SFTP server")
        self.sftp.put(source, remote_path)
    
    def files_are_same(self, local_file: str, remote_path: str) -> bool:
        """Check if local and remote files have same size"""
        if not self.sftp:
            raise RuntimeError("Not connected to SFTP server")
            
        try:
            remote_stat = self.sftp.stat(remote_path)
        except IOError:
            # Remote file doesn't exist
            return False
            
        local_stat = os.stat(local_file)
        return remote_stat.st_size == local_stat.st_size
    
    def close(self):
        """Close SFTP and SSH connections"""
        if self.sftp:
            self.sftp.close()
            self.sftp = None
        if self.client:
            self.client.close()
            self.client = None
        self.current_host = None
        self.current_username = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Global SFTP manager instance
_sftp_manager = SFTPManager()


def mkdir_p(remote_directory: str, sftp: paramiko.SFTPClient) -> None:
    """Legacy function - recursively create remote directories like `mkdir -p`."""
    path = PurePosixPath(remote_directory)
    cur = PurePosixPath(path.root)  # usually "/"

    for part in path.parts:
        cur = cur / part
        try:
            sftp.stat(str(cur)) # Check if directory exists
        except IOError: # If directory doesn't exist (stat fails)
            sftp.mkdir(str(cur)) # Create the directory
    
    return f"sftpparamiko.mkdir_p: {str(path)}"



def copy_with_sftp_paramiko(source: str, target: str, simulate: bool = False, logger = None) -> str:
    """Copy file using managed SFTP connection"""
    if ":" in target:
        _, remote_path = target.split(":", 1)
        remote_dir = os.path.dirname(remote_path)
        sftp_target = target
    else:
        # Local target - use localhost SFTP
        remote_path = target
        remote_dir = os.path.dirname(target)
        sftp_target = f"localhost:{target}"
        
    if not simulate:
        _sftp_manager.connect(sftp_target)
        mkdir_cmd = _sftp_manager.mkdir_p(remote_dir)
        _sftp_manager.put_file(source, remote_path)
    else:
        mkdir_cmd = f"sftpparamiko.mkdir_p: {remote_dir}"
        
    copy_cmd = f"sftpparamiko.put({source}, {remote_path})"
    return f"{mkdir_cmd}\n\n{copy_cmd}"



def files_are_same_sftp(local_file, remote_target):
    """Check if local file and remote SFTP file are the same using managed connection"""
    if ":" not in remote_target:
        # Local target - use existing method  
        return os.path.exists(remote_target) and os.path.getsize(local_file) == os.path.getsize(remote_target)
    
    _, remote_path = remote_target.split(":", 1)
    
    _sftp_manager.connect(remote_target)
    return _sftp_manager.files_are_same(local_file, remote_path)



def compare_files_destination_sftp(source_result_mapping, logger):
    """
    :param source_result_mapping:
    :return: map with fields "copied" and "not_copied"
    """
    copied = {}
    not_copied = {}
    for file_to_copy, target_file in source_result_mapping.items():
        if not target_file is None:
            print(target_file + "\n")
            # Check if files are the same (handles both local and remote SFTP)
            if files_are_same_sftp(file_to_copy, target_file):
                copied[file_to_copy] = target_file
                logger.debug(
                    "not copying {file} for {reasons}".format(file=file_to_copy, reasons=" already copied to : " + target_file)
                )
            else:
                not_copied[file_to_copy] = target_file
    return {"copied": copied, "not_copied": not_copied}



def noop_subprocess(*args, **kwargs):
    """Mock subprocess that does nothing"""
    pass



def mkdir_p_sub(remote_directory: str, host: str, 
                subprocess_fn: Callable = subprocess.run, logger = None) -> str:
    """Emulate `mkdir -p` using sftp -b - (ignore errors with -mkdir)."""
    path = PurePosixPath(remote_directory)
    cur = PurePosixPath(path.root)

    batch_lines = []
    for part in path.parts:
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
                       simulate: bool = False, logger = None) -> str:

    if simulate:
        subprocess_fn = noop_subprocess
    else:
        subprocess_fn: Callable = subprocess.run
        
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