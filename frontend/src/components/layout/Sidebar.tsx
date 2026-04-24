import type { ReactElement } from 'react'
import { Link, useLocation } from 'react-router-dom'

const navItems: Array<{
  label: string
  path: string
  icon: ReactElement
}> = [
  {
    label: 'Projects',
    path: '/projects',
    icon: (
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor">
        <rect x="2.5" y="2.5" width="11" height="11" />
        <line x1="2.5" y1="6" x2="13.5" y2="6" />
      </svg>
    ),
  },
  {
    label: 'Datasets',
    path: '/datasets',
    icon: (
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor">
        <ellipse cx="8" cy="4" rx="4.5" ry="2" />
        <path d="M3.5 4v6c0 1.1 2 2 4.5 2s4.5-.9 4.5-2V4" />
        <path d="M3.5 7c0 1.1 2 2 4.5 2s4.5-.9 4.5-2" />
      </svg>
    ),
  },
  {
    label: 'Controls',
    path: '/controls',
    icon: (
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor">
        <circle cx="8" cy="8" r="5.5" />
        <path d="M8 4v4l3 2" />
      </svg>
    ),
  },
]

interface SidebarProps {
  collapsed: boolean
  onToggle: () => void
}

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const location = useLocation()

  return (
    <aside className={`sidebar ${collapsed ? 'collapsed' : ''}`}>
      <button
        type="button"
        className="sidebar-hit-area"
        onClick={onToggle}
        aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        tabIndex={-1}
      />
      <div className="sidebar-logo-area">
        <Link to="/" className="sidebar-logo">
          <div className="sidebar-logo-glyph">
            <svg viewBox="0 0 22 22" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path
                d="M3 19 L11 3 L19 19"
                stroke="var(--copper)"
                strokeWidth="1.5"
                fill="none"
                strokeLinejoin="bevel"
              />
              <line x1="7" y1="11" x2="15" y2="11" stroke="var(--copper-dim)" strokeWidth="1" />
            </svg>
          </div>
          <span className="sidebar-logo-text">Artha</span>
        </Link>
      </div>

      <button type="button" className="sidebar-user">
        <span className="sidebar-user-avatar"><span>v</span></span>
        <span className="sidebar-user-name">local</span>
        <span className="sidebar-user-chevron">▾</span>
      </button>

      <div className="sidebar-divider" />

      <nav className="sidebar-nav">
        <div className="sidebar-section">
          <div className="sidebar-section-label">Workspace</div>
          {navItems.map((item) => {
            const isActive = location.pathname === item.path || location.pathname.startsWith(`${item.path}/`)

            return (
              <Link
                key={item.label}
                to={item.path}
                className={`sidebar-link ${isActive ? 'active' : ''}`}
                title={collapsed ? item.label : undefined}
              >
                <span className="sidebar-link-icon">{item.icon}</span>
                <span className="sidebar-link-label">{item.label}</span>
              </Link>
            )
          })}
        </div>
      </nav>
    </aside>
  )
}
