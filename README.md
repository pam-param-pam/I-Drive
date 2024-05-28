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
> [!NOTE]
> This endpoint requires Authentication.

Deletes auth token and flushes user's session

### Request

`POST /auth/token/logout/`


### Response

    Status: 204 No Content


## Get User
Gets user's information

### Request

`GET /auth/user/me/`

**Headers**

    {
        "Authorization": Token *auth_token*,
        "Content-Type": "application/json"

    }
   


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

### Request

`POST /api/user/changepassword/`

**Headers**

    {
        "Authorization": Token *auth_token*,
    }
   
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

### Request

`POST /api/user/updatesettings/`

**Headers**

    {
        "Authorization": Token *auth_token*,
    }
   
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


### Request

`POST /api/user/updatesettings/`

**Headers**

    {
        "Authorization": Token *auth_token*,
    }
   
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

> [!NOTE]
> Useful information that users should know, even when skimming content.