/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        darkBg: '#0a0a0a',
        darkCard: '#171717',
        brandAccent: '#3b82f6',
      }
    },
  },
  plugins: [],
}
