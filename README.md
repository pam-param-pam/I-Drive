
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
![Discord](https://img.shields.io/badge/Discord-%235865F2.svg?style=for-the-badge&logo=discord&logoColor=white)
<img src="https://img.shields.io/badge/build-passing-g" alt="Build Status"/>
# I Drive

I Drive is a cloud storage system & online web browser that stores files on Discord


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


| TODO List                                                    | Status               |
|--------------------------------------------------------------|----------------------|
| fix possible access to locked items via websocket send event | ☠️  ASAP             |
| Proper frontend networking & handling of errors              | 🛠️  in progress     |
| events in search context like file move                      | 🛠️  in progress     |
| fix 401 in locked folders in shares                          | 🛠️  in progress     |
| Error handling in upload process                             | ⚠️  Only partial     |
| Auto scroll when dragging                                    | ❌  Coming one day    |
| fix enable-scroll css cuz it's cursed                        | ❌  Coming one day    |
| cached docker build                                          | ❌  Coming one day    |
| fix scrollbar in shares prompt                               | ❌  Coming one day    |
| fix tasks                                                    | ❌  Coming one day    |
| Virtual list view                                            | ⛔  Coming prob never |
| Stop, pause, abort uploads                                   | ⛔  Coming prob never |
| Editor support for large files                               | ⛔  Coming prob never |
| fix __prependStaticUrl                                       | ⛔  Coming prob never |
| multiple files in 1 discord attachment support               | ⛔  Coming prob never |




# How it works

In essence, **I Drive** simply takes your upload files, and splits them into chunks to fit in Discord's (10Mb) file size limit. 
They are then encrypted and uploaded to discord. After the upload is done, file's metadata is sent to backend and stored into a central database.
This allows for a simple way of viewing, managing, and downloading of your files

# Technical Details

This section will include technical details about how **I Drive** is implemented. 
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

It's also  responsible for streaming files from discord. 
It supports partial requests, streaming, in browser video/audio seeking, decryption, mimetypes

Thanks to a [custom zipFly](https://github.com/pam-param-pam/ZipFly) library it also supports streaming zip files "on the fly"


### Database
Database is currently just sqlite3 file next to Backend. 
This is mostly for simplicity reasons and low demand.

### Redis
Fast in memory database for caching and message broker for celery.

### Celery
Asynchronous task queue for delegating long tasks like file deletion outside of HTTP call lifecycle.


## Solving discord's rate limit problems
    
On average discord allows a single bot to make 1 request a second, that's way to little! 
That's why, for **iDrive** to work, a single user needs at least few bots, 
this way backend can switch between tokens and bypass discord's ratelimits. 

Discord issues cloudflare bans if you make more than 10k 4xx requests in 10 minutes. 
**iDrive** tries to avoid this as much as possible, including throwing 502 errors when it can't handle more requests

The same concept applies to webhooks.

## Why use both webhooks and discord bots? 
Why are webhooks needed? Why not use discord bots to upload files?

Discord bots are in my opinion too powerful to send tokens back and forth in the browser. 
In an unlikely situation, a third party could steal bot's token and access all 
files stored(encrypted or not) on a discord server. 
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
todo

# PS
Dear discord, please don't sue me 👉👈

