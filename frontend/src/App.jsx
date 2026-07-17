import { useEffect, useState } from 'react'
import './App.css'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

function App() {
  const [summary, setSummary] = useState(null)
  const [hotspots, setHotspots] = useState([])
  const [epsKm, setEpsKm] = useState(100)
  const [minSamples, setMinSamples] = useState(15)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')

  const fetchData = async () => {
    setIsLoading(true)
    setError('')

    try {
      const [summaryResponse, hotspotResponse] = await Promise.all([
        fetch(`${API_BASE_URL}/api/summary`),
        fetch(`${API_BASE_URL}/api/hotspots?eps_km=${epsKm}&min_samples=${minSamples}`),
      ])

      if (!summaryResponse.ok) {
        throw new Error('Failed to load summary data')
      }

      if (!hotspotResponse.ok) {
        throw new Error('Failed to load hotspot data')
      }

      const summaryJson = await summaryResponse.json()
      const hotspotJson = await hotspotResponse.json()

      setSummary(summaryJson)
      setHotspots(hotspotJson.hotspots ?? [])
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : 'Unknown error')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    void fetchData()
  }, [])

  const handleSubmit = (event) => {
    event.preventDefault()
    void fetchData()
  }

  return (
    <main className="container">
      <header>
        <h1>AI Military Intelligence Dashboard</h1>
        <p>React frontend powered by a FastAPI backend.</p>
      </header>

      <form className="controls" onSubmit={handleSubmit}>
        <label>
          DBSCAN Radius (km)
          <input
            type="number"
            min="1"
            max="500"
            value={epsKm}
            onChange={(event) => setEpsKm(Number(event.target.value))}
          />
        </label>

        <label>
          Min Samples
          <input
            type="number"
            min="2"
            max="100"
            value={minSamples}
            onChange={(event) => setMinSamples(Number(event.target.value))}
          />
        </label>

        <button type="submit" disabled={isLoading}>
          {isLoading ? 'Loading...' : 'Refresh'}
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      {summary && (
        <section className="cards">
          <article>
            <h2>{summary.total_incidents.toLocaleString()}</h2>
            <p>Total Incidents</p>
          </article>
          <article>
            <h2>{summary.unique_countries}</h2>
            <p>Countries</p>
          </article>
          <article>
            <h2>{summary.unique_regions}</h2>
            <p>Regions</p>
          </article>
          <article>
            <h2>
              {summary.first_year}–{summary.last_year}
            </h2>
            <p>Coverage</p>
          </article>
        </section>
      )}

      <section>
        <h2>Hotspot Rankings</h2>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Rank</th>
                <th>Cluster</th>
                <th>Country</th>
                <th>Incidents</th>
                <th>Total TSI</th>
              </tr>
            </thead>
            <tbody>
              {hotspots.length === 0 && !isLoading ? (
                <tr>
                  <td colSpan="5">No hotspots found for these settings.</td>
                </tr>
              ) : (
                hotspots.map((hotspot) => (
                  <tr key={hotspot.cluster}>
                    <td>{hotspot.rank}</td>
                    <td>{hotspot.cluster}</td>
                    <td>{hotspot.countries}</td>
                    <td>{hotspot.incidents}</td>
                    <td>{hotspot.total_tsi.toFixed(2)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  )
}

export default App
