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


def test_add_ssh_key_from_stdin_with_comment(cli, requests_mock, fs, monkeypatch):
    """Test --add-ssh-key uses SSH key comment for key_id and name."""
    write_config(auth_req)

    monkeypatch.setattr("socket.gethostname", lambda: "TestHost")

    api_calls = []

    def track_put(request, context):
        api_calls.append(("PUT", request.path))
        return ""

    def track_post(request, context):
        api_calls.append(("POST", request.path, request.text))
        return ""

    # SSH key comment "test@example.com" becomes key_id "test-example-com"
    requests_mock.register_uri("PUT", f"{API_ROOT}admin/keys/test-example-com", text=track_put)
    requests_mock.register_uri("POST", f"{API_ROOT}admin/keys/test-example-com/key", text=track_post)
    requests_mock.register_uri("POST", f"{API_ROOT}admin/keys/test-example-com/name", text=track_post)
    requests_mock.register_uri("POST", f"{API_ROOT}admin/keys/test-example-com/summary", text=track_post)

    ssh_key = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC... test@example.com"
    out, err = cli("--add-ssh-key", stdin=ssh_key)

    # Verify key_id derived from comment
    assert ("PUT", "/v1/admin/keys/test-example-com") in api_calls
    # Name should be the original comment
    assert any(
        call[0] == "POST" and call[1] == "/v1/admin/keys/test-example-com/name" and "test@example.com" in call[2]
        for call in api_calls
    )
    # Summary should include hostname
    assert any(
        call[0] == "POST" and call[1] == "/v1/admin/keys/test-example-com/summary" and "TestHost" in call[2]
        for call in api_calls
    )

    assert "test-example-com" in out
    assert "successfully" in out


def test_add_ssh_key_from_stdin_no_comment(cli, requests_mock, fs, monkeypatch):
    """Test --add-ssh-key falls back to hostname when SSH key has no comment."""
    write_config(auth_req)

    monkeypatch.setattr("socket.gethostname", lambda: "TestHost")

    api_calls = []

    def track_put(request, context):
        api_calls.append(("PUT", request.path))
        return ""

    def track_post(request, context):
        api_calls.append(("POST", request.path, request.text))
        return ""

    # No comment in SSH key, should fall back to hostname
    requests_mock.register_uri("PUT", f"{API_ROOT}admin/keys/testhost", text=track_put)
    requests_mock.register_uri("POST", f"{API_ROOT}admin/keys/testhost/key", text=track_post)
    requests_mock.register_uri("POST", f"{API_ROOT}admin/keys/testhost/name", text=track_post)
    requests_mock.register_uri("POST", f"{API_ROOT}admin/keys/testhost/summary", text=track_post)

    # SSH key without comment (only algo and key)
    ssh_key = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC..."
    out, err = cli("--add-ssh-key", stdin=ssh_key)

    # Verify hostname used as key_id
    assert ("PUT", "/v1/admin/keys/testhost") in api_calls
    assert "testhost" in out
    assert "successfully" in out


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
    assert "successfully" in out


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

    def capture_token(request, context):
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            captured_tokens.append(auth_header[7:])
        return ""

    # Register mocks for both API roots
    for api_root in ["https://api1.test/v1/", "https://api2.test/v1/"]:
        requests_mock.register_uri("PUT", f"{api_root}admin/keys/testhost", text=capture_token)
        requests_mock.register_uri("POST", f"{api_root}admin/keys/testhost/key", text=capture_token)
        requests_mock.register_uri("POST", f"{api_root}admin/keys/testhost/name", text=capture_token)
        requests_mock.register_uri("POST", f"{api_root}admin/keys/testhost/summary", text=capture_token)

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
    assert "successfully" in out


def test_add_ssh_key_update_existing(cli, requests_mock, fs, monkeypatch):
    """Test --add-ssh-key updates existing key when it already exists (409)."""
    write_config(auth_req)

    monkeypatch.setattr("socket.gethostname", lambda: "TestHost")

    def return_empty_keys(request, context):
        return ""

    def return_conflict(request, context):
        context.status_code = 409
        return '{"status": "Failure", "message": "The plot already exist!"}'

    def return_ok(request, context):
        return ""

    requests_mock.register_uri("GET", f"{API_ROOT}admin/keys", text=return_empty_keys)
    requests_mock.register_uri("PUT", f"{API_ROOT}admin/keys/testhost", text=return_conflict)
    requests_mock.register_uri("POST", f"{API_ROOT}admin/keys/testhost/key", text=return_ok)
    requests_mock.register_uri("POST", f"{API_ROOT}admin/keys/testhost/name", text=return_ok)
    requests_mock.register_uri("POST", f"{API_ROOT}admin/keys/testhost/summary", text=return_ok)

    ssh_key = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC..."
    out, err = cli("--add-ssh-key", stdin=ssh_key)

    # Should succeed with "updated" message
    assert "testhost" in out
    assert "updated successfully" in out


def test_add_ssh_key_duplicate_key(cli, requests_mock, fs, monkeypatch):
    """Test --add-ssh-key handles duplicate key content gracefully."""
    write_config(auth_req)

    monkeypatch.setattr("socket.gethostname", lambda: "TestHost")

    def return_empty_keys(request, context):
        return ""

    def return_ok(request, context):
        return ""

    def return_duplicate(request, context):
        return '{"status": "Failure", "message": "Duplicate key detected, keys need to be unique."}'

    requests_mock.register_uri("GET", f"{API_ROOT}admin/keys", text=return_empty_keys)
    requests_mock.register_uri("PUT", f"{API_ROOT}admin/keys/testhost", text=return_ok)
    requests_mock.register_uri("POST", f"{API_ROOT}admin/keys/testhost/key", text=return_duplicate)

    ssh_key = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC..."

    with pytest.raises(CliExit) as e:
        cli("--add-ssh-key", stdin=ssh_key)

    out, err = e.value.args
    assert e.value.code == 1
    assert "Failed to add SSH key" in err
    assert "Duplicate" in err


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
