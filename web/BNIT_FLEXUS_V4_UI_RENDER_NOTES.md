# BNIT-FLEXUS v4: toolbar UI and rendering pass (10 Nov 2026)

Changes made to `index.html` (town page). `industrial-zone.html` untouched.

## UI
- Left panel replaced by a top toolbar: Places, Layers, Weather, Time, FLEXUS, View as, Events, Plan, Display. One flyout open at a time (`FLY.open/close/toggle`), Esc closes. All original element IDs kept, so the existing JS wiring is unchanged.
- Toolbar right: camera HUD (ALT above ground, RANGE to target, HDG, DETAIL = Blocks/Mid/Full, FPS), date/weather chip, compass.
- Counts moved to a bottom telemetry bar; place card and lodchip sit above it.
- Weather flyout: 7 presets as icon tiles, Real weather toggle, then Effects sliders (cloud, wind, rain, snow, fog), Lightning and Wet surfaces toggles, "Back to preset". Sliders write `ENV.fx` overrides; `curW()` merges preset → Met Éireann obs → fx. Choosing a preset clears overrides.
- Display flyout: shadows, cloud layer, reflections (env map), particles, distant hills, resolution (auto/high/low), theme.

## Rendering
- Sky shader: sun disc + corona, horizon haze band, stars at night (`skyU`).
- PMREM environment baked from the sky (`rebuildEnv`, throttled to ~3 Hz when the light changes): water, glass, PV and metal reflect it.
- Water: two scrolling procedural normal maps via `onBeforeCompile`, dielectric Fresnel reflection.
- Clouds: one instanced billboard draw (`cloudMat` ShaderMaterial) with a soft puff texture, lit top / shaded underside, 64 clouds at 520–800 m.
- Terrain: smooth shading + tiled grass/soil detail map (vertex colours lifted ×1.16 to compensate).
- Distant hills: `mountains` ring 1400–6800 m continuing `baseH()` outside the plane, ridge only to the north, tucked 4 m under the terrain where they overlap.
- Trees: 4-lump canopy (detail 1, merged vertices, smooth normals) with vertex-colour gradient; conifers as 3 stacked cones with gradient.
- Roads: ribbons now carry UVs; asphalt detail texture; roads/roofs/paving darken and go glossy with rain when "Wet surfaces" is on.
- Far-LOD blocks get a vertical shade (fake contact shadow).

## Loading / camera
- Clicking a building or EdgeWare beacon now flies the camera in (`openBuilding(..., true)`); offset scales with building footprint, so LOD2 and nearby LOD1 tiles load on arrival.
- `LOD.hint` pre-streams tiles around the fly destination for 5 s (set by `select()` and `flyTo()`).
- Auto resolution: render scale drops toward 0.55 when FPS < 24 and recovers when idle (> 50 FPS, no tile job, no fly).

## Verified
Headless Chromium (SwiftShader) renders with no console errors for: overview, harbour and town-centre zones, building click fly-in, rain, clear night, cloudy evening, plan grid on/off, FLEXUS ops room, role switch, 430 px mobile viewport with effects sliders.
