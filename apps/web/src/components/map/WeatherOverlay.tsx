/**
 * WeatherOverlay — Canvas overlay positioned to cover the farm map.
 * pointer-events: none, z-index between TreeCanvas and SVG overlay.
 *
 * Visual effects:
 * 1. Rain animation: active when condition contains 'rain' OR precipitation_probability_pct >= 60.
 *    Draws short diagonal cyan/white drops with requestAnimationFrame.
 * 2. Reduced motion: static semi-transparent blue tint instead of animation.
 * 3. Cloud tint: subtle gray rect (opacity 0.08) when cloud_cover_pct >= 70.
 * 4. Transparent when neither rain nor high cloud.
 */
import { memo, useEffect, useRef } from 'react';
import type { WeatherData } from '../../lib/api';
import { FARM } from '@algaroshy/map-model';
import { isRaining } from './weatherUtils';

const [, , VW, VH] = FARM.viewBox;
const CANVAS_W = typeof window !== 'undefined' && window.innerWidth >= 1200 ? 3600 : 2400;
const S = CANVAS_W / VW;
const CANVAS_H = Math.round(VH * S);

interface RainDrop {
  x: number;
  y: number;
  speed: number;
  len: number;
}

export const WeatherOverlay = memo(function WeatherOverlay({
  forecast,
  reduceMotion = false,
}: {
  forecast: WeatherData | null;
  reduceMotion?: boolean;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const dropsRef = useRef<RainDrop[]>([]);
  const forecastRef = useRef(forecast);
  forecastRef.current = forecast;

  const raining = isRaining(forecast);
  const cloudCover = forecast?.cloud_cover_pct ?? 0;
  const highCloud = cloudCover >= 70;
  const shouldAnimate = raining && !reduceMotion;

  // Initialize particles once
  useEffect(() => {
    const drops: RainDrop[] = [];
    const count = 180;
    for (let i = 0; i < count; i++) {
      drops.push({
        x: Math.random() * CANVAS_W,
        y: Math.random() * CANVAS_H,
        speed: (8 + Math.random() * 7) * S,
        len: (12 + Math.random() * 8) * S,
      });
    }
    dropsRef.current = drops;
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    let ctx: CanvasRenderingContext2D | null = null;
    try {
      ctx = canvas.getContext ? (canvas.getContext('2d') as CanvasRenderingContext2D | null) : null;
    } catch {
      ctx = null;
    }

    if (!shouldAnimate) {
      // Static draw when not animating
      if (ctx) {
        ctx.clearRect(0, 0, CANVAS_W, CANVAS_H);

        // Cloud tint: semi-transparent gray rect (opacity 0.08)
        if (highCloud) {
          ctx.fillStyle = 'rgba(20, 25, 30, 0.08)';
          ctx.fillRect(0, 0, CANVAS_W, CANVAS_H);
        }

        // Reduced motion rain: static semi-transparent blue tint
        if (raining && reduceMotion) {
          ctx.fillStyle = 'rgba(0, 180, 255, 0.12)';
          ctx.fillRect(0, 0, CANVAS_W, CANVAS_H);
        }
      }
      return;
    }

    // Animation loop for rain drops
    let rafId = 0;

    const frame = () => {
      if (ctx) {
        ctx.clearRect(0, 0, CANVAS_W, CANVAS_H);

        // Cloud tint underneath rain if cloud >= 70%
        if (highCloud) {
          ctx.fillStyle = 'rgba(20, 25, 30, 0.08)';
          ctx.fillRect(0, 0, CANVAS_W, CANVAS_H);
        }

        // Draw raindrops: short diagonal lines with cyan/white tint
        ctx.strokeStyle = 'rgba(200, 240, 255, 0.7)';
        ctx.lineWidth = 1.6 * S;
        ctx.beginPath();

        const drops = dropsRef.current;
        const windDrift = 0.28;

        for (let i = 0; i < drops.length; i++) {
          const d = drops[i];
          ctx.moveTo(d.x, d.y);
          ctx.lineTo(d.x - d.len * windDrift, d.y - d.len);

          d.y += d.speed;
          d.x += d.speed * windDrift;

          if (d.y > CANVAS_H) {
            d.y = -d.len;
            d.x = Math.random() * (CANVAS_W + 200) - 100;
          }
          if (d.x > CANVAS_W + 100) {
            d.x = -50;
          }
        }
        ctx.stroke();
      }

      rafId = requestAnimationFrame(frame);
    };

    rafId = requestAnimationFrame(frame);

    return () => {
      cancelAnimationFrame(rafId);
      if (ctx) {
        ctx.clearRect(0, 0, CANVAS_W, CANVAS_H);
      }
    };
  }, [shouldAnimate, raining, highCloud, reduceMotion]);

  return (
    <canvas
      ref={canvasRef}
      width={CANVAS_W}
      height={CANVAS_H}
      data-testid="weather-overlay"
      data-animating={shouldAnimate ? 'true' : 'false'}
      data-raining={raining ? 'true' : 'false'}
      data-cloud={highCloud ? 'true' : 'false'}
      className="absolute inset-0 w-full h-full pointer-events-none z-10"
    />
  );
});

export default WeatherOverlay;
