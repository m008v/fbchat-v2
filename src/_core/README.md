## ⚙️ Core (`src/core/`)

`core` là tầng nền tảng dùng chung cho toàn bộ project.  
Module trong `core` chỉ xử lý session/token, request chuẩn và helper kỹ thuật — **không chứa business logic**.

### Cấu trúc module

```text
src/core/
├── session.py
├── request.py
├── cookies.py
├── ids.py
└── helpers.py
