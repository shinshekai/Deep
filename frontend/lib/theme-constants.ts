export const THEME_STORAGE_KEY = "deep-theme";

export const THEMES = [
  { id: "dark", label: "Dark", colorScheme: "dark" },
  { id: "cream", label: "Cream", colorScheme: "light" },
  { id: "snow", label: "Snow", colorScheme: "light" },
  { id: "glass", label: "Glass", colorScheme: "light" },
] as const;

export type ThemeId = (typeof THEMES)[number]["id"];
