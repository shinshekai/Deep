export { useAppStore } from "@/stores/app-store";

// Provider-free Zustand — uses singleton create() pattern.
// All DEEP pages are client-side, so no SSR store leakage.
// Import { useAppStore } from "@/stores" from any component.
