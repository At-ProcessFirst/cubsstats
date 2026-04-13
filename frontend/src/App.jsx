import { Routes, Route, NavLink } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import PitchingLab from './pages/PitchingLab'
import HittingLab from './pages/HittingLab'
import DefenseLab from './pages/DefenseLab'
import Predictions from './pages/Predictions'
import Divergences from './pages/Divergences'
import Editorial from './pages/Editorial'

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard' },
  { to: '/pitching', label: 'Pitching Lab' },
  { to: '/hitting', label: 'Hitting Lab' },
  { to: '/defense', label: 'Defense' },
  { to: '/predictions', label: 'Predictions' },
  { to: '/divergences', label: 'Divergences' },
  { to: '/editorial', label: 'Editorial' },
]

function CubsLogo() {
  return (
    <div
      className="flex-shrink-0 rounded-full overflow-hidden flex items-center justify-center"
      style={{
        width: 44,
        height: 44,
        backgroundColor: '#0E3386',
        border: '3px solid #CC3433',
      }}
    >
      <img
        src="https://www.mlbstatic.com/team-logos/112.svg"
        alt="Chicago Cubs"
        width={34}
        height={34}
        onError={(e) => {
          e.target.style.display = 'none'
          e.target.parentElement.innerHTML = '<span style="color:white;font-weight:bold;font-size:22px">C</span>'
        }}
      />
    </div>
  )
}

export default function App() {
  return (
    <div className="min-h-screen bg-navy">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-surface border-b border-white-8">
        <div className="max-w-[1440px] mx-auto px-4 h-14 flex items-center gap-4">
          <CubsLogo />
          <span
            className="text-text-primary font-bold text-lg tracking-widest"
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            CUBSSTATS
          </span>

          <nav className="ml-8 flex items-center gap-1">
            {NAV_ITEMS.map(({ to, label }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                className={({ isActive }) =>
                  `px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-cubs-blue text-white'
                      : 'text-text-secondary hover:text-text-primary hover:bg-surface-hover'
                  }`
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>

      {/* Page content */}
      <main className="max-w-[1440px] mx-auto px-4 py-4">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/pitching" element={<PitchingLab />} />
          <Route path="/hitting" element={<HittingLab />} />
          <Route path="/defense" element={<DefenseLab />} />
          <Route path="/predictions" element={<Predictions />} />
          <Route path="/divergences" element={<Divergences />} />
          <Route path="/editorial" element={<Editorial />} />
        </Routes>
      </main>
    </div>
  )
}
