/** @type {import('tailwindcss').Config} */

module.exports = {
  content: ["./scheduler/templates/**/*.html",],
  theme: {
    extend: {      
      colors: {
        lightred: '#e53c38', // soft red
        regred: '#d11d27', // a light, soft red
        darkred: '#a90011', // a darker, more intense red
        beige: '#FFFAFF', // a light beige color could be used as background maybe
        borderRed:'#F8ABA9'
      },
    },
  plugins: [],
  }
}

