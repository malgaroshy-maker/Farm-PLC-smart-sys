import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest';
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import WeatherWidget from './WeatherWidget';
import WeatherOverlay from './WeatherOverlay';
import { parseWindDirection, conditionIcon, isRaining, selectForecastForFarmTime } from './weatherUtils';
import type { WeatherData, WeatherForecast } from '../../lib/api';

describe('Weather on Farm Map (Milestone F)', () => {
  let container: HTMLDivElement;
  let root: ReturnType<typeof createRoot>;
  const origGetContext = HTMLCanvasElement.prototype.getContext;

  beforeEach(() => {
    HTMLCanvasElement.prototype.getContext = vi.fn().mockReturnValue(null);
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    localStorage.clear();
  });

  afterEach(() => {
    HTMLCanvasElement.prototype.getContext = origGetContext;
    act(() => {
      root.unmount();
    });
    container.remove();
  });

  describe('WeatherWidget', () => {
    const mockWeather: WeatherData = {
      timestamp: '2026-11-20T12:00:00Z',
      temperature_c: 24.5,
      humidity_pct: 45,
      wind_speed_kmh: 12,
      wind_direction: '180',
      wind_direction_10m: 180,
      precipitation_probability_pct: 25,
      condition: 'clear',
      description: 'Clear sky',
      description_ar: 'سماء صافية',
    };

    it('WeatherWidget renders temperature from mock data', () => {
      act(() => {
        root.render(React.createElement(WeatherWidget, { forecast: mockWeather, lang: 'en' }));
      });

      expect(container.textContent).toContain('24.5°C');
      expect(container.textContent).toContain('12 km/h');
      expect(container.textContent).toContain('25%');
    });

    it('WeatherWidget shows no-data text when forecast is null', () => {
      act(() => {
        root.render(React.createElement(WeatherWidget, { forecast: null, lang: 'ar' }));
      });
      expect(container.textContent).toContain('لا توجد توقعات لهذا الوقت');

      act(() => {
        root.render(React.createElement(WeatherWidget, { forecast: null, lang: 'en' }));
      });
      expect(container.textContent).toContain('No forecast for this time');
    });

    it('Wind arrow rotates to correct angle (check the SVG transform string)', () => {
      act(() => {
        root.render(React.createElement(WeatherWidget, { forecast: mockWeather }));
      });

      const arrow = container.querySelector('[data-testid="wind-arrow"]');
      expect(arrow).not.toBeNull();
      const attrTransform = arrow?.getAttribute('transform') ?? '';
      const styleTransform = (arrow as HTMLElement)?.style?.transform ?? '';
      const hasRotate180 = attrTransform.includes('rotate(180') || styleTransform.includes('180deg');
      expect(hasRotate180).toBe(true);
    });

    it('Follows meteorological "from" convention (arrow points toward source)', () => {
      // 180° indicates wind FROM south (blowing north) -> arrow points south (180°)
      expect(parseWindDirection('180', 180)).toBe(180);
      expect(parseWindDirection('S')).toBe(180);
      expect(parseWindDirection('0', 0)).toBe(0);
      expect(parseWindDirection('N')).toBe(0);
      expect(parseWindDirection('90')).toBe(90);
      expect(parseWindDirection('E')).toBe(90);
      expect(parseWindDirection('270')).toBe(270);
      expect(parseWindDirection('W')).toBe(270);
    });

    it('Maps condition icons appropriately', () => {
      expect(conditionIcon('Rainy')).toBe('🌧️');
      expect(conditionIcon('light rain')).toBe('🌧️');
      expect(conditionIcon('thunderstorm')).toBe('⛈️');
      expect(conditionIcon('cloudy')).toBe('☁️');
      expect(conditionIcon('clear sky')).toBe('🌤️');
    });

    it('Renders next 6 hourly items in tooltip when provided', () => {
      const hourly: WeatherData[] = [
        {
          timestamp: '2026-11-20T13:00:00Z',
          temperature_c: 25,
          humidity_pct: 42,
          wind_speed_kmh: 11,
          precipitation_probability_pct: 10,
          condition: 'clear',
          description: 'Clear',
          description_ar: 'صافٍ',
        },
        {
          timestamp: '2026-11-20T14:00:00Z',
          temperature_c: 26,
          humidity_pct: 40,
          wind_speed_kmh: 13,
          precipitation_probability_pct: 0,
          condition: 'clear',
          description: 'Clear',
          description_ar: 'صافٍ',
        },
      ];

      act(() => {
        root.render(React.createElement(WeatherWidget, { forecast: mockWeather, hourly, lang: 'en' }));
      });

      // Click or hover to open tooltip
      const widget = container.querySelector('[data-testid="weather-widget"]');
      expect(widget).not.toBeNull();
      act(() => {
        widget?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      });

      const tooltip = container.querySelector('[data-testid="weather-hourly-tooltip"]');
      expect(tooltip).not.toBeNull();
      expect(tooltip?.textContent).toContain('25°');
      expect(tooltip?.textContent).toContain('26°');
    });
  });

  describe('WeatherOverlay', () => {
    it('WeatherOverlay activates rain animation when precipitation_probability_pct = 70', () => {
      const rainyForecast: WeatherData = {
        timestamp: '2026-11-20T12:00:00Z',
        temperature_c: 19,
        humidity_pct: 80,
        wind_speed_kmh: 18,
        precipitation_probability_pct: 70,
        condition: 'overcast',
        description: 'Overcast',
        description_ar: 'غائم كلياً',
      };

      const rafSpy = vi.spyOn(window, 'requestAnimationFrame');

      act(() => {
        root.render(React.createElement(WeatherOverlay, { forecast: rainyForecast, reduceMotion: false }));
      });

      const overlay = container.querySelector('[data-testid="weather-overlay"]');
      expect(overlay).not.toBeNull();
      expect(overlay?.getAttribute('data-animating')).toBe('true');
      expect(overlay?.getAttribute('data-raining')).toBe('true');
      expect(isRaining(rainyForecast)).toBe(true);
      expect(rafSpy).toHaveBeenCalled();

      rafSpy.mockRestore();
    });

    it('WeatherOverlay does NOT animate when precipitation_probability_pct = 30', () => {
      const dryForecast: WeatherData = {
        timestamp: '2026-11-20T12:00:00Z',
        temperature_c: 27,
        humidity_pct: 35,
        wind_speed_kmh: 10,
        precipitation_probability_pct: 30,
        condition: 'clear',
        description: 'Clear',
        description_ar: 'صافٍ',
      };

      const rafSpy = vi.spyOn(window, 'requestAnimationFrame');

      act(() => {
        root.render(React.createElement(WeatherOverlay, { forecast: dryForecast, reduceMotion: false }));
      });

      const overlay = container.querySelector('[data-testid="weather-overlay"]');
      expect(overlay).not.toBeNull();
      expect(overlay?.getAttribute('data-animating')).toBe('false');
      expect(overlay?.getAttribute('data-raining')).toBe('false');
      expect(isRaining(dryForecast)).toBe(false);
      expect(rafSpy).not.toHaveBeenCalled();

      rafSpy.mockRestore();
    });

    it('Activates rain animation when condition string includes rain', () => {
      const rainByCondition: WeatherData = {
        timestamp: '2026-11-20T12:00:00Z',
        temperature_c: 20,
        humidity_pct: 75,
        wind_speed_kmh: 15,
        precipitation_probability_pct: 20,
        condition: 'light_rain',
        description: 'Light rain',
        description_ar: 'مطر خفيف',
      };

      expect(isRaining(rainByCondition)).toBe(true);
    });

    it('Disables animation and renders static tint when reduceMotion is true', () => {
      const rainyForecast: WeatherData = {
        timestamp: '2026-11-20T12:00:00Z',
        temperature_c: 19,
        humidity_pct: 80,
        wind_speed_kmh: 18,
        precipitation_probability_pct: 80,
        condition: 'rain',
        description: 'Rain',
        description_ar: 'مطر',
      };

      const rafSpy = vi.spyOn(window, 'requestAnimationFrame');

      act(() => {
        root.render(React.createElement(WeatherOverlay, { forecast: rainyForecast, reduceMotion: true }));
      });

      const overlay = container.querySelector('[data-testid="weather-overlay"]');
      expect(overlay?.getAttribute('data-animating')).toBe('false');
      expect(overlay?.getAttribute('data-raining')).toBe('true');
      expect(rafSpy).not.toHaveBeenCalled();

      rafSpy.mockRestore();
    });

    it('Enables cloud tint attribute when cloud_cover_pct >= 70', () => {
      const cloudyForecast: WeatherData = {
        timestamp: '2026-11-20T12:00:00Z',
        temperature_c: 22,
        humidity_pct: 60,
        wind_speed_kmh: 10,
        precipitation_probability_pct: 20,
        cloud_cover_pct: 75,
        condition: 'cloudy',
        description: 'Cloudy',
        description_ar: 'غائم',
      };

      act(() => {
        root.render(React.createElement(WeatherOverlay, { forecast: cloudyForecast, reduceMotion: false }));
      });

      const overlay = container.querySelector('[data-testid="weather-overlay"]');
      expect(overlay?.getAttribute('data-cloud')).toBe('true');
    });
  });

  describe('Collapsible Legend Configuration', () => {
    it('Saves collapsed state to localStorage farm.legendOpen', () => {
      localStorage.setItem('farm.legendOpen', 'false');
      expect(localStorage.getItem('farm.legendOpen')).toBe('false');

      localStorage.setItem('farm.legendOpen', 'true');
      expect(localStorage.getItem('farm.legendOpen')).toBe('true');
    });
  });

  describe('Farm Time Hourly Forecast Alignment', () => {
    const mockHourly: WeatherData[] = Array.from({ length: 48 }, (_, i) => {
      const h = String(i % 24).padStart(2, '0');
      const d = i < 24 ? '2026-11-20' : '2026-11-21';
      return {
        timestamp: `${d}T${h}:00`,
        temperature_c: 18 + (i % 10),
        humidity_pct: 50,
        wind_speed_kmh: 10 + (i % 5),
        precipitation_probability_pct: i === 15 ? 70 : 10,
        condition: i === 15 ? 'rain' : 'clear',
        description: 'Clear',
        description_ar: 'صافٍ',
      };
    });

    const mockForecast: WeatherForecast = {
      current: mockHourly[12],
      hourly: mockHourly,
      daily: [],
      last_fetched_at: '2026-11-20T12:00:00Z',
      source: 'test',
      cached: false,
    };

    it('selects forecast in range at 1x real time', () => {
      const res = selectForecastForFarmTime(mockForecast, '2026-11-20T12:00:00+02:00');
      expect(res.inRange).toBe(true);
      expect(res.current?.timestamp).toBe('2026-11-20T12:00');
      expect(res.next6).toHaveLength(6);
      expect(res.next6[0].timestamp).toBe('2026-11-20T13:00');
    });

    it('selects forecast for farm hour mid-forecast', () => {
      const res = selectForecastForFarmTime(mockForecast, '2026-11-21T08:00:00+02:00');
      expect(res.inRange).toBe(true);
      expect(res.current?.timestamp).toBe('2026-11-21T08:00');
      expect(res.next6).toHaveLength(6);
      expect(res.next6[0].timestamp).toBe('2026-11-21T09:00');
    });

    it('returns no data when farm time is beyond forecast range (e.g. 14 Dec)', () => {
      const res = selectForecastForFarmTime(mockForecast, '2026-12-14T10:00:00+02:00');
      expect(res.inRange).toBe(false);
      expect(res.current).toBeNull();
      expect(res.next6).toHaveLength(0);
    });

    it('WeatherWidget displays "لا توجد توقعات لهذا الوقت" when out of range (null forecast)', () => {
      act(() => {
        root.render(React.createElement(WeatherWidget, { forecast: null, lang: 'ar' }));
      });
      expect(container.textContent).toContain('لا توجد توقعات لهذا الوقت');
    });
  });
});
