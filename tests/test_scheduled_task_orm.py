from metaprofile.settings_api.domain.orm_models import ScheduledTaskORM


def test_scheduled_task_orm_fields():
    orm = ScheduledTaskORM(name="nightly-translate", task_type="translate_batch",
                           cron="0 2 * * *", params={"entity_type": "tech"}, enabled=True)
    assert orm.task_type == "translate_batch"
    assert orm.cron == "0 2 * * *"
    assert orm.enabled is True
    assert orm.params == {"entity_type": "tech"}


def test_scheduled_task_last_status_default_configured():
    # default 在 flush/INSERT 时应用(非实例化),验列 default 配置即可
    col = ScheduledTaskORM.__table__.c.last_status
    assert col.default is not None and col.default.arg == "pending"
