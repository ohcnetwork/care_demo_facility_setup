from celery import current_app, shared_task

from care_demo_facility_setup.models import SeedRun
from care_demo_facility_setup.services.runner import DemoSeedRunner


@shared_task
def execute_seed_run(run_external_id: str):
    run = SeedRun.objects.get(external_id=run_external_id)
    DemoSeedRunner(run).execute()


@current_app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    # sender.add_periodic_task(
    #     crontab(hour="0", minute="0"),
    #     periodic_task_example.s(),
    #     name="reset_ai_usage_limits",
    # )
    return
