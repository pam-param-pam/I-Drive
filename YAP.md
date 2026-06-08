# How it works

In essence, **I Drive** simply takes your upload files, and splits them into chunks to fit in Discord's (10Mb) file size limit. 
They are then encrypted and uploaded to Discord. After the upload is done, file's metadata is sent to backend and stored into a backend database.
This allows for a simple way of viewing, managing, and downloading of your files.


# Technical Details
In reality the Frontend does a LOT more than just splitting the file into chunks.
It has to:
- Calculate crc checksum 
- Generate media metadata
- Generate thumbnails
- Extract subtitles
- Encrypt the file
- Efficiently package multiple files into a single discord request
- And more!

The same thing applies to pretty much every part of this app. Even if something looks simple at first glance. 
It's most likely pretty complicated under the hood. 
After all, this entire project has more than **36k** lines of code. 
And another **2k** of configuration and translation lines.


## Infrastructure

**I Drive** is made up of 5 main components.

### Frontend

Frontend is made with _vue3_ + _vite_. 
Vue Router is used for routing and Pinia as global state management.<br>
It's then built and served statically by NGINX.               

Why vue? Its data-driven approach makes it ideal for application which DOM is based on the underlying data.

### Backend

Backend is made with 🐍 Python, Django, Daphne, Channels, Rest Framework 🐍.<br>
It's responsible for authenticating users and communicating with a database. 
It uses REST API to both serve & modify data.
It has more than 85 different endpoints.

Backend uses websockets to send events to the client such as: _data changes, notifications, messages etc_.<br>
It's also responsible for streaming files from Discord. 
It supports partial requests, streaming, in browser video/audio seeking, decryption.

Thanks to a [custom zipFly](https://github.com/pam-param-pam/ZipFly) library it also supports streaming zip files "on the fly".


### Database
Postgres is currently used as a database.

### Redis
Redis is used as a fast in memory database for caching and message broker for celery.
It also serves as a channel layer for django websockets.
It's also used as a global memory for all python processes to manage discord's ratelimits.

### Celery
Asynchronous task queue for delegating long tasks outside of HTTP call lifecycle like:
1) File deletion 
2) Generating thumbnails out of Raw Images
3) Periodically cleaning up the database
4) Moving files between folders or to Trash

## Solving Discord's rate limit problems
    
On average Discord allows a single bot to make 1 request a second, that's way too little! 
That's why, for **iDrive** to work, a single user needs at least few bots, 
this way backend can switch between tokens and bypass Discord's ratelimits. 
The same thing applies to Discord channels and webhooks. 
Sadly discord still groups all requests per ip as well, so the ratelimits are still sometimes hit.

Discord issues cloudflare bans if you make more than 10k 4xx requests in 10 minutes. 
**iDrive** tries to avoid this as much as possible, including throwing 502 errors when it can't handle more requests.


## Why use both webhooks and Discord bots? 
Why are webhooks needed? Why not use Discord bots to upload files?

Discord bots are in my opinion too powerful to send tokens back and forth in the browser. 
In an unlikely situation, a third party could steal bot's token and access all 
files stored(encrypted or not) on a Discord server. 
Discord bots if given too many permissions would also allow for easy raiding and greefing.

Webhooks on the other hand can only send messages, and delete/modify their own ones.

## Why is this/that so slow!
It's written in python, what do you expect. Rewrite it in rust!