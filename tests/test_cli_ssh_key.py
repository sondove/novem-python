import pytest

from novem.utils import API_ROOT

from .conftest import CliExit
from .utils import write_config

auth_req = {
    "username": "demouser",
    "password": "demopass",
    "token_name": "demotoken",
    "token_description": "test token",
}


def test_add_ssh_key_from_stdin(cli, requests_mock, fs, monkeypatch):
    """Test --add-ssh-key reads key from stdin and creates key with hostname as id."""
    write_config(auth_req)

    # Mock hostname
    monkeypatch.setattr("socket.gethostname", lambda: "TestHost")

    # Track API calls
    api_calls = []

    def track_get(request, context):
        api_calls.append(("GET", request.path))
        # Return empty list of keys (no existing keys)
        return ""

    def track_put(request, context):
        api_calls.append(("PUT", request.path))
        return ""

    def track_post(request, context):
        api_calls.append(("POST", request.path, request.text))
        return ""

    requests_mock.register_uri("GET", f"{API_ROOT}admin/keys", text=track_get)
    requests_mock.register_uri("PUT", f"{API_ROOT}admin/keys/testhost", text=track_put)
    requests_mock.register_uri("POST", f"{API_ROOT}admin/keys/testhost/key", text=track_post)
    requests_mock.register_uri("POST", f"{API_ROOT}admin/keys/testhost/name", text=track_post)
    requests_mock.register_uri("POST", f"{API_ROOT}admin/keys/testhost/summary", text=track_post)

    ssh_key = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC... test@example.com"
    out, err = cli("--add-ssh-key", stdin=ssh_key)

    # Verify API calls were made in correct order
    assert ("GET", "/v1/admin/keys") in api_calls
    assert ("PUT", "/v1/admin/keys/testhost") in api_calls
    assert any(
        call[0] == "POST" and call[1] == "/v1/admin/keys/testhost/key" and ssh_key in call[2] for call in api_calls
    )
    assert any(
        call[0] == "POST" and call[1] == "/v1/admin/keys/testhost/name" and "TestHost" in call[2] for call in api_calls
    )
    assert any(
        call[0] == "POST" and call[1] == "/v1/admin/keys/testhost/summary" and "TestHost" in call[2]
        for call in api_calls
    )

    # Verify success message
    assert "testhost" in out
    assert "added successfully" in out


def test_add_ssh_key_with_custom_id(cli, requests_mock, fs, monkeypatch):
    """Test --add-ssh-key with custom key id."""
    write_config(auth_req)

    monkeypatch.setattr("socket.gethostname", lambda: "TestHost")

    api_calls = []

    def track_get(request, context):
        api_calls.append(("GET", request.path))
        return ""

    def track_put(request, context):
        api_calls.append(("PUT", request.path))
        return ""

    def track_post(request, context):
        api_calls.append(("POST", request.path, request.text))
        return ""

    requests_mock.register_uri("GET", f"{API_ROOT}admin/keys", text=track_get)
    requests_mock.register_uri("PUT", f"{API_ROOT}admin/keys/my-custom-key", text=track_put)
    requests_mock.register_uri("POST", f"{API_ROOT}admin/keys/my-custom-key/key", text=track_post)
    requests_mock.register_uri("POST", f"{API_ROOT}admin/keys/my-custom-key/name", text=track_post)
    requests_mock.register_uri("POST", f"{API_ROOT}admin/keys/my-custom-key/summary", text=track_post)

    ssh_key = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC..."
    out, err = cli("--add-ssh-key", "my-custom-key", stdin=ssh_key)

    # Verify the custom key ID was used
    assert ("PUT", "/v1/admin/keys/my-custom-key") in api_calls
    assert "my-custom-key" in out
    assert "added successfully" in out


def test_add_ssh_key_already_exists(cli, requests_mock, fs, monkeypatch):
    """Test --add-ssh-key fails when key id already exists."""
    write_config(auth_req)

    monkeypatch.setattr("socket.gethostname", lambda: "TestHost")

    def return_existing_keys(request, context):
        # Return existing keys list
        return "testhost\notherkey"

    requests_mock.register_uri("GET", f"{API_ROOT}admin/keys", text=return_existing_keys)

    ssh_key = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC..."

    with pytest.raises(CliExit) as e:
        cli("--add-ssh-key", stdin=ssh_key)

    out, err = e.value.args
    assert e.value.code == 1
    assert "already exists" in err
    assert "testhost" in err


def test_add_ssh_key_no_stdin(cli, requests_mock, fs, monkeypatch):
    """Test --add-ssh-key fails when no key provided on stdin (whitespace only)."""
    write_config(auth_req)

    monkeypatch.setattr("socket.gethostname", lambda: "TestHost")

    with pytest.raises(CliExit) as e:
        # Provide whitespace-only stdin which should be stripped to empty
        cli("--add-ssh-key", stdin="   \n  \t  ")

    out, err = e.value.args
    assert e.value.code == 1
    assert "No SSH key provided" in err


def test_add_ssh_key_tty_error(cli, requests_mock, fs, monkeypatch):
    """Test --add-ssh-key fails with helpful message when run interactively (TTY)."""
    write_config(auth_req)

    monkeypatch.setattr("socket.gethostname", lambda: "TestHost")
    # Simulate running in an interactive terminal (TTY)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    with pytest.raises(CliExit) as e:
        cli("--add-ssh-key")

    out, err = e.value.args
    assert e.value.code == 1
    assert "No SSH key provided" in err
    assert "cat ~/.ssh/id_rsa.pub" in err


def test_add_ssh_key_respects_profile(cli, requests_mock, fs, monkeypatch):
    """Test --add-ssh-key respects --profile option."""
    # Write config with two profiles
    conf = """\
[general]
profile = user1

[app:cli]
version = 0.5.0

[profile:user1]
username = user1
api_root = https://api1.test/v1
token = token1

[profile:user2]
username = user2
api_root = https://api2.test/v1
token = token2
"""

    import os

    from novem.utils import get_config_path

    cfolder, cpath = get_config_path()
    os.makedirs(cfolder, exist_ok=True)
    with open(cpath, "w") as f:
        f.write(conf)

    monkeypatch.setattr("socket.gethostname", lambda: "TestHost")

    captured_tokens = []

    def capture_get(request, context):
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            captured_tokens.append(auth_header[7:])
        return ""

    def capture_other(request, context):
        return ""

    # Register mocks for both API roots
    for api_root in ["https://api1.test/v1/", "https://api2.test/v1/"]:
        requests_mock.register_uri("GET", f"{api_root}admin/keys", text=capture_get)
        requests_mock.register_uri("PUT", f"{api_root}admin/keys/testhost", text=capture_other)
        requests_mock.register_uri("POST", f"{api_root}admin/keys/testhost/key", text=capture_other)
        requests_mock.register_uri("POST", f"{api_root}admin/keys/testhost/name", text=capture_other)
        requests_mock.register_uri("POST", f"{api_root}admin/keys/testhost/summary", text=capture_other)

    ssh_key = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC..."

    # Default profile (user1)
    cli("--add-ssh-key", stdin=ssh_key)
    assert captured_tokens[-1] == "token1"

    # Explicit profile user2
    cli("--profile", "user2", "--add-ssh-key", stdin=ssh_key)
    assert captured_tokens[-1] == "token2"


def test_add_ssh_key_sanitizes_hostname(cli, requests_mock, fs, monkeypatch):
    """Test --add-ssh-key sanitizes hostname with dots and special chars."""
    write_config(auth_req)

    # Hostname with dots (common on macOS like "imoen.local")
    monkeypatch.setattr("socket.gethostname", lambda: "My-Host.local")

    api_calls = []

    def track_get(request, context):
        api_calls.append(("GET", request.path))
        return ""

    def track_put(request, context):
        api_calls.append(("PUT", request.path))
        return ""

    def track_post(request, context):
        api_calls.append(("POST", request.path))
        return ""

    # The sanitized key_id should be "my-host-local" (dots -> dashes, lowercase)
    requests_mock.register_uri("GET", f"{API_ROOT}admin/keys", text=track_get)
    requests_mock.register_uri("PUT", f"{API_ROOT}admin/keys/my-host-local", text=track_put)
    requests_mock.register_uri("POST", f"{API_ROOT}admin/keys/my-host-local/key", text=track_post)
    requests_mock.register_uri("POST", f"{API_ROOT}admin/keys/my-host-local/name", text=track_post)
    requests_mock.register_uri("POST", f"{API_ROOT}admin/keys/my-host-local/summary", text=track_post)

    ssh_key = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC..."
    out, err = cli("--add-ssh-key", stdin=ssh_key)

    # Verify the sanitized key ID was used
    assert ("PUT", "/v1/admin/keys/my-host-local") in api_calls
    assert "my-host-local" in out
    assert "added successfully" in out


def test_add_ssh_key_summary_includes_version(cli, requests_mock, fs, monkeypatch):
    """Test --add-ssh-key includes version in summary."""
    write_config(auth_req)

    monkeypatch.setattr("socket.gethostname", lambda: "TestHost")

    summary_text = None

    def track_get(request, context):
        return ""

    def track_put(request, context):
        return ""

    def track_post(request, context):
        nonlocal summary_text
        if "summary" in request.path:
            summary_text = request.text
        return ""

    requests_mock.register_uri("GET", f"{API_ROOT}admin/keys", text=track_get)
    requests_mock.register_uri("PUT", f"{API_ROOT}admin/keys/testhost", text=track_put)
    requests_mock.register_uri("POST", f"{API_ROOT}admin/keys/testhost/key", text=track_post)
    requests_mock.register_uri("POST", f"{API_ROOT}admin/keys/testhost/name", text=track_post)
    requests_mock.register_uri("POST", f"{API_ROOT}admin/keys/testhost/summary", text=track_post)

    ssh_key = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC..."
    cli("--add-ssh-key", stdin=ssh_key)

    # Verify summary includes version
    assert summary_text is not None
    assert "TestHost" in summary_text
    assert "novem cli v" in summary_text
