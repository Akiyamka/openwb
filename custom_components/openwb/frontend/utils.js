import { FALLBACK_LANGUAGE, TRANSLATIONS } from "./constants.js";

export const cloneCards = (cards) => JSON.parse(JSON.stringify(cards));

export const escapeHtml = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[char]);

export const normalizeNumber = (value) => Number.parseInt(value, 10);

export const localize = (hass, key, values = {}) => {
  const language = String(hass?.language || FALLBACK_LANGUAGE).toLowerCase();
  const baseLanguage = language.split("-")[0];
  const message =
    TRANSLATIONS[language]?.[key] ||
    TRANSLATIONS[baseLanguage]?.[key] ||
    TRANSLATIONS[FALLBACK_LANGUAGE]?.[key] ||
    key;

  return message.replace(/\{([a-zA-Z0-9_]+)\}/g, (match, name) =>
    Object.prototype.hasOwnProperty.call(values, name) ? String(values[name]) : match
  );
};
