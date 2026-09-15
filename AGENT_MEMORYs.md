# Agent Memories

## 2026-09-15 — Đồng bộ source đóng gói v2.3.2

### Mục tiêu
- Đồng bộ toàn bộ package runtime từ release thay thế `fbchat-v2==2.3.2`, giữ branch `pypi` làm checkout đóng gói độc lập và chuẩn bị phát hành đúng artifact đã qua CI.

### Đã thực hiện
- Thay toàn bộ `src/fbchat_v2` bằng payload từ sdist GitHub Release `v2.3.2` target commit `981d0996db0a01af45526f8270d83559d5a3ef2e`; bổ sung module `_core/_console.py` và đồng bộ metadata, README, changelog, license cùng regression test bridge.
- Đồng bộ mọi version đang hoạt động sang `2.3.2` và bind năm bridge binary đúng checksum của GitHub Release `v2.3.2`.
- Thay artifact lần đầu bị chặn do owner GitHub cũ bằng replacement wheel/sdist đã sửa canonical repository `m008v/fbchat-v2`; regression test khóa exact API và asset URL owner.
- Cập nhật `PACKAGING.md` để phân biệt build thử cục bộ với hai artifact production; production không rebuild từ checkout này.
- Sửa bảy ký tự điều khiển tồn tại từ các Windows path bị escape sai trong lịch sử `AGENT_MEMORYs.md`; không thay đổi nội dung kỹ thuật tương ứng.
- Commit đồng bộ `700890d301c4a697b77cc2bbc7f72f6998333d5b` (`chore(pypi): synchronize v2.3.2 release source`) đã push fast-forward lên `origin/pypi`.
- Upload đúng replacement wheel và sdist lên PyPI bằng token lấy từ Windows keyring; credential không xuất hiện trong source, command line hoặc log.

### Quyết định kỹ thuật
- Lấy verified sdist làm nguồn đồng bộ thay vì copy từ working tree hoặc rebuild tùy hứng, tránh cùng version nhưng khác payload.
- Giữ cấu hình mypy riêng cho layout package-only `src/fbchat_v2`; metadata và runtime source vẫn tương thích với artifact release.
- Loại file checksum được release workflow sinh tự động khỏi Black để branch không tự sửa payload đã ký hash.

### Kiểm tra
- Runtime source khớp byte-for-byte 54 file trong verified sdist; không còn tham chiếu active `2.3.0` hoặc `2.3.1` ngoài changelog/memory lịch sử.
- Compileall, Ruff, Black in-process 45 file, mypy 45 source file và 5/5 pytest đều đạt; Twine strict và distribution verifier đạt cho wheel/sdist production.
- Isolated build bằng Hatchling 1.32.0 đạt; wheel build thử có toàn bộ member/content giống wheel production, nhưng không dùng để upload vì archive bytes khác.
- Replacement wheel SHA-256: `f7ea64c950b646b8c284086cd52b84d0825162f9f7d67b7a1880ca2433477832`; sdist SHA-256: `59f83b05167d4ebd3fa2d8a273817ab513c76faaa6e60ea5b46c41c1732dc8c7`.
- PyPI JSON trả đúng version `2.3.2`, đúng hai file/hash/kích thước, không bị yanked; public wheel/sdist tải lại khớp byte-for-byte với GitHub Release replacement.
- Fresh install trực tiếp từ `https://pypi.org/simple` đạt; `pip check`, import/version, canonical owner `m008v/fbchat-v2`, năm bridge checksum và distribution verifier đều đạt.

### Việc còn lại
- Không còn bước phát hành 2.3.2. PyPI hiện không có PEP 740 provenance vì upload cục bộ bằng Twine/token; tính toàn vẹn vẫn được đối chiếu bằng SHA-256 với artifact GitHub đã attest.
- Chưa chạy smoke bằng tài khoản Facebook thật; cần credential và hoạt động provider được cho phép riêng.

## 2026-09-07 — Đồng bộ tài liệu Facebook features & _reactionPost.py
- Viết mới và cập nhật toàn diện hệ thống tài liệu `README.md` liên quan đến `fbchat_v2._features._facebook`.
- Tạo mới `src/fbchat_v2/_features/_facebook/README.md` và `README_EN.md` tài liệu hóa 13 module cá nhân kèm tiêu điểm `_reactionPost.py` (bảng cảm xúc, alias, telemetry, chuẩn hóa Base64 target ID, code mẫu).
- Cập nhật cấu trúc thư mục, public API `__all__`, hướng dẫn `_reactionPost.py` và `_unFriend.py` vào `src/fbchat_v2/_features/README.md` & `README_EN.md`.
- Làm nổi bật `_reactionPost` tại root `README.md` & `README_EN.md`.
- Quét sạch mojibake và xác minh pass 100% `ruff check src tests` và `black --check src tests`. Đã commit và push `origin/pypi` (`bb5a956`).

## 2026-09-07 — Phát hành PyPI v2.3.1

### Mục tiêu
- Port module _reactionPost.py và cập nhật __init__.py sang checkout đóng gói fbchat-v2-pypi, bump version lên v2.3.1, push nhánh pypi và publish lên PyPI.

### Đã thực hiện
- Sao chép _reactionPost.py sang src/fbchat_v2/_features/_facebook/_reactionPost.py, chuẩn hóa namespace imports sang fbchat_v2._core._utils.
- Cập nhật export _reactionPost, _archivePost, _deletePost trong src/fbchat_v2/_features/_facebook/__init__.py.
- Bump version lên 2.3.1 trong pyproject.toml, src/fbchat_v2/_core/__init__.py.
- Decouple BRIDGE_RELEASE_VERSION trong _listening_e2ee.py để phiên bản bridge (2.3.0) có thể hoạt động độc lập với patch version của Python package mà không bị fail runtime check.
- Cập nhật CHANGELOG.md và test assertions trong tests/test_packaging_regressions.py.
- Xác minh: 5/5 pytest pass, Ruff pass, Mypy pass (44 source files), Twine strict pass.
- Commit feat(facebook): add reactionPost feature and bump to v2.3.1 và push lên origin/pypi.
- Build và upload hai distribution fbchat_v2-2.3.1-py3-none-any.whl và fbchat_v2-2.3.1.tar.gz lên PyPI qua Twine với API token trong keyring.
- Xác nhận release live tại https://pypi.org/project/fbchat-v2/2.3.1/.

## 2026-08-29 — Hoàn tất phát hành PyPI v2.3.0

### Mục tiêu
- Phát hành hai distribution đã xác minh của `fbchat-v2==2.3.0` lên PyPI và kiểm tra cài đặt trực tiếp từ registry.

### Đã thực hiện
- Nạp API token qua Windows keyring, không đưa credential vào source, command line hoặc log.
- Build lại wheel và sdist bằng Hatchling 1.27.0 để giữ metadata 2.4 cho sdist; wheel cuối được dựng từ sdist và khớp artifact đã attest.
- Upload wheel và sdist bằng Twine 7.0.0 lên `https://upload.pypi.org/legacy/`.
- Xác minh release công khai tại `https://pypi.org/project/fbchat-v2/2.3.0/` và clean-install trực tiếp từ PyPI.

### Quyết định kỹ thuật
- Không dùng artifact build cô lập đầu tiên vì dependency drift sinh metadata 2.5 mà Twine 6.2.0 cũ không đọc được; dùng toolchain release có phiên bản rõ ràng và Twine 7.0.0 để kiểm tra artifact cuối.
- Không upload các artifact 2.1.6 còn sót trong `dist/`; chỉ upload đúng hai file trong `.artifacts/publish-final`.
- Giữ token trong keyring; không tạo `.pypirc` chứa secret trong repository.

### Kiểm tra
- Ruff, Black, mypy 43 source file và 5/5 regression test package đều đạt.
- Twine strict đạt cho cả hai artifact; audit không phát hiện config, token, cache, test hoặc binary bị nhúng.
- Wheel SHA-256: `85834073ee11be664a83f3e2db13a6d70fad47f7577605e2c6c4552dacefc1b5`.
- Sdist SHA-256: `69750e05846fcab08a590d76a21736161fb6021eb954a4e230b3bd6e80572e07`.
- PyPI JSON trả đúng hai hash; fresh install `fbchat-v2==2.3.0`, `pip check`, import và version smoke đều đạt.

### Việc còn lại
- Nên pin build backend trong quy trình release để dependency drift không tiếp tục đổi metadata hoặc tính tái lập của artifact.

## 2026-08-29 — Đồng bộ refactor v2.3.0 và phát hành PyPI

### Mục tiêu
- Đồng bộ runtime refactor từ `fbchat-v2/main` sang checkout đóng gói `fbchat-v2-pypi`, push nhánh `pypi` và phát hành distribution `fbchat-v2==2.3.0`.

### Đã thực hiện
- Port 47 file tracked từ source commit `5f36a2c4f39e23c9bac6bbee9587bd225e7d17d5` vào `src/fbchat_v2`, gồm 42 file cập nhật và 5 module mới.
- Giữ public namespace `fbchat_v2.*` của các bản PyPI trước; cập nhật metadata, README VI/EN, CHANGELOG, hướng dẫn packaging và license classifier sang Apache-2.0.
- Sửa blocking listener gọi nhầm coroutine bằng `func_blocking()` dùng HTTP client sync; thêm regression test.
- Anchor allowlist sdist để không kéo README/LICENSE từ `.venv*`, cache, test hoặc artifact cũ vào package.
- Commit release `d0ec36ad9e3e9589e46e9e6c42caa6840e1f1a23` (`feat(pypi): publish refactored v2.3.0 package`) đã push fast-forward lên `origin/pypi`.
- Xác minh đủ năm bridge asset của GitHub Release `v2.3.0`, bind SHA-256 vào package, sửa downloader dùng canonical repository `m008v/fbchat-v2` và nhận diện đúng layout `src/fbchat_v2`.
- Commit corrective `bb5c814aab0e533955b17cda1444444e7afd4a86` (`fix(e2ee): bind canonical v2.3.0 bridge release`) chứa runtime fix, test và tài liệu liên quan.

### Quyết định kỹ thuật
- Không merge hai branch vì `pypi` và `main` không có common ancestor; dùng corrective snapshot commit trên lịch sử riêng của `pypi`.
- Không copy `src/config.json`, `.venv*`, `dist/`, cache, source test script hoặc Go submodule.
- Không tự tạo, di chuyển hoặc force-update tag. Tag/Release công khai `v2.3.0` xuất hiện trong lúc làm và trỏ đúng source `5f36a2c`; package `pypi` chỉ dùng các asset đã attest, không rerun job PyPI của main vì artifact đó làm vỡ namespace `fbchat_v2`.
- Checkout đóng gói không có Go source nên dùng cache được xác minh; checkout canonical có `bridge-e2ee/` vẫn giữ stale-build guard. `FBCHAT_E2EE_BIN` tiếp tục là override thủ công và fail-closed.

### Kiểm tra
- Fresh CPython 3.11: compileall, Ruff, Black và mypy 43 source file đều đạt; 144/144 runtime test source đã namespace-hoá và 5/5 regression test package đạt. Validation copy thay fixed sleep 100 ms bằng polling tối đa 1 giây cho một test startup subprocess Windows; production code không đổi vì file thật xuất hiện muộn với đúng request.
- Tải live Windows bridge qua chính downloader, xác minh SHA-256 `8dcd8ae81c4f74de805b11070b372de9efe99205b29f48fbd6e2eef89e6520dc`, rồi RPC `hello` trả protocol `1`, bridge `2.3.0` và đủ năm capability.
- Wheel/sdist final build sạch, Twine strict, member/metadata audit, không nhúng binary, namespace smoke, `pip check` và fresh-install riêng từng artifact đều đạt; wheel smoke thêm trên Python 3.10 và 3.13.
- Final wheel `85834073ee11be664a83f3e2db13a6d70fad47f7577605e2c6c4552dacefc1b5`; sdist `8f77cb23a7b800087315f49c1f5a224a6219e7c280c77527a68b8d5c98948bad`. Wheel dựng lại từ sdist có cùng SHA-256 với final wheel.

### Việc còn lại
- Upload PyPI đang chờ credential: Twine chạy non-interactive với username `__token__` đã dừng trước upload bằng lỗi `Credential not found for API token`; máy không có `.pypirc`, biến môi trường token hoặc GitHub CLI để dùng secret.
- PyPI `2.3.0` vẫn chưa tồn tại sau lần thử an toàn. Không rerun GitHub job từ tag main: job OIDC đang `invalid-publisher` và artifact của nó dùng namespace top-level sai contract. Khi credential được nạp, upload đúng hai artifact trong `artifacts-bound-final3`, rồi xác minh PyPI JSON và clean-install trực tiếp từ PyPI.
