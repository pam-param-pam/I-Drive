from django.db import migrations, models
from django.db.models import Count


ACTIVE_JOB_STATES = ["PENDING", "PLANNING", "RUNNING"]


def ensure_one_active_job_per_user(apps, schema_editor):
    DeletionJob = apps.get_model("website", "DeletionJob")
    duplicate_user_ids = list(
        DeletionJob.objects
        .filter(state__in=ACTIVE_JOB_STATES, requested_by_id__isnull=False)
        .values("requested_by_id")
        .annotate(job_count=Count("id"))
        .filter(job_count__gt=1)
        .values_list("requested_by_id", flat=True)[:10]
    )

    if duplicate_user_ids:
        raise RuntimeError(
            "Cannot enforce one active deletion job per user while duplicate "
            f"active jobs exist for users: {duplicate_user_ids}"
        )


class Migration(migrations.Migration):
    dependencies = [
        ("website", "0013_remove_file_file_valid_state_and_more"),
    ]

    operations = [
        migrations.RunPython(
            ensure_one_active_job_per_user,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name="deletionjob",
            constraint=models.UniqueConstraint(
                condition=models.Q(state__in=ACTIVE_JOB_STATES),
                fields=("requested_by",),
                name="uniq_active_deletion_job_per_user",
            ),
        ),
    ]
