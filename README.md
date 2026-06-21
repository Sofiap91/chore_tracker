# Chores Tracker

Home Assistant custom integration for recurring chores with three completion policies:

- one_off: complete once, then it does not renew
- from_completion: next due is every N days/weeks/months from completion time
- calendar: schedule remains calendar-aligned and, when completed, next due is the first scheduled occurrence on or after completion + interval

## Services

- chores_tracker.create_chore
- chores_tracker.update_chore
- chores_tracker.delete_chore
- chores_tracker.list_chores
- chores_tracker.list_due_chores
- chores_tracker.mark_complete
- chores_tracker.get_history

Service fields and selectors are documented in services.yaml.

## Card

`custom_cards/chores_tracker_today_card.js` provides a simple due-now list with a Done button.

Example Lovelace card config:

```yaml
type: custom:chores-tracker-today-card
title: Chores Today
due_entity: sensor.chores_tracker_due
domain: chores_tracker
```

## Deployment

Copy card files to Home Assistant www:

```bash
./deploy_cards.sh /homeassistant
```

Then add JS resource in Home Assistant:

- URL: /local/chores_tracker_today_card.js
- Type: module
