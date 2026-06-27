import enTranslations from "./translations/en.js";
import ruTranslations from "./translations/ru.js";

export const TRANSLATIONS = {
  en: enTranslations,
  ru: ruTranslations,
};

export const FALLBACK_LANGUAGE = "en";

export const EVENT_OPTIONS = [
  { value: 544, labelKey: "event.shortPress" },
  { value: 608, labelKey: "event.longPress" },
  { value: 672, labelKey: "event.doublePress" },
  { value: 736, labelKey: "event.shortThenLongPress" },
  { value: 864, labelKey: "event.risingEdge" },
  { value: 800, labelKey: "event.fallingEdge" },
];

export const ACTION_OPTIONS = [
  { value: 2, labelKey: "action.on" },
  { value: 1, labelKey: "action.off" },
  { value: 3, labelKey: "action.toggle" },
];

export const ACTION_NONE = 0;
export const DEFAULT_EVENT = EVENT_OPTIONS[0].value;
export const DEFAULT_ACTION = 3;

export const INPUT_MODE_MAPPING_MATRIX_EDGE = 4;
export const INPUT_MODE_MAPPING_MATRIX_BUTTON = 6;
export const MAPPING_MATRIX_INPUT_MODES = new Set([
  INPUT_MODE_MAPPING_MATRIX_EDGE,
  INPUT_MODE_MAPPING_MATRIX_BUTTON,
]);
