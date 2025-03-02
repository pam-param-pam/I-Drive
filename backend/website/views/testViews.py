import asyncio
import os
import time

import aiohttp
from asgiref.sync import sync_to_async
from django.contrib.auth.models import User
from django.http import FileResponse
from django.http import JsonResponse, HttpResponse
from django.http import StreamingHttpResponse
from rest_framework.decorators import api_view, throttle_classes

from ..models import File
from ..utilities.Decryptor import Decryptor
from ..utilities.Discord import discord
from ..utilities.decorators import check_signed_url, check_file
from ..utilities.throttle import MediaThrottle, defaultAuthUserThrottle


@api_view(['GET'])
@throttle_classes([MediaThrottle])
# @handle_common_errors
def get_folder_password(request):
    user = User.objects.get(id=1)
    discord._get_channel_id(user)

    bots_dict = []

    state = discord.users[user.id]
    retry_timestamp = state.get('retry_timestamp')
    if retry_timestamp:
        remaining_time = state['retry_timestamp'] - time.time()
    else:
        remaining_time = None

    for token in state['tokens'].values():
        bots_dict.append(token)

    return JsonResponse({"locked": state['locked'], "retry_after": remaining_time, "bots": bots_dict}, safe=False)

@api_view(['GET'])
def test_stream_file(request):
    file_name = "input.mp4"
    file_path = "D:\Projects\IDrive\\backend\website\\views\input.mp4"
    # Open the file in binary mode
    file = open(file_path, 'rb')

    # Get the file size
    file_size = os.path.getsize(file_path)

    # Get the 'Range' header from the request (if present)
    range_header = request.headers.get('Range', None)

    # If a Range header is provided, parse the byte range
    if range_header:
        # Example of Range header: "bytes=0-499"
        byte_range = range_header.split('=')[1]
        start, end = byte_range.split('-')

        start = int(start)
        end = int(end) if end else file_size - 1

        if start >= file_size:
            return HttpResponse("Requested range not satisfiable", status=416)

        # Open the file in binary mode
        file = open(file_path, 'rb')

        # Set the response to only include the specified byte range
        file.seek(start)
        file_data = file.read(end - start + 1)

        # Prepare the response with the appropriate status and headers
        response = HttpResponse(file_data, status=206)  # HTTP 206: Partial Content
        response['Content-Type'] = 'application/octet-stream'
        response['Content-Range'] = f'bytes {start}-{end}/{file_size}'
        response['Content-Length'] = len(file_data)

        return response
    else:
        # If no Range header is present, return the whole file
        file = open(file_path, 'rb')

        # Return a full file response
        response = FileResponse(file)
        response['Content-Type'] = 'application/octet-stream'
        response['Content-Disposition'] = f'attachment; filename="{file_name}"'

        return response


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@check_signed_url
@check_file
def hyper_stream_file(request, file_obj: File):
    print(f"========={file_obj.name}=========")

    is_inline = request.GET.get('inline', False)
    fragments = file_obj.fragments.all().order_by('sequence')
    user = file_obj.owner

    content_disposition = f'{"inline" if is_inline else "attachment"}; filename="{file_obj.name}"'
    BATCH = 2
    async def file_iterator():
        # Convert fragments to an ordered list
        fragment_list = [fragment async for fragment in fragments]
        total_fragments = len(fragment_list)
        if not fragment_list:
            return

        buffer = {}  # Stores decrypted fragments by sequence
        pending_tasks = set()  # Tracks ongoing fetch tasks
        current_seq = 0  # Current fragment being processed
        sem = asyncio.Semaphore(BATCH)  # Limit concurrent fetches

        async def fetch_fragment(seq):
            """Fetch and decrypt a single fragment"""
            async with sem:
                fragment = fragment_list[seq]
                url = await sync_to_async(discord.get_attachment_url)(user, fragment)
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        response.raise_for_status()
                        encrypted_data = await response.read()

                # Initialize decryptor with fragment's offset
                decryptor = Decryptor(
                    method=file_obj.get_encryption_method(),
                    key=file_obj.key,
                    iv=file_obj.iv,
                    start_byte=fragment.offset
                )
                buffer[seq] = decryptor.decrypt(encrypted_data)

        def schedule_fetches(start_seq):
            """Schedule next batch of n fragments"""
            for seq in range(start_seq, min(start_seq + BATCH, total_fragments)):
                if seq not in buffer and seq not in pending_tasks:
                    task = asyncio.create_task(fetch_fragment(seq))
                    pending_tasks.add(task)
                    task.add_done_callback(lambda t: pending_tasks.discard(t))

        # Initial fetch - first fragment + next 5 in background
        await fetch_fragment(0)  # Fetch first fragment immediately
        schedule_fetches(1)  # Start background fetch for next 5

        # Stream fragments in order
        while current_seq < total_fragments:
            if current_seq in buffer:
                # Yield decrypted data chunk by chunk
                decrypted_data = buffer.pop(current_seq)
                for i in range(0, len(decrypted_data), 8192 * 16):
                    yield decrypted_data[i:i + 8192 * 16]

                # Schedule new fragments as we progress
                if current_seq % BATCH == 0:
                    schedule_fetches(current_seq + 1)
                current_seq += 1
            else:
                # Wait for at least one fragment to complete
                if pending_tasks:
                    done, _ = await asyncio.wait(
                        pending_tasks,
                        return_when=asyncio.FIRST_COMPLETED
                    )
                else:
                    await asyncio.sleep(0.01)

    response = StreamingHttpResponse(
        file_iterator(),
        content_type=file_obj.mimetype,
        status=200
    )
    response['Content-Length'] = file_obj.size
    response['Content-Disposition'] = content_disposition
    return response