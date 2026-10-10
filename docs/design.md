# 🌿 Grassday Design System

The Grassday UI uses a calm, earthy "living nature" aesthetic based on Liquid Morphism and Glassmorphism.

## Design Principle
**"The screen is the shortest part of the experience."**
Everything on the home screen is accessible above the fold without scrolling. Complex settings are relegated to the sidebar, and the UI is designed to invite you *outside*, not keep you scrolling inside.

## Tokens

The system automatically switches between "Daylight" (Light Mode) and "Dusk" (Dark Mode) based on the user's OS preference using `@media (prefers-color-scheme: dark)`.

### Light Mode (Daylight)
| Token | Hex | Role | WCAG Contrast |
|-------|-----|------|---------------|
| `--bg-color` | `#FDFAF6` | Morning mist (Base background) | - |
| `--text-main` | `#2C2C2C` | Bark (Primary text) | 12.8:1 (AAA) |
| `--text-muted` | `#6B6560` | Dry earth (Secondary text) | 4.8:1 (AA) |
| `--accent-moss` | `#4A7C59` | Moss (Primary actions, blobs) | 5.3:1 (AA) |
| `--accent-amber` | `#D4A843` | Amber (Warm blobs, negative delta) | - |

### Dark Mode (Dusk)
| Token | Hex | Role | WCAG Contrast |
|-------|-----|------|---------------|
| `--bg-color` | `#1A1C1A` | Deep forest (Base background) | - |
| `--text-main` | `#F0EBE3` | Pale moon (Primary text) | 12.7:1 (AAA) |
| `--text-muted` | `#A09C96` | Muted stone (Secondary text) | 5.2:1 (AA) |
| `--accent-moss` | `#6B9E78` | Illuminated fern (Actions, blobs) | 5.0:1 (AA) |
| `--accent-amber` | `#E5C07B` | Golden hour (Warm blobs) | - |

---

## Components

The UI components are managed exclusively in `theme.py` as pure HTML/CSS strings that are injected into Streamlit.

### 1. Liquid Morphism Background Blobs
- `blob-1` (Moss) and `blob-2` (Amber) drift continuously.
- Animated using `border-radius` morphing and `transform` translations.
- Heavily blurred via `filter: blur(40px)`.
- Respects `@media (prefers-reduced-motion: reduce)` by disabling animations and lowering opacity.

### 2. Glassmorphism Cards
- Background: `rgba(253, 250, 246, 0.6)`
- Filter: `backdrop-filter: blur(16px)`
- In order to ensure WCAG AA contrast over bright underlying blobs, cards utilize an inner `box-shadow` trick (`inset 0 0 0 2000px var(--scrim)`) which effectively layers a semi-transparent solid color beneath the text.

### 3. Hero Component (`render_hero`)
- Minimalist typographic layout. Time in `ui-serif` display font.
- Conic-gradient confidence ring.

### 4. Horizontal Week View (`render_week_strip`)
- Touch-friendly, horizontally scrolling strip (`overflow-x: auto; -webkit-overflow-scrolling: touch;`).
- Heatmap gradient bars based on the predicted score.

### 5. Plant Progress (`render_plant_progress`)
- A subtle CSS-driven progress bar that tracks the "Cold Start" requirement of 10 logged outings.

---

## How to Tweak

All CSS resides in `theme.py::get_core_css()`. Streamlit specific classes (e.g., `.stDeployButton`) are hidden here natively. 
If modifying components:
1. Edit the Python string in `theme.py`.
2. Reload the Streamlit app.
3. Ensure you test in both light and dark modes, as the variables dynamically shift.
