"""
paths._user_data_dir() resolves the platform-standard config/reports
location. Each OS branch is tested independently by monkeypatching
sys.platform and the relevant environment variables/Path.home(), since a
single dev machine can only exercise one branch for real.
"""
import paths


def test_macos_path(monkeypatch):
    monkeypatch.setattr(paths.sys, "platform", "darwin")
    monkeypatch.setattr(paths.Path, "home", lambda: paths.Path("/Users/testuser"))
    result = paths._user_data_dir()
    assert result == paths.Path("/Users/testuser/Library/Application Support/APK-JTM")


def test_windows_path_uses_appdata(monkeypatch):
    monkeypatch.setattr(paths.sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", r"C:\Users\testuser\AppData\Roaming")
    result = paths._user_data_dir()
    assert result == paths.Path(r"C:\Users\testuser\AppData\Roaming") / "APK-JTM"


def test_windows_path_falls_back_without_appdata(monkeypatch):
    monkeypatch.setattr(paths.sys, "platform", "win32")
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setattr(paths.Path, "home", lambda: paths.Path("/home/testuser"))
    result = paths._user_data_dir()
    assert result == paths.Path("/home/testuser") / "AppData" / "Roaming" / "APK-JTM"


def test_linux_path_uses_xdg_data_home(monkeypatch):
    monkeypatch.setattr(paths.sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", "/home/testuser/.data")
    result = paths._user_data_dir()
    assert result == paths.Path("/home/testuser/.data") / "apk-jtm"


def test_linux_path_falls_back_to_local_share(monkeypatch):
    monkeypatch.setattr(paths.sys, "platform", "linux")
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setattr(paths.Path, "home", lambda: paths.Path("/home/testuser"))
    result = paths._user_data_dir()
    assert result == paths.Path("/home/testuser") / ".local" / "share" / "apk-jtm"
