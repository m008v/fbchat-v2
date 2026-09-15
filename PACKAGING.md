# fbchat-v2 - PyPI distribution

> Folder này là phiên bản **đóng gói lại** của repo gốc (`../fbchat-v2`) để publish lên [PyPI](https://pypi.org/).
> Code logic giữ nguyên - chỉ tái cấu trúc layout + đổi import thành package `fbchat_v2`.

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

Nhánh `pypi` đang đồng bộ runtime async-first `v2.3.2` từ verified sdist của
GitHub Release tương ứng.
Code module đã đổi import sang namespace `fbchat_v2.*` để chạy đúng sau khi cài qua `pip`.

Nguồn: [`../fbchat-v2/CHANGELOG.md`](../fbchat-v2/CHANGELOG.md).

---

## 🛠 Build local

```powershell
cd fbchat-v2-pypi
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip build twine

# Build thử vào thư mục rỗng riêng cho đúng version
python -m build --outdir .artifacts/v2.3.2-local

# Kết quả nằm ở .artifacts/v2.3.2-local/
ls .artifacts/v2.3.2-local/
# fbchat_v2-2.3.2-py3-none-any.whl
# fbchat_v2-2.3.2.tar.gz
```

## 🧪 Test cài thử

```powershell
deactivate
python -m venv .venv-test
.venv-test\Scripts\activate
pip install .artifacts/v2.3.2-local/fbchat_v2-2.3.2-py3-none-any.whl

python -c "import fbchat_v2; print(fbchat_v2.__version__)"
```

## 🚀 Upload

### TestPyPI (làm trước cho chắc)

```powershell
twine upload --repository testpypi .artifacts/v2.3.2-local/fbchat_v2-2.3.2-py3-none-any.whl .artifacts/v2.3.2-local/fbchat_v2-2.3.2.tar.gz
pip install --index-url https://test.pypi.org/simple/ fbchat-v2
```

### PyPI thật

```powershell
twine upload .artifacts/v2.3.2/fbchat_v2-2.3.2-py3-none-any.whl .artifacts/v2.3.2/fbchat_v2-2.3.2.tar.gz
```

> Production chỉ upload đúng hai artifact đã tải từ GitHub Release vào
> `.artifacts/v2.3.2/`; không rebuild từ checkout này. Token API được giữ trong
> keyring, không ghi vào repository hoặc command log.

---

## 🔗 E2EE bridge

Binary Go `fbchat-bridge-e2ee` **không** được đóng gói trong wheel. Bản `v2.3.2`
nhúng checksum của đúng năm binary từ GitHub Release `v2.3.2` và tự tải asset
phù hợp vào cache khi cần. Downloader pin repository, tag, asset path, host,
redirect, kích thước và SHA-256; trường hợp không khớp sẽ fail-closed. User vẫn
có thể tự build bridge cùng version và trỏ thủ công qua `FBCHAT_E2EE_BIN`.

```bash
pip install fbchat-v2          # core + async/httpx runtime
pip install fbchat-v2[e2ee]    # reserved, hiện chưa thêm dependency riêng
```

Hướng dẫn build bridge: [`../fbchat-v2/bridge-e2ee/README.md`](../fbchat-v2/bridge-e2ee/README.md).
