import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from website.core.errors import CannotProcessDiscordRequestError, DiscordError
from website.discord.Discord import discord
from website.models import Bot, Channel


class Command(BaseCommand):
    help = "Measure sustained Discord request throughput"

    def add_arguments(self, parser):
        parser.add_argument("--user-id", required=True, type=int)
        parser.add_argument("--bot-id")
        parser.add_argument("--duration", type=int, default=120)
        parser.add_argument("--window", type=int, default=5)
        parser.add_argument("--workers", type=int, default=32)

    def handle(self, *args, **options):
        user = User.objects.get(id=options["user_id"])

        bot = None
        if options["bot_id"]:
            bot = Bot.objects.get(id=options["bot_id"])

        channels = list(
            Channel.objects
            .filter(owner=user)
            .values_list("discord_id", flat=True)
        )

        if not channels:
            raise RuntimeError(f"User {user.id} has no Discord channels")

        channel_id = random.choice(channels)

        duration = options["duration"]
        window = options["window"]
        workers = options["workers"]

        # Cheap, read-only request. Avoids the application-level message cache.
        path = f"/channels/{channel_id}/messages"

        counters = {
            "ok": 0,
            "discord_errors": 0,
            "rate_limits": 0,
            "local_throttles": 0,
            "other_errors": 0,
        }

        lock = threading.Lock()
        stop = threading.Event()

        def increment(name):
            with lock:
                counters[name] += 1

        def worker():
            while not stop.is_set():
                try:
                    discord.manager.execute_bot_once(
                        user=user,
                        method="GET",
                        url=path,
                        bot=bot,
                        params={"limit": 1},
                    )
                    increment("ok")

                except CannotProcessDiscordRequestError:
                    # Redis-backed allocator currently has no request available.
                    increment("local_throttles")

                    # Prevent tight CPU/Redis spinning while locally throttled.
                    stop.wait(0.01)

                except DiscordError as exc:
                    increment("discord_errors")

                    if exc.status == 429:
                        increment("rate_limits")

                        retry_after = getattr(exc, "retry_after", None)
                        if retry_after:
                            stop.wait(float(retry_after))

                except Exception:
                    increment("other_errors")

        started = time.monotonic()
        end_at = started + duration

        previous = counters.copy()
        previous_time = started

        self.stdout.write(f"Using Discord channel {channel_id}")
        self.stdout.write(
            f"Running for {duration}s with {workers} workers, "
            f"reporting every {window}s"
        )

        executor = ThreadPoolExecutor(max_workers=workers)
        futures = [executor.submit(worker) for _ in range(workers)]

        interrupted = False

        try:
            while True:
                now = time.monotonic()

                if now >= end_at:
                    break

                sleep_time = min(window, end_at - now)
                time.sleep(sleep_time)

                now = time.monotonic()

                with lock:
                    current = counters.copy()

                elapsed = now - previous_time

                interval_ok = current["ok"] - previous["ok"]
                interval_discord_errors = (
                    current["discord_errors"]
                    - previous["discord_errors"]
                )
                interval_rate_limits = (
                    current["rate_limits"]
                    - previous["rate_limits"]
                )
                interval_local_throttles = (
                    current["local_throttles"]
                    - previous["local_throttles"]
                )
                interval_other_errors = (
                    current["other_errors"]
                    - previous["other_errors"]
                )

                # These calls actually reached Discord and returned an HTTP response.
                interval_requests = (
                    interval_ok
                    + interval_discord_errors
                )

                self.stdout.write(
                    f"{now - started:6.1f}s | "
                    f"{interval_requests / elapsed:6.2f} req/s | "
                    f"OK {interval_ok:4d} | "
                    f"429 {interval_rate_limits:3d} | "
                    f"local-throttle {interval_local_throttles:5d} | "
                    f"other-errors {interval_other_errors:3d}"
                )

                previous = current
                previous_time = now

        except KeyboardInterrupt:
            interrupted = True
            self.stdout.write("\nInterrupted")

        finally:
            stop.set()

            executor.shutdown(
                wait=True,
                cancel_futures=True,
            )

        elapsed = time.monotonic() - started

        with lock:
            final = counters.copy()

        total_requests = (
            final["ok"]
            + final["discord_errors"]
        )

        self.stdout.write("")

        if interrupted:
            self.stdout.write("Test interrupted by user")

        self.stdout.write(
            f"Total: {total_requests} Discord requests in "
            f"{elapsed:.2f}s = {total_requests / elapsed:.2f} req/s"
        )

        self.stdout.write(
            f"OK={final['ok']}, "
            f"429={final['rate_limits']}, "
            f"Discord errors={final['discord_errors']}, "
            f"local throttles={final['local_throttles']}, "
            f"other errors={final['other_errors']}"
        )