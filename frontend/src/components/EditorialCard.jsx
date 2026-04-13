import { useNavigate } from 'react-router-dom'

/**
 * Editorial insight card — analysis blurb with optional stat reference.
 * Clickable — navigates to the Editorial page.
 */
export default function EditorialCard({
  title,
  body,
  category,
  timestamp,
  accentColor = '#60A5FA',
}) {
  const navigate = useNavigate()

  return (
    <div
      onClick={() => navigate('/editorial')}
      className="bg-surface rounded-lg border border-white-8 p-4 hover:bg-surface-hover transition-colors cursor-pointer"
      style={{ borderLeftWidth: 3, borderLeftColor: accentColor }}
    >
      {/* Header */}
      <div className="flex items-center gap-2 mb-2">
        {category && (
          <span
            className="text-[8px] uppercase tracking-widest font-semibold px-1.5 py-0.5 rounded"
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              color: accentColor,
              backgroundColor: `${accentColor}18`,
            }}
          >
            {category}
          </span>
        )}
        {timestamp && (
          <span className="text-[9px] text-text-secondary ml-auto">
            {timestamp}
          </span>
        )}
      </div>

      {/* Title */}
      <h4 className="text-sm font-semibold text-text-primary mb-1">
        {title}
      </h4>

      {/* Body */}
      <p className="text-[12px] text-text-secondary leading-relaxed">
        {body}
      </p>
    </div>
  )
}
