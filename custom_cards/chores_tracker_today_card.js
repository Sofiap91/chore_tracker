class ChoresTrackerTodayCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {
      title: "Chores Today",
      due_entity: "sensor.chores_tracker_due",
      domain: "chores_tracker",
    };
    this._busy = false;
    this._error = "";
    this._initialized = false;

    this._editorOpen = false;
    this._editorBusy = false;
    this._editorError = "";
    this._editorSuccess = "";
    this._editorDraft = this._defaultEditorDraft();
  }

  setConfig(config) {
    this._config = Object.assign({}, this._config, config || {});
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._initialized) {
      this._initialized = true;
      this._hass.callService(this._config.domain, "list_due_chores", {}).catch(function () {});
      this._hass.callService(this._config.domain, "list_chores", {}).catch(function () {});
    }
    this._render();
  }

  getCardSize() {
    return 4;
  }

  _dueChores() {
    var stateObj = this._hass && this._hass.states ? this._hass.states[this._config.due_entity] : null;
    var list = stateObj && stateObj.attributes ? stateObj.attributes.chores : null;
    return Array.isArray(list) ? list : [];
  }

  _allChores() {
    var allChoresEntity = "sensor.chores_tracker_chores";
    var stateObj = this._hass && this._hass.states ? this._hass.states[allChoresEntity] : null;
    var list = stateObj && stateObj.attributes ? stateObj.attributes.chores : null;
    return Array.isArray(list) ? list : [];
  }

  _fmtDate(iso) {
    if (!iso) return "";
    var d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString();
  }

  async _markDone(id) {
    if (!this._hass || this._busy) return;
    this._busy = true;
    this._error = "";
    this._render();
    try {
      await this._hass.callService(this._config.domain, "mark_complete", { id: id });
      await this._hass.callService(this._config.domain, "list_due_chores", {});
    } catch (err) {
      this._error = (err && err.message) || "Failed to mark chore complete.";
    } finally {
      this._busy = false;
      this._render();
    }
  }

  _defaultEditorDraft() {
    return {
      title: "",
      description: "",
      recurrence_mode: "calendar",
      interval_value: "1",
      interval_unit: "weeks",
      calendar_weekday: "2",
      calendar_day_of_month: "1",
      anchor_date: "",
      first_due_at_local: "",
      is_active: true,
    };
  }

  _openEditor() {
    this._editorDraft = this._defaultEditorDraft();
    this._editorError = "";
    this._editorSuccess = "";
    this._editorOpen = true;
    this._render();
  }

  _closeEditor() {
    this._editorOpen = false;
    this._editorBusy = false;
    this._editorError = "";
    this._editorSuccess = "";
    this._render();
  }

  _saveEditorState() {
    var root = this.shadowRoot;
    if (!root) return;

    var titleEl = root.getElementById("ed-title");
    var descEl = root.getElementById("ed-description");
    var modeEl = root.getElementById("ed-mode");
    var intervalValueEl = root.getElementById("ed-interval-value");
    var intervalUnitEl = root.getElementById("ed-interval-unit");
    var weekdayEl = root.getElementById("ed-calendar-weekday");
    var dayOfMonthEl = root.getElementById("ed-calendar-day-of-month");
    var anchorDateEl = root.getElementById("ed-anchor-date");
    var firstDueEl = root.getElementById("ed-first-due-at");
    var activeEl = root.getElementById("ed-is-active");

    this._editorDraft.title = titleEl ? titleEl.value : this._editorDraft.title;
    this._editorDraft.description = descEl ? descEl.value : this._editorDraft.description;
    this._editorDraft.recurrence_mode = modeEl ? modeEl.value : this._editorDraft.recurrence_mode;
    this._editorDraft.interval_value = intervalValueEl ? intervalValueEl.value : this._editorDraft.interval_value;
    this._editorDraft.interval_unit = intervalUnitEl ? intervalUnitEl.value : this._editorDraft.interval_unit;
    this._editorDraft.calendar_weekday = weekdayEl ? weekdayEl.value : this._editorDraft.calendar_weekday;
    this._editorDraft.calendar_day_of_month = dayOfMonthEl ? dayOfMonthEl.value : this._editorDraft.calendar_day_of_month;
    this._editorDraft.anchor_date = anchorDateEl ? anchorDateEl.value : this._editorDraft.anchor_date;
    this._editorDraft.first_due_at_local = firstDueEl ? firstDueEl.value : this._editorDraft.first_due_at_local;
    this._editorDraft.is_active = activeEl ? !!activeEl.checked : this._editorDraft.is_active;
  }

  _onEditorModeChange() {
    this._saveEditorState();
    this._editorError = "";
    this._editorSuccess = "";

    if (this._editorDraft.recurrence_mode === "one_off") {
      this._editorDraft.interval_value = "";
      this._editorDraft.interval_unit = "days";
    } else {
      if (!this._editorDraft.interval_value) this._editorDraft.interval_value = "1";
      if (!this._editorDraft.interval_unit) this._editorDraft.interval_unit = "days";
    }

    this._render();
  }

  _onEditorUnitChange() {
    this._saveEditorState();
    this._editorError = "";
    this._editorSuccess = "";
    this._render();
  }

  _buildCreatePayload() {
    var d = this._editorDraft;
    var title = String(d.title || "").trim();
    if (!title) {
      throw new Error("Chore title is required.");
    }

    var mode = d.recurrence_mode;
    var payload = {
      title: title,
      recurrence_mode: mode,
      is_active: !!d.is_active,
    };

    var description = String(d.description || "").trim();
    if (description) payload.description = description;

    if (d.first_due_at_local) {
      var firstDueDate = new Date(d.first_due_at_local);
      if (!Number.isNaN(firstDueDate.getTime())) {
        payload.first_due_at = firstDueDate.toISOString();
      }
    }

    if (mode !== "one_off") {
      var value = parseInt(d.interval_value, 10);
      if (Number.isNaN(value) || value < 1) {
        throw new Error("Interval value must be at least 1.");
      }
      payload.interval_value = value;
      payload.interval_unit = d.interval_unit || "days";
    }

    if (mode === "calendar") {
      if (payload.interval_unit === "weeks") {
        var weekday = parseInt(d.calendar_weekday, 10);
        if (Number.isNaN(weekday) || weekday < 0 || weekday > 6) {
          throw new Error("Weekly calendar chores need a weekday between 0 and 6.");
        }
        payload.calendar_weekday = weekday;
      }

      if (payload.interval_unit === "months") {
        var dayOfMonth = parseInt(d.calendar_day_of_month, 10);
        if (Number.isNaN(dayOfMonth) || dayOfMonth < 1 || dayOfMonth > 31) {
          throw new Error("Monthly calendar chores need a day of month between 1 and 31.");
        }
        payload.calendar_day_of_month = dayOfMonth;
      }

      if (payload.interval_unit === "days") {
        var anchorDate = String(d.anchor_date || "").trim();
        if (anchorDate) payload.anchor_date = anchorDate;
      }
    }

    return payload;
  }

  async _createChoreFromEditor() {
    if (!this._hass || this._editorBusy) return;

    this._saveEditorState();
    this._editorBusy = true;
    this._editorError = "";
    this._editorSuccess = "";
    this._render();

    try {
      var payload = this._buildCreatePayload();
      await this._hass.callService(this._config.domain, "create_chore", payload);
      await this._hass.callService(this._config.domain, "list_due_chores", {});
      this._editorSuccess = 'Chore "' + payload.title + '" created.';
      this._editorOpen = false;
      this._editorDraft = this._defaultEditorDraft();
    } catch (err) {
      this._editorError = (err && err.message) || "Failed to create chore.";
    } finally {
      this._editorBusy = false;
      this._render();
    }
  }

  _renderEditorModal() {
    var d = this._editorDraft;
    var dis = this._editorBusy ? "disabled" : "";
    var mode = d.recurrence_mode;
    var unit = d.interval_unit || "days";

    var showInterval = mode !== "one_off";
    var showCalendarFields = mode === "calendar";
    var showWeekday = showCalendarFields && unit === "weeks";
    var showDayOfMonth = showCalendarFields && unit === "months";
    var showAnchorDate = showCalendarFields && unit === "days";

    return (
      '<div class="ed-overlay" id="ed-overlay">' +
        '<div class="ed-dialog">' +
          '<div class="ed-header">' +
            '<span>New Chore</span>' +
            '<button class="ed-close" id="ed-close-btn" aria-label="Close">&times;</button>' +
          '</div>' +
          (this._editorError ? '<div class="ed-error">' + this._esc(this._editorError) + '</div>' : '') +
          (this._editorSuccess ? '<div class="ed-success">' + this._esc(this._editorSuccess) + '</div>' : '') +
          '<div class="ed-scroll">' +
            '<div class="ed-field">' +
              '<label>Title *</label>' +
              '<input id="ed-title" type="text" placeholder="e.g. Clean toilet" value="' + this._esc(d.title) + '" ' + dis + '>' +
            '</div>' +
            '<div class="ed-field">' +
              '<label>Description</label>' +
              '<textarea id="ed-description" placeholder="Optional notes" ' + dis + '>' + this._esc(d.description) + '</textarea>' +
            '</div>' +
            '<div class="ed-field">' +
              '<label>Recurrence mode</label>' +
              '<select id="ed-mode" ' + dis + '>' +
                '<option value="one_off"' + (mode === 'one_off' ? ' selected' : '') + '>One-off</option>' +
                '<option value="from_completion"' + (mode === 'from_completion' ? ' selected' : '') + '>From completion</option>' +
                '<option value="calendar"' + (mode === 'calendar' ? ' selected' : '') + '>Calendar schedule</option>' +
              '</select>' +
            '</div>' +
            (showInterval
              ? '<div class="ed-grid-2">' +
                  '<div class="ed-field">' +
                    '<label>Every</label>' +
                    '<input id="ed-interval-value" type="number" min="1" step="1" value="' + this._esc(d.interval_value) + '" ' + dis + '>' +
                  '</div>' +
                  '<div class="ed-field">' +
                    '<label>Unit</label>' +
                    '<select id="ed-interval-unit" ' + dis + '>' +
                      '<option value="days"' + (unit === 'days' ? ' selected' : '') + '>Days</option>' +
                      '<option value="weeks"' + (unit === 'weeks' ? ' selected' : '') + '>Weeks</option>' +
                      '<option value="months"' + (unit === 'months' ? ' selected' : '') + '>Months</option>' +
                    '</select>' +
                  '</div>' +
                '</div>'
              : '') +
            (showWeekday
              ? '<div class="ed-field">' +
                  '<label>Weekday</label>' +
                  '<select id="ed-calendar-weekday" ' + dis + '>' +
                    '<option value="0"' + (String(d.calendar_weekday) === '0' ? ' selected' : '') + '>Monday</option>' +
                    '<option value="1"' + (String(d.calendar_weekday) === '1' ? ' selected' : '') + '>Tuesday</option>' +
                    '<option value="2"' + (String(d.calendar_weekday) === '2' ? ' selected' : '') + '>Wednesday</option>' +
                    '<option value="3"' + (String(d.calendar_weekday) === '3' ? ' selected' : '') + '>Thursday</option>' +
                    '<option value="4"' + (String(d.calendar_weekday) === '4' ? ' selected' : '') + '>Friday</option>' +
                    '<option value="5"' + (String(d.calendar_weekday) === '5' ? ' selected' : '') + '>Saturday</option>' +
                    '<option value="6"' + (String(d.calendar_weekday) === '6' ? ' selected' : '') + '>Sunday</option>' +
                  '</select>' +
                '</div>'
              : '') +
            (showDayOfMonth
              ? '<div class="ed-field">' +
                  '<label>Day of month</label>' +
                  '<input id="ed-calendar-day-of-month" type="number" min="1" max="31" step="1" value="' + this._esc(d.calendar_day_of_month) + '" ' + dis + '>' +
                '</div>'
              : '') +
            (showAnchorDate
              ? '<div class="ed-field">' +
                  '<label>Anchor date (optional)</label>' +
                  '<input id="ed-anchor-date" type="date" value="' + this._esc(d.anchor_date) + '" ' + dis + '>' +
                '</div>'
              : '') +
            '<div class="ed-field">' +
              '<label>First due at (optional)</label>' +
              '<input id="ed-first-due-at" type="datetime-local" value="' + this._esc(d.first_due_at_local) + '" ' + dis + '>' +
            '</div>' +
            '<label class="ed-check-row">' +
              '<input id="ed-is-active" type="checkbox" ' + (d.is_active ? 'checked ' : '') + dis + '>' +
              '<span>Active</span>' +
            '</label>' +
          '</div>' +
          '<div class="ed-actions">' +
            '<button class="ed-btn-primary" id="ed-submit-btn" ' + dis + '>Create chore</button>' +
            '<button id="ed-cancel-btn" ' + dis + '>Cancel</button>' +
          '</div>' +
        '</div>' +
      '</div>'
    );
  }

  _esc(value) {
    if (value === undefined || value === null) return "";
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  _render() {
    if (!this.shadowRoot) return;
    var dueChores = this._dueChores();
    var dueRows = dueChores.length
      ? dueChores
          .map(
            function (item) {
              return (
                '<div class="row">' +
                '<input class="task-check" type="checkbox" data-id="' + this._esc(item.id) + '" ' + (this._busy ? "disabled" : "") + '>' +
                '<div class="left">' +
                '<div class="title">' + this._esc(item.title) + "</div>" +
                (item.next_due_at ? '<div class="meta">Due ' + this._esc(this._fmtDate(item.next_due_at)) + "</div>" : "") +
                "</div>" +
                "</div>"
              );
            }.bind(this)
          )
          .join("")
      : '<div class="empty">No chores due right now.</div>';

    var allChores = this._allChores();
    var activeChores = allChores.filter(function (c) { return c.is_active; });
    var upcomingChores = activeChores
      .filter(function (c) { return c.next_due_at; })
      .sort(function (a, b) {
        var aTime = new Date(a.next_due_at).getTime();
        var bTime = new Date(b.next_due_at).getTime();
        return aTime - bTime;
      });
    var upcomingRows = upcomingChores.length
      ? upcomingChores
          .map(
            function (item) {
              return (
                '<div class="upcoming-row">' +
                '<input class="task-check" type="checkbox" data-id="' + this._esc(item.id) + '" ' + (this._busy ? "disabled" : "") + '>' +
                '<div class="left">' +
                '<div class="title">' + this._esc(item.title) + "</div>" +
                (item.next_due_at ? '<div class="meta">' + this._esc(this._fmtDate(item.next_due_at)) + "</div>" : "") +
                "</div>" +
                "</div>"
              );
            }.bind(this)
          )
          .join("")
      : '<div class="upcoming-empty">No upcoming chores.</div>';

    this.shadowRoot.innerHTML =
      '<ha-card>' +
      '<div class="card-content">' +
      '<div class="head">' +
      '<h2>' + this._esc(this._config.title) + "</h2>" +
      '<div class="head-right">' +
      '<span class="count">' + dueChores.length + "</span>" +
      '<button id="add-chore-btn" class="add">+ Add</button>' +
      '</div>' +
      "</div>" +
      (this._error ? '<div class="error">' + this._esc(this._error) + "</div>" : "") +
      dueRows +
      '<div class="upcoming-section">' +
      '<h3>Upcoming</h3>' +
      '<div class="upcoming-list">' +
      upcomingRows +
      '</div>' +
      '</div>' +
      "</div>" +
      "</ha-card>" +
      (this._editorOpen ? this._renderEditorModal() : "") +
      "<style>" +
      "ha-card { border-radius: 14px; overflow: hidden; }" +
      ".card-content { padding: 14px; }" +
      ".head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }" +
      ".head-right { display: flex; align-items: center; gap: 8px; }" +
      "h2 { margin: 0; font-size: 1.1rem; }" +
      ".count { background: var(--primary-color); color: white; font-size: 12px; border-radius: 999px; padding: 2px 8px; }" +
      ".add { border: 1px solid var(--divider-color); border-radius: 10px; background: var(--secondary-background-color); color: var(--primary-text-color); padding: 6px 10px; cursor: pointer; }" +
      ".add:hover { border-color: var(--primary-color); }" +
      ".row { display: flex; justify-content: flex-start; gap: 12px; align-items: flex-start; padding: 10px 0; border-bottom: 1px solid var(--divider-color); }" +
      ".row:last-child { border-bottom: none; }" +
      ".task-check { width: 18px; height: 18px; margin: 2px 0 0 0; accent-color: var(--primary-color); cursor: pointer; flex-shrink: 0; }" +
      ".left { min-width: 0; flex: 1; }" +
      ".title { font-weight: 600; }" +
      ".meta { color: var(--secondary-text-color); font-size: 0.85rem; margin-top: 2px; }" +
      ".empty { color: var(--secondary-text-color); font-style: italic; padding: 8px 0; }" +
      ".error { margin-bottom: 8px; color: #b00020; font-size: 0.9rem; }" +
      ".upcoming-section { margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--divider-color); }" +
      ".upcoming-section h3 { margin: 0 0 10px 0; font-size: 0.95rem; color: var(--secondary-text-color); text-transform: uppercase; letter-spacing: 0.05em; }" +
      ".upcoming-list { max-height: 300px; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; }" +
      ".upcoming-row { display: flex; align-items: flex-start; gap: 12px; padding: 8px 0; border-bottom: 1px solid var(--divider-color); }" +
      ".upcoming-row:last-child { border-bottom: none; }" +
      ".upcoming-empty { color: var(--secondary-text-color); font-style: italic; padding: 8px 0; font-size: 0.9rem; }" +
      ".ed-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.55); z-index: 9999; display: flex; align-items: center; justify-content: center; padding: 14px; box-sizing: border-box; }" +
      ".ed-dialog { width: min(620px, 96vw); max-height: 90vh; background: var(--card-background-color); border-radius: 14px; box-shadow: 0 10px 38px rgba(0,0,0,0.35); display: flex; flex-direction: column; }" +
      ".ed-header { display: flex; align-items: center; justify-content: space-between; padding: 14px 16px; border-bottom: 1px solid var(--divider-color); font-weight: 700; }" +
      ".ed-close { border: none; background: transparent; color: var(--primary-text-color); font-size: 1.4rem; line-height: 1; cursor: pointer; }" +
      ".ed-scroll { padding: 14px 16px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; }" +
      ".ed-field { display: flex; flex-direction: column; gap: 6px; }" +
      ".ed-field label { font-size: 0.85rem; color: var(--secondary-text-color); }" +
      ".ed-grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }" +
      ".ed-dialog input, .ed-dialog textarea, .ed-dialog select { width: 100%; box-sizing: border-box; border: 1px solid var(--divider-color); border-radius: 8px; background: var(--secondary-background-color); color: var(--primary-text-color); padding: 10px; font-size: 0.95rem; font-family: inherit; }" +
      ".ed-dialog textarea { min-height: 80px; resize: vertical; }" +
      ".ed-check-row { display: inline-flex; align-items: center; gap: 8px; margin-top: 2px; }" +
      ".ed-actions { padding: 12px 16px; border-top: 1px solid var(--divider-color); display: flex; justify-content: flex-end; gap: 8px; }" +
      ".ed-btn-primary { border: 1px solid var(--primary-color); background: var(--primary-color); color: var(--text-primary-color, #fff); border-radius: 8px; padding: 8px 12px; cursor: pointer; }" +
      ".ed-error { color: #c0392b; padding: 10px 16px 0 16px; font-size: 0.9rem; }" +
      ".ed-success { color: #1e8449; padding: 10px 16px 0 16px; font-size: 0.9rem; }" +
      "@media (max-width: 700px) { .ed-grid-2 { grid-template-columns: 1fr; } }" +
      "</style>";

    var checks = this.shadowRoot.querySelectorAll("input.task-check");
    for (var i = 0; i < checks.length; i++) {
      checks[i].addEventListener("change", function (ev) {
        var el = ev.currentTarget;
        if (!el.checked) return;
        var id = parseInt(el.getAttribute("data-id"), 10);
        if (!Number.isNaN(id)) this._markDone(id);
      }.bind(this));
    }

    var addBtn = this.shadowRoot.getElementById("add-chore-btn");
    if (addBtn) {
      addBtn.onclick = function () {
        this._openEditor();
      }.bind(this);
    }

    var closeBtn = this.shadowRoot.getElementById("ed-close-btn");
    if (closeBtn) {
      closeBtn.onclick = function () {
        this._closeEditor();
      }.bind(this);
    }

    var cancelBtn = this.shadowRoot.getElementById("ed-cancel-btn");
    if (cancelBtn) {
      cancelBtn.onclick = function () {
        this._closeEditor();
      }.bind(this);
    }

    var overlay = this.shadowRoot.getElementById("ed-overlay");
    if (overlay) {
      overlay.onclick = function (ev) {
        if (ev.target === overlay) this._closeEditor();
      }.bind(this);
    }

    var modeSelect = this.shadowRoot.getElementById("ed-mode");
    if (modeSelect) {
      modeSelect.onchange = function () {
        this._onEditorModeChange();
      }.bind(this);
    }

    var unitSelect = this.shadowRoot.getElementById("ed-interval-unit");
    if (unitSelect) {
      unitSelect.onchange = function () {
        this._onEditorUnitChange();
      }.bind(this);
    }

    var submitBtn = this.shadowRoot.getElementById("ed-submit-btn");
    if (submitBtn) {
      submitBtn.onclick = function () {
        this._createChoreFromEditor();
      }.bind(this);
    }
  }
}

if (!customElements.get("chores-tracker-today-card")) {
  customElements.define("chores-tracker-today-card", ChoresTrackerTodayCard);
}

window.customCards = window.customCards || [];
window.customCards.push({
  type: "chores-tracker-today-card",
  name: "Chores Tracker Today",
  description: "Shows due chores and lets you mark them complete.",
  preview: true,
});
