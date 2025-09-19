import pytest
from unittest.mock import patch
from biobeamer.sftpparamiko import copy_with_sftp_paramiko, copy_with_sftp_sub, noop_subprocess


@pytest.mark.parametrize("copy_func", [copy_with_sftp_paramiko, copy_with_sftp_sub])
def test_copy_with_sftp_works(copy_func):
    """Test that both SFTP copy functions work correctly"""
    if copy_func == copy_with_sftp_sub:
        # Use noop for subprocess function
        result = copy_func("/tmp/source.txt", "/tmp/target.txt", noop_subprocess)
        assert "sftp -b - localhost" in result
        assert 'put "/tmp/source.txt" "/tmp/target.txt"' in result
    else:
        # Mock SFTP manager methods for paramiko function
        with patch('biobeamer.sftpparamiko._sftp_manager.connect') as mock_connect, \
             patch('biobeamer.sftpparamiko._sftp_manager.mkdir_p') as mock_mkdir, \
             patch('biobeamer.sftpparamiko._sftp_manager.put_file') as mock_put:
            
            result = copy_func("/tmp/source.txt", "/tmp/target.txt")
            
            mock_connect.assert_called_once_with("/tmp/target.txt")
            mock_mkdir.assert_called_once_with("/tmp")
            mock_put.assert_called_once_with("/tmp/source.txt", "/tmp/target.txt")


@pytest.mark.parametrize("copy_func", [copy_with_sftp_paramiko, copy_with_sftp_sub])
def test_copy_with_sftp_fails_correctly(copy_func):
    """Test that both SFTP copy functions handle failures correctly"""
    if copy_func == copy_with_sftp_sub:
        # Mock subprocess.run to raise exception
        with patch('biobeamer.sftpparamiko.subprocess.run') as mock_subprocess:
            mock_subprocess.side_effect = Exception("Subprocess failed")
            
            with pytest.raises(Exception, match="Subprocess failed"):
                copy_func("/tmp/source.txt", "/tmp/target.txt", simulate=False, logger=None)
    else:
        # Mock SFTP manager to raise exception
        with patch('biobeamer.sftpparamiko._sftp_manager.connect') as mock_connect:
            mock_connect.side_effect = Exception("Connection failed")
            
            with pytest.raises(Exception, match="Connection failed"):
                copy_func("/tmp/source.txt", "/tmp/target.txt")


@pytest.mark.parametrize("copy_func", [copy_with_sftp_sub])
def test_copy_with_sftp_simulate(copy_func):
    """Test simulation mode (only applicable to subprocess function)"""
    result = copy_func("/tmp/source.txt", "/tmp/target.txt", noop_subprocess)
    
    # Should return command string without executing
    assert "sftp -b - localhost" in result
    assert 'put "/tmp/source.txt" "/tmp/target.txt"' in result