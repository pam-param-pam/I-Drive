import time

from django.contrib.auth.models import User
from django.http import JsonResponse
from rest_framework.decorators import api_view, throttle_classes, permission_classes
from rest_framework.permissions import AllowAny

from ..discord.Discord import discord
from ..utilities.other import get_ip
from ..utilities.throttle import defaultAuthUserThrottle


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([AllowAny])
def get_discord_state(request):
    user = User.objects.get(id=1)
    discord._get_channel_for_user(user)

    bots_dict = []

    state = discord.users_state[user.id]
    retry_timestamp = state.get('retry_timestamp')
    if retry_timestamp:
        remaining_time = state['retry_timestamp'] - time.time()
    else:
        remaining_time = None

    for token in state['bots'].values():
        bots_dict.append(token)

    return JsonResponse({"blocked": state['blocked'], "retry_after": remaining_time, "bots": bots_dict}, safe=False)


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([AllowAny])
def your_ip(request):
    ip, from_nginx = get_ip(request)

    return JsonResponse({"ip": ip, "nginx": from_nginx})



@api_view(['GET'])
# @throttle_classes([defaultAuthUserThrottle])
# @permission_classes([IsAuthenticated & ReadPerms])
def get_stats(request):
    qs = (
        File.objects
        .filter(owner_id=1, inTrash=False)
        .values('type')
        .annotate(count=Count('id'), total_size=Sum('size'))
        .order_by('type')
    )

    result = {
        row['type']: {
            "count": row['count'],
            "total_size": row['total_size']
        }
        for row in qs
    }

    return JsonResponse(result, safe=False)

@api_view(['GET'])
# @throttle_classes([defaultAuthUserThrottle])
# @permission_classes([IsAuthenticated & ReadPerms])
def get_discord_attachment_report(request):
    owner_id = 1  # hardcoded or use request.user.id

    # Query fragments and annotate needed fields
    fragments = Fragment.objects.filter(file__owner_id=owner_id).values(
        'message_id', 'size', 'sequence', 'file_id'
    )

    # Query thumbnails, assign sequence=1 for normalization, same fields
    thumbnails = Thumbnail.objects.filter(file__owner_id=owner_id).annotate(
        sequence=Value(1, output_field=IntegerField())
    ).values('message_id', 'size', 'sequence', 'file_id')

    # Query previews, subtitles, moments - assign sequence=None as no real sequence
    previews = Preview.objects.filter(file__owner_id=owner_id).annotate(
        sequence=Value(None, output_field=IntegerField())
    ).values('message_id', 'size', 'sequence', 'file_id')

    subtitles = Subtitle.objects.filter(file__owner_id=owner_id).annotate(
        sequence=Value(None, output_field=IntegerField())
    ).values('message_id', 'size', 'sequence', 'file_id')

    moments = Moment.objects.filter(file__owner_id=owner_id).annotate(
        sequence=Value(None, output_field=IntegerField())
    ).values('message_id', 'size', 'sequence', 'file_id')

    # Combine all attachments
    all_attachments = fragments.union(
        thumbnails, previews, subtitles, moments
    )

    # Aggregate data grouped by message_id
    # We'll track attachments count and total size per message
    message_data = defaultdict(lambda: {
        "attachments": 0,
        "total_size": 0,
        "files_with_thumbnail": set(),  # file_ids that have thumbnails in this message
        "files_with_first_fragment": set(),  # file_ids with fragment sequence=1 in this message
        "files": set(),  # all file_ids appearing in this message
    })

    # Populate message_data
    for item in all_attachments:
        msg_id = item['message_id']
        file_id = item['file_id']
        seq = item['sequence']
        size = item.get('size', 0)

        message_data[msg_id]["attachments"] += 1
        message_data[msg_id]["total_size"] += size
        message_data[msg_id]["files"].add(file_id)

        if seq == 1:
            message_data[msg_id]["files_with_first_fragment"].add(file_id)
        # Thumbnails we assigned seq=1, but also they appear in thumbnails QuerySet,
        # so distinguish thumbnails by their origin:
        # We'll treat thumbnails as those in thumbnails QuerySet only, so let's
        # mark files that have thumbnails here:
        # Since we combined QuerySets with union, we can track file_id with sequence=1
        # but must differentiate between fragment seq=1 and thumbnail seq=1.

        # To differentiate thumbnail from fragment for seq=1,
        # let's separately track thumbnails file_ids per message:
        # Actually, since thumbnails have sequence=1 and fragments have sequence=1,
        # to differentiate we can first build a set of (message_id, file_id) that contain thumbnails from thumbnails queryset.
        # But since union removes duplicates, let's query thumbnails separately and build a lookup:

    # Build a set of (message_id, file_id) for thumbnails to know which files have thumbnails in which messages
    thumbnail_file_msg_set = set(
        Thumbnail.objects.filter(file__owner_id=owner_id)
        .values_list('message_id', 'file_id')
    )

    # Now update files_with_thumbnail properly, since above loop can't distinguish
    for msg_id in message_data.keys():
        # add files from thumbnail_file_msg_set to files_with_thumbnail for each message
        thumbs_in_msg = {f for (m, f) in thumbnail_file_msg_set if m == msg_id}
        message_data[msg_id]["files_with_thumbnail"].update(thumbs_in_msg)

    # Prepare final report
    report = []
    for msg_id, data in message_data.items():
        total_size = data['total_size']
        attachments = data['attachments']
        usage_percent = round((total_size / MAX_DISCORD_MESSAGE_SIZE) * 100, 1)
        size_mb = round(total_size / 1024 / 1024, 2)

        waste_reasons = []

        if total_size < MAX_DISCORD_MESSAGE_SIZE:
            # Low count or small size waste
            if total_size < 9 * 1024 * 1024:
                waste_reasons.append("small total size")
            elif total_size < 1 * 1024 * 1024:
                waste_reasons.append("very small total size")

            # Check if any file with both thumbnail and first fragment is *not* stored together
            # For each file in this message that has both:
            files_with_both = data["files_with_thumbnail"].intersection(data["files_with_first_fragment"])

            # For the file(s) with both, they should be stored together in this message, so no waste.
            # But if for some file:
            # - thumbnail is in this message
            # - first fragment is in a DIFFERENT message
            # Then this message wastes space.

            # To check this, we need a reverse map file_id -> messages where first fragment appears
            # and file_id -> messages where thumbnail appears

            # Let's build those outside this loop once, for efficiency

        else:
            # Max size, no waste
            waste_reasons = []

        report.append({
            "message_id": msg_id,
            "attachments": attachments,
            "total_size_mb": size_mb,
            "usage_percent": usage_percent,
            "waste_reason": ", ".join(waste_reasons) if waste_reasons else None,
        })

    # --- Additional step: we need the cross-message logic for fragment-thumbnail separation ---
    # Build maps:
    # file_id -> set of messages with first fragment
    file_to_fragments_messages = defaultdict(set)
    for item in fragments:
        if item['sequence'] == 1:
            file_to_fragments_messages[item['file_id']].add(item['message_id'])

    # file_id -> set of messages with thumbnail
    file_to_thumbnails_messages = defaultdict(set)
    for item in thumbnails:
        file_to_thumbnails_messages[item['file_id']].add(item['message_id'])

    # Now revisit report to add waste reason for files with fragmented thumbnail separation
    for r in report:
        msg_id = r["message_id"]
        # get files in this message with thumbnail
        files_with_thumb = message_data[msg_id]["files_with_thumbnail"]
        for file_id in files_with_thumb:
            frag_msgs = file_to_fragments_messages.get(file_id, set())
            thumb_msgs = file_to_thumbnails_messages.get(file_id, set())
            # If the file has a thumbnail in this message, but its first fragment is NOT in this message
            if msg_id in thumb_msgs and msg_id not in frag_msgs:
                # Add reason
                if r["waste_reason"]:
                    r["waste_reason"] += ", fragment not stored together with thumbnail"
                else:
                    r["waste_reason"] = "fragment not stored together with thumbnail"

    return JsonResponse(report, safe=False)