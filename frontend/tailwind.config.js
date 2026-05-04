export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0f1117",
        surface: "#1a1f35",
        surface2: "#222840",
        accent: "#f97316",
        success: "#22c55e",
        danger: "#ef4444",
        warning: "#f59e0b",
        muted: "#64748b",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "monospace"],
      },
      boxShadow: {
        card: "0 4px 24px rgba(0,0,0,0.4)",
        "accent-glow": "0 4px 16px rgba(249,115,22,0.4)",
        "accent-hover": "0 8px 32px rgba(249,115,22,0.12)",
      },
    },
  },
  plugins: [],
};
