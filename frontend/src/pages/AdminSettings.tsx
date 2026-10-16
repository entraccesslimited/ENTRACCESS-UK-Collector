import { useEffect, useState, type FormEvent } from 'react'

import { Alert, PageTitle } from '@/components/ui'
import { api } from '@/lib/api'
import { currentPosition } from '@/lib/location'
import { useLoad } from '@/lib/useLoad'

interface Fence {
  enabled: boolean
  latitude: number | null
  longitude: number | null
  radius_m: number | null
  min_radius_m: number
  max_radius_m: number
}

export function AdminSettings() {
  return (
    <>
      <PageTitle title="Settings" sub="How door checks work at this nursery." />
      <GeofenceCard />
    </>
  )
}

function GeofenceCard() {
  const fence = useLoad<Fence>('/admin/geofence')
  const [lat, setLat] = useState('')
  const [lng, setLng] = useState('')
  const [radius, setRadius] = useState('150')
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [locating, setLocating] = useState(false)

  useEffect(() => {
    if (!fence.data?.enabled) return
    setLat(String(fence.data.latitude ?? ''))
    setLng(String(fence.data.longitude ?? ''))
    setRadius(String(fence.data.radius_m ?? 150))
  }, [fence.data])

  const useHere = async () => {
    setLocating(true)
    setError(null)
    const p = await currentPosition(15000)
    setLocating(false)
    if (!p) {
      setError('Could not get this device’s location. Allow location for this site, or type the coordinates.')
      return
    }
    setLat(p.latitude.toFixed(6))
    setLng(p.longitude.toFixed(6))
    setMessage(`Location found, accurate to about ${Math.round(p.accuracy_m)} m. Check it, then save.`)
  }

  const save = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    setMessage(null)
    try {
      await api('/admin/geofence', {
        method: 'PUT',
        json: { latitude: Number(lat), longitude: Number(lng), radius_m: Number(radius) },
      })
      setMessage('Geofence on. Door checks now need the phone to be within the circle.')
      await fence.reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save the geofence.')
    }
  }

  const turnOff = async () => {
    setError(null)
    try {
      await api('/admin/geofence', { method: 'DELETE' })
      setMessage('Geofence off. Door checks work from anywhere.')
      setLat('')
      setLng('')
      await fence.reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not turn the geofence off.')
    }
  }

  const valid = lat.trim() !== '' && lng.trim() !== '' && !Number.isNaN(Number(lat)) && !Number.isNaN(Number(lng))

  return (
    <section className="card max-w-xl">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">Geofence</h2>
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-semibold ${fence.data?.enabled ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-200 text-slate-700'}`}
        >
          {fence.data?.enabled ? 'On' : 'Off'}
        </span>
      </div>
      <p className="mt-1 text-sm text-slate-600">
        Only accept door checks from phones within a circle around the nursery. A check from outside it, or from a phone
        that won’t share its location, is refused and shows up as an exception.
      </p>
      <p className="mt-2 text-xs text-slate-500">
        This stops checks made from home or off site by mistake. A phone’s location can be faked, so it is not a security
        guarantee. Phone GPS indoors can be 50 m out, so a check passes if the phone could be inside the circle.
      </p>

      {error && <div className="mt-3"><Alert>{error}</Alert></div>}
      {message && <div className="mt-3"><Alert tone="ok">{message}</Alert></div>}

      <form onSubmit={save} className="mt-4 space-y-3">
        <button type="button" className="btn btn-secondary w-full" onClick={useHere} disabled={locating}>
          {locating ? 'Finding this device…' : 'Use this device’s location (stand at the nursery door)'}
        </button>
        <div className="grid grid-cols-2 gap-3">
          <label>
            <span className="label">Latitude</span>
            <input className="input" inputMode="decimal" value={lat} onChange={(e) => setLat(e.target.value)} placeholder="53.381100" />
          </label>
          <label>
            <span className="label">Longitude</span>
            <input className="input" inputMode="decimal" value={lng} onChange={(e) => setLng(e.target.value)} placeholder="-1.470100" />
          </label>
        </div>
        <label className="block">
          <span className="label">Radius: {radius} m</span>
          <input
            type="range"
            className="w-full"
            min={fence.data?.min_radius_m ?? 50}
            max={1000}
            step={10}
            value={radius}
            onChange={(e) => setRadius(e.target.value)}
          />
          <span className="text-xs text-slate-500">150 m suits most nurseries; widen it if staff check collectors at a car park.</span>
        </label>
        {valid && (
          <a
            className="block text-sm text-brand-700 underline"
            href={`https://www.openstreetmap.org/?mlat=${lat}&mlon=${lng}#map=18/${lat}/${lng}`}
            target="_blank"
            rel="noopener noreferrer"
          >
            Check this point on a map
          </a>
        )}
        <div className="flex flex-wrap gap-2">
          <button className="btn btn-primary" disabled={!valid}>
            {fence.data?.enabled ? 'Save changes' : 'Turn geofence on'}
          </button>
          {fence.data?.enabled && (
            <button type="button" className="btn btn-secondary" onClick={turnOff}>
              Turn off
            </button>
          )}
        </div>
      </form>
    </section>
  )
}
