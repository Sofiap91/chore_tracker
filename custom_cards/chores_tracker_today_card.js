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
  }

  setConfig(config) {
    this._config = Object.assign({}, this._config, config || {});
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
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
    var chores = this._dueChores();
    var rows = chores.length
      ? chores
          .map(
            function (item) {
              return (
                '<div class="row">' +
                '<div class="left">' +
                '<div class="title">' + this._esc(item.title) + "</div>" +
                (item.next_due_at ? '<div class="meta">Due ' + this._esc(this._fmtDate(item.next_due_at)) + "</div>" : "") +
                "</div>" +
                '<button class="done" data-id="' + this._esc(item.id) + '" ' + (this._busy ? "disabled" : "") + ">Done</button>" +
                "</div>"
              );
            }.bind(this)
          )
          .join("")
      : '<div class="empty">No chores due right now.</div>';

    this.shadowRoot.innerHTML =
      '<ha-card>' +
      '<div class="card-content">' +
      '<div class="head">' +
      '<h2>' + this._esc(this._config.title) + "</h2>" +
      '<span class="count">' + chores.length + "</span>" +
      "</div>" +
      (this._error ? '<div class="error">' + this._esc(this._error) + "</div>" : "") +
      rows +
      "</div>" +
      "</ha-card>" +
      "<style>" +
      "ha-card { border-radius: 14px; overflow: hidden; }" +
      ".card-content { padding: 14px; }" +
      ".head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }" +
      "h2 { margin: 0; font-size: 1.1rem; }" +
      ".count { background: var(--primary-color); color: white; font-size: 12px; border-radius: 999px; padding: 2px 8px; }" +
      ".row { display: flex; justify-content: space-between; gap: 10px; align-items: center; padding: 10px 0; border-bottom: 1px solid var(--divider-color); }" +
      ".row:last-child { border-bottom: none; }" +
      ".left { min-width: 0; }" +
      ".title { font-weight: 600; }" +
      ".meta { color: var(--secondary-text-color); font-size: 0.85rem; margin-top: 2px; }" +
      ".done { border: none; border-radius: 10px; background: var(--primary-color); color: white; padding: 7px 10px; cursor: pointer; }" +
      ".done:disabled { opacity: 0.55; cursor: wait; }" +
      ".empty { color: var(--secondary-text-color); font-style: italic; padding: 8px 0; }" +
      ".error { margin-bottom: 8px; color: #b00020; font-size: 0.9rem; }" +
      "</style>";

    var buttons = this.shadowRoot.querySelectorAll("button.done");
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].addEventListener("click", function (ev) {
        var id = parseInt(ev.currentTarget.getAttribute("data-id"), 10);
        if (!Number.isNaN(id)) this._markDone(id);
      }.bind(this));
    }
  }
}

customElements.define("chores-tracker-today-card", ChoresTrackerTodayCard);
