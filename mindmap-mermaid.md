# fbchat-v2 - Mindmap kiến trúc async

[README](README.md) | [Tài liệu API](DOCS.md) | [Flowchart](FLOWCHART.md)

```mermaid
mindmap
  root((fbchat-v2))
    Application
      src/main.py
        config validation
        FileSessionStorage
        shared AsyncClient
        E2EE listener task
        thread-safe event queue
        async command handlers
        graceful shutdown
      src/config.example.json
        cookies placeholder
        prefix
        admins
    Core
      Session
        dataGetHome
        homepage token parser
        required fields
        dataFB secret contract
      Storage
        SessionStorage
        FileSessionStorage
          atomic replace
        EnvSessionStorage
      HTTP
        httpx AsyncClient
        post_async
        get_async
        finite timeout
        TLS verification
        caller-owned client
      Utilities
        formAll
        request builders
        JSON prefix parser
        cookie parser
        threading IDs
      Credential login
        loginFacebook.main
        FB4A legacy defaults
        optional env override
        local pyotp
        checkpoint subcodes
    Features
      Facebook
        change bio
        create post
        search users
        user info
        notifications
        block and unblock
        professional mode
        additional profile
        Marketplace
      Thread
        all thread data
        last sequence ID
        thread information
        member export
        rename
        emoji
        nickname
        admin add and remove
      Contract
        async func
        optional AsyncClient
        input validation
        structured error
    Messaging
      Regular send
        text
        multi-recipient
        reply
        attachment IDs
      Attachment upload
        file validation
        multipart
        metadata parser
        normalized typeAttachment
        error diagnostics
      MQTT listener
        paho worker
        bounded queue
        drop oldest
        all deltas
        outer reconnect
      Message actions
        reactions
        edit LS task
        HTTP unsend
        message requests
        themes
        Messenger Notes
      E2EE listener
        binary discovery
        BridgeProcess
        line JSON-RPC
        readiness wait
        raw callbacks
        regular message event
        decrypted message event
        watchdog respawn
      BridgeActions
        edit and unsend
        typing and mark read
        E2EE image
        E2EE audio
        regular media download
        E2EE media decrypt
    Go bridge
      main.go dispatcher
      bridge package
        Messenger connect
        E2EE connect
        event conversion
        message actions
        media actions
      mautrix-meta submodule
      go.mod
        Go 1.26.5
      build output
        Windows exe
        Linux and macOS binary
    Tests
      pytest
        strict asyncio mode
        mocked HTTP
        parser edge cases
        compatibility boundaries
      Go tests
        bridge actions
        media security
      Static checks
        ruff
        compileall
        git diff check
        UTF-8 and mojibake scan
    Documentation
      README Vietnamese
      README English
      DOCS API guide
      Core docs
      Feature docs
      Messaging docs
      Bridge docs
      Flowchart
      Changelog
```

Mindmap thể hiện ownership, không phải call graph chính xác. Xem [FLOWCHART.md](FLOWCHART.md) để theo dõi trình tự runtime và [DOCS.md](DOCS.md) để xem chữ ký API.
