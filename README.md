
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
![Discord](https://img.shields.io/badge/Discord-%235865F2.svg?style=for-the-badge&logo=discord&logoColor=white)
<img src="https://img.shields.io/badge/build-passing-g" alt="Build Status"/>
# I Drive

**I Drive** is a cloud storage system & online file browser that stores files on Discord.
It's basically like Google Drive, but it stores all files on Discord instead.<br>

Want to know how **iDrive** works under the hood? [Read here](https://github.com/pam-param-pam/I-Drive/blob/master/YAP.md)


![Architecture diagram](./public/images/MainScreen.jpg)

# Demo
~~It's available at `https://idrive.pamparampam.dev`~~

~~Credentials: `demo`/`demo`~~

Sorry, no demo currently.

# Features

| Feature                                                              | Support |
|----------------------------------------------------------------------|---------|
| Online streaming and viewing of files without downloading            | ✅       |
| Delete/move/rename files & folders                                   | ✅       |
| Share files & folders                                                | ✅       |
| Full File encryption                                                 | ✅       |
| Advanced search                                                      | ✅       |
| Login & Permission system                                            | ✅       |
| Dark theme                                                           | ✅       |
| Code editor with highlighting                                        | ✅       |
| Mobile support                                                       | ✅       |
| Bulk zip download                                                    | ✅       |
| Supports Polish & English languages                                  | ✅       |
| Docker support                                                       | ✅       |
| Virtual lists to render tens of thousand of files in a single folder | ✅       |
| ZIP file archive viewer                                              | ✅       |
| And a LOT more features!                                             | ✅       |

# Architecture diagram

![Architecture diagram](./public/images/Diagram.png)

# Fast deployment

1) Run `curl -fsSL https://raw.githubusercontent.com/pam-param-pam/I-Drive/refs/heads/master/scripts/bootstrap.sh -o bootstrap.sh && chmod +x bootstrap.sh && bash bootstrap.sh`
2) Go to browser and type `localhost`

**How to configure Discord Settings:**

1. Enable Discord **Developer Mode**.  
   See: [How to enable Developer Mode](https://www.youtube.com/watch?v=8FNYLcjBERM)

2. Create a new Discord server and copy its **Guild ID**.  
   See: [How to copy the Guild ID](https://www.youtube.com/watch?v=HjkRZy5d_qM&t=40s)

3. Create a new Discord bot:  
   [Create a new Discord application](https://discord.com/developers/applications?new_application=true)

4. In the Discord Developer Portal, open your bot settings and enable the required intent:

   **Bot → Privileged Gateway Intents → Message Content Intent**

5. Generate an invite URL for the bot:

   **OAuth2 → URL Generator → Scopes → bot**

6. Select the required bot permissions.

   You can either select **Administrator**, or grant the following permissions manually:

   - Manage Channels
   - Manage Roles
   - Manage Webhooks 
   - Manage Messages
   - View Channels
   - Read Message History
   - Send Messages
   - Attach Files

7. Open the bot settings, reset the bot token, and copy the new access token:

   **Bot → Reset Token**

8. Open the generated invite URL and invite the bot to your Discord server.

After completing these steps, you should have:

- the Discord server
- its Guild ID
- the primary bot configured
- the bot token

> [!IMPORTANT] 
> If you want to add another bot in the future, you can skip step 6. The required permissions will be granted to the bot automatically after you invite the bot to the server.

# Building from source

### ⚠️THIS IS NOT TESTED AND WILL PROBABLY NOT WORK ⚠️
<br>

**You need python version 3.11 installed. 
Tested on Node v20.10.0**


1) Clone this repository
* `git clone https://github.com/pam-param-pam/I-Drive`

2) Start redis.
* `docker run -d --name dev_idrive_redis -p 6379:6379 redis:latest redis-server --requirepass 1234`

3) Start postgres
* `docker run -d --name dev_idrive_postgres -e POSTGRES_DB=dev_idrive_postgres -e POSTGRES_USER=admin -e POSTGRES_PASSWORD=1234 -p 5432:5432 -v dev_idrive_postgres_data:/var/lib/postgresql/data postgres:16`

4) Navigate to the cloned repo. Find `frontend` dir. In it create `.env` file and put these variables:
````
VITE_BACKEND_BASE_URL=http://localhost:8000
VITE_BACKEND_BASE_WS=ws://localhost:8000
````

5) Inside the `frontend` dir run these commands:
* `npm install` to install all requirements
* `npm run dev -- --host 0.0.0.0 --port 5173` to start the frontend dev server

6) Navigate back to the cloned repo root. Find `backend` dir. In it create `.env` file and put these variables:
```
IS_DEV_ENV=True
PROTOCOL=http
DEPLOYMENT_HOST=localhost
NGINX_PORT=80

BACKEND_SECRET_KEY=very_secret_key
BACKEND_BASE_URL=http://localhost:8000

REDIS_PASSWORD=1234
REDIS_ADDRESS=localhost
REDIS_PORT=6379

POSTGRES_ADDRESS=localhost
POSTGRES_PORT=5432
POSTGRES_NAME=dev_idrive_postgres
POSTGRES_USER=admin
POSTGRES_PASSWORD=1234

```
7) Inside `backend` dir run these commands.

```
# 1. Create virtual environment
py -3.11 -m venv .venv

# 2. Activate the virtual environment
.venv\Scripts\activate 

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run migrations
python manage.py migrate

# 5. Create admin user
python manage.py createuser

# 6. Start backend dev server
python manage.py runserver 0.0.0.0:8000

# 7. start all celeries
celery -A website worker -l INFO -P eventlet
celery -A website worker -l INFO --pool=solo -Q wsQ
celery -A website worker -l INFO --pool=solo -Q deletion -c 1
celery -A website beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

#### Everything should work now, head over to `localhost:5173` to see the website


# PS
Dear Discord, please don't sue me 👉👈

