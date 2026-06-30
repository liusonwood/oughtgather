import pytest
from unittest.mock import MagicMock, patch
from src.main import main

@patch("src.main.load_config")
@patch("src.main.DedupTracker")
@patch("src.main.get_fetcher")
@patch("src.main.process_results")
@patch("src.main.has_new_content")
@patch("src.main.EPUBGenerator")
@patch("src.main.SMTPSender")
@patch("src.main.get_logger")
def test_main_no_new_content(
    mock_get_logger,
    mock_sender,
    mock_generator,
    mock_has_new,
    mock_process,
    mock_fetcher,
    mock_tracker,
    mock_load_config
):
    # Setup
    mock_logger = MagicMock()
    mock_get_logger.return_value = mock_logger
    mock_config = MagicMock()
    mock_config.body = [MagicMock()]
    mock_load_config.return_value = mock_config
    
    mock_has_new.return_value = False
    
    # Run
    main()
    
    # Assert
    mock_load_config.assert_called_once()
    mock_has_new.assert_called_once()
    mock_generator.assert_not_called()
    mock_sender.assert_not_called()

@patch("src.main.load_config")
@patch("src.main.DedupTracker")
@patch("src.main.get_fetcher")
@patch("src.main.process_results")
@patch("src.main.has_new_content")
@patch("src.main.EPUBGenerator")
@patch("src.main.SMTPSender")
@patch("src.main.get_logger")
def test_main_failure(
    mock_get_logger,
    mock_sender,
    mock_generator,
    mock_has_new,
    mock_process,
    mock_fetcher,
    mock_tracker,
    mock_load_config
):
    # Setup
    mock_logger = MagicMock()
    mock_get_logger.return_value = mock_logger
    mock_load_config.side_effect = Exception("Config load failed")
    
    # Run
    with pytest.raises(SystemExit) as excinfo:
        main()
    
    # Assert
    assert excinfo.value.code == 1
    mock_logger.exception.assert_called()
