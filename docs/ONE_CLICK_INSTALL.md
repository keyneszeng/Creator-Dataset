# One-click Personal Installation

Creator Dataset is currently designed as a fully free personal Agent capability.

## One command

On macOS or Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/keyneszeng/Creator-Dataset/main/install.sh | bash
```

The installer will:

1. clone/update Creator Dataset into `~/.creator-dataset`;
2. find Python 3.12+;
3. on macOS, use Homebrew to install Python 3.12 if Homebrew already exists;
4. create `.venv`;
5. install Agent + Xiaohongshu + OCR + STT dependencies;
6. create/update `.env` for local free mode;
7. generate the local Plugin bundle;
8. install convenience commands under `~/.local/bin`;
9. run a configuration check.

It does **not** upload secrets or enable billing.

## After installation

Edit:

```text
~/.creator-dataset/.env
```

Set your own logged-in Xiaohongshu Cookie:

```text
CREATOR_DATASET_XHS_COOKIE=...
```

Then check:

```bash
~/.local/bin/creator-dataset --check
```

Start:

```bash
~/.local/bin/creator-dataset
```

Default MCP endpoint:

```text
http://127.0.0.1:8765/mcp
```

The generated Plugin bundle is:

```text
~/.creator-dataset/dist/plugins/creator-dataset
```

## Current free behavior

```text
Creator import      free
Post catalog        free
Dataset prepare     free
Dataset read        free
Comments            free
OCR / STT           free
```

No Dataset credit or payment flow is active in the Agent path.

## Update later

Run the same one-line installer again:

```bash
curl -fsSL https://raw.githubusercontent.com/keyneszeng/Creator-Dataset/main/install.sh | bash
```

It will pull the latest `main` branch and reinstall the editable package without replacing your existing `.env`.

## Custom install path

```bash
CREATOR_DATASET_INSTALL_DIR="$HOME/Creator-Dataset" \
curl -fsSL https://raw.githubusercontent.com/keyneszeng/Creator-Dataset/main/install.sh | bash
```

## Python override

If Python 3.12+ is already installed somewhere specific:

```bash
CREATOR_DATASET_PYTHON=/path/to/python3.12 \
curl -fsSL https://raw.githubusercontent.com/keyneszeng/Creator-Dataset/main/install.sh | bash
```

## macOS note

The installer does not install Docker Desktop.

For older Macs, the local Python + SQLite + local storage path is intentionally the default.

If Python 3.12+ is missing and Homebrew is not installed, install Homebrew/Python first, then rerun the one-line command.
