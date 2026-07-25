import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Download,
  FileText,
  Globe2,
  Landmark,
  Map,
  Search,
  Settings,
  Target,
  Brain,
  Radio,
  RefreshCw,
  Shield,
  Bot,
} from "lucide-react";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

const severityColors = {
  Low: "#34c759",
  Medium: "#ffd60a",
  High: "#ff6b35",
  Critical: "#ff2d55",
};

function App() {
  const [view, setView] = useState("dashboard");
  const [overview, setOverview] = useState(null);
  const [yearly, setYearly] = useState([]);
  const [regions, setRegions] = useState([]);
  const [attackTypes, setAttackTypes] = useState([]);
  const [countries, setCountries] = useState([]);
  const [liveFeed, setLiveFeed] = useState({ status: "loading", events: [] });
  const [globalMap, setGlobalMap] = useState(null);
  const [hotspots, setHotspots] = useState(null);
  const [facets, setFacets] = useState(null);
  const [explorer, setExplorer] = useState(null);
  const [predictionOptions, setPredictionOptions] = useState(null);
  const [settings, setSettings] = useState(null);
  const [selectedCountry, setSelectedCountry] = useState("");
  const [countryAnalysis, setCountryAnalysis] = useState(null);
  const [risk, setRisk] = useState(null);
  const [report, setReport] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    loadInitialData();
  }, []);

  useEffect(() => {
    if (selectedCountry) {
      loadRisk(selectedCountry);
      loadCountryAnalysis(selectedCountry);
    }
  }, [selectedCountry]);

  async function loadInitialData() {
    setLoading(true);
    setError("");
    try {
      const [overviewData, yearlyData, regionData, attackData, countryData, liveData] = await Promise.all([
        api("/api/overview"),
        api("/api/yearly-trends"),
        api("/api/top-regions"),
        api("/api/attack-types"),
        api("/api/countries?sort=name"),
        api("/api/live-feed"),
      ]);
      setOverview(overviewData);
      setYearly(yearlyData);
      setRegions(regionData);
      setAttackTypes(attackData);
      setCountries(countryData);
      setLiveFeed(liveData);
      setSelectedCountry(countryData[0]?.country || "");
      loadMirrorData();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function loadMirrorData() {
    const [mapData, hotspotData, facetData, explorerData, optionsData, settingsData] = await Promise.all([
      api("/api/global-threat-map"),
      api("/api/hotspots"),
      api("/api/data-explorer/facets"),
      api("/api/data-explorer"),
      api("/api/prediction/options"),
      api("/api/settings"),
    ]);
    setGlobalMap(mapData);
    setHotspots(hotspotData);
    setFacets(facetData);
    setExplorer(explorerData);
    setPredictionOptions(optionsData);
    setSettings(settingsData);
  }

  async function loadLiveFeed() {
    setLiveFeed((current) => ({ ...current, status: "loading" }));
    const data = await api("/api/live-feed");
    setLiveFeed(data);
  }

  async function loadRisk(country) {
    const data = await api(`/api/risk/${encodeURIComponent(country)}`);
    setRisk(data);
  }

  async function loadCountryAnalysis(country) {
    const data = await api(`/api/country-analysis/${encodeURIComponent(country)}`);
    setCountryAnalysis(data);
  }

  async function generateReport() {
    const data = await api("/api/situation-report", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ country: selectedCountry }),
    });
    setReport(data.report);
    setRisk((current) => ({ ...current, ...data.risk }));
  }

  async function downloadPdf() {
    const response = await fetch(`${API_BASE}/api/situation-report/pdf`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ country: selectedCountry }),
    });
    if (!response.ok) throw new Error("PDF generation failed");
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${selectedCountry.replaceAll(" ", "_")}_situation_report.pdf`;
    link.click();
    URL.revokeObjectURL(url);
  }

  async function downloadCountryCsv() {
    const response = await fetch(`${API_BASE}/api/country-analysis/${encodeURIComponent(selectedCountry)}/csv`);
    if (!response.ok) throw new Error("Country CSV download failed");
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${selectedCountry.replaceAll(" ", "_")}_country_data.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  const filteredLive = useMemo(() => liveFeed.events?.slice(0, 60) || [], [liveFeed]);

  if (loading) {
    return <Shell view={view} setView={setView}><div className="loading">Loading intelligence workspace...</div></Shell>;
  }

  return (
    <Shell view={view} setView={setView}>
      {error && <div className="alert error">{error}</div>}

      {view === "dashboard" && (
        <Dashboard
          overview={overview}
          yearly={yearly}
          regions={regions}
          attackTypes={attackTypes}
          liveFeed={liveFeed}
        />
      )}

      {view === "live" && (
        <LiveFeed liveFeed={liveFeed} events={filteredLive} onRefresh={loadLiveFeed} />
      )}

      {view === "global-map" && <GlobalThreatMap data={globalMap} />}

      {view === "hotspots" && <HotspotDetection data={hotspots} />}

      {view === "country" && (
        <CountryAnalysis
          countries={countries}
          selectedCountry={selectedCountry}
          setSelectedCountry={setSelectedCountry}
          analysis={countryAnalysis}
          onDownloadCsv={downloadCountryCsv}
        />
      )}

      {view === "risk" && (
        <RiskDesk
          countries={countries}
          selectedCountry={selectedCountry}
          setSelectedCountry={setSelectedCountry}
          risk={risk}
          report={report}
          onGenerateReport={generateReport}
          onDownloadPdf={downloadPdf}
        />
      )}

      {view === "attack-prediction" && <AttackPrediction options={predictionOptions} />}

      {view === "threat-level" && <ThreatLevelPrediction options={predictionOptions} />}

      {view === "data-explorer" && <DataExplorer facets={facets} initialData={explorer} />}

      {view === "settings" && <SettingsPage settings={settings} />}
    </Shell>
  );
}

function Shell({ view, setView, children }) {
  const nav = [
    ["dashboard", BarChart3, "Home"],
    ["global-map", Globe2, "Global threat map"],
    ["hotspots", Target, "Hotspot detection"],
    ["country", Landmark, "Country analysis"],
    ["attack-prediction", Bot, "Attack prediction"],
    ["threat-level", Shield, "Threat level"],
    ["risk", Brain, "AI intelligence"],
    ["live", Radio, "Live feed"],
    ["data-explorer", Search, "Data explorer"],
    ["settings", Settings, "Settings"],
  ];
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <Shield size={26} />
          <div>
            <strong>AI Military Intelligence</strong>
            <span>Threat assessment platform</span>
          </div>
        </div>
        <nav>
          {nav.map(([key, Icon, label]) => (
            <button key={key} className={view === key ? "active" : ""} onClick={() => setView(key)}>
              <Icon size={18} />
              {label}
            </button>
          ))}
        </nav>
      </aside>
      <main className="main-panel">{children}</main>
    </div>
  );
}

function Dashboard({ overview, yearly, regions, attackTypes, liveFeed }) {
  return (
    <>
      <Header title="Intelligence dashboard" subtitle="Historical GTD analytics with live public-source monitoring." />
      <section className="metric-grid">
        <Metric icon={Activity} label="Total incidents" value={formatNumber(overview?.incidents)} />
        <Metric icon={AlertTriangle} label="Fatalities" value={formatNumber(overview?.fatalities)} />
        <Metric icon={Globe2} label="Countries affected" value={formatNumber(overview?.countries)} />
        <Metric icon={Radio} label="Live feed status" value={liveFeed.status || "unknown"} tone={liveFeed.status === "live" ? "good" : "warn"} />
      </section>
      {liveFeed.message && <FallbackNotice message={liveFeed.message} status={liveFeed.status} />}
      <section className="dashboard-grid">
        <Panel title="Attacks over time">
          <LineChart data={yearly} xKey="year" yKey="attacks" />
        </Panel>
        <Panel title="Top regions">
          <BarList data={regions} labelKey="region" valueKey="incidents" />
        </Panel>
        <Panel title="Attack type mix">
          <BarList data={attackTypes.slice(0, 8)} labelKey="attack_type" valueKey="count" />
        </Panel>
      </section>
    </>
  );
}

function LiveFeed({ liveFeed, events, onRefresh }) {
  return (
    <>
      <Header
        title="Live intelligence feed"
        subtitle="GDELT-backed monitoring with stale-cache and historical fallback protection."
        action={<button className="primary" onClick={onRefresh}><RefreshCw size={16} /> Refresh</button>}
      />
      {liveFeed.message && <FallbackNotice message={liveFeed.message} status={liveFeed.status} />}
      <section className="metric-grid">
        <Metric icon={Radio} label="Feed status" value={liveFeed.status} />
        <Metric icon={Globe2} label="Items" value={formatNumber(events.length)} />
        <Metric icon={AlertTriangle} label="High or critical" value={events.filter((item) => ["High", "Critical"].includes(item.severity)).length} />
        <Metric icon={Activity} label="Updated" value={liveFeed.fetched_at ? new Date(liveFeed.fetched_at).toLocaleTimeString() : "n/a"} />
      </section>
      <Panel title="Global event map">
        <WorldMap events={events} />
      </Panel>
      <Panel title="Recent events">
        <EventTable events={events} />
      </Panel>
    </>
  );
}

function GlobalThreatMap({ data }) {
  const clusters = data?.clusters || [];
  const points = data?.points || [];
  return (
    <>
      <Header title="Global threat map" subtitle="3D-style density view and DBSCAN geospatial cluster summary." />
      <section className="metric-grid">
        <Metric icon={Map} label="Showing incidents" value={formatNumber(data?.summary?.incidents)} />
        <Metric icon={Target} label="DBSCAN clusters" value={formatNumber(data?.summary?.clusters)} />
        <Metric icon={Activity} label="Clustered incidents" value={formatNumber(data?.summary?.clustered)} />
        <Metric icon={AlertTriangle} label="Noise / isolated" value={formatNumber(data?.summary?.noise)} />
      </section>
      <Panel title="Incident density map">
        <WorldMap events={points.slice(0, 700).map((item) => ({
          ...item,
          country: item.country_txt,
          event: `Fatalities: ${item.nkill || 0}`,
          title: `${item.country_txt} incident`,
          severity: severityFromIncident({ fatalities: item.nkill, injuries: 0 }),
        }))} />
      </Panel>
      <Panel title="Top hotspot clusters">
        <SimpleTable rows={clusters.slice(0, 15)} columns={[
          ["rank", "Rank"],
          ["cluster", "Cluster ID"],
          ["incidents", "Incidents"],
          ["value", "Fatalities"],
          ["lat", "Lat center"],
          ["lon", "Lon center"],
        ]} />
      </Panel>
    </>
  );
}

function HotspotDetection({ data }) {
  const summaries = data?.hotspots || [];
  return (
    <>
      <Header title="Spatial hotspot detection" subtitle="DBSCAN clustering over incident geometry, ranked by non-linear TSI." />
      <section className="metric-grid">
        <Metric icon={Target} label="Hotspots detected" value={formatNumber(data?.summary?.hotspots)} />
        <Metric icon={Activity} label="Incidents in hotspots" value={formatNumber(data?.summary?.clustered)} />
        <Metric icon={AlertTriangle} label="Noise" value={formatNumber(data?.summary?.noise)} />
        <Metric icon={Globe2} label="Mapped points" value={formatNumber(data?.points?.length)} />
      </section>
      <Panel title="Hotspot map">
        <WorldMap events={(data?.points || []).slice(0, 700).map((item) => ({
          ...item,
          country: item.country_txt,
          event: `Cluster ${item.cluster}`,
          title: `${item.country_txt} hotspot incident`,
          severity: severityFromIncident({ fatalities: item.nkill, injuries: item.nwound }),
        }))} />
      </Panel>
      <Panel title="Top threat hotspots">
        <SimpleTable rows={summaries.slice(0, 20)} columns={[
          ["rank", "Rank"],
          ["country", "Dominant country"],
          ["incidents", "Incidents"],
          ["value", "Total TSI"],
          ["lat", "Lat"],
          ["lon", "Lon"],
        ]} />
      </Panel>
    </>
  );
}

function CountryAnalysis({ countries, selectedCountry, setSelectedCountry, analysis, onDownloadCsv }) {
  const summary = analysis?.summary || {};
  return (
    <>
      <Header title="Country analysis" subtitle="Country-wise historical intelligence from GTD." />
      <section className="control-row">
        <label>
          Country
          <select value={selectedCountry} onChange={(event) => setSelectedCountry(event.target.value)}>
            {countries.map((item) => <option key={item.country} value={item.country}>{item.country}</option>)}
          </select>
        </label>
        <button className="secondary" onClick={onDownloadCsv}><Download size={16} /> CSV</button>
      </section>

      <section className="metric-grid">
        <Metric icon={Activity} label="Incidents" value={formatNumber(summary.incidents)} />
        <Metric icon={AlertTriangle} label="Fatalities" value={formatNumber(summary.fatalities)} />
        <Metric icon={Globe2} label="Groups" value={formatNumber(summary.groups)} />
        <Metric icon={BarChart3} label="Years covered" value={`${summary.first_year || "n/a"}-${summary.latest_year || "n/a"}`} />
      </section>

      <section className="country-grid">
        <Panel title="Country attack trend">
          <LineChart data={analysis?.yearly || []} xKey="year" yKey="attacks" />
        </Panel>
        <Panel title="Attack types">
          <BarList data={analysis?.attack_types || []} labelKey="attack_type" valueKey="incidents" />
        </Panel>
        <Panel title="Weapon analysis">
          <BarList data={analysis?.weapon_types || []} labelKey="weapon_type" valueKey="incidents" />
        </Panel>
        <Panel title="Target types">
          <BarList data={analysis?.target_types || []} labelKey="target_type" valueKey="incidents" />
        </Panel>
        <Panel title="Province / area concentration">
          <BarList data={analysis?.areas || []} labelKey="area" valueKey="incidents" />
        </Panel>
        <Panel title="Active groups">
          <BarList data={analysis?.groups || []} labelKey="group" valueKey="incidents" />
        </Panel>
      </section>

      <Panel title="Incident locations">
        <WorldMap events={(analysis?.incident_locations || []).map((item) => ({
          ...item,
          country: selectedCountry,
          event: item.attack_type,
          title: `${item.attack_type || "Incident"} in ${item.location || selectedCountry} (${item.year})`,
          severity: severityFromIncident(item),
        }))} />
      </Panel>

      <Panel title="Incident details">
        <IncidentTable incidents={analysis?.incident_details || []} />
      </Panel>
    </>
  );
}

function RiskDesk({ countries, selectedCountry, setSelectedCountry, risk, report, onGenerateReport, onDownloadPdf }) {
  return (
    <>
      <Header title="Risk desk" subtitle="Country-level AI risk score, component drivers, and situation reports." />
      <section className="control-row">
        <label>
          Country
          <select value={selectedCountry} onChange={(event) => setSelectedCountry(event.target.value)}>
            {countries.map((item) => <option key={item.country} value={item.country}>{item.country}</option>)}
          </select>
        </label>
        <button className="primary" onClick={onGenerateReport}><FileText size={16} /> Generate report</button>
        <button className="secondary" onClick={onDownloadPdf}><Download size={16} /> PDF</button>
      </section>
      {risk?.live_message && <FallbackNotice message={risk.live_message} status={risk.live_status} />}
      <section className="risk-layout">
        <Panel title="Threat score">
          <Gauge score={risk?.score || 0} level={risk?.level || "Low"} color={risk?.color || severityColors.Low} />
        </Panel>
        <Panel title="Risk drivers">
          <BarList data={componentsToRows(risk?.components)} labelKey="name" valueKey="value" />
        </Panel>
      </section>
      <Panel title="Situation report">
        <pre className="report">{report || "Generate a report to create an analyst-ready situation summary."}</pre>
      </Panel>
    </>
  );
}

function AttackPrediction({ options }) {
  const [form, setForm] = useState(defaultAttackForm(options));
  const [result, setResult] = useState(null);
  useEffect(() => setForm(defaultAttackForm(options)), [options]);
  async function submit() {
    setResult(await api("/api/predict-attack", jsonPost(form)));
  }
  return (
    <>
      <Header title="Attack type prediction" subtitle="Enter incident details to predict the most likely attack type." />
      <PredictionForm form={form} setForm={setForm} options={options} includeAttack={false} />
      <button className="primary" onClick={submit}><Bot size={16} /> Predict attack type</button>
      {result && (
        <section className="risk-layout result-block">
          <Panel title="Prediction result">
            <h3>{result.prediction}</h3>
            <p>Model confidence: <strong>{result.confidence.toFixed(1)}%</strong></p>
          </Panel>
          <Panel title="Top predicted attack types">
            <BarList data={result.probabilities} labelKey="label" valueKey="probability" />
          </Panel>
        </section>
      )}
    </>
  );
}

function ThreatLevelPrediction({ options }) {
  const [form, setForm] = useState(defaultThreatForm(options));
  const [result, setResult] = useState(null);
  useEffect(() => setForm(defaultThreatForm(options)), [options]);
  async function submit() {
    setResult(await api("/api/predict-threat", jsonPost(form)));
  }
  return (
    <>
      <Header title="AI threat level prediction" subtitle="Estimate severity using the Streamlit classifier logic and TSI score." />
      <PredictionForm form={form} setForm={setForm} options={options} includeAttack />
      <button className="primary" onClick={submit}><Shield size={16} /> Predict threat level</button>
      {result && (
        <>
          <section className="risk-layout result-block">
            <Panel title="Threat severity index">
              <Gauge score={Math.round(result.tsi_score)} level={result.tsi_label} color={severityColors[result.tsi_label?.[0] + result.tsi_label?.slice(1).toLowerCase()] || "#40c4ff"} />
            </Panel>
            <Panel title="ML classifier result">
              <h3>{result.level}</h3>
              <p>Model confidence: <strong>{result.confidence.toFixed(1)}%</strong></p>
              <BarList data={result.probabilities} labelKey="label" valueKey="probability" />
            </Panel>
          </section>
          <Panel title="Feature importance">
            <BarList data={result.feature_importance} labelKey="feature" valueKey="importance" />
          </Panel>
        </>
      )}
    </>
  );
}

function DataExplorer({ facets, initialData }) {
  const [filters, setFilters] = useState({ search: "" });
  const [data, setData] = useState(initialData);
  useEffect(() => setData(initialData), [initialData]);
  async function applyFilters() {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(filters)) {
      if (value) params.set(key, Array.isArray(value) ? value.join("|") : value);
    }
    setData(await api(`/api/data-explorer?${params}`));
  }
  return (
    <>
      <Header title="Global terrorism data explorer" subtitle="Filter, visualize, and download the GTD dataset." />
      <section className="filter-grid">
        <SelectFilter label="Year" value={filters.years || ""} values={facets?.years || []} onChange={(value) => setFilters({ ...filters, years: value })} />
        <SelectFilter label="Country" value={filters.countries_filter || ""} values={facets?.countries || []} onChange={(value) => setFilters({ ...filters, countries_filter: value })} />
        <SelectFilter label="Region" value={filters.regions_filter || ""} values={facets?.regions || []} onChange={(value) => setFilters({ ...filters, regions_filter: value })} />
        <SelectFilter label="Attack type" value={filters.attacks_filter || ""} values={facets?.attack_types || []} onChange={(value) => setFilters({ ...filters, attacks_filter: value })} />
        <label>Search city/country<input value={filters.search || ""} onChange={(event) => setFilters({ ...filters, search: event.target.value })} placeholder="Kabul, Iraq..." /></label>
        <button className="primary" onClick={applyFilters}><Search size={16} /> Apply filters</button>
      </section>
      <section className="metric-grid">
        <Metric icon={Activity} label="Incidents" value={formatNumber(data?.summary?.incidents)} />
        <Metric icon={Globe2} label="Countries" value={formatNumber(data?.summary?.countries)} />
        <Metric icon={AlertTriangle} label="Fatalities" value={formatNumber(data?.summary?.fatalities)} />
        <Metric icon={Activity} label="Injuries" value={formatNumber(data?.summary?.injuries)} />
      </section>
      <section className="country-grid">
        <Panel title="Top countries by incidents"><BarList data={data?.by_country || []} labelKey="country" valueKey="incidents" /></Panel>
        <Panel title="Attack type distribution"><BarList data={data?.attack_types || []} labelKey="attack_type" valueKey="incidents" /></Panel>
        <Panel title="Weapon type distribution"><BarList data={data?.weapon_types || []} labelKey="weapon" valueKey="incidents" /></Panel>
      </section>
      <Panel title={`Filtered dataset (${formatNumber(data?.rows?.length || 0)} shown)`}>
        <SimpleTable rows={data?.rows || []} columns={(data?.summary?.columns || []).slice(0, 10).map((col) => [col, col])} />
      </Panel>
    </>
  );
}

function SettingsPage({ settings }) {
  return (
    <>
      <Header title="Dashboard settings" subtitle="Dataset status, theme configuration, API key guidance, and app metadata." />
      <section className="metric-grid">
        <Metric icon={Activity} label="Total incidents" value={formatNumber(settings?.dataset?.rows)} />
        <Metric icon={Globe2} label="Countries" value={formatNumber(settings?.dataset?.countries)} />
        <Metric icon={BarChart3} label="Data from" value={settings?.dataset?.from_year || "n/a"} />
        <Metric icon={BarChart3} label="Data to" value={settings?.dataset?.to_year || "n/a"} />
      </section>
      <section className="risk-layout">
        <Panel title="Appearance">
          <pre className="report">{JSON.stringify(settings?.theme || {}, null, 2)}</pre>
        </Panel>
        <Panel title="About">
          <SimpleTable rows={Object.entries(settings?.about || {}).map(([item, detail]) => ({ item, detail }))} columns={[["item", "Item"], ["detail", "Detail"]]} />
        </Panel>
      </section>
      <Panel title="Gemini API key">
        <pre className="report">export GEMINI_API_KEY=your_key_here</pre>
      </Panel>
      <Panel title="Column names">
        <div className="chips">{(settings?.dataset?.columns || []).map((column) => <span key={column}>{column}</span>)}</div>
      </Panel>
    </>
  );
}

function FallbackNotice({ message, status }) {
  return (
    <div className="alert info">
      <strong>{status === "historical-fallback" ? "Live source rate-limited" : "Live source notice"}</strong>
      <span>{message}</span>
    </div>
  );
}

function Header({ title, subtitle, action }) {
  return (
    <header className="page-header">
      <div>
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </div>
      {action}
    </header>
  );
}

function Metric({ icon: Icon, label, value, tone }) {
  return (
    <div className={`metric ${tone || ""}`}>
      <Icon size={20} />
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Panel({ title, children }) {
  return (
    <section className="panel">
      <h2>{title}</h2>
      {children}
    </section>
  );
}

function PredictionForm({ form, setForm, options, includeAttack }) {
  if (!options) return <div className="empty-state">Loading prediction options...</div>;
  return (
    <section className="form-grid">
      <SelectFilter label="Country" value={form.country_txt || ""} values={options.country_txt || []} onChange={(value) => setForm({ ...form, country_txt: value })} />
      <SelectFilter label="Region" value={form.region_txt || ""} values={options.region_txt || []} onChange={(value) => setForm({ ...form, region_txt: value })} />
      {includeAttack && <SelectFilter label="Attack type" value={form.attacktype1_txt || ""} values={options.attacktype1_txt || []} onChange={(value) => setForm({ ...form, attacktype1_txt: value })} />}
      <SelectFilter label="Weapon type" value={form.weaptype1_txt || ""} values={options.weaptype1_txt || []} onChange={(value) => setForm({ ...form, weaptype1_txt: value })} />
      <SelectFilter label="Target type" value={form.targtype1_txt || ""} values={options.targtype1_txt || []} onChange={(value) => setForm({ ...form, targtype1_txt: value })} />
      {!includeAttack && <SelectFilter label="Terrorist group" value={form.gname || ""} values={options.gname || []} onChange={(value) => setForm({ ...form, gname: value })} />}
      <label>Successful<input type="number" min="0" max="1" value={form.success ?? 1} onChange={(event) => setForm({ ...form, success: Number(event.target.value) })} /></label>
      {!includeAttack && <label>Suicide attack<input type="number" min="0" max="1" value={form.suicide ?? 0} onChange={(event) => setForm({ ...form, suicide: Number(event.target.value) })} /></label>}
      {includeAttack && <label>Claimed<input type="number" min="0" max="1" value={form.claimed ?? 0} onChange={(event) => setForm({ ...form, claimed: Number(event.target.value) })} /></label>}
      <label>Fatalities<input type="number" min="0" value={form.nkill ?? 0} onChange={(event) => setForm({ ...form, nkill: Number(event.target.value) })} /></label>
      <label>Injuries<input type="number" min="0" value={form.nwound ?? 0} onChange={(event) => setForm({ ...form, nwound: Number(event.target.value) })} /></label>
    </section>
  );
}

function SelectFilter({ label, value, values, onChange }) {
  return (
    <label>
      {label}
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">All</option>
        {values.map((item) => <option key={String(item)} value={item}>{String(item)}</option>)}
      </select>
    </label>
  );
}

function LineChart({ data, xKey, yKey }) {
  const width = 720;
  const height = 240;
  if (!data?.length) {
    return <div className="empty-state">No chart data available.</div>;
  }
  const values = data.map((item) => Number(item[yKey]));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const points = data.map((item, index) => {
    const x = (index / Math.max(data.length - 1, 1)) * width;
    const y = height - ((Number(item[yKey]) - min) / Math.max(max - min, 1)) * height;
    return `${x},${y}`;
  }).join(" ");

  return (
    <svg className="line-chart" viewBox={`0 0 ${width} ${height}`} role="img">
      <polyline points={points} fill="none" stroke="#40c4ff" strokeWidth="3" />
      {data.map((item, index) => ({ item, index })).filter(({ index }) => index % Math.ceil(data.length / 8) === 0).map(({ item, index }) => (
        <text key={`${item[xKey]}-${index}`} x={(index / Math.max(data.length - 1, 1)) * width} y={height - 4}>{item[xKey]}</text>
      ))}
    </svg>
  );
}

function BarList({ data, labelKey, valueKey }) {
  if (!data?.length) {
    return <div className="empty-state">No records available.</div>;
  }
  const max = Math.max(...data.map((item) => Number(item[valueKey] || 0)), 1);
  return (
    <div className="bar-list">
      {data.map((item) => (
        <div className="bar-row" key={item[labelKey]}>
          <span>{item[labelKey]}</span>
          <div><i style={{ width: `${(Number(item[valueKey]) / max) * 100}%` }} /></div>
          <strong>{formatNumber(Math.round(Number(item[valueKey] || 0)))}</strong>
        </div>
      ))}
    </div>
  );
}

function WorldMap({ events }) {
  return (
    <div className="world-map">
      <div className="map-grid" />
      {events.filter((item) => item.latitude && item.longitude).map((item, index) => {
        const left = ((Number(item.longitude) + 180) / 360) * 100;
        const top = ((90 - Number(item.latitude)) / 180) * 100;
        const color = severityColors[item.severity] || severityColors.Low;
        return (
          <span
            key={`${item.title}-${index}`}
            className="map-dot"
            title={`${item.country}: ${item.title}`}
            style={{ left: `${left}%`, top: `${top}%`, background: color }}
          />
        );
      })}
    </div>
  );
}

function EventTable({ events }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Country</th>
            <th>Event</th>
            <th>Severity</th>
            <th>Source</th>
            <th>Headline</th>
          </tr>
        </thead>
        <tbody>
          {events.map((item, index) => (
            <tr key={`${item.title}-${index}`}>
              <td>{item.country}</td>
              <td>{item.event}</td>
              <td><span className="pill" style={{ borderColor: severityColors[item.severity] }}>{item.severity}</span></td>
              <td>{item.source}</td>
              <td>{item.url ? <a href={item.url} target="_blank" rel="noreferrer">{item.title}</a> : item.title}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function IncidentTable({ incidents }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Year</th>
            <th>Location</th>
            <th>Attack</th>
            <th>Weapon</th>
            <th>Target</th>
            <th>Group</th>
            <th>Fatalities</th>
            <th>Injuries</th>
          </tr>
        </thead>
        <tbody>
          {incidents.map((item, index) => (
            <tr key={`${item.year}-${item.location}-${index}`}>
              <td>{item.year}</td>
              <td>{item.location || "Unknown"}</td>
              <td>{item.attack_type || "Unknown"}</td>
              <td>{item.weapon_type || "Unknown"}</td>
              <td>{item.target_type || "Unknown"}</td>
              <td>{item.group_name || "Unknown"}</td>
              <td>{formatNumber(item.fatalities || 0)}</td>
              <td>{formatNumber(item.injuries || 0)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SimpleTable({ rows, columns }) {
  if (!rows?.length) return <div className="empty-state">No records available.</div>;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>{columns.map(([, label]) => <th key={label}>{label}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {columns.map(([key]) => <td key={key}>{formatCell(row[key])}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Gauge({ score, level, color }) {
  return (
    <div className="gauge">
      <div className="gauge-ring" style={{ background: `conic-gradient(${color} ${score * 3.6}deg, rgba(255,255,255,0.08) 0deg)` }}>
        <div>
          <strong>{score}</strong>
          <span>/100</span>
        </div>
      </div>
      <h3 style={{ color }}>{level}</h3>
    </div>
  );
}

function componentsToRows(components = {}) {
  return Object.entries(components).map(([name, value]) => ({ name, value: Number(value).toFixed(1) }));
}

function severityFromIncident(item) {
  const impact = Number(item.fatalities || 0) * 2 + Number(item.injuries || 0);
  if (impact >= 50) return "Critical";
  if (impact >= 15) return "High";
  if (impact >= 3) return "Medium";
  return "Low";
}

function defaultAttackForm(options) {
  return {
    country_txt: options?.country_txt?.[0] || "",
    region_txt: options?.region_txt?.[0] || "",
    weaptype1_txt: options?.weaptype1_txt?.[0] || "",
    targtype1_txt: options?.targtype1_txt?.[0] || "",
    gname: options?.gname?.[0] || "",
    success: 1,
    suicide: 0,
    nkill: 0,
    nwound: 0,
  };
}

function defaultThreatForm(options) {
  return {
    country_txt: options?.country_txt?.[0] || "",
    region_txt: options?.region_txt?.[0] || "",
    attacktype1_txt: options?.attacktype1_txt?.[0] || "",
    weaptype1_txt: options?.weaptype1_txt?.[0] || "",
    targtype1_txt: options?.targtype1_txt?.[0] || "",
    nkill: 2,
    nwound: 5,
    success: 1,
    claimed: 0,
  };
}

function jsonPost(body) {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

async function api(path, options) {
  const response = await fetch(`${API_BASE}${path}`, options);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  return response.json();
}

function formatNumber(value) {
  if (value === undefined || value === null || Number.isNaN(value)) return "0";
  return new Intl.NumberFormat().format(value);
}

function formatCell(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "";
  if (typeof value === "number") return Number.isInteger(value) ? formatNumber(value) : value.toFixed(2);
  return String(value);
}

createRoot(document.getElementById("root")).render(<App />);
