import {
  ACTION_NONE,
  ACTION_OPTIONS,
  DEFAULT_ACTION,
  DEFAULT_EVENT,
  EVENT_OPTIONS,
} from "./constants.js";
import {
  cloneCards,
  escapeHtml,
  localize,
  normalizeNumber,
} from "./utils.js";

class OpenWBMappingPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = undefined;
    this._setupStarted = false;
    this._loading = false;
    this._saving = false;
    this._dirty = false;
    this._error = "";
    this._statusKey = "";
    this._config = { devices: [] };
    this._selectedDeviceKey = "";
    this._cards = [];
    this._originalCards = [];
    this._ruleId = 1;

    this.shadowRoot.addEventListener("click", (event) => this._handleClick(event));
    this.shadowRoot.addEventListener("change", (event) => this._handleChange(event));
  }

  set hass(hass) {
    const previousLanguage = this._hass?.language;
    const currentLanguage = hass?.language;
    this._hass = hass;
    if (previousLanguage && currentLanguage && previousLanguage !== currentLanguage) {
      this._render();
    }
    if (!this._setupStarted && hass) {
      this._setupStarted = true;
      this._loadConfig();
    }
  }

  set narrow(value) {
    this._narrow = Boolean(value);
    this._render();
  }

  set route(value) {
    this._route = value;
  }

  set panel(value) {
    this._panel = value;
  }

  connectedCallback() {
    this._render();
  }

  async _loadConfig() {
    if (!this._hass) {
      return;
    }

    this._loading = true;
    this._error = "";
    this._statusKey = "";
    this._render();

    try {
      const config = await this._hass.callWS({ type: "openwb/config" });
      this._config = {
        ...config,
        devices: Array.isArray(config.devices) ? config.devices : [],
      };

      if (!this._config.devices.length) {
        this._selectedDeviceKey = "";
        this._cards = [];
        this._originalCards = [];
        this._dirty = false;
        return;
      }

      const deviceKeys = this._config.devices.map((device) => this._deviceKey(device));
      if (!deviceKeys.includes(this._selectedDeviceKey)) {
        this._selectedDeviceKey = deviceKeys[0];
      }
      await this._loadSelectedDevice({ keepLoading: true });
    } catch (error) {
      this._error = this._errorMessage(error);
    } finally {
      this._loading = false;
      this._render();
    }
  }

  async _loadSelectedDevice(options = {}) {
    const device = this._selectedDevice();
    if (!this._hass || !device) {
      return;
    }

    if (!options.keepLoading) {
      this._loading = true;
      this._error = "";
      this._statusKey = "";
      this._render();
    }

    try {
      const result = await this._hass.callWS({
        type: "openwb/mapping_matrix/read",
        entry_id: device.entry_id,
        device_id: device.device_id,
      });
      this._cards = this._cardsFromMatrices(result.matrices || {}, device);
      this._originalCards = cloneCards(this._cards);
      this._dirty = false;
    } catch (error) {
      this._error = this._errorMessage(error);
    } finally {
      if (!options.keepLoading) {
        this._loading = false;
        this._render();
      }
    }
  }

  async _save() {
    const device = this._selectedDevice();
    if (!this._hass || !device || this._saving) {
      return;
    }

    let mappings;
    try {
      mappings = this._mappingsFromCards();
    } catch (error) {
      this._error = this._errorMessage(error);
      this._render();
      return;
    }

    this._saving = true;
    this._error = "";
    this._statusKey = "";
    this._render();

    try {
      await this._hass.callWS({
        type: "openwb/mapping_matrix/write",
        entry_id: device.entry_id,
        device_id: device.device_id,
        mappings,
      });
      this._originalCards = cloneCards(this._cards);
      this._dirty = false;
      this._statusKey = "status.saved";
    } catch (error) {
      this._error = this._errorMessage(error);
    } finally {
      this._saving = false;
      this._render();
    }
  }

  _handleClick(event) {
    const target = event.target;
    if (!(target instanceof Element)) {
      return;
    }

    const button = target.closest("[data-action]");
    if (!button) {
      return;
    }

    const action = button.dataset.action;
    if (action === "reload") {
      this._loadConfig();
      return;
    }
    if (action === "add-card") {
      this._addCard();
      return;
    }
    if (action === "delete-card") {
      this._deleteCard(button);
      return;
    }
    if (action === "add-rule") {
      this._addRule(button);
      return;
    }
    if (action === "delete-rule") {
      this._deleteRule(button);
      return;
    }
    if (action === "cancel") {
      this._cancel();
      return;
    }
    if (action === "save") {
      this._save();
    }
  }

  _handleChange(event) {
    const target = event.target;
    if (!(target instanceof Element)) {
      return;
    }

    if (target.matches("[data-device-select]")) {
      this._changeDevice(target.value);
      return;
    }

    if (target.matches("select[data-field]")) {
      this._updateRuleSelect(target);
      return;
    }

    if (target.matches("input[type='checkbox'][data-output]")) {
      this._updateRuleOutputs(target);
    }
  }

  async _changeDevice(nextKey) {
    if (nextKey === this._selectedDeviceKey) {
      return;
    }

    if (this._dirty && !window.confirm(this._t("confirm.discardChanges"))) {
      this._render();
      return;
    }

    this._selectedDeviceKey = nextKey;
    await this._loadSelectedDevice();
  }

  _addCard() {
    const device = this._selectedDevice();
    if (!device) {
      return;
    }

    const usedInputs = new Set(this._cards.map((card) => card.inputNumber));
    const inputNumber = this._inputNumbers(device).find(
      (candidate) => !usedInputs.has(candidate),
    );
    if (inputNumber === undefined) {
      return;
    }

    this._cards = [
      ...this._cards,
      {
        inputNumber,
        rules: [this._newRule()],
      },
    ].sort((left, right) => left.inputNumber - right.inputNumber);
    this._markDirty();
  }

  _deleteCard(element) {
    const cardIndex = this._cardIndex(element);
    if (cardIndex < 0) {
      return;
    }
    this._cards = this._cards.filter((_, index) => index !== cardIndex);
    this._markDirty();
  }

  _addRule(element) {
    const cardIndex = this._cardIndex(element);
    if (cardIndex < 0) {
      return;
    }
    this._cards = this._cards.map((card, index) =>
      index === cardIndex
        ? { ...card, rules: [...card.rules, this._newRule()] }
        : card,
    );
    this._markDirty();
  }

  _deleteRule(element) {
    const cardIndex = this._cardIndex(element);
    const ruleIndex = this._ruleIndex(element);
    if (cardIndex < 0 || ruleIndex < 0) {
      return;
    }

    this._cards = this._cards.map((card, index) =>
      index === cardIndex
        ? {
            ...card,
            rules: card.rules.filter((_, candidate) => candidate !== ruleIndex),
          }
        : card,
    );
    this._markDirty();
  }

  _updateRuleSelect(element) {
    const cardIndex = this._cardIndex(element);
    const ruleIndex = this._ruleIndex(element);
    const field = element.dataset.field;
    if (cardIndex < 0 || ruleIndex < 0 || !field) {
      return;
    }

    const value = normalizeNumber(element.value);
    this._cards = this._cards.map((card, currentCardIndex) => {
      if (currentCardIndex !== cardIndex) {
        return card;
      }
      return {
        ...card,
        rules: card.rules.map((rule, currentRuleIndex) =>
          currentRuleIndex === ruleIndex ? { ...rule, [field]: value } : rule,
        ),
      };
    });
    this._markDirty();
  }

  _updateRuleOutputs(element) {
    const cardIndex = this._cardIndex(element);
    const ruleIndex = this._ruleIndex(element);
    if (cardIndex < 0 || ruleIndex < 0) {
      return;
    }

    const device = this._selectedDevice();
    const allOutputs = this._outputNumbers(device);
    const outputValue = element.dataset.output;
    let outputs;

    if (outputValue === "all") {
      outputs = element.checked ? allOutputs : [];
    } else {
      const output = normalizeNumber(outputValue);
      const current = new Set(this._cards[cardIndex].rules[ruleIndex].outputs);
      if (element.checked) {
        current.add(output);
      } else {
        current.delete(output);
      }
      outputs = allOutputs.filter((candidate) => current.has(candidate));
    }

    this._cards = this._cards.map((card, currentCardIndex) => {
      if (currentCardIndex !== cardIndex) {
        return card;
      }
      return {
        ...card,
        rules: card.rules.map((rule, currentRuleIndex) =>
          currentRuleIndex === ruleIndex ? { ...rule, outputs } : rule,
        ),
      };
    });
    this._markDirty();
  }

  _cancel() {
    this._cards = cloneCards(this._originalCards);
    this._dirty = false;
    this._error = "";
    this._statusKey = "";
    this._render();
  }

  _cardsFromMatrices(matrices, device) {
    const inputNumbers = this._inputNumbers(device);
    const outputNumbers = this._outputNumbers(device);
    const cards = [];

    for (const inputNumber of inputNumbers) {
      const rules = [];
      for (const eventOption of EVENT_OPTIONS) {
        const cells = Array.isArray(matrices[String(eventOption.value)])
          ? matrices[String(eventOption.value)]
          : [];
        const grouped = new Map();

        for (const cell of cells) {
          if (Number(cell.input_number) !== inputNumber) {
            continue;
          }

          const action = Number(cell.action);
          const output = Number(cell.output);
          if (action === ACTION_NONE || !outputNumbers.includes(output)) {
            continue;
          }

          if (!grouped.has(action)) {
            grouped.set(action, []);
          }
          grouped.get(action).push(output);
        }

        for (const actionOption of ACTION_OPTIONS) {
          const outputs = (grouped.get(actionOption.value) || []).sort((left, right) =>
            left - right
          );
          if (outputs.length) {
            rules.push({
              id: this._nextRuleId(),
              event: eventOption.value,
              action: actionOption.value,
              outputs,
            });
          }
        }
      }

      if (rules.length) {
        cards.push({ inputNumber, rules });
      }
    }

    return cards;
  }

  _mappingsFromCards() {
    const mappings = [];
    const seenCells = new Set();

    for (const card of this._cards) {
      for (const rule of card.rules) {
        const outputs = this._outputNumbers(this._selectedDevice()).filter((output) =>
          rule.outputs.includes(output)
        );
        if (!outputs.length) {
          throw new Error(this._t("validation.selectRelay"));
        }

        for (const output of outputs) {
          const cellKey = `${card.inputNumber}:${rule.event}:${output}`;
          if (seenCells.has(cellKey)) {
            throw new Error(
              this._t("validation.duplicateCell"),
            );
          }
          seenCells.add(cellKey);
        }

        mappings.push({
          input_number: card.inputNumber,
          event: rule.event,
          action: rule.action,
          outputs,
        });
      }
    }

    return mappings;
  }

  _newRule() {
    const firstOutput = this._outputNumbers(this._selectedDevice())[0];
    return {
      id: this._nextRuleId(),
      event: DEFAULT_EVENT,
      action: DEFAULT_ACTION,
      outputs: firstOutput === undefined ? [] : [firstOutput],
    };
  }

  _nextRuleId() {
    const id = this._ruleId;
    this._ruleId += 1;
    return id;
  }

  _markDirty() {
    this._dirty = JSON.stringify(this._cards) !== JSON.stringify(this._originalCards);
    this._statusKey = "";
    this._render();
  }

  _selectedDevice() {
    return (this._config.devices || []).find(
      (device) => this._deviceKey(device) === this._selectedDeviceKey,
    );
  }

  _deviceKey(device) {
    return `${device.entry_id}:${device.device_id}`;
  }

  _inputNumbers(device) {
    return (device?.input_numbers || []).map(Number).sort((left, right) => left - right);
  }

  _outputNumbers(device) {
    return (device?.output_numbers || [])
      .map(Number)
      .sort((left, right) => left - right);
  }

  _cardIndex(element) {
    const card = element.closest("[data-card-index]");
    return card ? normalizeNumber(card.dataset.cardIndex) : -1;
  }

  _ruleIndex(element) {
    const rule = element.closest("[data-rule-index]");
    return rule ? normalizeNumber(rule.dataset.ruleIndex) : -1;
  }

  _errorMessage(error) {
    return error?.message || error?.error || String(error);
  }

  _t(key, values = {}) {
    return localize(this._hass, key, values);
  }

  _render() {
    if (!this.shadowRoot) {
      return;
    }

    const devices = this._config.devices || [];
    const selectedDevice = this._selectedDevice();
    const usedInputs = new Set(this._cards.map((card) => card.inputNumber));
    const canAddCard = selectedDevice
      ? this._inputNumbers(selectedDevice).some((input) => !usedInputs.has(input))
      : false;

    this.shadowRoot.innerHTML = `
      <style>${this._styles()}</style>
      <section class="page">
        <header class="topbar">
          <h1>openWB</h1>
          ${this._renderDeviceSelector(devices, selectedDevice)}
          <button class="icon-button" data-action="reload" title="${escapeHtml(this._t("button.refresh"))}" aria-label="${escapeHtml(this._t("button.refresh"))}" ${this._loading ? "disabled" : ""}>
            <ha-icon icon="mdi:refresh"></ha-icon>
          </button>
        </header>

        ${this._error ? `<div class="banner error">${escapeHtml(this._error)}</div>` : ""}
        ${this._statusKey ? `<div class="banner success">${escapeHtml(this._t(this._statusKey))}</div>` : ""}
        ${this._loading ? `<div class="banner muted">${escapeHtml(this._t("state.loading"))}</div>` : ""}

        ${
          devices.length
            ? this._renderGrid(canAddCard)
            : `<div class="empty">${escapeHtml(this._t("empty.noMappingDevices"))}</div>`
        }

        <footer class="footer">
          <button class="secondary" data-action="cancel" ${!this._dirty || this._saving || this._loading ? "disabled" : ""}>${escapeHtml(this._t("button.cancel"))}</button>
          <button class="primary" data-action="save" ${!this._dirty || this._saving || this._loading ? "disabled" : ""}>
            ${escapeHtml(this._saving ? this._t("button.saving") : this._t("button.save"))}
          </button>
        </footer>
      </section>
    `;
  }

  _renderDeviceSelector(devices, selectedDevice) {
    if (!devices.length) {
      return "";
    }

    if (devices.length === 1) {
      return `
        <div class="device-title">
          <span>${escapeHtml(selectedDevice?.name || "openWB")}</span>
          <small>${escapeHtml(selectedDevice?.model || "")}</small>
        </div>
      `;
    }

    return `
      <label class="device-select">
        <span>${escapeHtml(this._t("field.device"))}</span>
        <select data-device-select>
          ${devices.map((device) => `
            <option value="${escapeHtml(this._deviceKey(device))}" ${this._deviceKey(device) === this._selectedDeviceKey ? "selected" : ""}>
              ${escapeHtml(device.name)}
            </option>
          `).join("")}
        </select>
      </label>
    `;
  }

  _renderGrid(canAddCard) {
    return `
      <div class="grid">
        ${this._cards.map((card, index) => this._renderCard(card, index)).join("")}
        ${canAddCard ? this._renderAddCard() : ""}
      </div>
    `;
  }

  _renderCard(card, cardIndex) {
    return `
      <article class="input-card" data-card-index="${cardIndex}">
        <header class="card-header">
          <h2>${escapeHtml(this._t("card.inputTitle", { number: card.inputNumber }))}</h2>
          <button class="icon-button danger" data-action="delete-card" title="${escapeHtml(this._t("button.delete"))}" aria-label="${escapeHtml(this._t("button.delete"))}">
            <ha-icon icon="mdi:delete-outline"></ha-icon>
          </button>
        </header>
        <div class="rules">
          ${card.rules.map((rule, index) => this._renderRule(rule, index)).join("")}
          <button class="add-rule" data-action="add-rule">
            <ha-icon icon="mdi:plus"></ha-icon>
            <span>${escapeHtml(this._t("button.add"))}</span>
          </button>
        </div>
      </article>
    `;
  }

  _renderRule(rule, ruleIndex) {
    return `
      <div class="rule" data-rule-index="${ruleIndex}">
        <button class="icon-button rule-delete" data-action="delete-rule" title="${escapeHtml(this._t("button.delete"))}" aria-label="${escapeHtml(this._t("button.delete"))}">
          <ha-icon icon="mdi:close"></ha-icon>
        </button>
        <label class="control">
          <span>${escapeHtml(this._t("field.pressType"))}</span>
          <select data-field="event">
            ${EVENT_OPTIONS.map((option) => `
              <option value="${option.value}" ${Number(rule.event) === option.value ? "selected" : ""}>${escapeHtml(this._t(option.labelKey))}</option>
            `).join("")}
          </select>
        </label>
        <label class="control">
          <span>${escapeHtml(this._t("field.action"))}</span>
          <select data-field="action">
            ${ACTION_OPTIONS.map((option) => `
              <option value="${option.value}" ${Number(rule.action) === option.value ? "selected" : ""}>${escapeHtml(this._t(option.labelKey))}</option>
            `).join("")}
          </select>
        </label>
        <div class="control">
          <span>${escapeHtml(this._t("field.relay"))}</span>
          ${this._renderRelayPicker(rule)}
        </div>
      </div>
    `;
  }

  _renderRelayPicker(rule) {
    const device = this._selectedDevice();
    const outputs = this._outputNumbers(device);
    const selected = new Set((rule.outputs || []).map(Number));
    const allSelected = outputs.length > 0 && outputs.every((output) => selected.has(output));
    const summary = allSelected
      ? this._t("relay.all")
      : outputs.filter((output) => selected.has(output)).map((output) => this._t("relay.item", { number: output })).join(", ") || this._t("relay.select");

    return `
      <details class="relay-picker">
        <summary>${escapeHtml(summary)}</summary>
        <div class="relay-menu">
          <label class="check">
            <input type="checkbox" data-output="all" ${allSelected ? "checked" : ""}>
            <span>${escapeHtml(this._t("relay.all"))}</span>
          </label>
          ${outputs.map((output) => `
            <label class="check">
              <input type="checkbox" data-output="${output}" ${selected.has(output) ? "checked" : ""}>
              <span>${escapeHtml(this._t("relay.item", { number: output }))}</span>
            </label>
          `).join("")}
        </div>
      </details>
    `;
  }

  _renderAddCard() {
    return `
      <button class="add-card" data-action="add-card" aria-label="${escapeHtml(this._t("button.add"))}">
        <ha-icon icon="mdi:plus"></ha-icon>
      </button>
    `;
  }

  _styles() {
    return `
      :host {
        display: block;
        min-height: 100%;
        color: var(--primary-text-color);
        background: var(--primary-background-color);
      }

      * {
        box-sizing: border-box;
      }

      .page {
        min-height: 100vh;
        padding: 24px 24px 104px;
      }

      .topbar {
        display: flex;
        align-items: center;
        gap: 12px;
        margin: 0 0 18px;
      }

      h1,
      h2 {
        letter-spacing: 0;
      }

      h1 {
        flex: 1;
        margin: 0;
        font-size: 24px;
        line-height: 1.2;
        font-weight: 600;
      }

      h2 {
        margin: 0;
        font-size: 18px;
        line-height: 1.3;
        font-weight: 600;
      }

      .device-title {
        display: grid;
        justify-items: end;
        gap: 2px;
        min-width: 0;
      }

      .device-title span,
      .device-title small {
        max-width: 280px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .device-title small {
        color: var(--secondary-text-color);
        font-size: 12px;
      }

      .device-select {
        display: grid;
        gap: 4px;
        min-width: min(260px, 48vw);
        color: var(--secondary-text-color);
        font-size: 12px;
      }

      .device-select select,
      .control select,
      .relay-picker summary {
        width: 100%;
        min-height: 40px;
        border: 1px solid var(--divider-color);
        border-radius: 6px;
        padding: 0 10px;
        background: var(--card-background-color);
        color: var(--primary-text-color);
        font: inherit;
      }

      .grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(min(100%, 320px), 1fr));
        grid-auto-rows: minmax(360px, auto);
        gap: 16px;
        align-items: stretch;
      }

      .input-card,
      .add-card {
        min-height: 360px;
        border: 1px solid var(--divider-color);
        border-radius: 8px;
        background: var(--card-background-color);
        box-shadow: var(--ha-card-box-shadow, 0 2px 8px rgba(0, 0, 0, 0.14));
      }

      .input-card {
        display: flex;
        flex-direction: column;
        gap: 14px;
        padding: 16px;
      }

      .card-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
      }

      .rules {
        display: grid;
        gap: 12px;
      }

      .rule {
        position: relative;
        display: grid;
        gap: 10px;
        padding: 12px;
        border: 1px solid var(--divider-color);
        border-radius: 8px;
        background: var(--secondary-background-color);
      }

      .rule-delete {
        position: absolute;
        top: 8px;
        right: 8px;
      }

      .control {
        display: grid;
        gap: 6px;
        padding-right: 34px;
        color: var(--secondary-text-color);
        font-size: 12px;
      }

      .control select,
      .relay-picker,
      .relay-picker summary {
        color: var(--primary-text-color);
        font-size: 14px;
      }

      .relay-picker {
        position: relative;
      }

      .relay-picker summary {
        display: flex;
        align-items: center;
        cursor: pointer;
        list-style: none;
      }

      .relay-picker summary::-webkit-details-marker {
        display: none;
      }

      .relay-menu {
        position: absolute;
        z-index: 4;
        left: 0;
        right: 0;
        top: calc(100% + 4px);
        display: grid;
        gap: 2px;
        max-height: 240px;
        overflow: auto;
        padding: 8px;
        border: 1px solid var(--divider-color);
        border-radius: 8px;
        background: var(--card-background-color);
        box-shadow: var(--ha-card-box-shadow, 0 8px 20px rgba(0, 0, 0, 0.18));
      }

      .check {
        display: flex;
        align-items: center;
        gap: 8px;
        min-height: 34px;
        padding: 4px 6px;
        border-radius: 6px;
        color: var(--primary-text-color);
      }

      .check:hover {
        background: var(--secondary-background-color);
      }

      button {
        border: 0;
        font: inherit;
        cursor: pointer;
      }

      button:disabled {
        cursor: default;
        opacity: 0.55;
      }

      .icon-button {
        display: inline-grid;
        place-items: center;
        width: 40px;
        height: 40px;
        flex: 0 0 auto;
        border-radius: 6px;
        background: transparent;
        color: var(--primary-text-color);
      }

      .icon-button:hover:not(:disabled) {
        background: var(--secondary-background-color);
      }

      .danger {
        color: var(--error-color);
      }

      .add-rule {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        min-height: 40px;
        border-radius: 6px;
        background: color-mix(in srgb, var(--primary-color) 12%, transparent);
        color: var(--primary-color);
      }

      .add-card {
        display: grid;
        place-items: center;
        width: 100%;
        height: 100%;
        color: var(--primary-color);
      }

      .add-card ha-icon {
        --mdc-icon-size: 56px;
      }

      .banner,
      .empty {
        margin: 0 0 16px;
        padding: 12px 14px;
        border-radius: 8px;
        background: var(--card-background-color);
        border: 1px solid var(--divider-color);
      }

      .error {
        border-color: var(--error-color);
        color: var(--error-color);
      }

      .success {
        border-color: var(--success-color, #0b875b);
        color: var(--success-color, #0b875b);
      }

      .muted,
      .empty {
        color: var(--secondary-text-color);
      }

      .footer {
        position: fixed;
        left: 0;
        right: 0;
        bottom: 0;
        z-index: 3;
        display: flex;
        justify-content: flex-end;
        gap: 12px;
        padding: 14px 24px;
        border-top: 1px solid var(--divider-color);
        background: var(--card-background-color);
        box-shadow: 0 -2px 12px rgba(0, 0, 0, 0.08);
      }

      .primary,
      .secondary {
        min-width: 120px;
        min-height: 42px;
        border-radius: 6px;
        padding: 0 18px;
      }

      .primary {
        background: var(--primary-color);
        color: var(--text-primary-color);
      }

      .secondary {
        background: var(--secondary-background-color);
        color: var(--primary-text-color);
      }

      @media (max-width: 720px) {
        .page {
          padding: 16px 12px 96px;
        }

        .topbar {
          align-items: stretch;
          flex-wrap: wrap;
        }

        h1 {
          flex-basis: 100%;
        }

        .device-select {
          flex: 1;
          min-width: 0;
        }

        .device-title {
          flex: 1;
          justify-items: start;
        }

        .footer {
          padding: 12px;
        }

        .primary,
        .secondary {
          flex: 1;
          min-width: 0;
        }
      }
    `;
  }
}

customElements.define("openwb-mapping-panel", OpenWBMappingPanel);
