---
version: "alpha"
name: "Quantum Core Diagnostics"
description: "Quantum Core Dashboard Section is designed for demonstrating application workflows and interface hierarchy. Key features include clear information density, modular panels, and interface rhythm. It is suitable for product showcases, admin panels, and analytics experiences."
colors:
  primary: "#1F2937"
  secondary: "#60A5FA"
  tertiary: "#4B5563"
  neutral: "#FFFFFF"
  background: "#1F2937"
  surface: "#60A5FA"
  text-primary: "#FFFFFF"
  text-secondary: "#6B7280"
  border: "#FFFFFF"
  accent: "#1F2937"
typography:
  display-lg:
    fontFamily: "Inter"
    fontSize: "88px"
    fontWeight: 200
    lineHeight: "88px"
    letterSpacing: "-0.025em"
  body-md:
    fontFamily: "JetBrains Mono"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: "18px"
  label-md:
    fontFamily: "Inter"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: "24px"
rounded:
  md: "16px"
spacing:
  base: "4px"
  sm: "1px"
  md: "1.5px"
  lg: "2px"
  xl: "4px"
  gap: "6px"
  card-padding: "8px"
  section-padding: "28px"
components:
  button-primary:
    textColor: "{colors.neutral}"
    typography: "{typography.label-md}"
    rounded: "{rounded.md}"
    padding: "12px"
  card:
    rounded: "{rounded.md}"
    padding: "16px"
---

## Overview

- **Composition cues:**
  - Layout: Grid
  - Content Width: Full Bleed
  - Framing: Open
  - Grid: Strong

## Colors

The color system uses light mode with #1F2937 as the main accent and #FFFFFF as the neutral foundation.

- **Primary (#1F2937):** Main accent and emphasis color.
- **Secondary (#60A5FA):** Supporting accent for secondary emphasis.
- **Tertiary (#4B5563):** Reserved accent for supporting contrast moments.
- **Neutral (#FFFFFF):** Neutral foundation for backgrounds, surfaces, and supporting chrome.

- **Usage:** Background: #1F2937; Surface: #60A5FA; Text Primary: #FFFFFF; Text Secondary: #6B7280; Border: #FFFFFF; Accent: #1F2937

## Typography

Typography pairs Inter for display hierarchy with JetBrains Mono for supporting content and interface copy.

- **Display (`display-lg`):** Inter, 88px, weight 200, line-height 88px, letter-spacing -0.025em.
- **Body (`body-md`):** JetBrains Mono, 12px, weight 400, line-height 18px.
- **Labels (`label-md`):** Inter, 16px, weight 400, line-height 24px.

## Layout

Layout follows a grid composition with reusable spacing tokens. Preserve the grid, full bleed structural frame before changing ornament or component styling. Use 4px as the base rhythm and let larger gaps step up from that cadence instead of introducing unrelated spacing values.

Treat the page as a grid / full bleed composition, and keep that framing stable when adding or remixing sections.

- **Layout type:** Grid
- **Content width:** Full Bleed
- **Base unit:** 4px
- **Scale:** 1px, 1.5px, 2px, 4px, 6px, 8px, 10px, 12px
- **Section padding:** 28px
- **Card padding:** 8px, 12px, 14px, 16px
- **Gaps:** 6px, 8px, 10px, 12px

## Elevation & Depth

Depth is communicated through elevated, border contrast, and reusable shadow or blur treatments. Keep those recipes consistent across hero panels, cards, and controls so the page reads as one material system.

Surfaces should read as elevated first, with borders, shadows, and blur only reinforcing that material choice.

- **Surface style:** Elevated
- **Borders:** 0.8px #FFFFFF; 0.8px #60A5FA
- **Shadows:** rgba(0, 0, 0, 0.8) 0px 1px 1px 0px inset; rgb(96, 165, 250) 0px 0px 6px 0px; rgba(255, 255, 255, 0.04) 0px 1px 0px 0px inset

### Techniques
- **Gradient border shell:** Use a thin gradient border shell around the main card. Wrap the surface in an outer shell with 1.5px padding and a 39px radius. Drive the shell with linear-gradient(rgba(255, 255, 255, 0.22), rgba(255, 255, 255, 0.02) 40%, rgba(0, 0, 0, 0.4)) so the edge reads like premium depth instead of a flat stroke. Keep the actual stroke understated so the gradient shell remains the hero edge treatment. Inset the real content surface inside the wrapper with a slightly smaller radius so the gradient only appears as a hairline frame.

## Shapes

Shapes rely on a tight radius system anchored by 8px and scaled across cards, buttons, and supporting surfaces. Icon geometry should stay compatible with that soft-to-controlled silhouette.

Use the radius family intentionally: larger surfaces can open up, but controls and badges should stay within the same rounded DNA instead of inventing sharper or pill-only exceptions.

- **Corner radii:** 8px, 12px, 16px, 23px, 24px, 9999px
- **Icon treatment:** Linear
- **Icon sets:** Solar

## Components

Anchor interactions to the detected button styles. Reuse the existing card surface recipe for content blocks.

### Buttons
- **Primary:** text #FFFFFF, radius 16px, padding 12px, border 0px solid rgb(229, 231, 235).

### Cards and Surfaces
- **Card surface:** border 0px solid rgb(229, 231, 235), radius 16px, padding 16px, shadow rgba(255, 255, 255, 0.06) 0px 1px 0px 0px inset, rgba(0, 0, 0, 0.4) 0px 4px 12px 0px.

### Iconography
- **Treatment:** Linear.
- **Sets:** Solar.

## Do's and Don'ts

Use these constraints to keep future generations aligned with the current system instead of drifting into adjacent styles.

### Do
- Do use the primary palette as the main accent for emphasis and action states.
- Do keep spacing aligned to the detected 4px rhythm.
- Do reuse the Elevated surface treatment consistently across cards and controls.
- Do keep corner radii within the detected 8px, 12px, 16px, 23px, 24px, 9999px family.

### Don't
- Don't introduce extra accent colors outside the core palette roles unless the page needs a new semantic state.
- Don't mix unrelated shadow or blur recipes that break the current depth system.
- Don't exceed the detected moderate motion intensity without a deliberate reason.

## Motion

Motion feels controlled and interface-led across text, layout, and section transitions. Timing clusters around 150ms and 500ms. Easing favors ease and cubic-bezier(0.4. Scroll choreography uses GSAP ScrollTrigger for section reveals and pacing.

**Motion Level:** moderate

**Durations:** 150ms, 500ms, 700ms, 2000ms, 200ms

**Easings:** ease, cubic-bezier(0.4, 0, 0.2, 1)

**Scroll Patterns:** gsap-scrolltrigger

## WebGL

Reconstruct the graphics as a centered hero scene using webgl, renderer, alpha, antialias, dpr clamp. The effect should read as retro-futurist, technical, and meditative: fluid wave field with green on black and sparse spacing. Build it from shader field so the effect reads clearly. Animate it as slow breathing pulse. Interaction can react to the pointer, but only as a subtle drift. Preserve reduced motion + dom fallback.

**Id:** webgl

**Label:** WebGL

**Stack:** ThreeJS, WebGL

**Insights:**
  - **Scene:**
    - **Value:** Centered hero scene
  - **Effect:**
    - **Value:** Fluid wave field
  - **Primitives:**
    - **Value:** Shader field
  - **Motion:**
    - **Value:** Slow breathing pulse
  - **Interaction:**
    - **Value:** Pointer-reactive drift
  - **Render:**
    - **Value:** WebGL, Renderer, alpha, antialias, DPR clamp

**Techniques:** Breathing pulse, Pointer parallax, DOM fallback

**Code Evidence:**
  - **HTML reference:**
    - **Language:** html
    - **Snippet:**
      ```html
      <!-- Screen -->
      <div class="rounded-[18px] relative overflow-hidden flex-1 min-h-[420px]" style="background:#020410; box-shadow:inset 0 0 60px rgba(0,0,0,0.9), inset 0 2px 4px rgba(0,0,0,0.9), 0 0 0 1px rgba(0,0,0,0.6);">
        <canvas id="grid-canvas" class="absolute inset-0 w-full h-full"></canvas>

        <div class="absolute inset-0 pointer-events-none" style="background:linear-gradient(180deg, rgba(96,165,250,0.04) 0%,…
      ```
  - **JS reference:**
    - **Language:** html
    - **Snippet:**
      ```html
      <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
      ```

## ThreeJS

Reconstruct the Three.js layer as a centered hero scene with layered spatial depth that feels retro-futurist, volumetric, and technical. Use alpha, antialias, dpr clamp renderer settings, perspective, ~60deg fov, custom buffer geometry geometry, pointsmaterial materials, and ambient + key + rim lighting. Motion should read as slow orbital drift, with reduced motion + non-3d fallback.

**Id:** threejs

**Label:** ThreeJS

**Stack:** ThreeJS, WebGL

**Insights:**
  - **Scene:**
    - **Value:** Centered hero scene with layered spatial depth
  - **Render:**
    - **Value:** alpha, antialias, DPR clamp
  - **Camera:**
    - **Value:** Perspective, ~60deg FOV
  - **Lighting:**
    - **Value:** ambient + key + rim
  - **Materials:**
    - **Value:** PointsMaterial
  - **Geometry:**
    - **Value:** custom buffer geometry
  - **Motion:**
    - **Value:** Slow orbital drift

**Techniques:** Particle depth, Timeline beats, alpha, antialias, DPR clamp, Reduced motion + non-3D fallback

**Code Evidence:**
  - **HTML reference:**
    - **Language:** html
    - **Snippet:**
      ```html
      <!-- Screen -->
      <div class="rounded-[18px] relative overflow-hidden flex-1 min-h-[420px]" style="background:#020410; box-shadow:inset 0 0 60px rgba(0,0,0,0.9), inset 0 2px 4px rgba(0,0,0,0.9), 0 0 0 1px rgba(0,0,0,0.6);">
        <canvas id="grid-canvas" class="absolute inset-0 w-full h-full"></canvas>

        <div class="absolute inset-0 pointer-events-none" style="background:linear-gradient(180deg, rgba(96,165,250,0.04) 0%,…
      ```
  - **JS reference:**
    - **Language:** html
    - **Snippet:**
      ```html
      <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
      ```
