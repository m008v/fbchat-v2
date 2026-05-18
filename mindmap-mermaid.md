mindmap
  root((fbchat-v2))
    Root code
      requirements.txt
      .github/
      .gitattributes
      .gitignore

    website/
      index.html
      script.js
      style.css

    language/
      vi_VN.lang

    build/
      fbchat-bridge-e2ee.exe

    bridge-e2ee/
      main.go
      go.mod
      go.sum
      bridge/
        client.go
        events.go
        media.go
        messages.go
        store.go

    src/
      config.json
      main.py
      _e2ee_listening_test.py

      _core/
        __init__.py
        _facebookLogin.py
        _session.py
        _utils.py

      _features/
        _facebook/
          __init__.py
          _blocking.py
          _changeBio.py
          _createPost.py
          _get_user_info.py
          _marketplace.py
          _notification.py
          _professional.py
          _registerOnProfile.py
          _search.py

        _thread/
          __init__.py
          _addAdmin.py
          _all_thread_data.py
          _changeEmoji.py
          _changeNameThread.py
          _changeNickname.py

      _messaging/
        __init__.py
        _attachments.py
        _changeTheme.py
        _createNotes.py
        _editMessage.py
        _listening.py
        _listening_e2ee.py
        _message_requests.py
        _reactions.py
        _send.py
        _send_e2ee.py
        _unsend.py

    docs-text
      README.md
      README_EN.md
      DOCS.md
      FLOWCHART.md
      CHANGELOG.md
      CLAUDE.md
      CODE_OF_CONDUCT.md
      LICENSE
      language/README.md
      bridge-e2ee/README.md
      src/_core/README.md
      src/_core/README_EN.md
      src/_features/README.md
      src/_features/README_EN.md
      src/_messaging/README.md
      src/_messaging/README_EN.md
