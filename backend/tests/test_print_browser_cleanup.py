from pathlib import Path
import subprocess
import tempfile
from unittest.mock import Mock

import pytest
from websockets.exceptions import ConnectionClosed

from app.services import briefing_report_pdf as pdf


def test_failed_devtools_connection_cleans_up_the_owned_process_and_profile(monkeypatch):
    process = Mock()
    process.poll.return_value = None
    monkeypatch.setattr(pdf.subprocess, "Popen", Mock(return_value=process))
    monkeypatch.setattr(pdf, "_chrome_path", lambda: "test-chrome")
    monkeypatch.setattr(pdf, "_wait_debugger_address", lambda *_: ("1234", "/devtools/browser/test"))
    monkeypatch.setattr("websockets.sync.client.connect", Mock(side_effect=TimeoutError("connection failed")))
    browser = pdf._PrintBrowser()
    with pytest.raises(TimeoutError, match="connection failed"):
        browser.__enter__()
    process.terminate.assert_called_once()
    assert not Path(browser.profile.name).exists()


def test_already_closed_socket_still_reaps_the_browser_and_cleans_the_profile():
    browser = pdf._PrintBrowser()
    browser.profile = tempfile.TemporaryDirectory(prefix="podmaster-report-test-")
    browser.process = Mock()
    browser.process.poll.return_value = 0
    browser.socket = Mock()
    browser.socket.send.side_effect = ConnectionClosed(None, None)
    browser.sequence = 1
    browser.close()
    browser.process.wait.assert_called_once()
    assert not Path(browser.profile.name).exists()


@pytest.mark.skipif(pdf.os.name != "nt", reason="Windows process-tree cleanup")
def test_hung_windows_browser_is_reaped_with_its_own_process_tree(monkeypatch):
    browser = pdf._PrintBrowser()
    browser.profile = tempfile.TemporaryDirectory(prefix="podmaster-report-test-")
    browser.process = Mock(pid=123456)
    browser.process.poll.return_value = None
    browser.process.wait.side_effect = [subprocess.TimeoutExpired("test-chrome", 10), 0]
    stop_tree = Mock(return_value=subprocess.CompletedProcess([], 0))
    monkeypatch.setattr(pdf.subprocess, "run", stop_tree)
    browser.close()
    assert stop_tree.call_args.args[0] == ["taskkill", "/PID", "123456", "/T", "/F"]
    assert browser.process.wait.call_count == 2
    assert not Path(browser.profile.name).exists()


@pytest.mark.skipif(pdf.os.name != "nt", reason="Windows process-tree cleanup")
def test_failed_process_tree_command_still_terminates_the_owned_browser(monkeypatch):
    browser = pdf._PrintBrowser()
    browser.profile = tempfile.TemporaryDirectory(prefix="podmaster-report-test-")
    browser.process = Mock(pid=123456)
    browser.process.poll.return_value = None

    def wait(timeout):
        if not browser.process.kill.called:
            raise subprocess.TimeoutExpired("test-chrome", timeout)
        return 0

    browser.process.wait.side_effect = wait
    monkeypatch.setattr(pdf.subprocess, "run", Mock(return_value=subprocess.CompletedProcess([], 1)))
    browser.close()
    browser.process.kill.assert_called_once()
    assert not Path(browser.profile.name).exists()
