# I Drive

I Drive is a cloud storage system & online web browser that stores files on Discord


# Features

| Feature                                                   | Support            |
|-----------------------------------------------------------|--------------------|
| Login system                                              | ✅                  |
| Full File encryption                                      | ✅                  |
| Permission system                                         | ✅                  |
| Stream audio/video/images online without downloading      | ✅                  |
| Upload files & folders                                    | ✅                  |
| Websockets to show changes live   🎥                      | ✅                  |
| Create folders                                            | ✅                  |
| UI error handling                                         | ✅                  |
| Lock folders with password                                | ✅                  |
| Download files & folders                                  | ✅                  |
| Bulk zip download                                         | ✅                  |
| Share files & folders                                     | ✅                  |
| Delete files & folders                                    | ✅                  |
| Rename                                                    | ✅                  |
| Show folder                                               | ✅                  |
| Search                                                    | ✅                  |
| Wastebasket                                               | ✅                  |
| Supports Polish & English                                 | ✅                  |
| Video thumbnails                                          | ✅                  |
| Caching support                                           | ✅                  |
| Move                                                      | ✅                  |
| Drag and drop move                                        | ✅                  |
| Code editor with highlighting                             | ✅                  |
| Raw image previewer                                       | ✅                  |
| Right-click context menu                                  | ✅                  |
| Mobile support                                            | ✅                  |
| Supports uploading < 10 files in a single discord request | ✅                  |
| Backend rate limiting                                     | ✅                  |
| Custom ZIP64 Library to zip & stream files on the fly     | ✅                  |
| Docker support                                            | ⚠️  Coming soon    |
| Lock shares with password                                 | ⚠️  Only partial   |
| Drag and drop upload                                      | ⚠️  Coming soon    |
| Error handling in upload process                          | ⚠️  Only partial   |
| Proper handling of 429                                    | ❌  Coming one day  |
| Proper encryption of big files > 2GB                      | ❌  Coming one day  |
| Proper frontend networking & handling of errors           | ❌  Coming one day  |



# How it works

In essence, **I Drive** simply takes your upload files, and splits them to fit in Discord's (25MB) file size limit.
It then stores metadata about the file like the file name, size, extension, parent folder, time of creations and lots more 
in a separate central database.
This allows for a simple way to manage your files and download them back as one File.

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

### Backend

Main backend is made with 🐍 Python, Django, Daphne, Channels, Rest Framework 🐍
It's responsible for authenticating users and communicating with a database. 
It uses REST API to both serve & modify data.
The main backend has more than 40 different endpoints.

It's also  responsible for streaming files from discord. 
It supports partial requests, streaming, in browser video/audio seeking, decryption, mimetypes

Thanks to a [custom zipFly](https://github.com/pam-param-pam/ZipFly) library it also supports streaming zip files "on the fly"


### Database
Database is currently just sqlite3 next to Main Backend. 
This is mostly for simplicity reasons and low demand.

Sadly, this introduces challenges like streamer backend having no access to it. 
This is solved by main backend having special endpoints for serving metadata & download info about files.

### Redis
Fast in memory databases for caching.

### Celery
Asynchronous task queue for delegating long taks like file deletion outside HTTP call lifecycle.

# Other

### Webhooks

**I Drive**, when uploading files, uploads them directly to Discord itself. The files never go tru **I Drive** backends. 
Instead, only metadata is passed to Main Backend. 
This introduces another challenge: How to securely upload files client side?
There are 2 main ways to do this.
- Using bots: More permissions, less secure, more cumbersome.
- Using webhooks: More secure, simpler, less permissions.

**I Drive** uses webhooks.
