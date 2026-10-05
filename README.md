
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
![Discord](https://img.shields.io/badge/Discord-%235865F2.svg?style=for-the-badge&logo=discord&logoColor=white)
# I Drive

**I Drive** is a cloud storage system & online file browser that stores files on Discord.
It's basically like Google Drive, but it stores all files on Discord instead.<br>

Want to know how **iDrive** works under the hood? [Read here](YAP.md).

This checkout is undergoing a namespace/deletion refactor. Move, trash and restore
run through durable Celery batches. Permanent deletion uses durable scopes, bounded workers and supervisor recovery. See
[deletion status](delete.md) and [current gaps](TODO.md).


![Architecture diagram](./public/images/MainScreen.jpg)

# Demo
It's available at [https://idrive.pamparampam.dev](https://idrive.pamparampam.dev)

Credentials: `demo`/`demo`

**Please keep in mind that this project is maintained by a single student developer and is currently in an early alpha stage. 
If you encounter any bugs or issues, please report them.**


# Features

| Feature                                                              | Support |
|----------------------------------------------------------------------|---------|
| Online streaming and viewing of files without downloading            | ✅       |
| Move/rename/trash/restore files & folders                             | ✅       |
| Permanent deletion                                                   | ✅       |
| Share files & folders                                                | ✅       |
| Full File encryption                                                 | ✅       |
| Advanced search                                                      | ✅       |
| Login & Permission system                                            | ✅       |
| Dark theme                                                           | ✅       |
| Text/Code editor with highlighting                                   | ✅       |
| Mobile support                                                       | ✅       |
| Bulk zip download                                                    | ✅       |
| Supports Polish & English languages                                  | ✅       |
| Docker support                                                       | ✅       |
| Virtual lists to render tens of thousand of files in a single folder | ✅       |
| ZIP file archive viewer                                              | ✅       |
| Client side decryption                                               | ✅       |
| And a LOT more features!                                             | ✅       |

# Architecture diagram

![Architecture diagram](./public/images/Diagram.png)

# Fast deployment

1) Run `curl -fsSL https://raw.githubusercontent.com/pam-param-pam/I-Drive/refs/heads/master/scripts/bootstrap.sh -o bootstrap.sh && chmod +x bootstrap.sh && bash bootstrap.sh`
2) Go to browser and type `localhost`

To see all configurable options, run:
`bash bootstrap.sh --help`
<br>
<br>

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

# Local development

The local environment runs PostgreSQL, Redis, Prometheus, and Grafana in Docker. 
Django, Vite are run with hot reload.
Celery workers and Beat are required for accepted move/trash/restore operations,
folder hash/height repairs and scheduled work. They do not have hot reload.

> [!NOTE]
> The local configuration uses development credentials and settings. **Do not use it in production.**

## Prerequisites

- Python 3.12
- Node.js and npm
- Docker with Docker Compose
- A JetBrains IDE with Python support, such as PyCharm

## First-time setup

Select `backend/.venv` as the interpreter for the shared run configurations, then run **Setup local environment**. The setup installs the backend and frontend dependencies, starts the local Docker infrastructure, applies migrations, and creates the local administrator.

When setup finishes, configure the project structure in PyCharm:

1. Mark `backend` as **Sources Root**.
2. Mark `backend/staticfiles` as **Excluded**.

## Running the application

Select **Local development** from the run-configuration list and click **Run**. This configuration:

1. Starts PostgreSQL, Redis, Prometheus, and Grafana using `local-testing.docker-compose.yml`.
2. Waits until the infrastructure is ready.
3. Starts Django and Vite with hot reload.

After **Local development** is running, start the separate **Local Celery** configuration. It starts the general worker, cleanup queue worker, deletion queue worker and Celery Beat. The deletion queue processes scope expansion, remote attachment removal and bottom-up finalization.

Stopping a run configuration does not stop containers!

## Local addresses

| Service    | Address                 |
|------------|-------------------------|
| Frontend   | http://localhost:5173   |
| Backend    | http://localhost:8000   |
| Grafana    | http://localhost:3000   |
| Prometheus | http://localhost:9090   |

The default Django and Grafana login is `admin` / `admin`.

## Configuration

Local defaults are defined by the launcher and `local-testing.docker-compose.yml`. To override them, create or edit `.env` in the repository root. The same file is loaded by the native processes and Docker Compose.

Grafana provisioning and dashboards are mounted from `grafana/`. Prometheus loads its configuration from `prometheus/prometheus.yml`, so local monitoring changes do not require custom development images.


# Performance

Throughput depends on browser processing, backend bandwidth/CPU, encryption,
attachment sizes and Discord rate limits. The earlier speed figures were historical
measurements and are not a benchmark of this checkout.

# Developer documentation

[YAP.md](YAP.md) links to the current architecture documents.
[TODO.md](TODO.md) records implementation gaps.
[backend/STYLE.md](backend/STYLE.md) describes backend conventions.
