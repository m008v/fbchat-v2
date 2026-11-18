# fbchat-v2 - PyPI distribution

Checkout này lưu source của package [`fbchat-v2`](https://pypi.org/project/fbchat-v2/)
trên nhánh `pypi`. Package dùng namespace `fbchat_v2`; không merge trực tiếp
nhánh `main`. `src/fbchat_v2` là source duy nhất ở đây, không phải bản trùng.

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

Source package `2.3.5` được đồng bộ từ sdist đã xác minh của
[GitHub Release `v2.3.5`](https://github.com/m008v/fbchat-v2/releases/tag/v2.3.5),
build từ main `ec26e54`. Cả 55 file package, README Việt/Anh và changelog khớp
payload của release. Các module tiếp tục dùng import `fbchat_v2.*`.

Ở checkout main, code package được sinh vào `build/fbchat_v2` khi cài/build,
không còn được track trong `src/fbchat_v2`. Khi đồng bộ development sang đây,
lấy output đã kiểm tra của generator và README hai ngôn ngữ. Giữ layout
package-only cùng cấu hình build riêng của nhánh `pypi`; không chép build hook
của main vì checkout này không có source legacy để sinh lại package.

Giữ nguyên `_messaging/_bridge_checksums.py` đã bind cho release `2.3.5`.
Main chưa bind checksum có thể chứa placeholder; chép đè file này sẽ làm hỏng
tải bridge. Không dùng bản build thử từ snapshot development để thay artifact
đã phát hành hoặc upload lại cùng version.

Giữ cấu hình mypy cho layout package-only và không format lại file checksum
do workflow release sinh ra. Hai artifact dùng để phát hành phải giữ nguyên
bytes tải từ GitHub Release; build cục bộ chỉ để kiểm tra.

Workflow có thể tạo release ở trạng thái draft để xác minh artifact và đồng bộ
nhánh `pypi` trước khi công khai. Chỉ lấy source từ sdist đã đối chiếu metadata,
`SHA256SUMS-python` và checksum năm bridge nhúng trong package với manifest
`SHA256SUMS`. Không chép source từ một working tree chưa bind checksum, kể cả
khi version đã là `2.3.5`. Sau khi nhánh `pypi` được commit/push, công khai
GitHub Release và upload đúng hai artifact đã xác minh lên PyPI; không build lại.

Nguồn: [`../fbchat-v2/CHANGELOG.md`](../fbchat-v2/CHANGELOG.md).

---

## 🛠 Build local

```powershell
cd fbchat-v2-pypi
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip build twine

# Build thử vào thư mục rỗng riêng cho đúng version
python -m build --outdir .artifacts/v2.3.5-local

# Kết quả nằm ở .artifacts/v2.3.5-local/
ls .artifacts/v2.3.5-local/
# fbchat_v2-2.3.5-py3-none-any.whl
# fbchat_v2-2.3.5.tar.gz
```

## 🧪 Test cài thử

```powershell
deactivate
python -m venv .venv-test
.venv-test\Scripts\activate
pip install .artifacts/v2.3.5-local/fbchat_v2-2.3.5-py3-none-any.whl

python -c "import fbchat_v2; print(fbchat_v2.__version__)"
```

## 🚀 Upload

### TestPyPI

Nếu cần kiểm tra thao tác upload bằng bản build thử, dùng TestPyPI riêng.
Kết quả này không thay thế việc xác minh artifact production.

```powershell
twine upload --repository testpypi .artifacts/v2.3.5-local/fbchat_v2-2.3.5-py3-none-any.whl .artifacts/v2.3.5-local/fbchat_v2-2.3.5.tar.gz
pip install --index-url https://test.pypi.org/simple/ fbchat-v2
```

### PyPI thật

Tải đúng wheel và sdist từ GitHub Release vào `.artifacts/v2.3.5/`.
Đối chiếu cả hai file với `SHA256SUMS-python`, kiểm tra metadata bằng Twine 7
và xác nhận checksum bridge nhúng trong package khớp `SHA256SUMS` của release
trước khi upload. Chỉ truyền đúng hai đường dẫn dưới đây, không dùng wildcard
trên thư mục có thể chứa artifact cũ.

```powershell
twine check --strict .artifacts/v2.3.5/fbchat_v2-2.3.5-py3-none-any.whl .artifacts/v2.3.5/fbchat_v2-2.3.5.tar.gz
twine upload --non-interactive -u __token__ .artifacts/v2.3.5/fbchat_v2-2.3.5-py3-none-any.whl .artifacts/v2.3.5/fbchat_v2-2.3.5.tar.gz
```

Không rebuild hai artifact production từ checkout này. Dùng credential đã
lưu trong keyring; không đưa token vào source, tham số lệnh hoặc log.
Sau upload, kiểm tra lại tên, kích thước và SHA-256 của file trên PyPI so với
artifact GitHub, rồi cài thử trong môi trường mới. Những bước này kiểm tra
package và phát hành, không phải bằng chứng Facebook/Messenger live.

---

## 🔗 E2EE bridge

Wheel không chứa binary Go `fbchat-bridge-e2ee`. Package `2.3.5` nhúng checksum
của năm binary từ GitHub Release `v2.3.5` và tải asset phù hợp vào cache khi cần.
Downloader kiểm tra repository, tag, đường dẫn asset, host, redirect, kích thước
và SHA-256; nếu không khớp, nó dừng thay vì dùng binary chưa xác minh.
Có thể tự build bridge cùng version và trỏ qua `FBCHAT_E2EE_BIN`.

Reconnect từ `2.3.5` yêu cầu capability `structuredConnectionStatus`. Nếu đang
override binary, cập nhật bridge cùng phiên bản với package Python. Device
persistent chứa key/session; giữ trong thư mục riêng như `.state/` đã được
Git ignore, không commit hoặc chia sẻ. Chế độ mặc định memory-only báo
`device_state_lost` khi process chết, không tự pair mới hoặc ghi key ra đĩa.

```bash
pip install fbchat-v2          # core + async/httpx runtime
pip install fbchat-v2[e2ee]    # reserved, hiện chưa thêm dependency riêng
```

Hướng dẫn build bridge: [`../fbchat-v2/bridge-e2ee/README.md`](../fbchat-v2/bridge-e2ee/README.md).
