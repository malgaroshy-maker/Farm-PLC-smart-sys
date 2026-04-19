import { useState } from 'react';
import { TransformWrapper, TransformComponent } from 'react-zoom-pan-pinch';
import { ZoomIn, ZoomOut, Maximize, Navigation } from 'lucide-react';
import type { ZoneLiveState } from '../hooks/useFarmConnector';

/**
 * Metadata for each zone.  The keys MUST match the backend zone IDs
 * (e.g. `zone_rumman_1`) so that the live telemetry look-up in the
 * render loop actually finds a matching ZoneLiveState object.
 *
 * x / y  are CSS-percent positions **relative to the SVG container**
 * and have been tuned to sit on top of the corresponding polygons
 * drawn inside the embedded raster image (1600 × 900 viewport).
 *
 * The SVG background image is the original Algaroshy Farm sketch.
 * Zone positions are estimated from the visible field outlines and
 * Arabic labels such as رمان 1‒6, زيتون, عنب, etc.
 */
const ZONES_METADATA: Record<string, { name: string; x: number; y: number }> = {
  /* ── Pomegranate 1‒6 (رمان) ───────────────────────────── */
  'zone_rumman_1': { name: 'رمان 1',        x: 42, y: 82 },
  'zone_rumman_2': { name: 'رمان 2',        x: 52, y: 75 },
  'zone_rumman_3': { name: 'رمان 3',        x: 38, y: 68 },
  'zone_rumman_4': { name: 'رمان 4',        x: 56, y: 88 },
  'zone_rumman_5': { name: 'رمان 5',        x: 68, y: 72 },
  'zone_rumman_6': { name: 'رمان 6',        x: 58, y: 55 },

  /* ── Special pomegranate zones ─────────────────────────── */
  'zone_rumman_ummahat':{ name: 'رمان امهات',  x: 48, y: 90 },
  'zone_rumman_jadeed': { name: 'رمان جديد',   x: 32, y: 60 },

  /* ── Olives (زيتون) ────────────────────────────────────── */
  'zone_zaytoun':       { name: 'زيتون',       x: 35, y: 78 },
  'zone_zaytoun_2':     { name: 'زيتون 2',     x: 52, y: 93 },

  /* ── Grapes (عنب) ──────────────────────────────────────── */
  'zone_enab':          { name: 'عنب',         x: 43, y: 48 },

  /* ── Mixed fruit (خوخ + مشمش + كوبة) ───────────────────── */
  'zone_fruit_mix':     { name: 'خوخ+مشمش+كوبة', x: 30, y: 38 },
};

export default function LiveMap({
  onZoneSelect,
  zoneStates = []
}: {
  onZoneSelect: (id: string) => void,
  zoneStates?: ZoneLiveState[]
}) {
  const [activeZone, setActiveZone] = useState<string | null>(null);

  const getHotspotColor = (state: string) => {
    switch (state) {
      case 'running': return 'bg-[#00e5ff]/20 border-[#00e5ff] text-[#c3f5ff] shadow-[0_0_15px_rgba(0,229,255,0.4)]';
      case 'fault': return 'bg-[#ffb4ab]/20 border-[#ffb4ab] text-[#ffdad6] shadow-[0_0_15px_rgba(255,180,171,0.4)]';
      default: return 'bg-[#1c1b1b]/80 border-[#3b494c]/50 text-[#bac9cc]';
    }
  };

  const getIndicatorColor = (state: string) => {
    switch (state) {
      case 'running': return 'bg-[#00e5ff] shadow-[0_0_8px_#00e5ff]';
      case 'fault': return 'bg-[#ffb4ab] shadow-[0_0_8px_#ffb4ab] animate-pulse';
      default: return 'bg-[#849396]';
    }
  };

  return (
    <div className="w-full h-full min-h-[600px] bg-[#0e0e0e] border border-[#3b494c] rounded-xl overflow-hidden relative font-sans shadow-2xl">
      
      {/* HUD Header overlay on top of map */}
      <div className="absolute top-4 left-4 z-20 pointer-events-none">
        <div className="bg-[#1c1b1b]/80 backdrop-blur-md border border-[#353534] rounded-lg p-3 shadow-lg flex items-center gap-3">
          <Navigation size={20} className="text-[#00e5ff]" /> 
          <div>
            <h2 className="text-sm font-bold text-[#e5e2e1] tracking-wider font-mono">TACTICAL MAP</h2>
            <p className="text-[10px] text-[#bac9cc] uppercase font-mono">Topology Overview</p>
          </div>
        </div>
      </div>

      <div className="absolute top-4 right-4 z-20 flex gap-4 text-xs font-mono bg-[#1c1b1b]/80 backdrop-blur-md border border-[#353534] p-3 rounded-lg shadow-lg pointer-events-none">
        <span className="flex items-center gap-2 text-[#00e5ff]"><div className="w-2 h-2 rounded-full bg-[#00e5ff] shadow-[0_0_5px_#00e5ff]" /> RUNNING</span>
        <span className="flex items-center gap-2 text-[#ffb4ab]"><div className="w-2 h-2 rounded-full bg-[#ffb4ab] shadow-[0_0_5px_#ffb4ab]" /> FAULT</span>
        <span className="flex items-center gap-2 text-[#849396]"><div className="w-2 h-2 rounded-full bg-[#849396]" /> IDLE</span>
      </div>

      <TransformWrapper
        initialScale={1}
        minScale={0.5}
        maxScale={4}
        centerOnInit
        wheel={{ step: 0.1 }}
      >
        {({ zoomIn, zoomOut, resetTransform }) => (
          <>
            {/* Map Controls */}
            <div className="absolute bottom-4 right-4 z-20 flex flex-col gap-2">
              <button onClick={() => zoomIn()} className="bg-[#201f1f]/80 backdrop-blur border border-[#353534] p-2 rounded text-[#e5e2e1] hover:bg-[#353534] transition-colors"><ZoomIn size={18} /></button>
              <button onClick={() => zoomOut()} className="bg-[#201f1f]/80 backdrop-blur border border-[#353534] p-2 rounded text-[#e5e2e1] hover:bg-[#353534] transition-colors"><ZoomOut size={18} /></button>
              <button onClick={() => resetTransform()} className="bg-[#201f1f]/80 backdrop-blur border border-[#353534] p-2 rounded text-[#e5e2e1] hover:bg-[#353534] transition-colors"><Maximize size={18} /></button>
            </div>

            {/* Interactive Canvas */}
            <TransformComponent wrapperClass="w-full h-full cursor-grab active:cursor-grabbing" contentClass="w-full h-full relative">
              <div 
                className="relative origin-center"
                style={{ width: '1600px', height: '900px' }}
              >
                {/* Embedded Map Layout */}
                <img 
                  src="/farm_layout.svg" 
                  alt="Farm Layout Strategy" 
                  className="absolute inset-0 w-full h-full object-contain opacity-70 pointer-events-none filter sepia-[0.3] hue-rotate-[180deg] saturate-[1.5] brightness-75"
                />

                {/* Overlaid Zone Hotspots */}
                {Object.entries(ZONES_METADATA).map(([zoneId, meta]) => {
                  const stateNode = zoneStates.find(z => z.zone_id === zoneId);
                  const isActive = activeZone === zoneId;
                  const uiState = stateNode?.state === 'running' ? 'running' : stateNode?.health === 'fault' ? 'fault' : 'idle';
                  const moisture = stateNode?.moisture_pct != null ? stateNode.moisture_pct.toFixed(1) : '--';

                  return (
                    <div
                      key={zoneId}
                      onClick={(e) => {
                        e.stopPropagation();
                        setActiveZone(zoneId);
                        onZoneSelect(zoneId);
                      }}
                      className={`absolute -translate-x-1/2 -translate-y-1/2 cursor-pointer transition-all duration-300 ease-out z-10 
                        backdrop-blur-md rounded-lg border flex flex-col items-center justify-center
                        hover:scale-110 active:scale-95
                        ${isActive ? 'ring-2 ring-[#e5e2e1] scale-110 z-20' : ''}
                        ${getHotspotColor(uiState)}
                      `}
                      style={{
                        left: `${meta.x}%`,
                        top: `${meta.y}%`,
                        width: '100px',
                        height: '62px',
                      }}
                    >
                      <div className="absolute top-1 right-1 w-2 h-2 rounded-full">
                        <div className={`w-full h-full rounded-full ${getIndicatorColor(uiState)}`} />
                      </div>
                      
                      <span className="text-[9px] font-mono opacity-70 uppercase leading-none mb-0.5">{zoneId.replace(/_/g, ' ')}</span>
                      <span className="text-[11px] font-bold leading-none mb-0.5" dir="rtl">{meta.name}</span>
                      <div className="flex items-center gap-1">
                         <span className="text-[9px] font-mono opacity-70">{moisture}% moist</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </TransformComponent>
          </>
        )}
      </TransformWrapper>
    </div>
  );
}
