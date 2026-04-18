import BoothDataTable from './BoothDataTable'

export default function BoothMessage({ role, content, data, sources }) {
  const isUser = role === 'user'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div
        className={`max-w-[85%] md:max-w-[75%] rounded-2xl px-4 py-3 ${
          isUser
            ? 'bg-cubs-blue text-white rounded-br-sm'
            : 'border border-white-8 text-text-primary rounded-bl-sm'
        }`}
        style={!isUser ? {
          background: 'linear-gradient(135deg, #141B2D, #1A2340)',
          borderLeft: '3px solid #60A5FA',
          boxShadow: '0 2px 8px rgba(0,0,0,0.3)',
        } : undefined}
      >
        {/* Icon for booth messages */}
        {!isUser && (
          <div className="flex items-center gap-1.5 mb-1.5">
            <span className="text-sm">🎙️</span>
            <span className="text-[9px] uppercase tracking-widest text-text-secondary font-semibold"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}>
              THE BOOTH
            </span>
          </div>
        )}

        {/* Message text */}
        <p className={`text-[13px] leading-relaxed ${isUser ? 'text-white' : 'text-text-primary'}`}>
          {content}
        </p>

        {/* Data table if present */}
        {!isUser && data && <BoothDataTable data={data} />}

        {/* Source attribution */}
        {!isUser && sources && sources.length > 0 && (
          <div className="mt-2 pt-2 border-t border-white-8">
            <span className="text-[8px] text-text-secondary"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}>
              Sources: {sources.join(', ')}
            </span>
          </div>
        )}
      </div>
    </div>
  )
}
