// Which app this page belongs to, so "Add to Home Screen" or "Install" makes
// the right one: Parents, Nursery (managers and room leaders) or Company,
// each with its own name, icon and start page. One HTML page serves every
// portal, so the choice is made here from the address, before the browser
// reads the head, and again on every in-app navigation (see App.tsx).
//
// The start page of each app is its portal's sign-in address. Already signed
// in, that goes straight on to the portal, so it is also the permanent link
// to bookmark or send.
;(() => {
  const TITLES = { parent: 'Parents', nursery: 'Nursery', company: 'Company', site: 'Collector' }

  const appFor = (path, search) => {
    const params = new URLSearchParams(search)
    const portal = params.get('portal')
    if (portal && portal in TITLES) return portal
    const target = path === '/sign-in' ? params.get('next') || '' : path
    if (target.startsWith('/parent')) return 'parent'
    if (target.startsWith('/door') || target.startsWith('/admin')) return 'nursery'
    if (target.startsWith('/company')) return 'company'
    return 'site'
  }

  const tag = (selector, create) => {
    let node = document.head.querySelector(selector)
    if (!node) {
      node = create()
      document.head.appendChild(node)
    }
    return node
  }

  const update = () => {
    const app = appFor(location.pathname, location.search)
    const manifest = tag('link[rel="manifest"]', () => Object.assign(document.createElement('link'), { rel: 'manifest' }))
    if (manifest.getAttribute('href') !== `/${app}.webmanifest`) manifest.setAttribute('href', `/${app}.webmanifest`)
    tag('link[rel="apple-touch-icon"]', () => Object.assign(document.createElement('link'), { rel: 'apple-touch-icon' }))
      .setAttribute('href', `/icons/icon-${app}-180.png`)
    tag('meta[name="apple-mobile-web-app-title"]', () => Object.assign(document.createElement('meta'), { name: 'apple-mobile-web-app-title' }))
      .setAttribute('content', TITLES[app])
  }

  update()
  window.entraccessApp = { update }
})()
