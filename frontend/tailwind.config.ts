import type { Config } from "tailwindcss";
const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // semantic tokens via channel vars so /alpha modifiers work (v3 caveat)
        bg: "rgb(var(--s-bg) / <alpha-value>)",
        surface: {
          DEFAULT: "rgb(var(--s-surface) / <alpha-value>)",
          2: "rgb(var(--s-surface-2) / <alpha-value>)",
          3: "rgb(var(--s-surface-3) / <alpha-value>)",
        },
        fg: {
          DEFAULT: "rgb(var(--s-fg) / <alpha-value>)",
          muted: "rgb(var(--s-muted) / <alpha-value>)",
        },
        hairline: "rgb(var(--s-muted) / 0.14)",
        accent: {
          DEFAULT: "rgb(var(--s-accent) / <alpha-value>)",
          fg: "rgb(var(--s-accent-fg) / <alpha-value>)",
          ring: "rgb(var(--s-accent) / <alpha-value>)",
        },
        destructive: "rgb(var(--s-destructive) / <alpha-value>)",
        information: "rgb(var(--s-information) / <alpha-value>)",
        social: "rgb(var(--s-social) / <alpha-value>)",
        prediction: "rgb(var(--s-prediction) / <alpha-value>)",
        orderflow: "rgb(var(--s-orderflow) / <alpha-value>)",
        price: "rgb(var(--s-price) / <alpha-value>)",
        risk: "rgb(var(--s-risk) / <alpha-value>)",
        quantum: "rgb(var(--s-quantum) / <alpha-value>)",
        uncertainty: "rgb(var(--s-uncertainty) / <alpha-value>)",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      spacing: {
        xs: "var(--space-xs)", sm: "var(--space-sm)", md: "var(--space-md)",
        lg: "var(--space-lg)", xl: "var(--space-xl)", "2xl": "var(--space-2xl)", "3xl": "var(--space-3xl)",
      },
      boxShadow: { sm: "var(--shadow-sm)", md: "var(--shadow-md)", lg: "var(--shadow-lg)" },
      transitionDuration: { fast: "var(--dur-fast)", base: "var(--dur-base)", slow: "var(--dur-slow)" },
      transitionTimingFunction: { out: "var(--ease-out)", inout: "var(--ease-inout)" },
    },
  },
  plugins: [],
};
export default config;
