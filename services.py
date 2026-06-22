import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.core import ServiceCall

from .const import DOMAIN
from .const import RECURRENCE_CALENDAR
from .const import RECURRENCE_FROM_COMPLETION
from .const import RECURRENCE_ONE_OFF
from .const import UNIT_DAYS
from .const import UNIT_MONTHS
from .const import UNIT_WEEKS

CHORES_STATE_ENTITY_ID = "sensor.chores_tracker_chores"
DUE_STATE_ENTITY_ID = "sensor.chores_tracker_due"


def _set_chores_state(hass: HomeAssistant, chores: list[dict]) -> None:
    hass.states.async_set(
        CHORES_STATE_ENTITY_ID,
        len(chores),
        {
            "chores": chores,
            "unit_of_measurement": "items",
            "friendly_name": "Chores Tracker Chores",
        },
    )


def _set_due_state(hass: HomeAssistant, due_chores: list[dict]) -> None:
    hass.states.async_set(
        DUE_STATE_ENTITY_ID,
        len(due_chores),
        {
            "chores": due_chores,
            "unit_of_measurement": "items",
            "friendly_name": "Chores Tracker Due",
        },
    )


async def _refresh_chores_state(hass: HomeAssistant) -> None:
    db = hass.data[DOMAIN]["db"]
    chores = await hass.async_add_executor_job(db.list_chores)
    _set_chores_state(hass, chores)


async def _refresh_due_state(hass: HomeAssistant) -> None:
    db = hass.data[DOMAIN]["db"]
    due = await hass.async_add_executor_job(db.list_due_chores)
    _set_due_state(hass, due)


async def _refresh_all(hass: HomeAssistant) -> None:
    await _refresh_chores_state(hass)
    await _refresh_due_state(hass)


def _recurrence_mode_validator(value: str) -> str:
    if value not in {RECURRENCE_ONE_OFF, RECURRENCE_FROM_COMPLETION, RECURRENCE_CALENDAR}:
        raise vol.Invalid("recurrence_mode must be one_off, from_completion, or calendar")
    return value


def _interval_unit_validator(value: str) -> str:
    if value not in {UNIT_DAYS, UNIT_WEEKS, UNIT_MONTHS}:
        raise vol.Invalid("interval_unit must be days, weeks, or months")
    return value


async def async_register_services(hass: HomeAssistant) -> None:
    db = hass.data[DOMAIN]["db"]

    async def handle_list_chores(call: ServiceCall):
        chores = await hass.async_add_executor_job(db.list_chores)
        _set_chores_state(hass, chores)

    async def handle_list_due_chores(call: ServiceCall):
        due = await hass.async_add_executor_job(db.list_due_chores)
        _set_due_state(hass, due)

    async def handle_create_chore(call: ServiceCall):
        await hass.async_add_executor_job(
            db.create_chore,
            call.data["title"],
            call.data["recurrence_mode"],
            call.data.get("interval_value"),
            call.data.get("interval_unit"),
            call.data.get("calendar_weekday"),
            call.data.get("calendar_day_of_month"),
            call.data.get("anchor_date"),
            call.data.get("first_due_at"),
            call.data.get("description"),
            call.data.get("is_active", True),
        )
        await _refresh_all(hass)

    async def handle_update_chore(call: ServiceCall):
        await hass.async_add_executor_job(
            db.update_chore,
            call.data["id"],
            call.data.get("title"),
            call.data.get("description"),
            call.data.get("recurrence_mode"),
            call.data.get("interval_value"),
            call.data.get("interval_unit"),
            call.data.get("calendar_weekday"),
            call.data.get("calendar_day_of_month"),
            call.data.get("anchor_date"),
            call.data.get("first_due_at"),
            call.data.get("is_active"),
        )
        await _refresh_all(hass)

    async def handle_delete_chore(call: ServiceCall):
        await hass.async_add_executor_job(db.delete_chore, call.data["id"])
        await _refresh_all(hass)

    async def handle_mark_complete(call: ServiceCall):
        await hass.async_add_executor_job(
            db.mark_complete,
            call.data["id"],
            call.data.get("note"),
        )
        await _refresh_all(hass)

    async def handle_undo_completion(call: ServiceCall):
        await hass.async_add_executor_job(
            db.undo_last_completion,
            call.data["id"],
        )
        await _refresh_all(hass)

    async def handle_get_history(call: ServiceCall):
        history = await hass.async_add_executor_job(
            db.get_completion_history,
            call.data["id"],
            call.data.get("limit", 20),
        )
        entity_id = f"sensor.chores_tracker_history_{call.data['id']}"
        hass.states.async_set(
            entity_id,
            len(history),
            {
                "entries": history,
                "unit_of_measurement": "items",
                "friendly_name": f"Chore {call.data['id']} History",
            },
        )

    hass.services.async_register(DOMAIN, "list_chores", handle_list_chores)
    hass.services.async_register(
        DOMAIN,
        "list_due_chores",
        handle_list_due_chores,
    )

    hass.services.async_register(
        DOMAIN,
        "create_chore",
        handle_create_chore,
        schema=vol.Schema(
            {
                vol.Required("title"): str,
                vol.Required("recurrence_mode"): _recurrence_mode_validator,
                vol.Optional("description"): str,
                vol.Optional("interval_value"): vol.Coerce(int),
                vol.Optional("interval_unit"): _interval_unit_validator,
                vol.Optional("calendar_weekday"): vol.All(vol.Coerce(int), vol.Range(min=0, max=6)),
                vol.Optional("calendar_day_of_month"): vol.All(vol.Coerce(int), vol.Range(min=1, max=31)),
                vol.Optional("anchor_date"): str,
                vol.Optional("first_due_at"): str,
                vol.Optional("is_active"): bool,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        "update_chore",
        handle_update_chore,
        schema=vol.Schema(
            {
                vol.Required("id"): vol.Coerce(int),
                vol.Optional("title"): str,
                vol.Optional("description"): str,
                vol.Optional("recurrence_mode"): _recurrence_mode_validator,
                vol.Optional("interval_value"): vol.Coerce(int),
                vol.Optional("interval_unit"): _interval_unit_validator,
                vol.Optional("calendar_weekday"): vol.All(vol.Coerce(int), vol.Range(min=0, max=6)),
                vol.Optional("calendar_day_of_month"): vol.All(vol.Coerce(int), vol.Range(min=1, max=31)),
                vol.Optional("anchor_date"): str,
                vol.Optional("first_due_at"): str,
                vol.Optional("is_active"): bool,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        "delete_chore",
        handle_delete_chore,
        schema=vol.Schema({vol.Required("id"): vol.Coerce(int)}),
    )

    hass.services.async_register(
        DOMAIN,
        "mark_complete",
        handle_mark_complete,
        schema=vol.Schema(
            {
                vol.Required("id"): vol.Coerce(int),
                vol.Optional("note"): str,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        "get_history",
        handle_get_history,
        schema=vol.Schema(
            {
                vol.Required("id"): vol.Coerce(int),
                vol.Optional("limit"): vol.Coerce(int),
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        "undo_completion",
        handle_undo_completion,
        schema=vol.Schema({vol.Required("id"): vol.Coerce(int)}),
    )

    await _refresh_all(hass)
