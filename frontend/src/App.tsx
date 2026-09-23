import { useState, type FormEvent } from 'react'
import './App.css'

// The figures both endpoints return per row (see backend/metrics.py `summarise`).
type Figures = {
  policy_count: number
  earned_premium_dkk: number
  incurred_loss_dkk: number
  loss_ratio: number | null
  underwriting_result_dkk: number
  claim_count: number
  largest_claim_dkk: number
}

// GET /portfolios/{portfolio_id}/loss-experience
type PortfolioLossExperience = {
  portfolio_id: string
  currency: string
  perils: Record<string, Figures>
}

// GET /portfolios
type PortfolioList = {
  portfolios: string[]
}

// GET /portfolios/loss-experience
type AllPortfoliosLossExperience = {
  currency: string
  ordering: string
  book_total: Figures
  rankings: Record<string, string>
  portfolios: ({ rank: number; portfolio_id: string } & Figures)[]
}

// Readable labels for the backend's `rankings` keys; unknown keys fall back to the raw key.
const RANKING_LABELS: Record<string, string> = {
  worst_loss_ratio: 'Worst loss ratio',
  best_loss_ratio: 'Best loss ratio',
  smallest_underwriting_result: 'Smallest underwriting result',
  largest_single_claim: 'Largest single claim',
}

// One locale for every number, so "." and "," always mean the same thing on the page.
// en-GB: 6,586,893 and 0.97. Switch to 'da-DK' for 6.586.893 and 0,97.
const LOCALE = 'en-GB'
const dkk = new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 0 })
const count = new Intl.NumberFormat(LOCALE)
const ratio = new Intl.NumberFormat(LOCALE, { minimumFractionDigits: 2, maximumFractionDigits: 2 })

async function getJson<T>(url: string): Promise<T> {
  let res: Response
  try {
    res = await fetch(url)
  } catch {
    throw new Error('Could not reach the backend. Is it running on port 8000?')
  }
  const body = await res.json()
  if (!res.ok) throw new Error(body.detail ?? `Request failed (${res.status})`)
  return body
}

function FiguresRow({ name, f }: { name: string; f: Figures }) {
  return (
    <tr>
      <td>{name}</td>
      <td>{count.format(f.policy_count)}</td>
      <td>{dkk.format(f.earned_premium_dkk)}</td>
      <td>{dkk.format(f.incurred_loss_dkk)}</td>
      <td>{f.loss_ratio === null ? '–' : ratio.format(f.loss_ratio)}</td>
      <td>{dkk.format(f.underwriting_result_dkk)}</td>
      <td>{count.format(f.claim_count)}</td>
      <td>{dkk.format(f.largest_claim_dkk)}</td>
    </tr>
  )
}

function FiguresTable({
  label,
  rows,
  total,
}: {
  label: string
  rows: [string, Figures][]
  total?: [string, Figures]
}) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>{label}</th>
            <th>Policies</th>
            <th>Earned premium</th>
            <th>Incurred loss</th>
            <th>Loss ratio</th>
            <th>Underwriting result</th>
            <th>Claims</th>
            <th>Largest claim</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([name, f]) => (
            <FiguresRow key={name} name={name} f={f} />
          ))}
        </tbody>
        {total && (
          <tfoot>
            <FiguresRow name={total[0]} f={total[1]} />
          </tfoot>
        )}
      </table>
    </div>
  )
}

function App() {
  const [portfolioId, setPortfolioId] = useState('')
  const [portfolio, setPortfolio] = useState<PortfolioLossExperience | null>(null)
  const [allPortfolios, setAllPortfolios] = useState<AllPortfoliosLossExperience | null>(null)
  const [portfolioIds, setPortfolioIds] = useState<string[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  // Runs one request, clearing the previous result and error so only one view shows at a time.
  async function load(request: () => Promise<void>) {
    setLoading(true)
    setError(null)
    setPortfolio(null)
    setAllPortfolios(null)
    setPortfolioIds(null)
    try {
      await request()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  function showPortfolio(id: string) {
    load(async () =>
      setPortfolio(await getJson(`/portfolios/${encodeURIComponent(id)}/loss-experience`)),
    )
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const id = portfolioId.trim()
    if (id) showPortfolio(id)
  }

  function handlePortfolioList() {
    load(async () => setPortfolioIds((await getJson<PortfolioList>('/portfolios')).portfolios))
  }

  // Clicking an ID in the list fills the text box too, so the box always matches what is shown.
  function handlePickPortfolio(id: string) {
    setPortfolioId(id)
    showPortfolio(id)
  }

  function handleAllPortfolios() {
    load(async () => setAllPortfolios(await getJson('/portfolios/loss-experience')))
  }

  return (
    <main>
      <h1>Loss experience</h1>

      <form onSubmit={handleSubmit}>
        <input
          value={portfolioId}
          onChange={(e) => setPortfolioId(e.target.value)}
          placeholder="Portfolio ID, e.g. PF-01"
          aria-label="Portfolio ID"
        />
        <button type="submit" disabled={loading}>
          Show
        </button>
        <button type="button" onClick={handleAllPortfolios} disabled={loading}>
          Get loss experience statistics
        </button>
        <button type="button" onClick={handlePortfolioList} disabled={loading}>
          Show all portfolios
        </button>
      </form>

      {loading && <p className="muted">Loading…</p>}
      {error && <p className="error">{error}</p>}

      {portfolioIds && (
        <section>
          <h2>Available portfolios</h2>
          <p className="muted">Click one to see its loss experience.</p>
          <ul className="portfolio-list">
            {portfolioIds.map((id) => (
              <li key={id}>
                <button type="button" onClick={() => handlePickPortfolio(id)}>
                  {id}
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {portfolio && (
        <section>
          <h2>{portfolio.portfolio_id}</h2>
          <p className="muted">All amounts in {portfolio.currency}.</p>
          <FiguresTable label="Peril" rows={Object.entries(portfolio.perils)} />
        </section>
      )}

      {allPortfolios && (
        <section>
          <h2>All portfolios</h2>
          <p className="muted">
            All amounts in {allPortfolios.currency}. Totals across all perils. Ordered by{' '}
            {allPortfolios.ordering}.
          </p>
          <dl className="rankings">
            {Object.entries(allPortfolios.rankings).map(([key, winner]) => (
              <div key={key}>
                <dt>{RANKING_LABELS[key] ?? key}</dt>
                <dd>{winner}</dd>
              </div>
            ))}
          </dl>
          <FiguresTable
            label="Portfolio"
            rows={allPortfolios.portfolios.map((p) => [`${p.rank}. ${p.portfolio_id}`, p])}
            total={['Whole book', allPortfolios.book_total]}
          />
        </section>
      )}
    </main>
  )
}

export default App
