import type { Config } from "tailwindcss";
export default {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: { extend: { colors: { ink: "#15241f", cream: "#f5f2e9", sage: "#426b5a", lime: "#dff07a", coral: "#f47f61" }, boxShadow: { soft: "0 16px 40px rgba(21,36,31,.09)" } } },
  plugins: []
} satisfies Config;
