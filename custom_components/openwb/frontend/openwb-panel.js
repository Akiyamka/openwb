import {
  ACTION_NONE,
  ACTION_OPTIONS,
  BUTTON_EVENT_VALUES,
  DEFAULT_ACTION,
  DEFAULT_EVENT,
  EDGE_EVENT_VALUES,
  EVENT_OPTIONS,
  INPUT_MODE_DISABLE_ALL_OUTPUTS,
  INPUT_MODE_FREQUENCY,
  INPUT_MODE_HELP_KEYS,
  INPUT_MODE_LATCHING,
  MAPPING_MATRIX_INPUT_MODES,
  INPUT_MODE_MAPPING_MATRIX_BUTTON,
  INPUT_MODE_MAPPING_MATRIX_EDGE,
  INPUT_MODE_OPTIONS,
  INPUT_MODE_MOMENTARY,
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
    this._openRelayPickerKey = "";
    this._handleDocumentClick = (event) => this._closeRelayPickerFromEvent(event);

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
    document.addEventListener("click", this._handleDocumentClick);
    this._render();
  }

  disconnectedCallback() {
    document.removeEventListener("click", this._handleDocumentClick);
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
      this._cards = this._cardsFromMatrices(
        result.matrices || {},
        result.input_modes || [],
        device,
      );
      this._openRelayPickerKey = "";
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
    let inputModes;
    try {
      mappings = this._mappingsFromCards();
      inputModes = this._inputModesFromCards();
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
        input_modes: inputModes,
      });
      this._cards = this._cards.map((card) =>
        MAPPING_MATRIX_INPUT_MODES.has(Number(card.inputMode))
          ? card
          : { ...card, rules: [] }
      );
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

    const relayPicker = target.closest(".relay-picker");
    if (relayPicker) {
      if (target.closest("summary")) {
        this._toggleRelayPicker(relayPicker);
      }
      return;
    }

    this._closeRelayPicker();

    const button = target.closest("[data-action]");
    if (!button) {
      return;
    }

    const action = button.dataset.action;
    if (action === "reload") {
      this._loadConfig();
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

    if (target.matches("select[data-input-mode]")) {
      this._updateInputMode(target);
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

  _updateInputMode(element) {
    const cardIndex = this._cardIndex(element);
    if (cardIndex < 0) {
      return;
    }

    const inputMode = normalizeNumber(element.value);
    this._cards = this._cards.map((card, index) => {
      if (index !== cardIndex) {
        return card;
      }

      const nextCard = { ...card, inputMode };
      if (!MAPPING_MATRIX_INPUT_MODES.has(inputMode)) {
        return nextCard;
      }

      const matchingRules = nextCard.rules.filter((rule) =>
        this._ruleMatchesInputMode(rule, inputMode)
      );
      return {
        ...nextCard,
        rules: matchingRules.length
          ? matchingRules
          : [this._newRule({ ...nextCard, rules: [] })],
      };
    });
    this._markDirty();
  }

  _addRule(element) {
    const cardIndex = this._cardIndex(element);
    if (cardIndex < 0) {
      return;
    }
    if (!MAPPING_MATRIX_INPUT_MODES.has(Number(this._cards[cardIndex].inputMode))) {
      return;
    }
    this._cards = this._cards.map((card, index) =>
      index === cardIndex
        ? { ...card, rules: [...card.rules, this._newRule(card)] }
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
    this._openRelayPickerKey = this._relayPickerKey(
      this._cards[cardIndex],
      this._cards[cardIndex].rules[ruleIndex],
    );

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

  _cardsFromMatrices(matrices, inputModes, device) {
    const inputNumbers = this._inputNumbers(device);
    const outputNumbers = this._outputNumbers(device);
    const inputModeByInput = new Map(
      (Array.isArray(inputModes) ? inputModes : []).map((item) => [
        Number(item.input_number),
        Number(item.mode),
      ]),
    );
    const cards = [];

    for (const inputNumber of inputNumbers) {
      const rules = [];
      const inputMode = inputModeByInput.get(inputNumber) ??
        this._defaultInputMode(inputNumber);
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

      cards.push({
        inputNumber,
        inputMode,
        rules,
      });
    }

    return cards;
  }

  _mappingsFromCards() {
    const mappings = [];
    const seenCells = new Set();
    const eventTypeByInput = new Map();

    for (const card of this._cards) {
      if (!MAPPING_MATRIX_INPUT_MODES.has(Number(card.inputMode))) {
        continue;
      }

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

        const eventType = this._mappingEventType(rule.event);
        if (!this._ruleMatchesInputMode(rule, Number(card.inputMode))) {
          throw new Error(this._t("validation.modeEventMismatch"));
        }
        const existingEventType = eventTypeByInput.get(card.inputNumber);
        if (existingEventType && existingEventType !== eventType) {
          throw new Error(this._t("validation.mixedEventTypes"));
        }
        eventTypeByInput.set(card.inputNumber, eventType);

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

  _inputModesFromCards() {
    return this._cards.map((card) => ({
      input_number: card.inputNumber,
      mode: Number(card.inputMode),
    }));
  }

  _newRule(card = undefined) {
    const firstOutput = this._outputNumbers(this._selectedDevice())[0];
    return {
      id: this._nextRuleId(),
      event: this._defaultEventForCard(card),
      action: DEFAULT_ACTION,
      outputs: firstOutput === undefined ? [] : [firstOutput],
    };
  }

  _defaultEventForCard(card) {
    if (Number(card?.inputMode) === INPUT_MODE_MAPPING_MATRIX_EDGE) {
      return 864;
    }
    if (Number(card?.inputMode) === INPUT_MODE_MAPPING_MATRIX_BUTTON) {
      return DEFAULT_EVENT;
    }
    if (card?.rules?.length) {
      const firstEvent = card.rules[0].event;
      return EDGE_EVENT_VALUES.has(Number(firstEvent)) ? 864 : DEFAULT_EVENT;
    }
    return DEFAULT_EVENT;
  }

  _ruleMatchesInputMode(rule, inputMode) {
    const event = Number(rule.event);
    if (inputMode === INPUT_MODE_MAPPING_MATRIX_EDGE) {
      return EDGE_EVENT_VALUES.has(event);
    }
    if (inputMode === INPUT_MODE_MAPPING_MATRIX_BUTTON) {
      return BUTTON_EVENT_VALUES.has(event);
    }
    return false;
  }

  _eventOptionsForInputMode(inputMode) {
    const mode = Number(inputMode);
    if (mode === INPUT_MODE_MAPPING_MATRIX_EDGE) {
      return EVENT_OPTIONS.filter((option) => EDGE_EVENT_VALUES.has(option.value));
    }
    if (mode === INPUT_MODE_MAPPING_MATRIX_BUTTON) {
      return EVENT_OPTIONS.filter((option) => BUTTON_EVENT_VALUES.has(option.value));
    }
    return EVENT_OPTIONS;
  }

  _mappingEventType(event) {
    const eventNumber = Number(event);
    if (BUTTON_EVENT_VALUES.has(eventNumber)) {
      return "button";
    }
    if (EDGE_EVENT_VALUES.has(eventNumber)) {
      return "edge";
    }
    return "unknown";
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

  _defaultInputMode(inputNumber) {
    return Number(inputNumber) === 0
      ? INPUT_MODE_DISABLE_ALL_OUTPUTS
      : INPUT_MODE_LATCHING;
  }

  _inputModeOptions(inputNumber) {
    if (Number(inputNumber) === 0) {
      return INPUT_MODE_OPTIONS.filter((option) =>
        ![INPUT_MODE_MOMENTARY, INPUT_MODE_LATCHING].includes(option.value)
      );
    }
    return INPUT_MODE_OPTIONS;
  }

  _cardIndex(element) {
    const card = element.closest("[data-card-index]");
    return card ? normalizeNumber(card.dataset.cardIndex) : -1;
  }

  _ruleIndex(element) {
    const rule = element.closest("[data-rule-index]");
    return rule ? normalizeNumber(rule.dataset.ruleIndex) : -1;
  }

  _relayPickerKey(card, rule) {
    return `${card.inputNumber}:${rule.id}`;
  }

  _toggleRelayPicker(element) {
    const key = element.dataset.relayKey || "";
    if (!key) {
      return;
    }

    if (element.open) {
      this._openRelayPickerKey = "";
      return;
    }

    this._closeRelayPicker();
    this._openRelayPickerKey = key;
  }

  _closeRelayPicker() {
    if (!this._openRelayPickerKey) {
      return;
    }

    const key = this._openRelayPickerKey;
    this._openRelayPickerKey = "";
    const openPicker = this.shadowRoot.querySelector(
      `.relay-picker[data-relay-key="${key}"]`,
    );
    if (openPicker) {
      openPicker.open = false;
    }
  }

  _closeRelayPickerFromEvent(event) {
    if (event.composedPath().includes(this)) {
      return;
    }
    this._closeRelayPicker();
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
            ? this._renderGrid()
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

  _renderGrid() {
    return `
      <div class="grid">
        ${this._cards.map((card, index) => this._renderCard(card, index)).join("")}
      </div>
    `;
  }

  _renderCard(card, cardIndex) {
    return `
      <article class="input-card" data-card-index="${cardIndex}">
        <header class="card-header">
          <h2>${escapeHtml(this._t("card.inputTitle", { number: card.inputNumber }))}</h2>
        </header>
        ${this._renderInputModeControl(card)}
        <div class="rules">
          ${this._renderCardRules(card)}
        </div>
      </article>
    `;
  }

  _renderInputModeControl(card) {
    const helpKey = INPUT_MODE_HELP_KEYS[Number(card.inputMode)];
    const helpText = helpKey ? this._t(helpKey) : "";
    return `
      <label class="mode-control">
        <span>${escapeHtml(this._t("field.inputMode"))}</span>
        <div class="mode-row">
          <select data-input-mode>
            ${this._inputModeOptions(card.inputNumber).map((option) => `
              <option value="${option.value}" ${Number(card.inputMode) === option.value ? "selected" : ""}>
                ${escapeHtml(this._t(option.labelKey))}
              </option>
            `).join("")}
          </select>
          <span class="mode-help" title="${escapeHtml(helpText)}" aria-label="${escapeHtml(helpText)}">
            <ha-icon icon="mdi:help-circle-outline"></ha-icon>
          </span>
        </div>
      </label>
    `;
  }

  _renderCardRules(card) {
    if (!MAPPING_MATRIX_INPUT_MODES.has(Number(card.inputMode))) {
      return this._renderLegacyRule(card);
    }

    return `
      ${card.rules.map((rule, index) => this._renderRule(card, rule, index)).join("")}
      <button class="add-rule" data-action="add-rule">
        <ha-icon icon="mdi:plus"></ha-icon>
        <span>${escapeHtml(this._t("button.add"))}</span>
      </button>
    `;
  }

  _renderLegacyRule(card) {
    const behavior = this._legacyBehavior(card);
    return `
      <div class="rule read-only-rule">
        <div class="control">
          <span>${escapeHtml(this._t("field.pressType"))}</span>
          <div class="readonly-value">${escapeHtml(behavior.event)}</div>
        </div>
        <div class="control">
          <span>${escapeHtml(this._t("field.action"))}</span>
          <div class="readonly-value">${escapeHtml(behavior.action)}</div>
        </div>
        <div class="control">
          <span>${escapeHtml(this._t("field.relay"))}</span>
          <div class="readonly-value">${escapeHtml(behavior.relay)}</div>
        </div>
      </div>
    `;
  }

  _legacyBehavior(card) {
    const mode = Number(card.inputMode);
    if ([INPUT_MODE_MOMENTARY, INPUT_MODE_LATCHING].includes(mode)) {
      return {
        event: this._t("event.shortPress"),
        action: this._t("action.toggle"),
        relay: this._t("relay.item", { number: card.inputNumber }),
      };
    }

    if (mode === INPUT_MODE_DISABLE_ALL_OUTPUTS) {
      return {
        event: this._t("event.risingEdge"),
        action: this._t("action.off"),
        relay: this._t("relay.all"),
      };
    }

    if (mode === INPUT_MODE_FREQUENCY) {
      return {
        event: this._t("event.notApplicable"),
        action: this._t("action.none"),
        relay: this._t("relay.none"),
      };
    }

    return {
      event: this._t("event.notApplicable"),
      action: this._t("action.none"),
      relay: this._t("relay.none"),
    };
  }

  _renderRule(card, rule, ruleIndex) {
    const eventOptions = this._eventOptionsForInputMode(card.inputMode);
    return `
      <div class="rule" data-rule-index="${ruleIndex}">
        <button class="icon-button rule-delete" data-action="delete-rule" title="${escapeHtml(this._t("button.delete"))}" aria-label="${escapeHtml(this._t("button.delete"))}">
          <ha-icon icon="mdi:close"></ha-icon>
        </button>
        <label class="control">
          <span>${escapeHtml(this._t("field.pressType"))}</span>
          <select data-field="event">
            ${eventOptions.map((option) => `
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
          ${this._renderRelayPicker(card, rule)}
        </div>
      </div>
    `;
  }

  _renderRelayPicker(card, rule) {
    const device = this._selectedDevice();
    const outputs = this._outputNumbers(device);
    const selected = new Set((rule.outputs || []).map(Number));
    const allSelected = outputs.length > 0 && outputs.every((output) => selected.has(output));
    const summary = allSelected
      ? this._t("relay.all")
      : outputs.filter((output) => selected.has(output)).map((output) => this._t("relay.item", { number: output })).join(", ") || this._t("relay.select");
    const pickerKey = this._relayPickerKey(card, rule);

    return `
      <details class="relay-picker" data-relay-key="${escapeHtml(pickerKey)}" ${pickerKey === this._openRelayPickerKey ? "open" : ""}>
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
      .mode-control select,
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

      .input-card {
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

      .mode-control {
        display: grid;
        gap: 6px;
        color: var(--secondary-text-color);
        font-size: 12px;
      }

      .mode-row {
        display: grid;
        grid-template-columns: minmax(0, 1fr) 40px;
        gap: 8px;
        align-items: center;
      }

      .mode-help {
        display: inline-grid;
        place-items: center;
        width: 40px;
        height: 40px;
        color: var(--secondary-text-color);
      }

      .rule {
        position: relative;
        display: grid;
        gap: 10px;
        padding: 12px;
        padding-top: 32px;
        border: 1px solid var(--divider-color);
        border-radius: 8px;
        background: var(--secondary-background-color);
      }

      .rule-delete {
        position: absolute;
        top: 0px;
        right: 0px;
      }

      .control {
        display: grid;
        gap: 6px;
        color: var(--secondary-text-color);
        font-size: 12px;
      }

      .read-only-rule .control {
        padding-right: 0;
      }

      .control select,
      .readonly-value,
      .relay-picker,
      .relay-picker summary {
        color: var(--primary-text-color);
        font-size: 14px;
      }

      .readonly-value {
        display: flex;
        align-items: center;
        min-height: 40px;
        border: 1px solid var(--divider-color);
        border-radius: 6px;
        padding: 0 10px;
        background: var(--card-background-color);
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
