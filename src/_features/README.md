## 👤 _features (`src/_features/`)

`_features` chứa các feature liên quan user/_features và các thao tác mở rộng trên Facebook.  
Thiết kế theo hướng tách nhỏ module để tránh monolith.

### Cấu trúc module

```text
src/_features/ 
├── user_info.py
├── message_requests.py
├── _facebook/bio.py
├── _facebook/posts.py
├── _facebook/search.py
├── _facebook/notifications.py
├── _facebook/blocking.py
├── _facebook/marketplace.py
└── _facebook/professional_mode.py