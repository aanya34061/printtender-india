export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0f1117",
        surface: "#1e2235",
        navbar: "#13172a",
        accent: "#f97316",
        success: "#22c55e",
        warning: "#eab308",
        danger: "#ef4444",
        navy: "#1A2C52",
        crimson: "#C0392B",
        paper: "#F5F0E8",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
