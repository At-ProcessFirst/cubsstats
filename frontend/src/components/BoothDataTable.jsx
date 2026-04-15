export default function BoothDataTable({ data }) {
  if (!data || !data.length) return null

  const columns = Object.keys(data[0])

  return (
    <div className="overflow-x-auto mt-3 rounded-lg border border-white-8">
      <table className="w-full text-left">
        <thead>
          <tr className="bg-surface-hover">
            {columns.map(col => (
              <th key={col}
                className="text-[9px] uppercase text-text-secondary px-3 py-2 whitespace-nowrap"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                {col.replace(/_/g, ' ')}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr key={i} className="border-t border-white-8 hover:bg-surface-hover transition-colors">
              {columns.map(col => (
                <td key={col}
                  className="text-[11px] text-text-primary px-3 py-1.5 whitespace-nowrap"
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                  {formatCell(row[col])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function formatCell(value) {
  if (value == null) return '—'
  if (typeof value === 'number') {
    if (Number.isInteger(value)) return value.toString()
    return value.toFixed(3).replace(/\.?0+$/, '') || '0'
  }
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  return String(value)
}
