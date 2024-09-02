# I Drive

I Drive is a cloud storage system & online web browser that stores files on Discord


# Features

| Feature                                                | Support                |
|--------------------------------------------------------|------------------------|
| Login system                                           | ✅                      |
| Full File encryption                                   | ✅                      |
| Permission system                                      | ✅                      |
| Stream audio/video/images online without downloading   | ✅                      |
| Upload files & folders                                 | ✅                      |
| Websockets to show changes live    🎥                  | ✅                      |
| Drag and drop upload                                   | ⚠️ Coming soon         |
| Create folders                                         | ✅                      |
| Lock folders with password                             | ✅                      |
| Download files & folders                               | ✅                      |
| Bulk zip download                                      | ✅                      |
| Share files & folders                                  | ✅                      |
| Lock shares with password                              | ❌ Coming one day       |
| Delete files & folders                                 | ✅                      |
| Rename                                                 | ✅                      |
| Show folder                                            | ✅                      |
| Search                                                 | ✅                      |
| Wastebasket                                            | ✅                      |
| Supports Polish & English                              | ✅                      |
| Video thumbnails                                       | ✅                      |
| Caching support                                        | ✅                      |
| Move                                                   | ✅                      |
| Drag and drop move                                     | ✅                      |
| Code editor with highlighting                          | ✅                      |
| Raw image previewer                                    | ✅                      |
| Right-click context menu                               | ✅                      |
| Mobile support                                         | ✅                      |
| Supports uploading < 10 files in a single discord request | ✅                      |
| Backend rate limiting                                  | ✅                      |
| Error handling in upload process                       | ️ ⚠️ Only partial      |
| Proper handling of 429                                 | ❌   Coming one day                    |
| Custom ZIP64 Library to zip & stream files on the fly  | ❌   Coming one day                    |



# How it works

In essence, **I Drive** simply takes your upload files, and splits them to fit in Discord's (25MB) file size limit.
It then stores metadata about the file like the file name, size, extension, parent folder, time of creations and lots more 
in a separate central database.
This allows for a simple way to manage your files and download them back as one chunk.

# Technical Details

This section will include technical details about how **I Drive** is implemented. 
It exists to help understand why **I Drive** does certain things 'weirdly' and to know its limitations.
It also includes challenges in implementing a project like this, for people who're interested.

## Infrastructure

**I Drive** is made up of 3 main components.

### Frontend

Frontend is made with _vue3_ + _vite_. 
Vue Router is used for routing and Pinia as global state management. 
It's then built and served statically by NGINX                 

Why vue? Its data-driven approach makes it ideal for application which DOM is based on the underlying data.

### Main Backend

Main backend is made with 🐍 Python, Django, Daphne, Channels, Rest Framework 🐍
It's responsible for authenticating users and communicating with a database. 
It uses REST API to both serve & modify data.
The main backend has more than 40 different endpoints.


### Streamer Backend
Streamer backend is made with 🐍 Python, Django 🐍
It's responsible for streaming files from discord. 
It supports partial requests, streaming, in browser video/audio seeking, decryption, mimetypes

⚠️ It also will support ZIP requests one day ⚠️

### Database
Database is currently just sqlite3 next to Main Backend. 
This is mostly for simplicity reasons and low demand.

Sadly, this introduces challenges like streamer backend having no access to it. 
This is solved by main backend having special endpoints for serving metadata & download info about files.

# Other

### Why are Streamer Backend and Main Backend split?

Well Main Backend has to work with ASGI Protocol, and StreamingHttpResponse is fucked up on ASGI. 
Hence, there's a second server responsible for streaming under WSGI protocol - Streamer Backend.
Is this the most elegant solution? Definitely not. It was, however, the easiest to implement back in the day.


### Webhooks

**I Drive**, when uploading files, uploads them directly to Discord itself. The files never go tru **I Drive** backends. 
Instead, only metadata is passed to Main Backend. 
This introduces another challenge: How to securely upload files client side?
There are 2 main ways to do this.
- Using bots: More permissions, less secure, more cumbersome.
- Using webhooks: More secure, simpler, less permissions.

**I Drive** uses webhooks.


#### CORS

As with any secure site, discord doesn't allow other websites to fetch and download data from the API. 
This is a big issue, because it blocks the ability to download your files from the web client directly.

**I Drive** solves this via **Streamer backend**. Instead of the directly trying to fetch files from Discord, **Streamer Backend** is used as a Proxy. 
It also allows for easier joining of split files. And for bulk ZIP download.

Sadly this introduces problems: One of which is slower downloads which speeds are limited by **Streamer Backend**'s internet speed.