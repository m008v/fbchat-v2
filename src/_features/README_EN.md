# _features (`src/_features`)

`_features` is the layer that implements direct Facebook and messaging features. This folder does not handle low-level session/token infrastructure like `_core`. Instead, it focuses on feature-level business logic:

- Profile actions (bio, posts, additional profile, professional mode).
- User data and notification retrieval.
- Facebook search, block/unblock actions.
- Marketplace item creation and product info retrieval.
- Group thread management (rename thread, emoji, nickname, admin role).

---

## 1) Folder structure

```text
src/_features/
|-- _facebook/
|   |-- __init__.py
|   |-- _blocking.py
|   |-- _changeBio.py
|   |-- _createPost.py
|   |-- _get_user_info.py
|   |-- _marketplace.py
|   |-- _notification.py
|   |-- _professional.py
|   |-- _registerOnProfile.py
|   `-- _search.py
|-- _thread/
|   |-- __init__.py
|   |-- _addAdmin.py
|   |-- _all_thread_data.py
|   |-- _changeEmoji.py
|   |-- _changeNameThread.py
|   `-- _changeNickname.py
|-- README.md
`-- README_EN.md
```

### Main exports

`src/_features/_facebook/__init__.py` currently exports:

```python
__all__ = [
    "_changeBio",
    "_createPost",
    "_professional",
    "_search",
    "_blocking",
    "_registerOnProfile",
    "_notification",
    "_marketplace",
    "_get_user_info",
]
```

`src/_features/_thread/__init__.py` currently exports:

```python
__all__ = [
    "_changeNickname",
    "_addAdmin",
    "_changeEmoji",
    "_changeNameThread",
]
```

This means you can import `_thread` or `_facebook` and access the modules listed above.

---

## 2) Primary responsibility (**IMPORTANT**): `_features_`

### `_features` is used to:

- Implement business logic for each concrete feature.
- Reuse `dataFB` session data from `_core._session`.
- Integrate critical capabilities for tools and bots.

---

## 3) Shared input data (**IMPORTANT**): `dataFB`

Most functions in `_features` receive `dataFB` as the first parameter.

### Frequently used fields

- `fb_dtsg`
- `jazoest`
- `FacebookID`
- `clientRevision`
- `sessionID`
- `cookieFacebook`

`dataFB` is produced by `_core._session.dataGetHome(setCookies)`.

---

## 4) Detailed module reference
(**IMPORTANT**): `dataFB` is exported from `_core._session` via `dataGetHome(setCookies)`.

## 4.1 `_features._facebook` | `_facebook` group

### `_changeBio.py`

- Function: `func(dataFB, newContents, uploadPost=False)`
- Purpose: change the account bio.
- Input:
  - `newContents`: new bio content.
  - `uploadPost`: whether to publish a feed story about this bio change.
- Output:
  - Success: `{ "success": 1, "messages": ... }`
  - Failure: `{ "error": 1, ... }`

### `_createPost.py`

- Function: `func(dataFB, newContents, attachmentID=None)`
- Purpose: create a new timeline post.
- Input:
  - `newContents`: post content.
  - `attachmentID`: reserved parameter; currently not used in the active feature flow.
- Output:
  - Success: returns created `urlPost`.
  - Failure: returns `error` and API message.

### `_professional.py`

- Function: `func(dataFB, statusBusiness=None)`
- Purpose: enable/disable Professional Mode on the profile.
- Input:
  - `statusBusiness`: accepts `"on"`, `"off"`, `"bật"`, `"tắt"`, `True`, `False`.
- Output: `success` or `error` dictionary.

### `_search.py`

- Function: `func(dataFB, keywordSearch)`
- Purpose: search Facebook users.
- Input:
  - `keywordSearch`: search keyword.
- Output:
  - `searchResults`: preformatted string for tools/bots.
  - `searchResultsDict`: list of dictionaries with `name`, `id`, `url`.

### `_blocking.py`

- Function: `func(dataFB, idUser, choiceInteract)`
- Purpose: block or unblock a user.
- Input:
  - `choiceInteract`: `"block"` or `"unblock"`.
- Output: `success`/`error` dictionary based on API response.

### `_registerOnProfile.py`

- Function: `func(dataFB, newName, newUsername)`
- Purpose: create an additional profile under the same account.
- Input:
  - `newName`: additional profile name.
  - `newUsername`: additional profile username.
- Output:
  - Success: `{ "success": 1, ... }`
  - Business/API failure: `{ "error": 1, ... }`
- Note: this feature works only for some eligible accounts.

### `_notification.py`

- Function: `func(dataFB)`
- Purpose: fetch notification list.
- Input: none.
- Output:
  - Success: `{ "success": 1, "NotificationResults": [...] }`
  - Failure: `{ "error": 1, "messages": ... }`

### `_marketplace.py`

- Function 1: `createItem(dataFB, nameItem, brandItem, priceItem, currencyItem, decriptionItem, hashtagList, typeItem, photoIDList, locationSeller)`
  - Purpose: create a Marketplace listing.
  - Input:
    - `nameItem`: product name.
    - `brandItem`: brand.
    - `priceItem`: product price.
    - `currencyItem`: currency code.
    - `decriptionItem`: product description.
    - `hashtagList`: hashtag list.
    - `typeItem`: product category/type.
    - `photoIDList`: list of uploaded attachment IDs (from `_messaging._attachments.py`).
    - `locationSeller`: seller location.
  - Output: `success` with listing `url`/`id`, or `error`.

- Function 2: `getInformationProductItemMarketPlace(dataFB, idProductItem)`
  - Purpose: retrieve product details by ID.
  - Input: `idProductItem` (target product ID).
  - Output: dictionary containing product details, price, seller info, link, and creation time.

### `_get_user_info.py`

- Function: `func(dataFB, userID)`
- Purpose: fetch user info through the chat user-info endpoint.
- Input:
  - `userID`: target user ID.
- Output:
  - Success: detailed user information dictionary.
  - Failure: `{ "err": 0 }`.

---

## 4.2 `_features._thread` | `_thread` group

### `_changeNameThread.py`

- Function: `func(dataFB, threadID, newNameThread)`
- Purpose: rename a group/thread.
- Input:
  - `newNameThread`: new thread name.
  - `threadID`: target thread ID.
- Output: `formatResults(status, message)` from `_core._utils`.

### `_changeEmoji.py`

- Function: `func(dataFB, threadID, newEmoji)`
- Purpose: change the default thread emoji.
- Input:
  - `newEmoji`: new emoji value.
  - `threadID`: target thread ID.
- Output: `formatResults("success"|"error", message)`.

### `_addAdmin.py`

- Function: `func(dataFB, threadID, idUser, statusChoice=True)`
- Purpose: add/remove admin rights in a group thread.
- Input:
  - `idUser`: user ID to promote/demote.
  - `threadID`: target thread ID.
- Output: `formatResults("success"|"error", message)`.

### `_changeNickname.py`

- Function: `func(datatFB, threadID, idUser, NewNickname)`
- Purpose: change a member nickname in a thread.
- Input:
  - `threadID`: target thread ID.
  - `idUser`: target member ID.
  - `NewNickname`: new nickname.
- Output: `formatResults("success"|"error", message)`.

### `_all_thread_data.py`

- Function 1: `func(dataFB)`
  - Purpose: fetch INBOX thread list and `last_seq_id`.
  - Input: none.
  - Output: `dataGet`, `ProcessingTime`, `last_seq_id`, `dataAllThread`.

- Function 2: `features(dataGet, threadID, commandUse)`
  - Purpose: extract deeper data from `dataGet` based on command.
  - Supported `commandUse` values:
    - `"getAdmin"`
    - `"threadInfomation"`
    - `"exportMemberListToJson"`

---

## 5) Dependency map in the project

`_features` mainly depends on `_core._utils` and `dataFB`:

- `_core._session` -> `dataGetHome(setCookies)`
- `formAll`
- `mainRequests`
- `parse_cookie_string`
- `Headers`
- `formatResults`
- `randStr`

*WARNING*: breakage may occur if Facebook changes GraphQL structures.

---

## 6) Sample source code

```python
from _features._facebook import *
from _features._thread import *


# Fetch Facebook notifications (_features._facebook)

result = _notification.func(dataFB)
print(result)

# Block a user (_features._facebook)

result = _blocking.func(dataFB, idUser="1000...", choiceInteract="block")
print(result)

# Change thread emoji (_features._thread)

result = _changeEmoji.func(dataFB, threadID="1234567890", newEmoji="(emoji)")
print(result)

# Fetch overall thread data (_features._thread)

threads = _all_thread_data.func(dataFB)
print(threads["dataAllThread"])
```

---

## 7) Common issues and troubleshooting

### Case 1: auth/session errors across multiple features

- Check whether the cookie is still valid.
- Regenerate `dataFB` via `_core._session.dataGetHome(...)`.

### Case 2: API returns errors or empty data

- Endpoint/doc_id may have changed.
- Verify that `variables` payload still matches the current schema.

### Case 3: JSON parsing errors in responses

- Some endpoints return responses prefixed with `for (;;);`.
- Split that prefix before calling `json.loads` (already handled in some modules).
