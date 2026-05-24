/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        apple: {
          gray: '#1d1d1f',
          blue: '#0071e3',
          light: '#f5f5f7'
        }
      }
    },
  },
  plugins: [],
}

