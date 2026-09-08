import { useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { Map, Layers } from 'lucide-react'
import { getRegistry, heatmapUrl } from '../api'
import { STATUS_COLOUR } from '../types'
import { Failed, Wrap } from '../components/Shell'

export default function MapView() {
  const el = useRef<HTMLDivElement>(null)
  const map = useRef<L.Map | null>(null)
  const { data: hazards, error } = useQuery({ queryKey: ['registry'], queryFn: getRegistry })

  useEffect(() => {
    if (!el.current || map.current) return
    map.current = L.map(el.current).setView([12.9231, 74.6012], 13)
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 19,
      className: 'dark-map-tiles',
    }).addTo(map.current)

    fetch(heatmapUrl)
      .then((r) => (r.ok ? r.json() : null))
      .then((gj) => {
        if (!gj?.features?.length || !map.current) return
        L.geoJSON(gj, {
          style: (f) => ({
            color: '#f97316',
            weight: 1,
            fillColor: '#f97316',
            fillOpacity: 0.1 + 0.45 * (f?.properties?.intensity ?? 0),
          }),
          onEachFeature: (f, layer) =>
            layer.bindPopup(
              `<div style="font-family: sans-serif; font-size: 12px; color: #e2e8f0;">` +
              `<strong style="color: #00f2ff;">Risk Grid Cell</strong><br/>` +
              `Hazards: <b>${f.properties.hazards}</b><br/>` +
              `Accumulated Risk: <b>${f.properties.risk_sum}</b><br/>` +
              `Confirmed: <b>${f.properties.persistent}</b>` +
              `</div>`,
            ),
        }).addTo(map.current)
      })
      .catch(() => undefined)

    return () => {
      map.current?.remove()
      map.current = null
    }
  }, [])

  useEffect(() => {
    if (!map.current || !hazards?.length) return
    const group = L.layerGroup().addTo(map.current)
    hazards.forEach((h) => {
      L.circleMarker([h.lat, h.lon], {
        radius: 6 + Math.min(h.times_seen, 4) * 2,
        color: '#070d1a',
        weight: 2,
        fillColor: STATUS_COLOUR[h.status] ?? '#94a3b8',
        fillOpacity: 0.9,
      })
        .bindPopup(
          `<div style="font-family: sans-serif; font-size: 12px; color: #e2e8f0;">` +
          `<div style="color: #00f2ff; font-weight: bold; font-family: monospace;">${h.hazard_id}</div>` +
          `<div><b>Class:</b> ${h.class}</div>` +
          `<div><b>Status:</b> ${h.status}</div>` +
          `<div><b>Sightings:</b> ${h.times_seen}×</div>` +
          `<div><b>Last Sighted:</b> ${h.last_seen}</div>` +
          `</div>`,
        )
        .addTo(group)
    })
    map.current.fitBounds(
      L.latLngBounds(hazards.map((h) => [h.lat, h.lon] as [number, number])).pad(0.2),
    )
    return () => {
      group.remove()
    }
  }, [hazards])

  return (
    <Wrap wide>
      {/* Header Info */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-line pb-5">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-wreck/30 bg-wreck/10 px-3 py-0.5 text-xs font-mono text-wreck mb-1">
            <Map className="h-3.5 w-3.5 text-wreck" />
            GIS SPATIAL RISK MAP
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            Bathymetric Debris Map
          </h1>
          <p className="mt-1 text-sm text-muted">
            Geospatial visualization of target hazards and accumulated sonar risk grid intensity.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 rounded-xl border border-line bg-panel/70 px-3 py-1.5 text-xs font-mono text-slate-300">
            <span className="h-2 w-2 rounded-full bg-wreck animate-pulse" />
            Sector 4B Bathymetry
          </div>
        </div>
      </div>

      {error && <div className="mt-4"><Failed error={error} /></div>}

      {/* Map Container Card */}
      <div className="mt-6 relative overflow-hidden rounded-2xl border border-line bg-panel/60 p-2 backdrop-blur-sm shadow-2xl">
        <div ref={el} className="h-[620px] w-full rounded-xl" />

        {/* Floating Map Legend Overlay */}
        <div className="absolute bottom-6 left-6 z-[1000] rounded-xl border border-line bg-marine-950/90 p-4 text-xs backdrop-blur-md max-w-xs shadow-xl">
          <div className="font-mono font-bold text-slate-200 uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <Layers className="h-3.5 w-3.5 text-wreck" /> Map Legend
          </div>
          <div className="space-y-2 font-mono text-[11px]">
            <div className="flex items-center gap-2">
              <span className="h-3 w-3 rounded-full bg-wreck inline-block border border-black" />
              <span className="text-slate-300">Present / Confirmed Hazard</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="h-3 w-3 rounded-full bg-amber-400 inline-block border border-black" />
              <span className="text-slate-300">Unconfirmed Single Sight</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="h-3 w-3 rounded-full bg-emerald-400 inline-block border border-black" />
              <span className="text-slate-300">Recovered Debris</span>
            </div>
            <div className="flex items-center gap-2 border-t border-line/60 pt-2">
              <span className="h-3 w-3 rounded bg-orange-500/40 border border-orange-500 inline-block" />
              <span className="text-muted">Sonar Accumulation Grid</span>
            </div>
          </div>
        </div>
      </div>
    </Wrap>
  )
}
