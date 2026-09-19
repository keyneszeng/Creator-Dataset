import subprocess
from pathlib import Path


def test_install_script_has_valid_bash_syntax() -> None:
    path = Path("install.sh")
    assert path.exists()

    result = subprocess.run(
        ["bash", "-n", str(path)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
