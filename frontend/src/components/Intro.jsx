import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import BIRDS from 'vanta/dist/vanta.birds.min'

/**
 * Entry animation: Vanta birds over the wordmark.
 * Parent owns the 3-second timer; `leaving` fades this layer out (the waves mount underneath).
 */
export default function Intro({ leaving }) {
  const ref = useRef(null)

  useEffect(() => {
    let effect
    try {
      effect = BIRDS({
        el: ref.current,
        THREE,
        mouseControls: true,
        touchControls: true,
        gyroControls: false,
        minHeight: 200,
        minWidth: 200,
        scale: 1,
        scaleMobile: 1,
        backgroundColor: 0x06222c,
        color1: 0xf0b95a,
        color2: 0x7fd3c8,
        colorMode: 'lerpGradient',
        birdSize: 1.5,
        wingSpan: 26,
        speedLimit: 5,
        separation: 38,
        alignment: 30,
        cohesion: 24,
        quantity: 4,
      })
    } catch (e) {
      console.warn('Vanta birds failed to start (WebGL unavailable?)', e)
    }
    return () => effect?.destroy()
  }, [])

  return (
    <div
      className={`fixed inset-0 z-50 transition-opacity duration-700 ${leaving ? 'opacity-0 pointer-events-none' : 'opacity-100'}`}
      aria-hidden={leaving}
    >
      <div ref={ref} className="absolute inset-0 bg-abyss" />
      <div className="relative z-10 flex h-full flex-col items-center justify-center px-6 text-center">
        <h1 className="rise font-display text-6xl font-extrabold tracking-tight text-foam sm:text-8xl">
          DocBot
        </h1>
        <p className="rise-late mt-4 max-w-md font-read text-xl italic text-mist sm:text-2xl">
          Ask your documents. Get answers with page numbers.
        </p>
      </div>
    </div>
  )
}
