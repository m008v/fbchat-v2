# Agent Memories

## 2026-10-15 — Media ACL, bounded logs, typing cancellation và E2EE soak

### Mục tiêu
- Triển khai bốn follow-up được chọn: bảo vệ media plaintext temp, giới hạn
  log buffer, typing cancellation, kiểm chứng E2EE payload/cold restart và
  soak có telemetry. Giữ version `2.3.3`, chưa phát hành.

### Đã thực hiện
- Media dùng helper private temp với DACL protected ngay từ creation trên
  Windows; test đi qua production helper và kiểm open handle trước plaintext.
- Typing yêu cầu connected/authenticated, dùng timeout 10 giây từ lifecycle
  context; test kiểm deadline, cancel/disconnect và giữ nguyên lỗi transport.
- Go/Python giữ tối đa 64 KiB mỗi raw log line, discard nguyên dòng quá cỡ,
  drain tới newline và phát diagnostic cố định; không log fragment. Python
  đọc chunk 4 KiB, giữ Unicode, EOF và tiếp tục sau JSON lồng sâu.
- Thêm `scripts/soak_e2ee.py` và regression test: peer opt-in theo nonce từng
  run, freshness/dedupe, ACK nonce riêng chỉ xuất hiện trong reply E2EE,
  media <=2 MiB được download/digest/echo, không retry uncertain send, cold
  restart dùng persistent device và fault injection đúng child process.
- CI base `6788b19` fail vulnerability step: pinned scanner tìm 9 reachable
  records. Nâng tối thiểu Go `1.26.9` + `golang.org/x/net v0.60.0`; không bỏ
  gate hoặc nâng dependency dây chuyền.

### Quyết định kỹ thuật
- Report chỉ lưu counter, boolean, RSS/queue/generation; không lưu chat ID,
  nội dung, khóa media, tên file gốc hoặc fingerprint identity. Device chứa
  secret nằm riêng trong thư mục ignored và không được đưa vào Git.
- `status=completed` chỉ nghĩa đủ thời gian; `acceptance_passed` cần đủ từng
  check, gồm xác nhận thật từ peer. Exit `2` là hoàn tất nhưng thiếu/fail check.
- Kill child bridge là fault injection crash, không phải test mất mạng thật;
  không suy diễn ít traffic thành bằng chứng không mất mọi message.

### Kiểm tra
- Full Python `287 passed`; targeted soak `19 passed` sau ACK hardening; Ruff,
  Black 119 file, mypy legacy/scripts 49 file + canonical 45 file, compileall
  và canonical sync đạt.
- Full Go test/vet/mod verify, native Windows ACL/typing và log storm tests đạt.
  Pinned `govulncheck@v1.8.0` báo 0 reachable vulnerabilities sau bản vá; còn
  một record ở module không import/call. POSIX/race cần CI Linux.
- Rebuild binary Go 1.26.9, native RPC version 2.3.3 đạt.
- Wheel/sdist hardening 2.3.3 build được, Twine 7 strict và distribution
  verifier sau cài thử riêng từng artifact đều đạt.
- Live run `.tmp/e2ee-soak-20261015-1329`, driver PID ban đầu `13552`, ready lúc
  13:29:54 Asia/Saigon. Cold restart đã reuse cùng identity, sample đầu regular
  và E2EE connected, queue drop 0. Peer roundtrip và soak 2 giờ vẫn đang chạy.

### Việc còn lại
- Đọc report cuối sau khoảng 15:30 Asia/Saigon; chưa được gọi soak pass trước
  khi có duration, shutdown và từng acceptance check. Người dùng đã đồng ý
  gửi challenge E2EE, ảnh và file khi listener ready.
- Auto-review từ chối tạo heartbeat vì chưa có yêu cầu rõ cho lịch persistent;
  chưa tạo automation. Process soak tự chạy và ghi report local.
- Không tag, GitHub Release hoặc upload PyPI. Giữ nguyên `.vs/`.

## 2026-10-15 — Ổn định LightSpeed DB1 và E2EE cho v.2.3.3

### Mục tiêu
- Khôi phục bot thử nghiệm nhận/trả lời group qua Go LightSpeed, sửa bootstrap
  E2EE, chia timeout startup, che log nhạy cảm và chuẩn bị source version
  `2.3.3` với tên GitHub Release dự kiến `v.2.3.3`.

### Đã thực hiện
- Cập nhật submodule `bridge-e2ee/meta` lên flow DGW/LightSpeed V4 có sync
  `databaseID=1`; thích nghi event, table, media và Whatsmeow store API mới.
- Sửa pairing transaction để đăng ký/lưu device trước khi tạo E2EE client;
  thêm rollback test và persistence cho privacy token/NCT salt.
- Thêm redaction Python/Go cho cookie, token, provider ID, JID, thread name,
  URL, cursor, payload/data và XML crypto; giữ `database_id` phục vụ debug.
- Tách timeout theo contract/new client/regular/E2EE connect-ready, giữ
  exception gốc qua `__cause__`, và sửa `wait_until_connected()` chờ đúng
  watchdog generation sau reconnect.
- Bot/demo bắt buộc E2EE; group regular reply qua Go LightSpeed, không fallback
  sang Python MQTT. Chuẩn hóa console UTF-8, onboarding và namespace
  `fbchat_v2`.
- Đồng bộ package, bridge, workflow, verifier, docs, tests và canonical
  namespace lên `2.3.3`; release workflow dùng tag kỹ thuật `v2.3.3` nhưng đặt
  tên hiển thị `v.2.3.3`; thêm changelog và release note tương ứng.

### Quyết định kỹ thuật
- Giữ tag SemVer `v2.3.3` để không phá release validator và asset resolver;
  dấu chấm sau `v` chỉ thuộc tên hiển thị GitHub Release.
- Không hạ cấp E2EE sang Python MQTT khi group regular có sự cố; cùng Go bridge
  chịu trách nhiệm receive/send để canary phản ánh đúng production path.
- Không đọc hoặc ghi cookie vào source/log; live probe chỉ dùng credential nội
  bộ và không in ID thật.

### Kiểm tra
- Canary clone: DB1 sync, E2EE ready, nhận `ping`, gửi trước reconnect, kill
  đúng child bridge, watchdog respawn attempt đầu, E2EE reconnect và gửi lại
  qua Go LightSpeed đều đạt.
- `258 passed`; Ruff, Black 117 file, mypy legacy 48 file/canonical 45 file,
  compileall, canonical sync, Go test/vet/mod verify và gofmt first-party đạt.
- Release binary 2.3.3 qua native JSON-RPC smoke; wheel/sdist 2.3.3 qua Twine
  7 strict và fresh-install distribution verifier riêng biệt.
- `git diff --check`, strict UTF-8, mojibake và secret/diff scope được kiểm tra
  trước commit.

### Việc còn lại
- Chưa tạo tag, GitHub Release hoặc upload PyPI theo yêu cầu của người dùng.
- CI đa nền tảng và Go race vẫn cần chạy trên commit đã push; local Windows
  không thay thế bằng chứng đó.
- Canary hiện chứng minh E2EE authenticated/ready và regular Go LightSpeed
  receive/send/reconnect; chưa có bằng chứng payload E2EE hai chiều hoặc cold
  restart dùng lại persistent device. Driver canary dùng `e2ee_memory_only=True`.
- Ưu tiên tiếp theo: media plaintext temp dùng `createPrivateTempFile` để có
  DACL Windows từ lúc tạo; typing dùng context có timeout từ `c.ctx`; giới hạn
  log line/buffer ở Go writer và Python stderr reader. Mới phân tích code,
  chưa triển khai các thay đổi này.

### Git
- Sau yêu cầu trực tiếp “push đi”, commit source
  `31262eb70ebacf3047e5c2510624d0753b7d1417` đã push fast-forward lên
  `origin/main`; `git ls-remote` xác nhận cùng SHA.
- CI run `38689231679` được tạo cho đúng commit, đang chạy tại lúc kiểm tra.
  Không dispatch release workflow, không tạo tag và không upload PyPI.
- `.vs/` tiếp tục được giữ nguyên, không đưa vào commit.

## 2026-09-15 — Hoàn tất replacement release và PyPI v2.3.2

### Mục tiêu
- Sửa blocker live E2EE downloader, đồng bộ toàn bộ version `2.3.2`, thay release/tag đã tạo sai, đồng bộ checkout `fbchat-v2-pypi` và phát hành đúng artifact lên PyPI.

### Đã thực hiện
- Dùng một canonical repository constant `m008v/fbchat-v2` cho cả GitHub API và strict asset path; cập nhật regression test ở hai namespace source.
- Commit `981d0996db0a01af45526f8270d83559d5a3ef2e` (`fix(e2ee): use canonical release repository`) đã push lên `origin/main`.
- Theo lựa chọn thay thế release của người dùng, xóa release cũ, force-with-lease tag `v2.3.2` từ `a90f940` sang `981d0996`, rồi workflow tạo release ID `388898995` với chín asset mới.
- Đồng bộ verified sdist sang checkout `fbchat-v2-pypi`, push commit source `700890d301c4a697b77cc2bbc7f72f6998333d5b` và commit memory hậu phát hành `a8c10b377ea95a0afb0b841522277793296d6a04` lên `origin/pypi`, rồi upload exact replacement wheel/sdist lên PyPI.

### Quyết định kỹ thuật
- Không rebuild artifact từ branch `pypi`; chỉ publish đúng byte của GitHub Release đã qua CI và attestation, tránh cùng version nhưng khác payload.
- Upload PyPI cục bộ bằng token trong Windows keyring vì Trusted Publisher hiện chưa cấu hình; token không xuất hiện trong source, argument hoặc log.

### Kiểm tra
- Full Python test `251 passed`; Ruff, Black, mypy cho cả legacy/canonical, compileall, Go test/vet/race CI, native RPC và distribution gates đều đạt.
- Workflow run `34934791316` thành công 20/20 job tại đúng SHA `981d0996`; release/tag/main remote cùng trỏ SHA đó.
- Wheel SHA-256 `f7ea64c950b646b8c284086cd52b84d0825162f9f7d67b7a1880ca2433477832`; sdist SHA-256 `59f83b05167d4ebd3fa2d8a273817ab513c76faaa6e60ea5b46c41c1732dc8c7`.
- Public PyPI trả đúng hai file/hash, không yanked; fresh install trực tiếp từ registry, `pip check`, import/version/owner/checksum và distribution verifier đều đạt.
- Exact Windows release binary qua RPC; production `_download_bridge` từ exact installed wheel tải đúng asset live và RPC smoke đạt.

### Việc còn lại
- Chưa chạy smoke bằng tài khoản Facebook thật vì chưa có quyền hoạt động provider/credential; không suy diễn CI thành bằng chứng live Messenger.
- PyPI file đang có `provenance=False` do upload Twine/token; byte vẫn khớp SHA-256 với artifact GitHub replacement đã attest.

- 2026-09-07: Sửa lỗi CI release validation tag `v2.3.1` bị fail (`Release tag 'v2.3.1' không khớp package version 'v2.3.0'`). Nguyên nhân do release tag `v2.3.1` được tạo khi repo `fbchat-v2` (`main`) vẫn còn mang version metadata `2.3.0`. Đã đồng bộ toàn bộ 12 file: `pyproject.toml`, `src/_core/__init__.py`, `bridge-e2ee/main.go`, `scripts/verify_distribution.py` (thêm kiểm tra `_reactionPost`), `.github/workflows/quality-gate.yml`, `.github/workflows/release.yml`, `tests/test_release_artifacts.py`, `tests/test_e2ee_bridge_lifecycle.py`, `CHANGELOG.md`, `DOCS.md`, `README.md` & `README_EN.md`. Rebuild Go bridge binary với `main.bridgeVersion = 2.3.1` và chạy pass smoke test RPC, pass 149/149 pytest, pass Go test/vet, pass `release_artifacts.py validate --release-tag v2.3.1`. Đã commit `fix(release): align package version to 2.3.1 for release tag validation` (`3e7676c`), push lên `origin/main` và force-push tag `v2.3.1` trỏ thẳng tới commit mới.
- 2026-09-07: Viết mới và cập nhật toàn diện hệ thống tài liệu `README.md` liên quan đến `_features._facebook`. Đã tạo mới `src/_features/_facebook/README.md` và `README_EN.md` tài liệu hóa 13 module cá nhân kèm tiêu điểm `_reactionPost.py` (bảng cảm xúc, alias, telemetry, chuẩn hóa Base64 target ID, code mẫu); cập nhật cấu trúc thư mục, public API `__all__`, hướng dẫn `_reactionPost.py` và `_unFriend.py` vào `src/_features/README.md` & `README_EN.md`; làm nổi bật `_reactionPost` tại root `README.md` & `README_EN.md`. Đồng bộ toàn bộ tài liệu sang repo `fbchat-v2-pypi`, quét sạch mojibake và pass 100% `ruff check`/`black --check`. Đã commit chuẩn conventional commit `docs(readme): add facebook features documentation and spotlight reactionPost` và push lên cả `fbchat-v2` (`main` `69136c2`) và `fbchat-v2-pypi` (`pypi` `bb5a956`).
- 2026-09-07: Sửa lỗi CI gate GitHub Actions `black --check src tests scripts` bị fail do thiếu trailing comma trong `__init__.py` và line length quá 88 ký tự trong `_reactionPost.py`. Đã format chuẩn bằng `black` trên cả repo `fbchat-v2` (`c394ec2`) và `fbchat-v2-pypi` (`dc2fc23`), xác minh `black --check` và `ruff check` pass 100%.
- 2026-09-07: Soạn thảo và thêm tài liệu release `.github/RELEASE_NOTES_v2.3.1.md` bao quát tính năng mới `_reactionPost`, sửa telemetry chống checkpoint tài khoản, đồng bộ export `__all__`, sửa lỗi CI linter F401 và hướng dẫn cài đặt/nâng cấp. Đã commit `docs(release): add v2.3.1 release notes` (`2039fd7`) và push lên `origin/main`.
- 2026-09-07: Sửa lỗi CI gate GitHub Actions nhánh `main` bị fail tại bước `ruff check src tests scripts` do import `random` không sử dụng trong `src/_features/_facebook/_reactionPost.py` (lỗi F401). Đã gỡ bỏ import thừa, kiểm tra lại full test (149/149 pytest) và ruff pass 100%, commit `fix(facebook): remove unused random import in reactionPost` và push lên `origin/main`.
- 2026-09-07: Đồng bộ `_reactionPost.py` và `__init__.py` sang checkout `fbchat-v2-pypi`, bump version lên `v2.3.1`, push nhánh `pypi` và publish thành công lên PyPI (`fbchat-v2==2.3.1`). Build wheel và sdist đạt Twine strict, không chứa file rác/cache; upload hoàn tất và live tại `https://pypi.org/project/fbchat-v2/2.3.1/`.
- 2026-09-07: Rà soát và hoàn thiện module `_reactionPost.py` trong `src/_features/_facebook`. Đã sửa lỗi cú pháp f-string đặt nhầm trên dict key khiến biến attribution `time` và `jazoest` không được evaluate (Ruff F401/F541), loại bỏ khối tracking base64 thừa, sửa `feedback_referrer` từ trang 2FA thành profile hợp lệ để tránh checkpoint telemetry từ Facebook; chuẩn hóa input reaction type (case-insensitive) và hàm resolve `feedback_id`; bổ sung try-except đầy đủ cho async transport; đồng bộ export trong `__init__.py`. Xác minh Ruff check, py_compile và UTF-8 sạch hoàn toàn, không mojibake.
- 2026-08-20: Fixed the release/v2.2.2 GitHub Actions Python gate after run 32290786845. Added repository-root pytest import coverage, switched CI to `python -m pytest`, made response/exception unions explicit for latest mypy, and upgraded pinned official setup actions to Node 24 majors. Verified in a fresh CPython 3.10.20 editable environment: 149/149 pytest, mypy 2.3.1 over 48 files, Ruff, Black, compileall, actionlint, workflow YAML, diff-check, UTF-8/mojibake and secret scans all passed. Committed exactly 6 files as `871d6313695406a292fa804816d6a753da3ccb0d` (`fix(ci): make Python quality gate reproducible`) and pushed to `origin/release/v2.2.2`; local and remote SHAs matched. `src/config.json` was neither read nor staged. The temporary validation venv was moved to the Recycle Bin.
- 2026-08-20: Commit và push toàn bộ 30 file hardening v2.2.2 lên `origin/release/v2.2.2` bằng commit conventional `7f73c67b3f38a348937cb334076a282e4e824c66` (`fix(release): harden v2.2.2 runtime and quality gates`). Trước push đã fetch và xác nhận local/remote cùng nền `cbdd8fb`, kiểm đúng danh sách 21 file sửa + 9 file mới, không stage `src/config.json`, `AGENT_MEMORYs.md` hoặc `build/`. Gate cuối đạt 149/149 pytest, mypy 48 file, Ruff/Black, Go test/vet, native bridge RPC, YAML, diff-check, UTF-8/mojibake và secret scan 30/30. Sau push đã fetch lại và xác nhận HEAD khớp chính xác remote, worktree tracked sạch.
- 2026-08-20: Hoàn tất ba trụ hardening được chọn cho `release/v2.2.2`. Đã sửa toàn bộ ranh giới sync/async thật, khôi phục tương thích CPython 3.10 và mở mypy sang toàn bộ `src`/`scripts`; viết lại lifecycle/watchdog E2EE theo generation với RPC `hello`, readiness socket + đăng nhập thật, recovery transaction, deadline tổng, reader/writer chống pipe treo, short-write, payload sai kiểu và shutdown race; bổ sung fallback an toàn khi Messagix phát socket error không kèm `Err`. CI/release nay dùng reusable quality gate cho mọi PR, `release/**`, tag và merge queue, có Python 3.10-3.14, Go race trên Linux, native JSON-RPC ba hệ điều hành, wheel/sdist, Twine strict và kiểm tra năm checksum bridge trước publish. Xác minh cuối: 149/149 pytest, lifecycle 28/28 x5, mypy 48 file, Ruff/Black/compileall, CPython 3.10.20, Go test/vet + stress, native bridge smoke, wheel/sdist fresh-install, YAML, UTF-8/mojibake, secret scan và diff-check đều đạt. Không đọc `src/config.json`, không đụng process real-account đang chạy, không commit/push; thư mục tạm package smoke đã chuyển vào Recycle Bin.
- Fixed SyntaxError in src/_core/_http.py caused by placing `from __future__ import annotations` after a second docstring.
- Fixed Mermaid syntax error in FLOWCHART.md caused by using the reserved keyword loop as an actor name.
- Restored missing EN/VI language switch button in website/index.html and added missing JS logic to website/script.js to toggle lang attribute dynamically.
- Fixed the excessive white space above the hero section by setting padding-top: 0 for .doc-section:first-child in website/style.css.
- Extracted and injected English translations for all missing h2, h3, sidebar links, and headings in website/index.html via a Python replacement script to make the UI completely bilingual.
- Ran a secondary deep extraction script to translate ~100 remaining small text snippets (paragraphs, table cells, feature grids, list items) to fully complete the EN translation of website/index.html.
- Fixed the final batch of deeply nested list items and corrupted duplicate strings (e.g. docs(website)) inside the release checklist that had inline tags.
- Fixed missing translations and mangled Vietnamese strings in website/index.html across 174 elements (including text nodes outside spans and Python code blocks).
- Fixed a bug where the language toggle button was wrapped in language spans, causing it to become unclickable in English mode because the JS event listener was bound to the hidden element.
- Restored missing Contributors and Conduct sections in the documentation with full bilingual support, grid layouts, and active sidebar scrolling integration.
- Fixed missing serif font on newly added section titles by restructuring their HTML to use header tags.\n- Fixed hero buttons layout on mobile to be horizontal (side-by-side) instead of stacked, and updated primary button color to black.\n- Fixed issue where the V2 badge next to the fbchat logo in the header was hidden on mobile devices (< 440px) by removing its display:none rule in the media query.\n- Added JavaScript code to fetch the latest fbchat version dynamically from the GitHub releases API and update the DOM accordingly.\n- Fixed a SyntaxError in script.js caused by a literal newline character that broke JavaScript execution, restoring the live star counter and dynamic version fetching.\n- Fixed issue where GitHub API returned a malformed tag name ('v.2.2.1') by adding JavaScript logic to normalize it to standard semantic versioning format ('v2.2.1').\n- Fixed a visual bug in the status pill by updating CSS selector from .status-pill > span to .status-pill > span:first-child.\n- Promoted the owner (MinhHuyDev) to a prominently styled box at the top of the Community section and added a full Github avatar, replacing the previous sub-heading and old grid item.\n- Fixed a CSS syntax error (literal newline) that prevented the new owner box styles from applying, which caused the avatar and text to stack vertically without a box.\n- Added Hakiraxx as a Co-owner next to MinhHuyDev in the Community section by wrapping them in a flex container and adding the corresponding HTML/CSS.\n- Updated the CSS for contributor letter avatars to use a boxed style (border, background, and rounded corners) similar to the owner avatars.\n- Added a sleek full-page loading spinner that fades out on window load, and a skeleton loading animation for the dynamic GitHub version and star counter elements.\n- Updated the Github stars target from 1000 to 199 in both HTML and JS.\n- Fixed a JS syntax error caused by a literal newline that broke the EN/VI and Theme switchers, and caused the version and star texts to remain invisible (skeleton class not removed).\n- Changed the default theme from system to light in both HTML inline script and JS.\n- Fixed a SyntaxError in script.js (line 143) that broke the star counter, dark mode, and language toggles.\n- Fixed invisible dynamic version text by removing the skeleton class after DOM injection.\n- Changed the default theme to light.\n- Hardcoded the Github star counter to 199 as requested instead of dynamically fetching the actual count.\n- Reduced the target GitHub star count from 1000 to 200 in both script.js and index.html to reflect the hardcoded 199 star display more accurately.\n- Restored realtime GitHub star fetching from the API in script.js as the user clarified they did not want it hardcoded.\n- Replaced the canonical URL in index.html to point to the custom domain (https://nqminkhuy.com/fbchat/).
- Created scripts/standardize_releases.py to automatically batch update and normalize all 31 legacy GitHub release titles into semantic versioning format (vX.X.X).\n
- 2026-08-18: Đánh giá lại toàn bộ fbchat-v2 ở commit 2e63bfe (92 file). Không sửa source, không commit/push. Xác minh 67/67 pytest, Go test/vet và JavaScript syntax đều đạt; phát hiện các blocker phát hành gồm 7 file Python không compile do future import, wheel đóng gói sai namespace, mutation báo thành công giả, async disconnect không dừng listener, RNG E2EE không an toàn, DeviceStore no-op, auto-download bridge fail-open và persistence race. Đã tạo knowledge graph hợp lệ với 573 node, 1.033 edge, 8 layer, 10 tour step và fingerprint baseline 92 file; kiểm tra mojibake trước khi bàn giao.

- 2026-08-19: Sửa toàn bộ blocker review fbchat-v2 và bump bản vá lên 2.2.1. Python đã sửa 7 lỗi compile, mutation false-success, async disconnect, log riêng tư, ACL config, updater bridge pin tag/checksum và wheel namespace; CI/release thêm quality matrix, smoke install, checksum và provenance. Go E2EE chuyển sang crypto/rand, persistence transaction atomic có rollback, lưu đầy đủ device metadata, lifecycle connect/disconnect an toàn, callback không chặn ratchet và cấm hạ cấp E2EE sang transport thường. Xác minh 93/93 pytest, Ruff/Black/mypy/compileall, wheel + editable fresh install, Go test/vet + stress lifecycle, Node syntax, YAML, diff và mojibake đều đạt. Không commit/push.

- 2026-08-19: Đổi planned release của toàn bộ đợt hardening từ 2.2.1 sang 2.2.2. Đồng bộ pyproject, fallback __version__, distribution verifier, README VI/EN, DOCS, CHANGELOG, release workflow và đổi tên release notes thành RELEASE_NOTES_v2.2.2.md; giữ nguyên lumberjack v2.2.1 vì đó là dependency Go. Build/fresh-install wheel fbchat_v2-2.2.2 thành công, 93/93 pytest và toàn bộ quality/version/mojibake checks đều đạt. Không commit/push.

- 2026-08-20: Sửa lỗi SimpleBot không nhận/trả lời message dù vẫn thấy typing/readReceipt/reaction. Lọc event phụ ngay trên listener thread trước asyncio, tách control event khỏi queue message, thêm overflow telemetry đã che nội dung và dedupe command không bị placeholder đầu độc. Bridge phát standalone upsert live có cutoff trượt/chống replay, cho authoritative insert nâng cấp placeholder cùng ID, đăng ký handler E2EE trước connect, báo lỗi undecryptable, không mutate raw table và không emit trùng message thiếu ID. Source checkout giờ phát hiện binary Go cũ bằng freshness guard; đã rebuild build/fbchat-bridge-e2ee.exe và xác minh RPC. Kết quả: 107/107 pytest, Ruff/Black/mypy/compileall, go test/vet và stress event pipeline đều đạt; quét mojibake sạch. Không đọc config/cookie, không commit/push.

- 2026-08-20: Đã commit bản sửa pipeline nhận tin nhắn bằng `fix(messaging): restore incoming message delivery` tại `cbdd8fb490a3433f7e202d6d9720041145f63e0c` và push thành công lên `origin/release/v2.2.2`. Trước khi push đã xác minh đúng 7 file staged, `src/config.json` được ignore và không tracked, không có secret hoặc mojibake trong diff, 107/107 pytest đạt, Ruff/Black/compileall đạt, Go test/vet và gofmt đạt; local HEAD khớp chính xác remote branch sau push.

- 2026-08-20: Rà soát read-only bước tiếp theo cho `release/v2.2.2` tại `cbdd8fb`. Kết luận chưa nên tag: full mypy trên 45 file phát hiện 37 lỗi, trong đó xác nhận các hàm blocking ở `_createNotes.py`, `_changeTheme.py`, `_listening.py` gọi coroutine sai; `_core/_types.py` không tương thích Python 3.10. Phát hiện thêm cleanup startup nằm ngoài `finally`, watchdog có thể kẹt/crash-loop, health check Go báo theo context thay vì socket thật, chưa có protocol handshake và bridge event queue Python không giới hạn. CI không chạy trên push branch release/tag và release workflow chưa tái chạy quality gate hoặc smoke artifact sau khi nhúng checksum; Go coverage hiện 31,9% cho bridge và 0% cho main. Roadmap: sửa runtime blockers, dựng release gate + RPC contract test đa nền tảng, cập nhật changelog/release notes/API docs, chạy canary thật rồi mới merge/tag. Không đọc `src/config.json`, không sửa source và không commit/push.

- 2026-08-20: Gia cố lifecycle/watchdog E2EE cho v2.2.2. `SimpleBot` luôn cleanup listener khi readiness timeout/lỗi và vẫn truyền cancellation; listener single-use, startup fail closed và chỉ publish readiness sau watchdog. Bridge thêm RPC `hello` với protocol/version/capabilities; regular socket theo event thật, E2EE bắt buộc vừa connected vừa logged-in. Watchdog cô lập generation, khóa RPC ngoài suốt respawn/replay, áp total deadline, kill/recover process treo hoặc reader/writer chết, dùng writer queue riêng có full-write/short-write/cancel/taint semantics, chỉ reset retry sau uptime ổn định và không respawn sau close. Thêm 28 test hermetic cho hang, blocked pipe, malformed JSON/RPC, replay, crash-loop, close/concurrent-start race và state flags cùng Go health/contract tests; full 149 pytest, full mypy 48 file, Ruff/Black/compileall, Go test/vet và native binary smoke đều đạt. `go test -race` local chưa chạy được vì Windows thiếu CGO/GCC; CI Linux chịu trách nhiệm race gate. Không đọc `src/config.json`, không commit/push.

- 2026-08-20: Dựng release gate tái sử dụng cho v2.2.2. CI chạy trên mọi PR, push `release/**`, tag, merge queue và manual; gate gồm Python 3.10-3.14, full mypy, wheel/sdist smoke, Go test/vet/race và native bridge JSON-RPC trên Linux/Windows/macOS. Release bắt buộc qua gate, build đúng 5 binary với version từ tag, bind và đối chiếu SHA256SUMS trong cả wheel/sdist, chạy Twine strict + fresh-install trước khi attest/upload/publish; toàn bộ action được pin SHA và checkout không giữ credential. Đã rehearsal đủ 5 binary + artifact cuối, actionlint, 133 pytest, full mypy, Go test/vet, UTF-8/mojibake và secret scan đều đạt. Không đọc `src/config.json`, không commit/push.

## 2026-08-29 — Tài liệu chuẩn bị release v2.3.0

### Mục tiêu
- Viết tài liệu release cho đợt hoàn thiện refactor codebase và lưu đúng convention trong `.github` với version `v2.3.0`.

### Đã thực hiện
- Thêm `.github/RELEASE_NOTES_v2.3.0.md` bằng tiếng Việt, bao quát runtime async, message pipeline, E2EE lifecycle, DeviceStore, bảo mật, migration, artifact, release gate và known limitations.
- Refresh remote refs và xác nhận PR #33 đã merge source refactor vào `origin/main` tại `b4afaa1`; release note dùng tag công khai gần nhất `v.2.2.1` làm baseline nội dung.
- Tạo `.understand-anything/diff-overlay.json` theo skill `understand-diff`; file nằm trong path đã ignore và không thuộc release diff.

### Quyết định kỹ thuật
- Gọi `v2.3.0` là bản hoàn thiện refactor và behavior-hardening, không quảng cáo lại archive/delete như feature mới; feature mới thực sự là `unFriend`.
- Giữ tài liệu ở trạng thái chuẩn bị phát hành vì metadata source, bridge và workflow vẫn pin `2.2.2`; tag `v2.3.0` hiện sẽ fail version validation nếu chưa đồng bộ.
- Không tuyên bố production-ready: CI source đã xanh, nhưng chưa có artifact `v2.3.0`, post-release clean install hoặc real-account canary 30–60 phút.

### Kiểm tra
- So sánh `v.2.2.1..origin/main`: 11 commit, 81 file, `+8443/-983`; đối chiếu source, test và workflow liên quan.
- Xác minh GitHub Actions run `33254435063` tại merge commit `b4afaa1` hoàn tất thành công 11/11 job.
- Kiểm tra release note: đúng filename workflow yêu cầu, code fence cân bằng, JSON mẫu hợp lệ, 6 link hợp lệ và không có trailing whitespace.
- Strict UTF-8, quét Unicode replacement character cùng các mẫu mojibake phổ biến, secret pattern và spot-check trực tiếp chuỗi tiếng Việt đều đạt trên release note cùng `AGENT_MEMORYs.md`.
- Commit scope chỉ có `.github/RELEASE_NOTES_v2.3.0.md`; `AGENT_MEMORYs.md` và diff overlay vẫn nằm trong path đã ignore.
- Commit `59024e766826731a0fd1a2559dac64d73a19b3dc` (`docs(release): add v2.3.0 release notes`) đã push fast-forward lên `origin/main`; local, tracking ref và `ls-remote` khớp tuyệt đối.
- GitHub Actions run `33255150673` cho commit tài liệu hoàn tất thành công 11/11 job: Python quality và 3.10–3.14, wheel/sdist, Go test/vet/race, native bridge RPC Linux/Windows/macOS.

### Việc còn lại
- Khi phát hành thật, đồng bộ toàn bộ version declaration sang `2.3.0`, chạy release workflow, kiểm artifact/checksum và thực hiện real-account canary.

## 2026-08-29 — Sửa version refactor thành v2.3.0

### Mục tiêu
- Sửa nhãn version bị ghi nhầm `2.2.2` thành `2.3.0` trên toàn bộ source, workflow, tài liệu và test đang hoạt động; đẩy bản sửa lên `main` mà không viết lại lịch sử Git đã chia sẻ.

### Đã thực hiện
- Đồng bộ project metadata, fallback runtime, Go bridge, distribution verifier, quality/release workflow, README VI/EN, DOCS, CHANGELOG và fixture test sang `2.3.0`.
- Xóa release note dự kiến `.github/RELEASE_NOTES_v2.2.2.md`; giữ `.github/RELEASE_NOTES_v2.3.0.md` làm nguồn tài liệu release duy nhất và cập nhật trạng thái chuẩn bị phát hành.
- Loại bỏ toàn bộ chuỗi `2.2.2` khỏi tracked tree. Không sửa dependency `gopkg.in/natefinch/lumberjack.v2 v2.2.1` vì đó là version độc lập.
- Commit `5f36a2c4f39e23c9bac6bbee9587bd225e7d17d5` (`fix(release): align refactor version to 2.3.0`) đã push fast-forward lên `origin/main`; SHA local, tracking ref và remote khớp tuyệt đối.

### Quyết định kỹ thuật
- Dùng corrective commit trên `main`; không force-push/rebase để sửa các commit message và branch lịch sử có tên `release/v2.2.2`.
- Giữ `src/_messaging/_bridge_checksums.py` ở trạng thái placeholder; release workflow sẽ bind version và checksum của năm binary vào staging package khi phát hành.

### Kiểm tra
- Fresh environment: compileall, Ruff, Black, mypy 48 file và 149/149 pytest đều đạt.
- Build wheel/sdist `2.3.0`, Twine strict, fresh-install riêng từng artifact và `verify_distribution.py` đều đạt; một lần tải dependency bị lỗi mạng tạm thời, retry thành công.
- Go test/vet, fallback build, release build với ldflags và native JSON-RPC smoke version `2.3.0` đều đạt; workflow YAML parse hợp lệ.
- `gofmt` không có khác biệt nội dung ngoài line ending CRLF hiện hữu; tracked tree không còn reference `2.2.2`.
- GitHub Actions run `33256141903` của đúng commit hoàn tất thành công 11/11 job: Python quality và 3.10–3.14, wheel/sdist, Go test/vet/race, native bridge RPC trên Linux, macOS và Windows.

### Việc còn lại
- Tag, artifact release, PyPI publish và real-account canary vẫn là bước phát hành riêng; chưa được suy diễn từ việc source CI đã xanh.

## 2026-08-29 — Chẩn đoán PyPI Trusted Publishing cho v2.3.0

### Mục tiêu
- Xác định nguyên nhân release `v2.3.0` thất bại tại bước publish PyPI.

### Đã thực hiện
- Kiểm tra live GitHub Actions run `33257352488`, job `99113736756` và đối chiếu `.github/workflows/release.yml`.
- Xác nhận OIDC token hợp lệ nhưng PyPI trả `invalid-publisher`; claim thực tế là owner `m008v`, repository `fbchat-v2`, workflow `release.yml` và không có environment.
- Đối chiếu hai run cũ `29657659421` và `29766272782`: cùng lỗi `invalid-publisher`, nên đây là cấu hình Trusted Publisher tồn đọng chứ không phải lỗi mạng tạm thời.

### Quyết định kỹ thuật
- Không sửa workflow hoặc di chuyển tag `v2.3.0`: job hiện tại đã có `id-token: write`, còn rerun luôn dùng workflow tại tag `5f36a2c`.
- Cách khôi phục ít rủi ro nhất là cấu hình publisher PyPI với owner `m008v`, repository `fbchat-v2`, workflow `release.yml`, environment để trống rồi rerun riêng failed job.
- Nếu PyPI còn publisher owner `MinhHuyDev`, cần xóa hoặc thay thế vì username này hiện trỏ tới account ID khác; không sao chép mù cấu hình cũ.

### Kiểm tra
- Toàn bộ quality gate, build, package smoke, provenance và upload GitHub Release đều đạt; chỉ publish PyPI thất bại.
- GitHub Release `v2.3.0` đã tồn tại; PyPI `fbchat-v2==2.3.0` trả HTTP 404 tại thời điểm kiểm tra.
- Worktree tracked sạch; không sửa source, workflow, tag, release, secret hoặc cấu hình external.

### Việc còn lại
- Maintainer PyPI cần cập nhật Trusted Publisher và rerun failed job trước khi artifact hết hạn.
- Với tag tương lai, có thể thêm GitHub environment `pypi` có protection rules và cấu hình cùng tên ở PyPI; thay đổi này không cứu được run `v2.3.0` hiện tại.

## 2026-08-29 — Gỡ PyPI publishing khỏi CI/CD

### Mục tiêu
- Ngừng hoàn toàn việc tự động publish package lên PyPI trong release workflow, nhưng giữ nguyên quality gate, build, provenance, artifact và GitHub Release.

### Đã thực hiện
- Xóa toàn bộ job `publish-pypi` khỏi `.github/workflows/release.yml`, gồm OIDC permission riêng của job, download artifact và `pypa/gh-action-pypi-publish`.
- Giữ `verified-python-distributions` làm workflow artifact nội bộ trong 7 ngày để tải thủ công khi cần; artifact này không được publish ra PyPI.
- Giữ hai quyền `id-token: write` còn lại vì chúng phục vụ `actions/attest-build-provenance`, không liên quan PyPI.

### Quyết định kỹ thuật
- Không sửa hoặc di chuyển tag `v2.3.0`; run cũ vẫn phản ánh workflow tại commit tag cũ và không nên được rerun.
- Thay đổi trên `main` áp dụng cho workflow mới và các tag tương lai; không tạo release/tag mới trong nhiệm vụ này.
- Không sửa README, changelog hoặc lịch sử release PyPI cũ vì phạm vi chỉ là hành vi CI/CD.

### Kiểm tra
- `actionlint v1.7.7` đạt trên `.github/workflows/release.yml`.
- YAML parse và structural assertions đạt: còn đúng năm job, không có `publish-pypi`, GitHub Release và artifact Python vẫn tồn tại.
- `scripts/release_artifacts.py validate --release-tag v2.3.0` và `git diff --check` đạt.
- Quét `.github/workflows` không còn `publish-pypi`, Trusted Publishing hoặc `gh-action-pypi-publish`.
- Strict UTF-8 và mojibake sẽ được kiểm tra lại trước commit/push.

### Việc còn lại
- Không còn việc CI/CD nào trong phạm vi này. Run release `v2.3.0` cũ vẫn đỏ theo lịch sử vì dùng workflow tại tag cũ; không rerun và không di chuyển tag.

### Git
- Commit `19e3a07261320f2bcbf784749b4efd06d8d08737` (`ci(release): remove PyPI publishing`) đã push fast-forward lên `origin/main`; local, tracking ref và remote SHA khớp tuyệt đối.
- GitHub Actions run `33261107135` của đúng commit hoàn tất `success`: toàn bộ 11/11 job đạt, gồm Python quality, Python 3.10–3.14, wheel/sdist, Go test/vet/race và native bridge RPC trên Linux, macOS, Windows.

## 2026-09-01 — Sửa thống kê ngôn ngữ GitHub

### Mục tiêu
- Để GitHub Languages hiển thị cả Python và Go thay vì 100% Python.

### Đã thực hiện
- Sửa `.gitattributes` để code Go do dự án duy trì tại `bridge-e2ee/main.go` và `bridge-e2ee/bridge/` không còn bị đánh dấu `linguist-vendored`.
- Tiếp tục loại `bridge-e2ee/meta/` khỏi thống kê vì đây là submodule upstream `mautrix/meta`.

### Quyết định kỹ thuật
- Không ép tỷ lệ hoặc gán sai language; để GitHub Linguist tính từ source được track.
- Không đưa website đang bị ignore vào thống kê vì nó không thuộc tracked tree hiện tại.

### Kiểm tra
- Xác minh Git attributes của source Python, Go nội bộ và submodule upstream.
- Kiểm tra diff, UTF-8 và các mẫu mojibake trước khi bàn giao.

### Việc còn lại
- GitHub chỉ cập nhật tỷ lệ Languages sau khi commit được push và Linguist xử lý lại repository.

## 2026-09-05 — Hoàn thiện bản dịch Anh và hiệu ứng website

### Mục tiêu
- Rà soát toàn bộ giao diện tiếng Anh và sửa các thành phần mất định dạng hoặc hiệu ứng sau khi đổi locale.

### Đã thực hiện
- Chuẩn hóa `website/index.html` thành 386 cặp VI/EN có cấu trúc tương ứng; loại bỏ bản dịch lặp, locale lồng nhau, literal `\1\n` và khôi phục thẻ `<body>`.
- Giữ chung cấu trúc `<pre>`, `<code>`, `<button>`, liên kết và tab giữa hai locale; chỉ tách nội dung cần dịch để code block, hover, skeleton và tab không biến mất ở tiếng Anh.
- Bản địa hóa title, metadata, ARIA, placeholder, tìm kiếm, nút sao chép, theme toggle và định dạng số trong `website/script.js`; copy code chỉ lấy nội dung của locale đang hiển thị.
- Sửa các CSS variable không tồn tại trong phần contributor, owner, preloader và skeleton; thêm `website/validate_i18n.py` làm gate không cần dependency ngoài.

### Quyết định kỹ thuật
- Không nhân đôi component theo ngôn ngữ; component và hiệu ứng dùng một DOM chung, còn `.vi`/`.en` chỉ bọc text hoặc inline markup tương ứng.
- Giữ `website/` trong trạng thái ignored hiện hữu; không force-add khi chưa có yêu cầu commit website rõ ràng.

### Kiểm tra
- `python website/validate_i18n.py` đạt: 386 cặp VI/EN, số lượng `a/button/code/em/i/pre/strong/svg` bằng nhau giữa hai locale, không lộ tiếng Việt trong chế độ Anh.
- `node --check website/script.js`, `python -m py_compile website/validate_i18n.py`, kiểm tra 13 tab/panel, CSS brace/variable và strict UTF-8 đều đạt.
- Không phát hiện U+FFFD hoặc mẫu mojibake trong website; browser tích hợp không có phiên khả dụng nên chưa có visual QA/screenshot thật.

### Việc còn lại
- Chạy visual smoke trên browser thật ở desktop/mobile cho cả VI và EN khi có browser session.
- Chưa commit hoặc push vì `website/` và `AGENT_MEMORYs.md` đều đang bị Git ignore, đồng thời nhiệm vụ không có yêu cầu force-add/push rõ ràng.

## 2026-09-05 — Làm liền progress sao và bổ sung vận hành v2.3

### Mục tiêu
- Sửa vệt animation bị tách khỏi phần progress tại mức `62.5%` và cập nhật mục Vận hành theo bản hiện hành `v2.3.0`.

### Đã thực hiện
- Clip vệt shine trong `.star-progress__fill`, bo đúng đầu progress, chuyển sweep sang transform tuyến tính và căn chu kỳ sọc chéo để không lộ đường nối tile.
- Giữ nguyên phép tính `stars / 200`; `62.5%` là giá trị đúng cho 125 sao, không hard-code hoặc kéo thanh thành 100% giả.
- Tách rõ hai lối nâng cấp v2.1→v2.2 và v2.2→v2.3 trong sidebar cùng section migration song ngữ.
- Bổ sung hợp đồng bridge v2.3, error payload, lifecycle `AsyncClient`, listener E2EE single-use, privacy flags và giới hạn Windows ARM64 từ release notes/source hiện hành.
- Đồng bộ fallback/SEO sang v2.3.0 và cập nhật mục phát hành theo workflow thật: năm bridge binary, `SHA256SUMS`, provenance, workflow artifact và không tự publish PyPI.

### Quyết định kỹ thuật
- Sửa containment và keyframe của layer shine thay vì thay đổi `width`, vì độ rộng phản ánh dữ liệu tiến độ thật.
- Giữ migration v2.2 làm lịch sử tĩnh; không để JavaScript đổi nhãn lịch sử theo latest release.
- Nội dung vận hành lấy từ `CHANGELOG.md`, release notes, source bridge/listener và workflow; không sao chép claim PyPI auto-publish đã lỗi thời.

### Kiểm tra
- `python website/validate_i18n.py`, `node --check website/script.js` và `python -m py_compile website/validate_i18n.py` đạt.
- Kiểm tra CSS đạt: brace cân bằng, toàn bộ CSS variable được định nghĩa, sweep đã clip và dùng transform; kiểm tra HTML xác nhận nội dung v2.3, target điều hướng và ID duy nhất.
- `python scripts/release_artifacts.py validate --release-tag v2.3.0` đạt.
- Strict UTF-8, mojibake, whitespace và phạm vi file được kiểm tra lại trước bàn giao.

### Việc còn lại
- Browser tích hợp không có phiên khả dụng, nên chưa có visual smoke/video trực tiếp cho animation ở desktop và mobile.
- `website/` cùng `AGENT_MEMORYs.md` vẫn bị Git ignore; chưa commit hoặc push khi chưa có yêu cầu force-add rõ ràng.

## 2026-09-05 — Quét lại toàn bộ codebase và chuỗi phát hành

### Mục tiêu
- Rà soát lại toàn bộ tracked source Python, Go bridge, test, workflow, dependency và artifact phát hành hiện tại; không đọc `src/config.json` và không sửa production source trong lượt audit.

### Đã thực hiện
- Quét 111 file tracked; loại source của submodule upstream `bridge-e2ee/meta`, nhưng vẫn kiểm dependency graph và call path từ code Go do dự án duy trì.
- Xác nhận regular MQTT listener gọi coroutine `_all_thread_data.func()` như dict trong nhánh blocking, khiến fresh connect thất bại.
- Xác nhận async Notes chấp nhận response rỗng như success; mutation retry không idempotent; nhiều GraphQL parser chấp nhận partial data kèm `errors`.
- Xác nhận các khoảng trống về ACL Windows, `/unsend` fail-open, `/search` không rate limit, queue E2EE không giới hạn, E2EE media download không hard cap và partial-connect có thể để client auto-reconnect cũ sống nền.
- `govulncheck` tìm năm advisory có call path thật: bốn lỗi standard library ở Go `1.26.5` và `GO-2026-6278` ở `gorilla/websocket v1.5.0`.
- Đối chiếu artifact public cho thấy PyPI `2.3.0` có layout/metadata/hash khác tag `v2.3.0`; wheel public không vượt qua `scripts/verify_distribution.py` của repo.
- Lưu báo cáo bảo mật chi tiết tại `vbsec-reports/scan-2026-09-05-233509.md`.

### Quyết định kỹ thuật
- Chưa sửa source để giữ nhiệm vụ đúng phạm vi audit; ưu tiên remediation theo thứ tự release integrity và dependency reachable, runtime listener/Notes, rồi authorization, resource bounds, ACL và failure-path.
- Không coi FB4A compatibility constants là project/user secret; không báo false positive khi data-flow không dẫn tới secret do repo sở hữu.
- Kết luận security taxonomy là `WARN`: 0 Critical, 2 High và 7 Medium. PyPI artifact mismatch được ghi riêng là release-integrity blocker, không ép sai vào rule bảo mật canonical.

### Kiểm tra
- Python: `compileall`, Ruff, Black, mypy và full pytest `149/149` đều đạt; `pip-audit` không thấy vulnerability trong tập dependency resolver chọn.
- Go: `go test -count=1 ./...`, `go test -count=10 ./...`, `go vet ./...`, `go build ./...` và `gofmt -l` đạt; `govulncheck` exit `3` vì năm vulnerability reachable.
- Release: năm test `test_release_artifacts.py`, validator tag `v2.3.0`, `actionlint v1.7.7`, TOML/JSON/YAML parse và artifact import smoke đạt theo đúng kết quả mong đợi; wheel PyPI bị verifier repo từ chối do thiếu package top-level.
- Strict UTF-8, U+FFFD, mojibake, secret-pattern triage, `git diff --check` và phạm vi worktree được kiểm tra; không đọc config thật.

### Việc còn lại
- Chưa có live Facebook/Messenger provider smoke vì không dùng credential thật.
- `go test -race ./...` chưa chạy local do CGO tắt và không có C compiler; cần xác minh lại trên CI/Linux sau khi nâng dependency.
- Cần quyết định namespace đóng gói canonical, phát hành patch mới từ immutable SHA và exact verified bytes; không ghi đè version PyPI `2.3.0`.
- Temp audit `C:\Users\minhh\AppData\Local\Temp\fbchat-v2-audit-8404a64e7d604d1fab7ae7a1ddcee46e` còn khoảng 79 MB public artifact/venv; policy chặn lệnh xóa đệ quy nên chưa dọn được.

### Git
- Không sửa tracked source, không commit và không push vì nhiệm vụ chỉ yêu cầu quét lại; HEAD/local/`origin/main` cùng ở `9aa7028912012367af0db6d00b3c76c176a27c5d` tại thời điểm audit.

## 2026-09-05 — Nâng cấp preloader kiểu package stream

### Mục tiêu
- Thay spinner đơn giản của website bằng hiệu ứng tải package lấy cảm hứng từ npm, nhưng giữ nội dung kỹ thuật đúng với dự án Python.

### Đã thực hiện
- Thay spinner bằng terminal package stream trong `website/index.html`: lệnh `python -m pip install`, bốn bước resolve/fetch/link/hydrate, thanh tiến trình liên tục và trạng thái VI/EN.
- Viết lại CSS preloader trong `website/style.css` theo visual paper/terminal hiện hữu; thêm animation chỉ dùng transform/opacity, responsive 320px/viewport thấp, dark mode, reduced motion, forced colors và print.
- Thay lifecycle `window.load` trong `website/script.js` bằng dismiss idempotent sau bootstrap đồng bộ; không chờ font, avatar hoặc GitHub API.
- Thêm cơ chế fail-open: markup mặc định `hidden`, bootstrap inline mới bật loader và hard timeout 3,5 giây tự gỡ nếu script chính lỗi.
- Tăng query version của CSS/JS để trình duyệt không giữ asset cũ.

### Quyết định kỹ thuật
- Dùng progress indeterminate thay vì dựng phần trăm tải giả; terminal dùng cú pháp `pip` thay vì câu lệnh npm sai hệ.
- Toàn bộ visual chuyển động là decorative và `aria-hidden`; screen reader chỉ nhận một `role=status` song ngữ.
- Giữ hiệu ứng tối thiểu 640 ms từ lúc loader được bật ở chế độ motion thường; bỏ thời gian chờ và animation khi `prefers-reduced-motion` được bật.

### Kiểm tra
- `python website/validate_i18n.py` đạt 405 cặp VI/EN; không lộ tiếng Việt trong chế độ Anh.
- `node --check website/script.js` đạt; lifecycle harness đạt cho motion thường, reduced motion, double-dismiss và fallback khi thiếu `transitionend`.
- Static gates đạt cho DOM accessibility, fail-open, progress indeterminate, CSS brace/variable, responsive viewport thấp, forced colors, print và cache version.
- Browser tích hợp không có session khả dụng, nên chưa có visual QA/screenshot thật.

### Việc còn lại
- Smoke trực tiếp trên browser thật ở VI/EN, light/dark, mobile 320px và reduced motion khi có browser session.
- `website/` cùng `AGENT_MEMORYs.md` vẫn bị Git ignore; chưa commit hoặc push khi chưa có yêu cầu force-add rõ ràng.

## 2026-09-11 — Hoàn thiện lịch sử CHANGELOG

### Mục tiêu
- Khôi phục đầy đủ các thay đổi đáng chú ý trong `CHANGELOG.md` từ agent memory,
  release notes, tag và commit history hiện có.

### Đã thực hiện
- Bổ sung ba phiên bản bị thiếu: `2.1.4`, `2.2.0` và `2.2.1`; sửa ngày
  `2.1.3b` theo tag thực tế.
- Mở rộng `2.3.0` với unfriend, message pipeline, E2EE lifecycle/watchdog,
  DeviceStore, security hardening, packaging/release gate và compatibility.
- Mở rộng `2.3.1` với reaction aliases, public exports, Linguist, version
  alignment, distribution verification, publication `2.3.1` và việc gỡ PyPI
  auto-publish khỏi CI.
- Ghi các thay đổi website local vào `Unreleased`, kèm cảnh báo `website/`
  đang bị Git ignore và chưa thuộc tag/package phát hành.
- Bổ sung reference link cho mọi version heading theo remote `m008v/fbchat-v2`
  và giữ đúng các tag legacy có dấu chấm.

### Quyết định kỹ thuật
- Không tạo section `2.2.2` vì đây chỉ là planned release/branch; toàn bộ
  hardening cuối cùng được merge và phát hành dưới `2.3.0`.
- Không đưa các phát hiện audit chưa được sửa vào changelog vì chúng không phải
  thay đổi sản phẩm; các giới hạn chưa phát hành của website được ghi rõ.
- Ưu tiên source/tag/release note hiện tại khi memory cũ mâu thuẫn với trạng
  thái thực tế.

### Kiểm tra
- Đối chiếu `git log`, `git ls-remote --heads --tags origin` và GitHub Releases
  API cho các mốc `v2.1.4`, `v2.2.0`, `v.2.2.1`, `v2.3.0`, `v2.3.1`.
- `python website/validate_i18n.py` đạt 405 cặp VI/EN; `node --check
  website/script.js` đạt.
- Strict UTF-8, reference link, duplicate heading, CRLF, `git diff --check` và
  mojibake được kiểm tra lại sau khi hoàn tất diff.

### Việc còn lại
- `website/` vẫn là working copy bị ignore và chưa thuộc release.

### Git
- Commit `470e805ce8cfbeff4270015e840a733bbc3a7dd9`
  (`docs(changelog): restore complete release history`) đã push fast-forward
  lên `origin/main`; local, tracking ref và remote SHA khớp.
- Chỉ commit `CHANGELOG.md`; `AGENT_MEMORYs.md` tiếp tục giữ local theo
  `.gitignore` và `.vs/` không bị đụng tới.

## 2026-09-14 — Đánh giá độ ổn định toàn bộ codebase

### Mục tiêu
- Rà soát trạng thái hiện tại của toàn bộ phần code do dự án duy trì, test,
  dependency, CI và chuỗi phát hành; không đọc `src/config.json` hoặc source
  bên trong submodule upstream `bridge-e2ee/meta`.

### Đã thực hiện
- Quét 113 file được duy trì và dựng knowledge graph gồm 787 node, 1.379 edge,
  7 layer và 11 bước tour; reviewer đối chiếu đủ 113/113 file và 65/65 import.
- Xác nhận regular MQTT listener blocking gọi coroutine như dict; ba parser
  Facebook mutation có thể báo success khi response chứa unrelated data hoặc
  GraphQL errors; async Notes có thể báo success với `data=None`.
- Xác nhận lỗi ACL khi Python chạy từ PowerShell 7 gọi `powershell.exe`, leak
  bridge ở failure path của standalone E2EE sender, queue/media E2EE thiếu hard
  bound, partial `ConnectE2EE` thiếu rollback và timeout gửi bị diễn giải như
  success.
- `govulncheck` hiện báo năm vulnerability reachable: bốn lỗi standard library
  cần Go 1.26.6 và `GO-2026-6278` cần `gorilla/websocket >= 1.5.3`.
- Đối chiếu tag, source checkout và artifact public PyPI `2.3.1`: namespace,
  nội dung và embedded bridge checksum không đồng nhất; wheel public vẫn mang
  bridge release/checksum `2.3.0` và có MQTT fix không tồn tại trong tag.
- Tạo canvas readiness audit và knowledge graph local; không sửa production
  source, không gửi request tới Facebook/Messenger và không dùng credential.

### Quyết định kỹ thuật
- Kết luận `NO-GO` cho production/release mới dù CI hiện xanh; ưu tiên sửa
  dependency/release provenance, MQTT/parser correctness và Windows ACL trước
  các hardening E2EE còn lại.
- Tách bằng chứng source gate, artifact public, Windows runtime và live-provider;
  không dùng một lớp bằng chứng để tuyên bố thay cho lớp khác.

### Kiểm tra
- Python: Ruff, Black, mypy, build, compileall và `pip-audit` đạt.
- Full pytest ngoài sandbox: 145 pass, 4 fail; ba fail ACL Windows tái hiện ổn
  định, một timing test pass 10/10 khi chạy cô lập nên được ghi là flaky signal.
- Go: `go test -count=1 ./...` và `go vet ./...` đạt; `govulncheck` exit `3` vì
  năm call path reachable.
- Graph reviewer đạt với 0 critical issue; strict UTF-8, mojibake và Git scope
  được kiểm lại ở bước bàn giao.

### Việc còn lại
- Chưa có live Facebook/Messenger smoke; không thể tuyên bố behavior provider
  hiện tại đã ổn định chỉ từ mock và static analysis.
- Cần sửa các blocker rồi phát hành patch mới từ một immutable source checkout,
  publish đúng bytes đã verify và đối chiếu lại wheel/sdist public.

### Git
- HEAD/local tracking/public remote cùng SHA
  `470e805ce8cfbeff4270015e840a733bbc3a7dd9` tại thời điểm audit.
- Không commit hoặc push vì nhiệm vụ chỉ yêu cầu đánh giá; giữ nguyên `.vs/` của
  người dùng và mọi production source.

## 2026-09-15 — Hardening và phát hành patch 2.3.2

### Mục tiêu
- Sửa toàn bộ blocker từ stability audit, đồng bộ mọi version active lên
  `2.3.2`, phát hành từ immutable source và đồng bộ checkout phân phối PyPI.

### Đã thực hiện
- Sửa regular MQTT fresh-start, validation payload, GraphQL mutation fail-closed,
  Notes/reaction mutation ID và retry policy; thêm bound/quota cho bot `/search`.
- Siết Windows ACL cho Python session và Go DeviceStore, rollback/cleanup E2EE,
  queue/RPC/media hard limit và trạng thái gửi timeout `unknown` chống retry trùng.
- Nâng Go lên `1.26.6`, `gorilla/websocket` lên `1.5.3`; đồng bộ package,
  bridge, test, docs và workflow lên `2.3.2`.
- Tạo canonical package `src/fbchat_v2` từ legacy source; verifier khóa exact
  54-file payload, archive path/type/collision, wheel `RECORD` và sdist
  `PKG-INFO`.
- Release workflow checkout immutable SHA, recheck tag ngay trước upload, từ
  chối asset thừa/sai hash, pin third-party actions và phát hành đúng artifact
  đã bind checksum bridge.

### Quyết định kỹ thuật
- Giữ legacy source làm implementation editable; `src/fbchat_v2` là snapshot
  generated để public distribution không chiếm các top-level package chung.
- Mutation hoặc send timeout không có bằng chứng xác nhận phải fail closed hoặc
  trả `uncertain`; không tự retry thao tác không idempotent.
- Checkout `fbchat-v2-pypi` phải lấy canonical tree từ verified sdist sau khi
  bind bridge checksum, tuyệt đối không rebuild từ placeholder của source tag.

### Kiểm tra
- Python local: compileall, Ruff, Black, mypy legacy/canonical và full pytest
  `251/251` đạt; `pip-audit` không thấy vulnerability đã biết.
- Wheel/sdist local: Twine strict, exact verifier, clean-install smoke và build
  lặp byte-identical đều đạt.
- Go local: module verify/tidy, full test, vet, build/native RPC smoke và
  `govulncheck` đạt với 0 vulnerability reachable; race detector chưa chạy được
  local vì không có `gcc`, vẫn là gate bắt buộc trên CI Linux.
- Workflow: `actionlint 1.7.12` đạt; external actions được pin full commit SHA.

### Việc còn lại
- Ghi SHA commit/tag, GitHub Release assets, nhánh `pypi`, public PyPI hash và
  clean-install public sau khi pipeline/tag hoàn tất.
- Chưa chạy live Facebook/Messenger smoke vì không dùng credential thật; mock,
  static gate và artifact smoke không thay thế bằng chứng provider live.

### Git
- Đang chờ final diff/encoding gate trước commit, push `main`, tag `v2.3.2` và
  đồng bộ/push nhánh `pypi`.

## 2026-09-16 — Đánh giá lại độ ổn định sau release 2.3.2

### Mục tiêu
- Rà lại source, test, Go/E2EE bridge, release provenance và artifact public;
  không đọc credential/config nhạy cảm hoặc gọi Facebook/Messenger live.

### Đã thực hiện
- Xác nhận các blocker của audit trước đã được sửa và không còn finding
  Critical/High đã biết; `govulncheck` không tìm thấy vulnerability reachable.
- Xác nhận `main`, tag `v2.3.2`, GitHub Release và PyPI hội tụ đúng commit và
  artifact; wheel/sdist PyPI byte-identical với asset GitHub đã được attest.
- Phát hiện media plaintext tạm trên Windows chỉ dùng `Chmod(0600)` thay vì
  private DACL; typing RPC dùng `context.Background()` thay vì lifecycle
  context; một test E2EE timeout flaky tái hiện 4/10 lần chạy riêng.
- Ghi nhận các gap thấp: PyPI không có native provenance, CLI release `--help`
  lỗi trên CP1252, `DOCS.md` còn trỏ nhánh beta và indirect Go dependency có
  advisory nhưng chưa có symbol call path.

### Quyết định kỹ thuật
- Release integrity của 2.3.2 là GO; chưa gọi toàn bộ codebase là ổn định tuyệt
  đối cho tới khi đóng hai Medium E2EE runtime/security và test timing flaky.
- Tách rõ source/package/CI, public artifact và provider-live evidence; không
  suy diễn 20/20 workflow xanh thành bằng chứng Meta API đang ổn định.

### Kiểm tra
- Python: compileall, Ruff, Black, mypy legacy/canonical, sync package, build và
  verifier wheel/sdist đạt; full pytest xác nhận `250 pass, 1 fail`, test lỗi
  chạy riêng 10 lần đạt 6 và lỗi 4.
- `pip-audit` cô lập trên runtime site-packages hiện tại không tìm thấy
  vulnerability đã biết; editable distribution được bỏ qua như thiết kế.
- Go: module verify/tidy, full test, vet, native Windows build/RPC smoke đạt;
  `govulncheck` đạt với 0 reachable vulnerability. Local race không chạy do
  thiếu CGO/C compiler; Linux CI race thuộc workflow 20/20 thành công.
- Release: workflow `34934791316` đạt 20/20 job; 7 payload có GitHub SLSA v1
  attestation; fresh PyPI install, import 2.3.2 và `pip check` đạt.
- Không phát hiện thay đổi tracked ngoài phạm vi; `.vs/` được giữ nguyên.

### Việc còn lại
- Dùng `createPrivateTempFile` cho media E2EE trên Windows; truyền lifecycle
  context cho typing RPC; làm test timeout deterministic bằng readiness marker.
- Sau đó sửa CLI CP1252/docs, nâng indirect Go dependencies, bật PyPI Trusted
  Publishing và chạy smoke bằng account test cô lập nếu được cấp phép.
- Knowledge graph chưa refresh vì ignore scope nhạy cảm đang chờ xác nhận.

### Git
- Audit không sửa production source, không commit hoặc push. HEAD vẫn là
  `981d0996db0a01af45526f8270d83559d5a3ef2e`; worktree tracked sạch và chỉ còn
  `.vs/` untracked ngoài phạm vi.

## 2026-10-05 — Smoke bot như dev mới và kiểm tra live bằng account clone

### Mục tiêu
- Thử onboarding, cài package và chạy bot theo góc nhìn dev bình thường; xác
  định điểm khó hiểu hoặc không hoạt động, sau đó kiểm tra live có kiểm soát
  bằng cookie account clone và group test.

### Đã thực hiện
- Kiểm tra fresh PyPI `2.3.2`, public imports, session storage, bridge download,
  RPC contract, mock `/ping` và pipeline startup/cleanup.
- Chạy live bot mẫu bằng bridge build từ source `2.3.2`; đăng nhập HTTP thành
  công nhưng regular transport của bridge không đạt ready sau 90 giây.
- Chạy Python MQTT regular trên cùng cookie/máy: kết nối, nhận `/ping` thật từ
  group và gửi reply thật thành công; Facebook trả message ID và timestamp.
- Chạy bridge regular-only ở log `info`: tái hiện LightSpeed `databaseID=1`
  timeout, reconnect thất bại và nhiều cảnh báo decoder do schema/type drift.
- Ghi nhận onboarding sai hoặc mơ hồ: README build bridge sai cwd, DOCS clone
  nhánh beta `2.2.0`, tài liệu dùng namespace legacy không import được từ wheel,
  bot group-only vẫn bắt bridge E2EE, ví dụ send sai key và ví dụ thiếu `await`.

### Quyết định kỹ thuật
- Cookie, login HTTP, group, Python MQTT và regular send không phải nguyên nhân
  của failure live; blocker nằm ở bridge Go/LightSpeed bootstrap trước E2EE.
- Không tăng timeout để che lỗi `databaseID=1`; cần sửa/upstream decoder và sync
  flow. Timeout ngoài 90 giây của bot đang race với timeout regular 90 giây nên
  thường che mất exception gốc.
- Không bật bridge log `info` mặc định: log hiện có thể chứa thread/user metadata
  và dữ liệu sync; cần redaction trước khi dùng làm hướng dẫn debug.

### Kiểm tra
- Fresh PyPI install/import/pip check và 44 module import đạt; bridge public
  checksum/RPC contract đạt khi kiến trúc Windows được nhận diện.
- Targeted pytest dùng basetemp sạch: 53/53 đạt; mock group `/ping` reply đạt.
- Live Python MQTT: `REGULAR_READY`, nhận body `/ping` và
  `REGULAR_REPLY success=True`.
- Live bridge Go `2.3.2`: fail `regular connection did not become ready`; log gốc
  xác nhận sync LightSpeed `databaseID=1` timeout qua nhiều lần reconnect.
- Không đọc hoặc in cookie; payload shape chỉ ghi key/type/độ dài, không ghi nội
  dung. Các script chẩn đoán tạm đã được xóa.

### Việc còn lại
- Sửa bridge LightSpeed bootstrap/schema drift và thêm live regression test bằng
  account clone; sau đó mới kiểm tra E2EE connect/receive/send/reconnect.
- Tách bot group regular khỏi yêu cầu E2EE bridge hoặc hỗ trợ fallback rõ ràng.
- Làm timeout startup lệch tầng và preserve exception gốc; redact bridge logs.
- Sửa tài liệu onboarding, CP1252 console, config validation và stale local
  bridge/venv trước patch release tiếp theo.

### Git
- Không sửa production source, không commit hoặc push trong lượt chẩn đoán.
- Giữ nguyên `.vs/`; không đưa cookie, config hoặc log nhạy cảm vào Git.

## 2026-10-15 — Đánh giá toàn diện codebase v2.3.2

### Mục tiêu
- Rà soát và đánh giá tổng thể kiến trúc, chất lượng code, bảo mật, độ tin cậy runtime và những điểm nghẽn thực tế của codebase `fbchat-v2` (phiên bản `2.3.2`).

### Đã thực hiện
- Kiểm tra trực tiếp các tầng `_core`, `_features`, `_messaging`, bot mẫu `src/main.py`, Go bridge `bridge-e2ee/` và pipeline đóng gói `scripts/verify_distribution.py` + `pyproject.toml`.
- Tổng hợp các điểm sáng kỹ thuật đã đạt được ở `2.3.2`, chỉ ra các lỗi/nợ kỹ thuật còn tồn đọng (LightSpeed `databaseID=1` sync drift, Windows DACL cho E2EE media temp file, `context.Background()` trong `SendE2EETyping`, `requests` legacy trong `_facebookLogin.py`, onboarding/docs drift) kèm đề xuất code tối ưu.
- Không đọc `src/config.json`, không sửa production source và không commit/push.
