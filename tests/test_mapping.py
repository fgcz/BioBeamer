import pytest
from unittest import mock

from biobeamer import mapping


def test_map_data_for_container_success():
    """Test map_data_for_container function with valid QEXACTIVE paths."""
    logger = mock.Mock()
    
    # Test data from your debugging session
    test_cases = [
        {
            'input': r'\\fgcz-biobeamer.uzh.ch\Data2San\orders\Proteomics\QEXACTIVE_1\analytic_20250923\20250923_001_C39861_autoQC01.raw',
            'expected': r'\\fgcz-biobeamer.uzh.ch\Data2San\p39861\Proteomics\QEXACTIVE_1\analytic_20250923\20250923_001_C39861_autoQC01.raw'
        },
        {
            'input': '\\\\fgcz-biobeamer.uzh.ch\\Data2San\\orders\\Proteomics\\QEXACTIVE_1\\analytic_20250923\\20250923_002_C39861_S1020786_CDC25C-1.raw',
            'expected': '\\\\fgcz-biobeamer.uzh.ch\\Data2San\\p39861\\Proteomics\\QEXACTIVE_1\\analytic_20250923\\20250923_002_C39861_S1020786_CDC25C-1.raw'
        }
    ]
    
    for case in test_cases:
        result = mapping.map_data_for_container(case['input'], logger)
        assert result == case['expected'], f"Failed for input: {case['input']}\nExpected: {case['expected']}\nGot: {result}"


def test_map_data_for_container_no_match():
    """Test map_data_for_container function with paths that don't match the pattern."""
    logger = mock.Mock()
    
    # Test paths that don't match the regex pattern
    test_cases = [
        '\\\\fgcz-biobeamer.uzh.ch\\Data2San\\p39861\\Proteomics\\QEXACTIVE_1\\analytic_20250923\\file.raw',  # already has p39861 instead of orders
        '\\\\different-server.com\\Data2San\\orders\\Proteomics\\QEXACTIVE_1\\analytic_20250923\\20250923_001_C39861_file.raw',  # different server
        '\\\\fgcz-biobeamer.uzh.ch\\Data2San\\orders\\Proteomics\\QEXACTIVE_1\\analytic_20250923\\20250923_001_invalid_file.raw',  # no container ID pattern
        'local_path\\file.raw'  # local path, not UNC
    ]
    
    for input_path in test_cases:
        result = mapping.map_data_for_container(input_path, logger)
        # For non-matching paths, the function should return the original path unchanged
        assert result == input_path, f"Expected unchanged path for non-matching input: {input_path}, got: {result}"


def test_map_data_for_container_different_containers():
    """Test map_data_for_container function with different container IDs."""
    logger = mock.Mock()
    
    test_cases = [
        {
            'input': '\\\\fgcz-biobeamer.uzh.ch\\Data2San\\orders\\Proteomics\\QEXACTIVE_1\\analytic_20250923\\20250923_001_C12345_test.raw',
            'expected': '\\\\fgcz-biobeamer.uzh.ch\\Data2San\\p12345\\Proteomics\\QEXACTIVE_1\\analytic_20250923\\20250923_001_C12345_test.raw'
        },
        {
            'input': '\\\\fgcz-biobeamer.uzh.ch\\Data2San\\orders\\Metabolomics\\QEXACTIVE_2\\analytic_20250924\\20250924_002_C987654_sample.raw',
            'expected': '\\\\fgcz-biobeamer.uzh.ch\\Data2San\\p987654\\Metabolomics\\QEXACTIVE_2\\analytic_20250924\\20250924_002_C987654_sample.raw'
        }
    ]
    
    for case in test_cases:
        result = mapping.map_data_for_container(case['input'], logger)
        assert result == case['expected'], f"Failed for input: {case['input']}\nExpected: {case['expected']}\nGot: {result}"


def test_map_data_for_container_edge_cases():
    """Test map_data_for_container function with edge cases."""
    logger = mock.Mock()
    
    # Test with minimum and maximum container ID lengths based on regex pattern
    test_cases = [
        {
            'input': '\\\\fgcz-biobeamer.uzh.ch\\Data2San\\orders\\Proteomics\\QEXACTIVE_1\\analytic_20250923\\20250923_001_C123_test.raw',
            'expected': '\\\\fgcz-biobeamer.uzh.ch\\Data2San\\p123\\Proteomics\\QEXACTIVE_1\\analytic_20250923\\20250923_001_C123_test.raw'
        },
        {
            'input': '\\\\fgcz-biobeamer.uzh.ch\\Data2San\\orders\\Proteomics\\QEXACTIVE_1\\analytic_20250923\\20250923_001_C123456_test.raw',
            'expected': '\\\\fgcz-biobeamer.uzh.ch\\Data2San\\p123456\\Proteomics\\QEXACTIVE_1\\analytic_20250923\\20250923_001_C123456_test.raw'
        }
    ]
    
    for case in test_cases:
        result = mapping.map_data_for_container(case['input'], logger)
        assert result == case['expected'], f"Failed for input: {case['input']}\nExpected: {case['expected']}\nGot: {result}"
