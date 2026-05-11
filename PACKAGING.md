# fbchat-v2 — PyPI distribution

> Folder này là phiên bản **đóng gói lại** của repo gốc (`../fbchat-v2`) để publish lên [PyPI](https://pypi.org/).
> Code logic giữ nguyên — chỉ tái cấu trúc layout + đổi import thành package `fbchat_v2`.

---

## 📐 Layout

```
fbchat-v2-pypi/
├── pyproject.toml          # Hatchling build, metadata PEP 621
├── MANIFEST.in
├── LICENSE                 # Copy từ ../fbchat-v2/LICENSE
├── README.md               # Copy từ ../fbchat-v2/README.md
├── README_EN.md
├── CHANGELOG.md
├── .gitignore
└── src/
    └── fbchat_v2/          # ← Package thực sự được install qua pip
        ├── __init__.py     # Expose public API + __version__
        ├── py.typed        # Marker PEP 561
        ├── _core/
        ├── _features/
        └── _messaging/
```

---

## 🚧 Trạng thái

Đây là **work-in-progress**. Theo dõi các bước hoàn thành trong todo list.

Nguồn: [`../fbchat-v2/CHANGELOG.md §2.1.0`](../fbchat-v2/CHANGELOG.md).

---

## 🛠 Build local

```powershell
cd fbchat-v2-pypi
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip build twine

# Build sdist + wheel
python -m build

# Kết quả nằm ở dist/
ls dist/
# fbchat_v2-2.1.0-py3-none-any.whl
# fbchat_v2-2.1.0.tar.gz
```

## 🧪 Test cài thử

```powershell
deactivate
python -m venv .venv-test
.venv-test\Scripts\activate
pip install dist/fbchat_v2-2.1.0-py3-none-any.whl

python -c "import fbchat_v2; print(fbchat_v2.__version__)"
```

## 🚀 Upload

### TestPyPI (làm trước cho chắc)

```powershell
twine upload --repository testpypi dist/*
pip install --index-url https://test.pypi.org/simple/ fbchat-v2
```

### PyPI thật

```powershell
twine upload dist/*
```

> Cần token API. Tạo tại <https://pypi.org/manage/account/token/> và lưu vào `~/.pypirc`.

---

## 🔗 E2EE bridge

Binary Go `fbchat-bridge-e2ee` **không** được đóng gói trong wheel (PyPI không nhận binary native không phải Python).
User cài qua extras + tự build, hoặc auto-download từ GitHub Releases (đang reserve cho future).

```bash
pip install fbchat-v2          # core (group messages)
pip install fbchat-v2[e2ee]    # reserved — hiện chưa khác core
```

Hướng dẫn build bridge: [`../fbchat-v2/bridge-e2ee/README.md`](../fbchat-v2/bridge-e2ee/README.md).
