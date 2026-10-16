/** The phone's position for a geofenced door check, or null if it cannot be had.
 *  A fresh fix every time: a cached one could be from before the phone left. */
export interface Position {
  latitude: number
  longitude: number
  accuracy_m: number
}

export function currentPosition(timeoutMs = 10000): Promise<Position | null> {
  if (typeof navigator === 'undefined' || !navigator.geolocation) return Promise.resolve(null)
  return new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      (p) => resolve({ latitude: p.coords.latitude, longitude: p.coords.longitude, accuracy_m: p.coords.accuracy }),
      () => resolve(null),
      { enableHighAccuracy: true, timeout: timeoutMs, maximumAge: 0 },
    )
  })
}
