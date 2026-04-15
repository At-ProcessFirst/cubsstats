import { useState, useRef, useEffect } from 'react'
import { useApi } from '../hooks/useApi'
import BoothMessage from '../components/BoothMessage'
import BoothSuggestions from '../components/BoothSuggestions'

const API_BASE = (import.meta.env.VITE_API_URL || '') + '/api'

export default function TheBooth() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [conversationId, setConversationId] = useState(null)
  const chatEndRef = useRef(null)
  const inputRef = useRef(null)

  const { data: suggestionsData } = useApi('/booth/suggestions')
  const suggestions = suggestionsData?.suggestions || []

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = async (question) => {
    if (!question.trim() || loading) return

    const userMsg = { role: 'user', content: question }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const res = await fetch(`${API_BASE}/booth/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: question.trim(),
          conversation_id: conversationId,
        }),
      })

      if (res.status === 429) {
        setMessages(prev => [...prev, {
          role: 'booth',
          content: 'Rate limit reached — max 20 questions per hour. Take a seventh-inning stretch and come back.',
        }])
        return
      }

      const data = await res.json()
      setConversationId(data.conversation_id)

      setMessages(prev => [...prev, {
        role: 'booth',
        content: data.answer || 'No answer available.',
        data: data.data,
        sources: data.sources,
      }])
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'booth',
        content: 'The Booth is temporarily unavailable. Check back in a moment.',
      }])
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    sendMessage(input)
  }

  return (
    <div className="flex flex-col h-[calc(100vh-120px)] max-w-[900px] mx-auto">
      {/* Header */}
      <div className="text-center py-4 md:py-6">
        <div className="flex items-center justify-center gap-2 mb-2">
          <span className="text-2xl">🎙️</span>
          <h1 className="text-xl md:text-2xl font-bold text-text-primary tracking-wide"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}>
            THE BOOTH
          </h1>
        </div>
        <p className="text-sm text-text-secondary">
          Ask anything about Cubs stats — powered by live data from 2015-present
        </p>
      </div>

      {/* Chat area */}
      <div className="flex-1 overflow-y-auto px-2 md:px-4 pb-4">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-6">
            <div className="w-20 h-20 rounded-full bg-surface border border-white-8 flex items-center justify-center">
              <span className="text-4xl">🎙️</span>
            </div>
            <div className="text-center">
              <p className="text-text-secondary text-sm mb-1">
                Step up to the mic
              </p>
              <p className="text-text-secondary text-[11px]">
                Ask about Cubs stats, player performance, team records, or matchup analysis
              </p>
            </div>
            <BoothSuggestions suggestions={suggestions} onSelect={sendMessage} />
          </div>
        ) : (
          <>
            {messages.map((msg, i) => (
              <BoothMessage
                key={i}
                role={msg.role}
                content={msg.content}
                data={msg.data}
                sources={msg.sources}
              />
            ))}

            {loading && (
              <div className="flex justify-start mb-4">
                <div className="bg-surface border border-white-8 rounded-2xl rounded-bl-sm px-4 py-3">
                  <div className="flex items-center gap-1.5">
                    <span className="text-sm">🎙️</span>
                    <div className="flex gap-1">
                      <span className="w-1.5 h-1.5 bg-text-secondary rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                      <span className="w-1.5 h-1.5 bg-text-secondary rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                      <span className="w-1.5 h-1.5 bg-text-secondary rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                    </div>
                  </div>
                </div>
              </div>
            )}

            <div ref={chatEndRef} />

            {/* Show suggestions after answers */}
            {!loading && messages.length > 0 && messages[messages.length - 1].role !== 'user' && (
              <div className="mt-4">
                <BoothSuggestions suggestions={suggestions} onSelect={sendMessage} />
              </div>
            )}
          </>
        )}
      </div>

      {/* Input bar */}
      <form onSubmit={handleSubmit}
        className="border-t border-white-8 bg-surface px-3 md:px-4 py-3 flex gap-2">
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about Cubs stats..."
          maxLength={500}
          disabled={loading}
          className="flex-1 bg-navy border border-white-8 rounded-full px-4 py-2.5
                     text-sm text-text-primary placeholder-text-secondary
                     focus:outline-none focus:border-cubs-blue transition-colors"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="w-10 h-10 rounded-full bg-cubs-blue text-white flex items-center justify-center
                     hover:brightness-110 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
        >
          🎙️
        </button>
      </form>
    </div>
  )
}
