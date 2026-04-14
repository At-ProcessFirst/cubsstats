import { useState, Component } from 'react'
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

function HamburgerIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
    </svg>
  )
}

function CloseIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  )
}

class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="bg-surface rounded-lg border border-white-8 p-8 text-center m-4">
          <p className="text-lg text-text-primary mb-2">Something went wrong</p>
          <p className="text-sm text-text-secondary">{this.state.error?.message}</p>
          <button onClick={() => this.setState({ hasError: false })}
            className="mt-4 px-4 py-2 bg-cubs-blue text-white rounded text-sm">
            Try again
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

export default function App() {
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <div className="min-h-screen bg-navy">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-surface border-b border-white-8">
        <div className="max-w-[1440px] mx-auto px-3 md:px-4 h-14 flex items-center gap-3 md:gap-4">
          <CubsLogo />
          <span
            className="text-text-primary font-bold text-base md:text-lg tracking-widest"
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            CUBSSTATS
          </span>

          {/* Desktop nav */}
          <nav className="ml-8 hidden md:flex items-center gap-1">
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

          {/* Mobile hamburger */}
          <button
            className="ml-auto md:hidden text-text-secondary hover:text-text-primary p-1"
            onClick={() => setMenuOpen(!menuOpen)}
          >
            {menuOpen ? <CloseIcon /> : <HamburgerIcon />}
          </button>
        </div>

        {/* Mobile dropdown nav */}
        {menuOpen && (
          <nav className="md:hidden border-t border-white-8 bg-surface px-3 pb-3 pt-2 flex flex-col gap-1">
            {NAV_ITEMS.map(({ to, label }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                onClick={() => setMenuOpen(false)}
                className={({ isActive }) =>
                  `px-3 py-2 rounded text-sm font-medium transition-colors ${
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
        )}
      </header>

      {/* Page content */}
      <main className="max-w-[1440px] mx-auto px-3 md:px-4 py-3 md:py-4">
        <ErrorBoundary>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/pitching" element={<PitchingLab />} />
            <Route path="/hitting" element={<HittingLab />} />
            <Route path="/defense" element={<DefenseLab />} />
            <Route path="/predictions" element={<Predictions />} />
            <Route path="/divergences" element={<Divergences />} />
            <Route path="/editorial" element={<Editorial />} />
          </Routes>
        </ErrorBoundary>
      </main>

      {/* Footer */}
      <footer className="border-t border-white-8 mt-8 py-4 text-center">
        <span
          className="text-[11px] text-text-secondary"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          Built by{' '}
          <a
            href="https://at-processfirst.com"
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent-blue hover:underline"
          >
            At Process
          </a>
          {' '}| at-processfirst.com
        </span>
      </footer>
    </div>
  )
}
