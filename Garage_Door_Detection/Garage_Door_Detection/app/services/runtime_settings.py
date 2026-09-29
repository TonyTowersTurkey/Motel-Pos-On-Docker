from sqlalchemy.orm import Session

from app.models import AppSetting

UNIFI_CONSOLE_ID_KEY = "unifi_console_id"


def get_runtime_setting(db: Session, key: str) -> str | None:
    setting = db.get(AppSetting, key)
    return setting.value if setting is not None else None


def set_runtime_setting(db: Session, key: str, value: str | None) -> None:
    normalized = value.strip() if value else ""
    setting = db.get(AppSetting, key)
    if not normalized:
        if setting is not None:
            db.delete(setting)
    elif setting is None:
        db.add(AppSetting(key=key, value=normalized))
    else:
        setting.value = normalized
    db.commit()


def get_unifi_console_id(db: Session) -> str | None:
    return get_runtime_setting(db, UNIFI_CONSOLE_ID_KEY)
