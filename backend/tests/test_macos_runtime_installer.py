from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_installer_uses_unprotected_application_support_runtime():
    installer = (PROJECT_ROOT / "scripts" / "install-macos-runtime.sh").read_text()

    assert "Library/Application Support/HomeSentinel" in installer
    assert "Library/Logs/HomeSentinel" in installer
    assert "Documents/GitHub" not in installer


def test_installer_backs_up_launch_agents_and_uses_bootstrap():
    installer = (PROJECT_ROOT / "scripts" / "install-macos-runtime.sh").read_text()

    assert "plist-backups" in installer
    assert "launchctl bootstrap" in installer
    assert "launchctl bootout" in installer


def test_rollback_restores_previous_launch_agents():
    rollback = (PROJECT_ROOT / "scripts" / "rollback-macos-runtime.sh").read_text()

    assert "plist-backups" in rollback
    assert "com.homesentinel.backend.plist" in rollback
    assert "com.homesentinel.frontend.plist" in rollback
    assert "launchctl bootstrap" in rollback


def test_installed_backend_uses_external_database_and_logs():
    installer = (PROJECT_ROOT / "scripts" / "install-macos-runtime.sh").read_text()

    assert "DB_PATH" in installer
    assert "data/homesentinel.db" in installer
    assert "backend.stderr.log" in installer
    assert "frontend.stderr.log" in installer


def test_service_control_script_is_allowlisted_and_never_accepts_a_pid():
    controller = (PROJECT_ROOT / "scripts" / "control-macos-service.sh").read_text()

    assert 'backend|frontend' in controller
    assert 'restart|stop' in controller
    assert "launchctl kickstart" in controller
    assert "launchctl bootout" in controller
    assert "kill -9" not in controller
