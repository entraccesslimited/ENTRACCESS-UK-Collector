// Sets the website's theme before anything is drawn, so it never flashes the
// wrong one: a choice saved by the toggle, or else the device's setting, which
// it keeps following until somebody chooses. A file rather than an inline
// script because the CSP allows scripts from 'self' only.
;(() => {
  const KEY = 'entraccess-theme'
  const saved = () => {
    try {
      return localStorage.getItem(KEY)
    } catch {
      return null
    }
  }
  const system = window.matchMedia('(prefers-color-scheme: dark)')
  const apply = (theme) => {
    document.documentElement.dataset.theme = theme
  }
  apply(saved() || (system.matches ? 'dark' : 'light'))
  system.addEventListener('change', (event) => {
    if (!saved()) apply(event.matches ? 'dark' : 'light')
  })
})()
