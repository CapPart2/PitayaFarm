/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class', // optional: add class="dark" to html for dark mode
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['Poppins', 'Inter', 'sans-serif'],
      },
      colors: {
        // Agri-Tech theme
        pitaya: {
          'deep': '#1a3d16',
          'primary': '#2f6a21',
          'leaf': '#3c7b2b',
          'light': '#4d9c3d',
          'mint': '#6bb854',
          'pale': '#e8f5e4',
          'bg': '#f4faf2',
          // Dark mode variants
          'dark-deep': '#0d1e0a',
          'dark-primary': '#1a3510',
          'dark-leaf': '#234218',
          'dark-light': '#2d5622',
          'dark-mint': '#3a6b2a',
          'dark-pale': '#1a2e16',
          'dark-bg': '#0f1f0c',
        },
        earth: {
          'dark': '#3d3229',
          'brown': '#5c5044',
          'tan': '#8b7355',
          'light': '#d4c4b0',
          // Dark mode variants
          'dark-dark': '#1a1612',
          'dark-brown': '#2d241a',
          'dark-tan': '#4a3d2a',
          'dark-light': '#6b5d4a',
        },
        accent: {
          yellow: '#e8c547',
          'yellow-soft': '#f5e6b3',
          // Dark mode variants
          'dark-yellow': '#d4b034',
          'dark-yellow-soft': '#e8d080',
        },
        // Dark mode semantic colors
        dark: {
          'bg-primary': '#0a0f08',
          'bg-secondary': '#0f1f0c',
          'bg-tertiary': '#1a2e16',
          'text-primary': '#f0f4ed',
          'text-secondary': '#d4e0cc',
          'text-tertiary': '#b8c8a8',
          'border': '#2d5622',
          'border-light': '#3a6b2a',
          'card': '#1a2e16',
          'card-hover': '#234218',
          'input': '#0f1f0c',
          'input-border': '#2d5622',
          'button': '#3a6b2a',
          'button-hover': '#4d9c3d',
          'success': '#6bb854',
          'warning': '#e8c547',
          'error': '#ef4444',
          'info': '#3b82f6',
        },
      },
      boxShadow: {
        'card': '0 1px 3px 0 rgb(0 0 0 / 0.06), 0 1px 2px -1px rgb(0 0 0 / 0.06)',
        'card-hover': '0 10px 25px -5px rgb(0 0 0 / 0.08), 0 4px 10px -4px rgb(0 0 0 / 0.04)',
      },
      borderRadius: {
        'xl': '1rem',
        '2xl': '1.25rem',
      },
      animation: {
        float: 'float 6s ease-in-out infinite',
        gradient: 'gradient 12s ease infinite',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-10px)' },
        },
        gradient: {
          '0%, 100%': { backgroundPosition: '0% 50%' },
          '50%': { backgroundPosition: '100% 50%' },
        },
      },
      backgroundSize: {
        'gradient': '200% 200%',
      },
    },
  },
  plugins: [],
}
