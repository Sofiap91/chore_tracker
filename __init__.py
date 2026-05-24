from pathlib import Path
import logging

from homeassistant.core import HomeAssistant

from .const import DB_NAME, DOMAIN
from .db import Database
from .services import async_register_services

LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    db_path = Path(hass.config.path(DB_NAME))
    db = Database(str(db_path))

    await hass.async_add_executor_job(db.create_tables)

    hass.data[DOMAIN] = {
        "db": db,
    }

    await async_register_services(hass)
    return True
