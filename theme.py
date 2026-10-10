"""theme.py - Grassday Design System.

Centralizes CSS variables, glassmorphism, liquid animations, and HTML components.
"""

from typing import Dict, Any, List

def get_core_css() -> str:
    """Returns the main CSS block to be injected into Streamlit."""
    return """
    <style>
        /* ── CSS Variables (Light/Dark via prefers-color-scheme) ── */
        :root {
            /* Light Theme (Daylight) */
            --bg-color: #FDFAF6; /* morning mist */
            --text-main: #2C2C2C; /* bark */
            --text-muted: #6B6560; /* dry earth */
            --accent-moss: #4A7C59;
            --accent-fern: #6B9E78;
            --accent-amber: #D4A843;
            --glass-bg: rgba(253, 250, 246, 0.6);
            --glass-border: rgba(255, 255, 255, 0.4);
            --glass-shadow: 0 8px 32px 0 rgba(74, 124, 89, 0.05);
            --scrim: rgba(253, 250, 246, 0.4);
            
            /* Typography */
            --font-display: ui-serif, Georgia, Cambria, "Times New Roman", Times, serif;
            --font-body: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }

        @media (prefers-color-scheme: dark) {
            :root {
                /* Dark Theme (Dusk) */
                --bg-color: #1A1C1A; /* deep forest */
                --text-main: #F0EBE3; /* pale moon */
                --text-muted: #A09C96;
                --accent-moss: #6B9E78;
                --accent-fern: #4A7C59;
                --accent-amber: #E5C07B;
                --glass-bg: rgba(44, 44, 44, 0.6);
                --glass-border: rgba(255, 255, 255, 0.05);
                --glass-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
                --scrim: rgba(26, 28, 26, 0.6);
            }
        }

        /* ── Base Reset & Typography ── */
        html, body, .stApp {
            font-family: var(--font-body);
            color: var(--text-main);
            background-color: var(--bg-color);
        }
        
        /* Hide Streamlit Chrome */
        header[data-testid="stHeader"], footer { visibility: hidden; }
        .stDeployButton { display: none; }
        
        /* Mobile-first main container padding */
        .block-container {
            padding: 2rem 1rem 5rem 1rem !important;
            max-width: 600px !important;
            margin: 0 auto;
        }

        /* ── Liquid Morphism (Background Blobs) ── */
        .blob-container {
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            overflow: hidden;
            z-index: -1;
            pointer-events: none;
            background: var(--bg-color);
        }
        
        .blob {
            position: absolute;
            filter: blur(40px);
            opacity: 0.4;
            animation: blob-drift 30s infinite alternate ease-in-out,
                       blob-morph 20s infinite alternate ease-in-out;
            will-change: transform, border-radius;
        }
        
        .blob-1 {
            top: -10%; left: -10%;
            width: 300px; height: 300px;
            background: var(--accent-moss);
            animation-delay: 0s;
        }
        
        .blob-2 {
            bottom: -20%; right: -10%;
            width: 400px; height: 400px;
            background: var(--accent-amber);
            animation-delay: -5s;
            animation-duration: 40s;
        }

        @keyframes blob-drift {
            0% { transform: translate(0, 0) scale(1); }
            100% { transform: translate(50px, 30px) scale(1.1); }
        }
        @keyframes blob-morph {
            0% { border-radius: 60% 40% 30% 70% / 60% 30% 70% 40%; }
            50% { border-radius: 30% 60% 70% 40% / 50% 60% 30% 60%; }
            100% { border-radius: 60% 40% 30% 70% / 60% 30% 70% 40%; }
        }

        /* ── Glassmorphism ── */
        .glass-card {
            background: var(--glass-bg);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid var(--glass-border);
            box-shadow: var(--glass-shadow);
            border-radius: 1.5rem;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            position: relative;
            overflow: hidden;
            /* Subscrim to ensure contrast over bright blobs */
            box-shadow: inset 0 0 0 2000px var(--scrim);
        }

        /* Fallback for no backdrop-filter */
        @supports not (backdrop-filter: blur(16px)) {
            .glass-card { background: var(--bg-color); }
        }

        /* ── Hero Component ── */
        .hero-time {
            font-family: var(--font-display);
            font-size: 3.5rem;
            font-weight: 500;
            line-height: 1.1;
            margin-bottom: 0.5rem;
            letter-spacing: -0.03em;
        }
        .hero-reason {
            font-size: 1.1rem;
            color: var(--text-muted);
            margin-bottom: 1rem;
        }

        /* Confidence Ring */
        .confidence-ring {
            width: 44px; height: 44px;
            border-radius: 50%;
            background: conic-gradient(var(--accent-moss) var(--conf-deg), transparent 0);
            display: inline-flex;
            align-items: center; justify-content: center;
            border: 2px solid var(--glass-border);
            margin-right: 0.75rem;
            vertical-align: middle;
        }
        .confidence-inner {
            width: 36px; height: 36px;
            background: var(--glass-bg);
            border-radius: 50%;
            display: flex; align-items: center; justify-content: center;
            font-size: 0.8rem; font-weight: 600;
        }

        /* ── Chips & Tags ── */
        .chip-container { display: flex; gap: 0.5rem; flex-wrap: wrap; margin-top: 1rem; }
        .chip {
            background: var(--scrim);
            border: 1px solid var(--glass-border);
            padding: 0.4rem 0.8rem;
            border-radius: 1rem;
            font-size: 0.85rem;
            color: var(--text-main);
            display: inline-flex; align-items: center; gap: 0.4rem;
        }
        .chip-pos { border-left: 3px solid var(--accent-moss); }
        .chip-neg { border-left: 3px solid var(--accent-amber); }

        /* ── Horizontal Week View ── */
        .week-strip {
            display: flex; gap: 0.75rem;
            overflow-x: auto;
            padding-bottom: 1rem;
            scrollbar-width: none;
            -webkit-overflow-scrolling: touch;
        }
        .week-strip::-webkit-scrollbar { display: none; }
        
        .day-tile {
            flex: 0 0 auto;
            width: 60px;
            padding: 0.75rem 0.5rem;
            text-align: center;
            border-radius: 1rem;
            background: var(--glass-bg);
            border: 1px solid var(--glass-border);
            cursor: pointer;
            transition: transform 0.2s;
            /* Subscrim for contrast */
            box-shadow: inset 0 0 0 2000px var(--scrim);
        }
        .day-tile:active { transform: scale(0.95); }
        .day-name { font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; margin-bottom: 0.25rem; }
        .day-score { font-weight: 600; font-size: 1rem; color: var(--text-main); }
        .day-heat { height: 4px; border-radius: 2px; margin-top: 0.5rem; background: var(--accent-moss); opacity: var(--heat-op); }

        /* ── Plant Progress Indicator ── */
        .plant-progress {
            font-size: 0.85rem; color: var(--text-muted);
            display: flex; align-items: center; gap: 0.5rem;
            margin-bottom: 1rem;
        }
        .plant-bar { flex-grow: 1; height: 6px; background: var(--scrim); border-radius: 3px; overflow: hidden; }
        .plant-fill { height: 100%; background: var(--accent-moss); width: var(--prog-width); transition: width 1s; }

        /* ── Screen Time Footer ── */
        .screen-time-footer {
            position: fixed; bottom: 0; left: 0; right: 0;
            padding: 0.75rem; text-align: center;
            background: var(--glass-bg);
            backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
            border-top: 1px solid var(--glass-border);
            font-size: 0.75rem; color: var(--text-muted);
            z-index: 100;
        }
        .screen-time-val { font-weight: 600; color: var(--text-main); }

        /* ── Reduced Motion ── */
        @media (prefers-reduced-motion: reduce) {
            .blob { animation: none !important; opacity: 0.2; }
            .day-tile, .plant-fill { transition: none !important; }
        }
    </style>
    
    <div class="blob-container">
        <div class="blob blob-1"></div>
        <div class="blob blob-2"></div>
    </div>
    """

def render_hero(time_str: str, reason: str, confidence: float, score: float, is_offline: bool = False) -> str:
    conf_deg = int(confidence * 360)
    offline_tag = '<div style="font-size:0.75rem; color:var(--text-muted); margin-top:1rem;">📴 Offline mode — showing cached forecast</div>' if is_offline else ""
    return (
        f'<div class="glass-card">'
        f'<div class="hero-time">{time_str}</div>'
        f'<div class="hero-reason">{reason}</div>'
        f'<div style="display: flex; align-items: center;">'
        f'<div class="confidence-ring" style="--conf-deg: {conf_deg}deg;" aria-label="Confidence {int(confidence*100)}%">'
        f'<div class="confidence-inner">{score}</div>'
        f'</div>'
        f'<span style="font-size: 0.85rem; color: var(--text-muted);">/5 Predicted Enjoyment</span>'
        f'</div>'
        f'{offline_tag}'
        f'</div>'
    )

def render_chips(drivers: List[Dict[str, Any]]) -> str:
    chips = []
    for d in drivers:
        cls = "chip-pos" if d.get("direction") == "positive" else "chip-neg"
        arrow = "↑" if d.get("direction") == "positive" else "↓"
        label = d.get("label", d.get("feature", ""))
        chips.append(f'<div class="chip {cls}"><span>{arrow}</span> {label}</div>')
    return f'<div class="chip-container">{"".join(chips)}</div>'

def render_week_strip(days: List[Dict[str, Any]]) -> str:
    tiles = []
    for d in days:
        heat_op = min(1.0, max(0.2, (float(d["score"]) - 1.0) / 4.0))
        tiles.append(
            f'<div class="day-tile">'
            f'<div class="day-name">{d["name"]}</div>'
            f'<div class="day-score">{d["score"]}</div>'
            f'<div class="day-heat" style="--heat-op: {heat_op};"></div>'
            f'</div>'
        )
    return f'<div class="week-strip">{"".join(tiles)}</div>'

def render_plant_progress(train_count: int) -> str:
    needed = max(0, 10 - train_count)
    if needed == 0:
        return '<div class="plant-progress">🌱 Personalization unlocked (10+ outings)</div>'
    
    pct = (train_count / 10.0) * 100
    msg = f"🌱 {needed} more outings until predictions get personal"
    return (
        f'<div class="plant-progress">'
        f'<span>{msg}</span>'
        f'<div class="plant-bar"><div class="plant-fill" style="--prog-width: {pct}%;"></div></div>'
        f'</div>'
    )

def render_footer(seconds: int) -> str:
    mins, secs = divmod(seconds, 60)
    val = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
    return (
        f'<div class="screen-time-footer">'
        f'Screen-time budget: <span class="screen-time-val">{val}</span>. The grass misses you.'
        f'</div>'
    )
