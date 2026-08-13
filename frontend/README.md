# PITAYA Frontend

React SPA for **PITAYA: Plant Illness Tracking and Automated Yield Analysis System**.

## Stack

- **React 18** + **Vite**
- **Tailwind CSS** (Agri-Tech theme: deep green, leaf green, earth brown, soft yellow)
- **Recharts** (Line, Bar, Pie – tooltips, legends, animations)
- **Framer Motion** (landing animations, page transitions)
- **React Router** (Landing → Dashboard)

## Run

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000

## Build

```bash
npm run build
```

Output in `dist/`. Can be served by Django static or any static host.

### Android APK download

Set `VITE_ANDROID_APK_URL` to the public URL of the final APK before building.
The landing page's **Download Android APK** button uses this value. Upload the
APK to a file host or release service; do not add large generated APK files to
the repository or Railway deployment.

## Structure

- `/` – **Landing**: full-screen hero, PITAYA title, subtitle, “Enter Dashboard” CTA, Framer Motion + floating icons
- `/app/dashboard` – **Dashboard**: KPI cards, Monthly Yield (line), Disease Occurrence (bar), Disease Distribution (pie), Recent alerts with severity
- `/app/identify` – **Disease Detection**: upload / camera capture, animated image preview, result card (disease name, confidence %, severity badge with icons/color)
- `/app/yield` – **Yield Prediction**: drone image preview panel, yield chart (line + bar with dataset toggle), historical yield comparison table, animated chart transitions

## Data & API

- Mock data: `src/data/mockDashboard.js`
- API layer: `src/api/dashboard.js` – replace `fetchDashboard()` with `fetch('/api/dashboard/')` when Django REST (or similar) is ready.
- Charts use dynamic data and animate on load; tooltips and legends are enabled.

## Responsiveness & Accessibility

- **Mobile-first**: Sidebar collapses off-canvas on small screens; hamburger opens it; overlay closes on tap.
- **Touch-friendly**: Buttons use `min-h-[44px]` and `touch-manipulation`; tap highlight removed.
- **Labels**: Page titles and chart/table labels use readable font sizes; header title updates by route.

## Theme (Tailwind)

- **pitaya**: deep, primary, leaf, light, mint, pale, bg
- **earth**: dark, brown, tan, light
- **accent**: yellow, yellow-soft
- **Fonts**: Inter (body), Poppins (display)
