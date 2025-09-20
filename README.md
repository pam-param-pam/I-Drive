
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
![Discord](https://img.shields.io/badge/Discord-%235865F2.svg?style=for-the-badge&logo=discord&logoColor=white)
<img src="https://img.shields.io/badge/build-passing-g" alt="Build Status"/>
# I Drive

I Drive is a cloud storage system & online file browser that stores files on Discord.

It's basically like Google Drive, but instead it stores all files in Discord.

# Demo
It's available at `https://idrive.pamparampam.dev`

Credentials: `demo`/`demo`


# Features

| Feature                                                              | Support |
|----------------------------------------------------------------------|---------|
| Login & Permission system                                            | ✅       |
| Full File encryption                                                 | ✅       |
| Online streaming and viewing of files without downloading            | ✅       |
| Support for file/upload/drag and drop uploads                        | ✅       |
| Locked folders                                                       | ✅       |
| Bulk zip download                                                    | ✅       |
| Mobile support                                                       | ✅       |
| Websockets to show changes live   🎥                                 | ✅       |
| Share files & folders                                                | ✅       |
| Delete/move/rename files & folders                                   | ✅       |
| Search                                                               | ✅       |
| Wastebasket                                                          | ✅       |
| Supports Polish & English languages                                  | ✅       |
| Code editor with highlighting                                        | ✅       |
| Raw image previewer                                                  | ✅       |
| Docker support                                                       | ✅       |
| Dark theme                                                           | ✅       |
| Virtual lists to render tens of thousand of files in a single folder | ✅       |


| TODO List                                              | Status               |
|--------------------------------------------------------|----------------------|
| Proper frontend networking & handling of errors        | 🛠️  in progress     |
| Error handling in upload process                       | ⚠️  Only partial     |
| Optimize shares                                        | ❌  Coming one day    |
| cached docker build                                    | ❌  Coming one day    |
| Virtual list view                                      | ⛔  Coming prob never |
| Stop, pause, abort uploads                             | ⛔  Coming prob never |
| Editor support for large files                         | ⛔  Coming prob never |
| Change  __prependStaticUrl                             | ⛔  Coming prob never |
| multiple files in 1 Discord attachment support         | ⛔  Coming prob never |
| add deselect                                           | ⛔  Coming prob never |
| add multiple file select for mobile                    | ⛔  Coming prob never |
| switch to a different backend framework                | ⛔  Coming prob never |
| load balancing with round robin for nginx              | ⛔  Coming prob never |
| add resolution to images                               | ⛔  Coming prob never |
| move away from cancelToken in axios to abortController | ⛔  Coming prob never |

fix urls mapping, clean Discord class, tasks, shares

| BUGS                                                                    |
|-------------------------------------------------------------------------|
| fix 401 in locked folders in shares                                     |
| Fix file download for mobile                                            |
| fix tasks                                                               |
| fix mobile number download info frontend                                |
| CannotProcessDiscordRequestError in tasks                               |
| remove dangling discord attachments is buggy at best                    |
| zip timeouts on thousands of files                                      |
| share -> settings error                                                 |
| upload file prompt displays on top of context menu                      |
| handle empty files (upload, editor, anything else)                      |
| fix next/prev on desktop with images move                               |
| share password bugged                                                   |
| 0 byte (corrupted uploaded file) causes zip download to completely fail |
| fix locked folders duplicate tab                                        |
| fix upload on frontend and make it less error prone                     |
| fix race conditions in upload on frontend                               |

> [!WARNING]  
> This section is very much unfinished

# How it works

In essence, **I Drive** simply takes your upload files, and splits them into chunks to fit in Discord's (10Mb) file size limit. 
They are then encrypted and uploaded to Discord. After the upload is done, file's metadata is sent to backend and stored into a central database.
This allows for a simple way of viewing, managing, and downloading of your files

# Technical Details

This section includes technical details about how **I Drive** is implemented. 
It exists to help understand why **I Drive** does certain things 'weirdly' and to know its limitations.
It also includes challenges in implementing a project like this, for people who're interested.

## Infrastructure

**I Drive** is made up of 5 main components.

### Frontend

Frontend is made with _vue3_ + _vite_. 
Vue Router is used for routing and Pinia as global state management. 
It's then built and served statically by NGINX                 

Why vue? Its data-driven approach makes it ideal for application which DOM is based on the underlying data.

### Backend

Main backend is made with 🐍 Python, Django, Daphne, Channels, Rest Framework 🐍
It's responsible for authenticating users and communicating with a database. 
It uses REST API to both serve & modify data.
The main backend has more than 40 different endpoints.

It's also  responsible for streaming files from Discord. 
It supports partial requests, streaming, in browser video/audio seeking, decryption, mimetypes

Thanks to a [custom zipFly](https://github.com/pam-param-pam/ZipFly) library it also supports streaming zip files "on the fly"


### Database
Database is currently just sqlite3 file next to Backend. 
This is mostly for simplicity reasons and low demand.

### Redis
Fast in memory database for caching and message broker for celery.

### Celery
Asynchronous task queue for delegating long tasks like file deletion outside of HTTP call lifecycle.


## Solving Discord's rate limit problems
    
On average Discord allows a single bot to make 1 request a second, that's way to little! 
That's why, for **iDrive** to work, a single user needs at least few bots, 
this way backend can switch between tokens and bypass Discord's ratelimits. 

Discord issues cloudflare bans if you make more than 10k 4xx requests in 10 minutes. 
**iDrive** tries to avoid this as much as possible, including throwing 502 errors when it can't handle more requests

The same concept applies to webhooks.

## Why use both webhooks and Discord bots? 
Why are webhooks needed? Why not use Discord bots to upload files?

Discord bots are in my opinion too powerful to send tokens back and forth in the browser. 
In an unlikely situation, a third party could steal bot's token and access all 
files stored(encrypted or not) on a Discord server. 
Discord bots if given too many permissions would also allow for easy raiding and greefing.

Webhooks on the other hand can only send messages, and delete/modify their own.

## Why is this/that so slow!
It's written is python, what do you expect. Rewrite it in rust!


## Docker support
I drive is fully dockerized! Yay. There are 3 containers managed by `docker compose`: 

* Backend, containing a backend server and celery
* Nginx, it's responsible for reverse proxy, cache, and serving the static frontend files.
* Redis



# Deployment

1) Create a fresh directory and in it
2) create `docker-compose.yml` file. Copy content from [here ](https://raw.githubusercontent.com/pam-param-pam/I-Drive/refs/heads/master/docker-compose.yml) to it.

3) create `nginx.conf` file. Copy content from [here ](https://raw.githubusercontent.com/pam-param-pam/I-Drive/refs/heads/master/nginx.conf) to it.
4) create `.env` file and copy these values:
```
IS_DEV_ENV=True     
I_DRIVE_BACKEND_SECRET_KEY=your secret key
PROTOCOL=http
```

5) Run `docker-compose up`
6) Run `docker exec -it idrive-backend bash`
7) Run `python manage.py migrate website` to setup a database
8) Run `python manage.py createsuperuser` to create admin user
9) Go to browser and type `localhost`


# Building from source

1) Clone this repository
* `git clone https://github.com/pam-param-pam/I-Drive`

2) Start a redis server. The easiest way is to run redis with [docker](https://hub.docker.com/_/redis) 

2) Navigate to frontend dir and create .env file and put these values:
* `VITE_BACKEND_BASE_URL=http://localhost:8000`
* `VITE_BACKEND_BASE_WS=ws://localhost:8000`

3) Then run these commands:
* `npm install`
* `npm run dev -- --host`

3) Navigate to backend dir and create .env file and put these values:
* `I_DRIVE_BACKEND_SECRET_KEY`=<your_secret_key>
* `IS_DEV_ENV=True`
* `I_DRIVE_REDIS_ADDRESS=localhost`
* `I_DRIVE_REDIS_PORT=6379`
* `I_DRIVE_BACKEND_STORAGE_DIR=`
* `BACKEND_BASE_URL=http://localhost:8000`

4) Then run these commands:
* `pip install -r requirements.txt`
* Run `python manage.py migrate website` to setup a database 
* Run `python manage.py createsuperuser` to create admin user
* `python manage.py runserver 0.0.0.0:8000`

5) Everything should work now, head over to `localhost` to see the website


### All .env variables:
*THIS IS NOT FINISHED*

| Name                           | default (with docker compose)        | required (with docker compose) | required (building from source) | description |
|--------------------------------|--------------------------------------|--------------------------------|---------------------------------|-------------|
| I_DRIVE_BACKEND_SECRET_KEY     | -                                    | Yes                            | Yes                             | todo        |
| IS_DEV_ENV                     | false                                | No                             | Yes                             | todo        |
| DEPLOYMENT_HOST                | localhost:2137                       | No                             | Yes                             | todo        |
| PROTOCOL                       | http                                 | No                             | Yes                             | todo        |
| NGINX_PORT                     | 2137                                 | No                             | Yes                             | todo        |
| I_DRIVE_REDIS_ADDRESS          | redis                                | No                             | Yes                             | todo        |
| I_DRIVE_REDIS_PORT             | 6379                                 | No                             | Yes                             | todo        |
| I_DRIVE_BACKEND_STORAGE_DIR    | /app/data                            | No                             | Yes                             | todo        |
| BACKEND_BASE_URL               | ${PROTOCOL}://${DEPLOYMENT_HOST}/api | No                             | Yes                             | todo        |
| VITE_BACKEND_BASE_URL          | ${PROTOCOL}://${DEPLOYMENT_HOST}/api | No                             | Yes                             | todo        |
| VITE_BACKEND_BASE_WS           | ${PROTOCOL}://${DEPLOYMENT_HOST}/api | No                             | Yes                             | todo        |


# PS
Dear Discord, please don't sue me 👉👈

