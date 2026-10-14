import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import WAVES from 'vanta/dist/vanta.waves.min'

/** Persistent animated background behind the whole app. */
export default function WavesBackground() {
  const ref = useRef(null)

  useEffect(() => {
    const calm = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    let effect
    try {
      effect = WAVES({
        el: ref.current,
        THREE,
        mouseControls: true,
        touchControls: true,
        gyroControls: false,
        minHeight: 200,
        minWidth: 200,
        scale: 1,
        scaleMobile: 1,
        color: 0x0a3d4d,
        shininess: 32,
        waveHeight: 16,
        waveSpeed: calm ? 0.15 : 0.65,
        zoom: 0.85,
      })
    } catch (e) {
      console.warn('Vanta waves failed to start (WebGL unavailable?)', e)
    }
    return () => effect?.destroy()
  }, [])

  return <div ref={ref} className="fixed inset-0 -z-10 bg-tide" aria-hidden="true" />
}
