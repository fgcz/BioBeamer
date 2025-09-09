import pytest
from unittest.mock import patch
from biobeamer.sftpparamiko import copy_with_sftp_paramiko, copy_with_sftp_sub, noop_subprocess


@pytest.mark.parametrize("copy_func", [copy_with_sftp_paramiko, copy_with_sftp_sub])
@patch('biobeamer.sftpparamiko.paramiko.SSHClient')
def test_copy_with_sftp_works(mock_ssh_class, copy_func):
    """Test that both SFTP copy functions work correctly"""
    # Setup mocks for paramiko function
    mock_client = mock_ssh_class.return_value
    mock_sftp = mock_client.open_sftp.return_value
    
    if copy_func == copy_with_sftp_sub:
        # Use noop for subprocess function
        result = copy_func("/tmp/source.txt", "/tmp/target.txt", noop_subprocess)
        assert "sftp -b - localhost" in result
        assert 'put "/tmp/source.txt" "/tmp/target.txt"' in result
    else:
        # Test paramiko function
        copy_func("/tmp/source.txt", "/tmp/target.txt")
        mock_client.connect.assert_called_once_with("localhost")
        mock_sftp.put.assert_called_once_with("/tmp/source.txt", "/tmp/target.txt")


@pytest.mark.parametrize("copy_func", [copy_with_sftp_paramiko, copy_with_sftp_sub])
@patch('biobeamer.sftpparamiko.paramiko.SSHClient')
def test_copy_with_sftp_fails_correctly(mock_ssh_class, copy_func):
    """Test that both SFTP copy functions handle failures correctly"""
    if copy_func == copy_with_sftp_sub:
        # Mock subprocess to raise exception
        def failing_subprocess(*args, **kwargs):
            raise Exception("Subprocess failed")
        
        with pytest.raises(Exception, match="Subprocess failed"):
            copy_func("/tmp/source.txt", "/tmp/target.txt", failing_subprocess)
    else:
        # Mock paramiko to raise exception
        mock_ssh_class.return_value.connect.side_effect = Exception("Connection failed")
        
        with pytest.raises(Exception, match="Connection failed"):
            copy_func("/tmp/source.txt", "/tmp/target.txt")


@pytest.mark.parametrize("copy_func", [copy_with_sftp_sub])
def test_copy_with_sftp_simulate(copy_func):
    """Test simulation mode (only applicable to subprocess function)"""
    result = copy_func("/tmp/source.txt", "/tmp/target.txt", noop_subprocess)
    
    # Should return command string without executing
    assert "sftp -b - localhost" in result
    assert 'put "/tmp/source.txt" "/tmp/target.txt"' in result