import { useEffect, useRef } from 'react';

/** Sparse square snow, paused for hidden tabs and reduced-motion preferences. */
export default function PixelSnow({ enabled }: { enabled: boolean }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas || !enabled) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
    let width = 0, height = 0, frame = 0, previous = 0;
    const flakes = Array.from({ length: 68 }, () => ({ x: Math.random(), y: Math.random(), size: Math.random() < .8 ? 2 : 3, speed: 8 + Math.random() * 18, opacity: .12 + Math.random() * .33, drift: Math.random() * 5 - 2.5 }));
    function resize() {
      width = window.innerWidth; height = window.innerHeight;
      const scale = Math.min(window.devicePixelRatio || 1, 2);
      canvas!.width = width * scale; canvas!.height = height * scale;
      ctx!.setTransform(scale, 0, 0, scale, 0, 0);
    }
    function draw(time: number) {
      if (time - previous >= 32) {
        const delta = previous ? Math.min((time - previous) / 1000, .08) : 0;
        previous = time;
        ctx!.clearRect(0, 0, width, height);
        flakes.slice(0, width < 600 ? 28 : 68).forEach(flake => {
          flake.y += flake.speed * delta / height;
          flake.x += flake.drift * delta / width;
          if (flake.y > 1) { flake.y = -.01; flake.x = Math.random(); }
          ctx!.fillStyle = `rgba(235,237,231,${flake.opacity})`;
          ctx!.fillRect(Math.round(flake.x * width), Math.round(flake.y * height), flake.size, flake.size);
        });
      }
      frame = requestAnimationFrame(draw);
    }
    function sync() {
      cancelAnimationFrame(frame);
      previous = 0;
      const paused = reduced.matches || document.hidden;
      canvas!.dataset.motion = paused ? 'paused' : 'running';
      if (paused) ctx!.clearRect(0, 0, width, height);
      else frame = requestAnimationFrame(draw);
    }
    resize(); sync();
    window.addEventListener('resize', resize);
    document.addEventListener('visibilitychange', sync);
    reduced.addEventListener('change', sync);
    return () => { cancelAnimationFrame(frame); window.removeEventListener('resize', resize); document.removeEventListener('visibilitychange', sync); reduced.removeEventListener('change', sync); };
  }, [enabled]);
  return enabled ? <canvas ref={ref} className="pixel-snow" aria-hidden="true" /> : null;
}
