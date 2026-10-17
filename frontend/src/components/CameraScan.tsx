import { useEffect, useRef, useState } from 'react'

interface BarcodeDetectorLike {
  detect(source: CanvasImageSource): Promise<{ rawValue: string }[]>
}
declare global {
  interface Window {
    BarcodeDetector?: new (options: { formats: string[] }) => BarcodeDetectorLike
  }
}

/** Any phone or laptop with a camera the browser will share. */
export const cameraSupported = () => typeof navigator !== 'undefined' && Boolean(navigator.mediaDevices?.getUserMedia)

/** Reads QR codes off video frames, with whatever this browser can do. */
async function frameReader(): Promise<(frame: HTMLVideoElement) => Promise<string[]>> {
  if (window.BarcodeDetector) {
    const detector = new window.BarcodeDetector({ formats: ['qr_code'] })
    return async (frame) => (await detector.detect(frame)).map((code) => code.rawValue)
  }
  // Safari and iPhones have no detector. Loaded only when the camera opens,
  // so nobody else downloads it.
  const { default: jsQR } = await import('jsqr')
  const canvas = document.createElement('canvas')
  const context = canvas.getContext('2d', { willReadFrequently: true })
  return async (frame) => {
    if (!context || !frame.videoWidth) return []
    // A pass needs nowhere near full resolution, and a smaller frame decodes fast.
    const scale = Math.min(1, 640 / frame.videoWidth)
    canvas.width = Math.round(frame.videoWidth * scale)
    canvas.height = Math.round(frame.videoHeight * scale)
    context.drawImage(frame, 0, 0, canvas.width, canvas.height)
    const image = context.getImageData(0, 0, canvas.width, canvas.height)
    const code = jsQR(image.data, image.width, image.height, { inversionAttempts: 'dontInvert' })
    return code ? [code.data] : []
  }
}

/**
 * The camera, reading collector passes until one is found. Shared by the door
 * check and the prototype, so both behave the same on every phone.
 */
export function CameraScan({
  onFound,
  onError,
  onClose,
  prefix = 'CP1.',
}: {
  onFound: (value: string) => void
  onError: (message: string) => void
  onClose: () => void
  prefix?: string
}) {
  const video = useRef<HTMLVideoElement>(null)
  const [starting, setStarting] = useState(true)

  useEffect(() => {
    let stream: MediaStream | null = null
    let stopped = false
    ;(async () => {
      try {
        const read = await frameReader()
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
        if (stopped || !video.current) return
        video.current.srcObject = stream
        await video.current.play()
        setStarting(false)
        while (!stopped) {
          const found = (await read(video.current).catch(() => [])).find((value) => value.startsWith(prefix))
          if (found) {
            stopped = true
            onFound(found)
            break
          }
          await new Promise((resolve) => setTimeout(resolve, 200))
        }
      } catch {
        if (!stopped) onError('Could not open the camera. Allow camera access, or type or paste the pass instead.')
      }
    })()
    return () => {
      stopped = true
      stream?.getTracks().forEach((track) => track.stop())
    }
    // One scan session per opening; the callbacks do not restart it.
  }, [])

  return (
    <div className="space-y-2">
      <div className="relative">
        <video ref={video} className="aspect-square w-full rounded-lg bg-black object-cover" muted playsInline />
        {/* The target, so it is obvious where to hold the pass. */}
        <div className="pointer-events-none absolute inset-[18%] rounded-xl border-4 border-white/80" />
        {starting && <p className="absolute inset-x-0 top-1/2 text-center text-sm text-white">Opening the camera…</p>}
      </div>
      <p className="text-center text-xs text-slate-500">Hold the collector’s QR code inside the square.</p>
      <button type="button" className="btn btn-secondary w-full" onClick={onClose}>
        Stop camera
      </button>
    </div>
  )
}
