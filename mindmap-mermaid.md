# fbchat-v2 — async architecture mind map

```mermaid
mindmap
  root((fbchat-v2))
    Core
      httpx transport
        post_async
        get_async
        reusable AsyncClient
      session
        dataGetHome_async
        dataFB secret
      login
        main_async
        local pyotp
        env app token
    Features
      Facebook
        bio and posts
        search and blocking
        professional profile
        Marketplace
      Thread
        inbox and last_seq_id
        admin and nickname
        emoji and name
    Messaging
      send_async
      attachments
      reactions and unsend
      notes and themes
      MQTT
        connect_mqtt_async
        bounded queue
        outer reconnect loop
      E2EE
        Go subprocess
        JSON-RPC
        BridgeActions async
    Quality
      pytest
      ruff
      mojibake scan
      security scan
```
