# I Drive's REST API

# User Endpoints

## Login
 Returns auth token for later authentication

### Request

`GET /auth/token/login`

**Body**

    {
        "username": username,
        "password": password
    }

    

### Response

    Status: 200 OK
    Content-Type: application/json
    
    {"auth_token": "1f217e41afae84ee8430cf0636f7355a3e4fcde3"}


## Logout
Deletes auth token and flushes user's session
> [!NOTE]
> This endpoint requires Authentication.

### Request

`POST /auth/token/logout/`

### Response

    Status: 204 No Content






## Get User
Gets user's information
> [!NOTE]
> This endpoint requires Authentication.
### Request

`GET /auth/user/me/`

### Response

    Status: 200 OK
    Content-Type: application/json

    {
        "user": {
            "name": "name",
            "root": "AiFaPmQuECmHAdFfgvrTDd"
        },
        "perms": {
            "admin": false,
            "execute": true,
            "create": true,
            "lock": true,
            "modify": true,
            "delete": true,
            "share": true,
            "download": true
        },
        "settings": {
            "locale": "pl",
            "hideLockedFolders": false,
            "dateFormat": false,
            "viewMode": "mosaic gallery",
            "sortingBy": "size",
            "sortByAsc": true,
            "subfoldersInShares": true,
            "webhook": "https://discord.com/api/webhooks/1218956937798877295/I4YOzsDhnHDypTDWNqzcefcAveEaiEddE5YUwtUVrjJySjFcfz"
        }
    }


## Change Password
Change's user's password. Flushes old session. Returns new auth token
> [!NOTE]
> This endpoint requires Authentication.
### Request

`POST /api/user/changepassword/`


**Body**

    {
        "current_password": "current_password",
        "new_password": "new_password"
    }


### Response

    Status: 200 OK
    Content-Type: application/json
    
    {"auth_token": "1f217e41afae84ee8430cf0636f7355a3e4fcde3"}

## Change User Settings
Change's user's password. Flushes old session. Returns new auth token
> [!NOTE]
> This endpoint requires Authentication.
### Request

`POST /api/user/updatesettings`

   
**Body**

    {
        "locale": String,
        "subfoldersInShares": Boolean,
        "hideLockedFolders": Boolean,
        "dateFormat": Boolean,
        "webhook": String
    }

### Response

    Status: 204 No Content

# File Endpoints

## create File 
This endpoint is used to create files
> [!NOTE]
> This endpoint requires Authentication.

### Request

`POST /api/file/create`
   
**Body**

    {
        "files": [
            {
                "name": "video1.mp4",
                "parent_id": "UiFtSmQuACmHAaGJEvXTbd",
                "mimetype": "video/mp4",
                "extension": ".mp4",
                "size": 44060824,
                "index": 0
            },
            {
                "name": "text1.txt",
                "parent_id": "UiFtPeQxECXHAaXJgvREbd",
                "mimetype": "text/plain",
                "extension": ".txt",
                "size": 211,
                "index": 1
            }
        ]
    }

> [!WARNING]
> Maximum length of PARAM 'files' is 100

### Response

    Status: 200 OK

    [
        {
            "index": 0,
            "file_id": "S4S2daHGsaSMNCeEtLbAEWy",
            "parent_id": "UiFtSmQuACmHAaGJEvXTbd",
            "name": "video1.mp4",
            "type": "video"
        },
        {
            "index": 1,
            "file_id": "SA22dGHGESMNCekXLbraWa",
            "parent_id": "UiFtPeQxECXHAaXJgvREbd",
            "name": "text1.txt",
            "type": "video"
        }
    ]

### Request

`PATCH /api/file/create`
> [!TIP]
> This endpoint is used to tell the server about client uploaded file fragments

> [!Note]
> When all fragments are uploaded and fragment_sequence == total_fragments,
> Websocket event is fired!

**Body**

    {
        "file_id": "S4S2daHGsaSMNCeEtLbAEWy",
        "fragment_sequence": 1,
        "total_fragments": 2,
        "fragment_size": 26188800,
        "message_id": "1245110389444557862",
        "attachment_id": "1145030487422524561"
    }


### Response

    Status: 204 No Content

### Request
`PUT /api/file/create`
> [!TIP]
> This endpoint is to modify a file for example when it's edited

**Body**

    {
        "file_id": "nCzW5cASTWxaUH8xAAwBfc",
        "fragment_sequence": 1,
        "total_fragments": 1,
        "fragment_size":189, 
        "message_id": "1245214733181628215",
        "attachment_id":"12240148453362055828"
    }

> [!WARNING]
> You cannot modify a file that is bigger than 25Mb
> [!WARNING]
> 'total_fragments' cannot be > 1
### Response

    Status: 204 No Content

## Get File 
> [!TIP]
> This endpoint is used to get file information

> [!NOTE]
> This endpoint requires Authentication.

### Request

`GET /api/file/<file_id>`
   

### Response

    Status: 200 OK

    {
        "isDir": false,
        "id": "nCzW5cWTWxbaUzUH8xwBfc",
        "name": "a.txt",
        "parent_id": "UiFtPmQuECmHAaGJgvRTbd",
        "extension": ".txt",
        "streamable": false,
        "size": 172,
        "type": "text",
        "encrypted_size": 0,
        "created": "2024-05-17 19:29",
        "last_modified": "2024-05-27 14:30",
        "preview_url": "https://get.pamparampam.dev/stream/nCzW5cWTWxbaUzUH8xwBfc:1sBwFs:e7fHxO2hFT8skYL1BEEIaP8oIHf08pTKHDIGMqGnRZU",
        "download_url": "https://get.pamparampam.dev/stream/nCzW5cWTWxbaUzUH8xwBfc:1sBwFs:e7fHxO2hFT8skYL1BEEIaP8oIHf08pTKHDIGMqGnRZU"
    }

## Get File Preview
> [!TIP]
> This endpoint is used to get preview or raw image formats such as CR2 or RW2

> [!NOTE]
> This endpoint requires Authentication.

### Request

`GET /api/file/<file_id>`
   

### Response

    Status: 200 OK

    {
        "isDir": false,
        "id": "nCzW5cWTWxbaUzUH8xwBfc",
        "name": "a.txt",
        "parent_id": "UiFtPmQuECmHAaGJgvRTbd",
        "extension": ".txt",
        "streamable": false,
        "size": 172,
        "type": "text",
        "encrypted_size": 0,
        "created": "2024-05-17 19:29",
        "last_modified": "2024-05-27 14:30",
        "preview_url": "https://get.pamparampam.dev/stream/nCzW5cWTWxbaUzUH8xwBfc:1sBwFs:e7fHxO2hFT8skYL1BEEIaP8oIHf08pTKHDIGMqGnRZU",
        "download_url": "https://get.pamparampam.dev/stream/nCzW5cWTWxbaUzUH8xwBfc:1sBwFs:e7fHxO2hFT8skYL1BEEIaP8oIHf08pTKHDIGMqGnRZU"
    }

