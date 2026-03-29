# Project Flowchart

This diagram covers the full repository structure (excluding deep internals in `.git/` and `.venv/`) and the main runtime flow inside `src/`.

## 1) Directory Flow (whole project)

```mermaid
flowchart TD
    REPO[fbchat-v2-new_version]

    REPO --> ROOT[Root Files]
    ROOT --> README[README.md]
    ROOT --> README_EN[README_EN.md]
    ROOT --> DOCS[DOCS.md]
    ROOT --> COC[CODE_OF_CONDUCT.md]
    ROOT --> LICENSE[LICENSE]
    ROOT --> REQ[requirements.txt]

    REPO --> META[Environment and Git]
    META --> GIT[.git/]
    META --> VENV[.venv/]

    REPO --> LANG[language/]
    LANG --> LANG_README[language/README.md]
    LANG --> LANG_VI[language/vi_VN.lang]

    REPO --> SRC[src/]
    SRC --> SRC_MAIN[src/main.py]
    SRC --> SRC_CFG[src/config.json]

    SRC --> CORE[src/_core/]
    CORE --> CORE_INIT[__init__.py]
    CORE --> CORE_SESSION[_session.py]
    CORE --> CORE_UTILS[_utils.py]
    CORE --> CORE_LOGIN[_facebookLogin.py]
    CORE --> CORE_README[README.md]
    CORE --> CORE_README_EN[README_EN.md]

    SRC --> FEATURES[src/_features/]
    FEATURES --> FB[src/_features/_facebook/]
    FEATURES --> TH[src/_features/_thread/]
    FEATURES --> FT_README[README.md]
    FEATURES --> FT_README_EN[README_EN.md]

    FB --> FB_INIT[__init__.py]
    FB --> FB_BLOCK[_blocking.py]
    FB --> FB_BIO[_changeBio.py]
    FB --> FB_POST[_createPost.py]
    FB --> FB_USER[_get_user_info.py]
    FB --> FB_MARKET[_marketplace.py]
    FB --> FB_NOTI[_notification.py]
    FB --> FB_PRO[_professional.py]
    FB --> FB_REG[_registerOnProfile.py]
    FB --> FB_SEARCH[_search.py]

    TH --> TH_INIT[__init__.py]
    TH --> TH_ADMIN[_addAdmin.py]
    TH --> TH_DATA[_all_thread_data.py]
    TH --> TH_EMOJI[_changeEmoji.py]
    TH --> TH_NAME[_changeNameThread.py]
    TH --> TH_NICK[_changeNickname.py]

    SRC --> MSG[src/_messaging/]
    MSG --> MSG_INIT[__init__.py]
    MSG --> MSG_ATTACH[_attachments.py]
    MSG --> MSG_LISTEN[_listening.py]
    MSG --> MSG_REQ[_message_requests.py]
    MSG --> MSG_REACT[_reactions.py]
    MSG --> MSG_SEND[_send.py]
    MSG --> MSG_UNSEND[_unsend.py]
    MSG --> MSG_README[README.md]
    MSG --> MSG_README_EN[README_EN.md]
```

## 2) Runtime Flow (main source behavior)

```mermaid
flowchart LR
    USER[User or Bot Logic]
    CFG[src/config.json]
    MAIN[src/main.py]

    USER --> MAIN
    MAIN --> CFG

    MAIN --> SESSION[_core._session.dataGetHome]
    SESSION --> DFB[dataFB]

    DFB --> UTILS[_core._utils helpers]

    DFB --> FEATURES[_features modules]
    DFB --> MESSAGING[_messaging modules]

    FEATURES --> FB_API[Facebook GraphQL and Web Endpoints]
    MESSAGING --> FB_API

    ATTACH[_messaging._attachments]
    SEND[_messaging._send]
    MARKET[_features._facebook._marketplace]
    THREAD_DATA[_features._thread._all_thread_data]
    LISTENER[_messaging._listening]

    ATTACH --> SEND
    ATTACH --> MARKET
    THREAD_DATA --> LISTENER

    LISTENER --> MQTT[wss://edge-chat.facebook.com via MQTT]

    REACT[_messaging._reactions] --> FB_API
    UNSEND[_messaging._unsend] --> FB_API
    MSG_REQ[_messaging._message_requests] --> FB_API

    EXTERNAL[External libs: requests, paho-mqtt, attrs]
    EXTERNAL --> FEATURES
    EXTERNAL --> MESSAGING
    EXTERNAL --> SESSION
```
