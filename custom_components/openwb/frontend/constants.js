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

export const INPUT_MODE_MOMENTARY = 0;
export const INPUT_MODE_LATCHING = 1;
export const INPUT_MODE_DISABLE_ALL_OUTPUTS = 2;
export const INPUT_MODE_FREQUENCY = 3;
export const INPUT_MODE_MAPPING_MATRIX_EDGE = 4;
export const INPUT_MODE_MAPPING_MATRIX_BUTTON = 6;
export const MAPPING_MATRIX_INPUT_MODES = new Set([
  INPUT_MODE_MAPPING_MATRIX_EDGE,
  INPUT_MODE_MAPPING_MATRIX_BUTTON,
]);
export const BUTTON_EVENT_VALUES = new Set([544, 608, 672, 736]);
export const EDGE_EVENT_VALUES = new Set([800, 864]);

export const INPUT_MODE_LABEL_KEYS = {
  0: "inputMode.momentary",
  1: "inputMode.latching",
  2: "inputMode.disableAllOutputs",
  3: "inputMode.frequency",
  4: "inputMode.mappingMatrixEdge",
  5: "inputMode.unused",
  6: "inputMode.mappingMatrixButton",
};

export const INPUT_MODE_HELP_KEYS = {
  0: "inputModeHelp.momentary",
  1: "inputModeHelp.latching",
  2: "inputModeHelp.disableAllOutputs",
  3: "inputModeHelp.frequency",
  4: "inputModeHelp.mappingMatrixEdge",
  6: "inputModeHelp.mappingMatrixButton",
};

export const INPUT_MODE_OPTIONS = [
  { value: INPUT_MODE_MOMENTARY, labelKey: INPUT_MODE_LABEL_KEYS[0] },
  { value: INPUT_MODE_LATCHING, labelKey: INPUT_MODE_LABEL_KEYS[1] },
  { value: INPUT_MODE_DISABLE_ALL_OUTPUTS, labelKey: INPUT_MODE_LABEL_KEYS[2] },
  { value: INPUT_MODE_FREQUENCY, labelKey: INPUT_MODE_LABEL_KEYS[3] },
  { value: INPUT_MODE_MAPPING_MATRIX_EDGE, labelKey: INPUT_MODE_LABEL_KEYS[4] },
  { value: INPUT_MODE_MAPPING_MATRIX_BUTTON, labelKey: INPUT_MODE_LABEL_KEYS[6] },
];
