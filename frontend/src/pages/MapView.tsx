import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { Map, Layers } from 'lucide-react'
import { getRegistry, heatmapUrl } from '../api'
import { STATUS_COLOUR } from '../types'
import { Failed, Wrap } from '../components/Shell'

export default function MapView() {
  const navigate = useNavigate()
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

    // Leaflet measures the container once, at construction. This one is inside
    // a flex column that has not been laid out yet, so it measures zero width -
    // and a map zero pixels wide can only ever fit the whole world into it,
    // whatever bounds it is given. Re-measure once laid out, and again whenever
    // the container changes size.
    // The risk grid is a backdrop, so it gets its own pane below the overlay
    // pane the markers live in. Sharing a pane, the grid loaded last and drew
    // on top, and every click on a hazard opened the grid cell's popup instead.
    map.current.createPane('riskgrid')
    const gridPane = map.current.getPane('riskgrid')
    if (gridPane) gridPane.style.zIndex = '390'

    const resize = () => map.current?.invalidateSize()
    requestAnimationFrame(resize)
    const observer = new ResizeObserver(resize)
    observer.observe(el.current)

    fetch(heatmapUrl)
      .then((r) => (r.ok ? r.json() : null))
      .then((gj) => {
        if (!gj?.features?.length || !map.current) return
        L.geoJSON(gj, {
          pane: 'riskgrid',
          style: (f) => ({
            color: '#f97316',
            weight: 1,
            fillColor: '#f97316',
            fillOpacity: 0.06 + 0.22 * (f?.properties?.intensity ?? 0),
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
      observer.disconnect()
      map.current?.remove()
      map.current = null
    }
  }, [])

  useEffect(() => {
    if (!map.current || !hazards?.length) return
    const group = L.layerGroup().addTo(map.current)
    hazards.forEach((h) => {
      const body = document.createElement('div')
      body.style.cssText = 'font-family: sans-serif; font-size: 12px; color: #e2e8f0; min-width: 190px;'
      body.innerHTML =
        `<div style="color: #00f2ff; font-weight: bold; font-family: monospace; font-size: 13px;">${h.hazard_id}</div>` +
        `<div style="margin-top: 4px;"><b>Class:</b> ${h.class}</div>` +
        `<div><b>Status:</b> ${h.status}</div>` +
        `<div><b>Sightings:</b> ${h.times_seen}×</div>` +
        `<div><b>Last sighted:</b> ${h.last_seen}</div>` +
        `<div style="margin-top: 4px; font-family: monospace; color: #94a3b8;">` +
        `${h.lat.toFixed(6)}, ${h.lon.toFixed(6)}</div>`

      // A link would reload the whole app and lose the router, so this drives
      // the router directly.
      const more = document.createElement('button')
      more.type = 'button'
      more.textContent = 'Full info →'
      more.style.cssText =
        'margin-top: 8px; width: 100%; cursor: pointer; border-radius: 6px;' +
        'border: 1px solid rgba(0,242,255,0.35); background: rgba(0,242,255,0.10);' +
        'color: #00f2ff; font-family: monospace; font-size: 11px; padding: 5px 8px;'
      more.addEventListener('click', () => navigate(`/hazards/${h.hazard_id}`))
      body.appendChild(more)

      L.circleMarker([h.lat, h.lon], {
        radius: 6 + Math.min(h.times_seen, 4) * 2,
        color: '#070d1a',
        weight: 2,
        fillColor: STATUS_COLOUR[h.status] ?? '#94a3b8',
        fillOpacity: 0.9,
      })
        .bindPopup(body)
        .addTo(group)
    })

    // fitBounds divides by the container width, so on a container Leaflet still
    // measures as zero it can only fit the whole world - which is what this map
    // did: right centre, zoom 0. Wait for a real width before fitting.
    //
    // Everything from one survey line sits within metres of everything else, so
    // the bounds are nearly a point; cap the zoom instead of slamming to the
    // maximum, where there are no tiles.
    const bounds = L.latLngBounds(hazards.map((h) => [h.lat, h.lon] as [number, number]))
    let frame = 0
    const fit = () => {
      if (!map.current || !bounds.isValid()) return
      map.current.invalidateSize()
      if (map.current.getSize().x === 0) {
        frame = requestAnimationFrame(fit)
        return
      }
      map.current.fitBounds(bounds.pad(0.4), { maxZoom: 18 })
    }
    fit()
    return () => {
      cancelAnimationFrame(frame)
      group.remove()
    }
  }, [hazards, navigate])

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
            {hazards?.length
              ? `${hazards.length} hazard${hazards.length === 1 ? '' : 's'} in registry`
              : 'Registry empty'}
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
