import React, { useState } from 'react';
import { Database, ShieldAlert, Cpu, CheckCircle2, ChevronRight, Activity, TerminalSquare, AlertTriangle } from 'lucide-react';

const API_URL = "http://localhost:8000";

function App() {
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    severity: 'Medium',
    affected_asset: ''
  });
  
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [showRaw, setShowRaw] = useState(false);
  const [error, setError] = useState(null);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const loadSampleData = () => {
    setFormData({
      title: 'SQL Injection in user authentication endpoint',
      description: 'The login endpoint at /api/v1/auth does not sanitize user input before passing it to the database query. This allows an attacker to bypass authentication using a basic boolean-based payload (e.g., admin\' OR 1=1--).',
      severity: 'Critical',
      affected_asset: 'Authentication Service'
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.title || !formData.description) return;
    
    setLoading(true);
    setError(null);
    setResult(null);
    setShowRaw(false);

    try {
      // Connecting to the backend /demo/analyze endpoint
      const response = await fetch(`${API_URL}/demo/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...formData,
          scanner: 'manual_entry',
          org_id: 'demo-org'
        })
      });

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}`);
      }

      const data = await response.json();
      // Simulate slight delay for the animation wow factor if it was too fast
      setTimeout(() => {
        setResult(data);
        setLoading(false);
      }, 800);
      
    } catch (err) {
      console.error(err);
      setError("Failed to connect to the backend. Make sure the API is running.");
      setLoading(false);
    }
  };

  return (
    <div className="app-container">
      <header>
        <h1 className="brand-title">Self Hosted LLM for Vulnerabilities</h1>
        <p className="brand-subtitle">Local-first, AI-driven security advisory engine</p>
      </header>

      <main className="main-grid">
        {/* Left Column: Input Form */}
        <div className="glass-panel form-panel">
          <div className="form-header">
            <h2><ShieldAlert className="inline-icon" size={24} style={{ marginRight: '8px', color: 'var(--accent-cyan)' }}/> New Scan Finding</h2>
            <button type="button" onClick={loadSampleData} className="btn btn-secondary" style={{ padding: '0.4rem 0.8rem', fontSize: '0.85rem' }}>
              Fill Sample Data
            </button>
          </div>

          <form onSubmit={handleSubmit}>
            <div className="input-group">
              <label>Finding Title</label>
              <input 
                type="text" 
                name="title"
                required
                className="glass-input" 
                placeholder="e.g., Cross-Site Scripting (XSS)"
                value={formData.title}
                onChange={handleInputChange}
              />
            </div>

            <div className="input-group">
              <label>Description Details</label>
              <textarea 
                name="description"
                required
                className="glass-input" 
                placeholder="Describe the vulnerability in detail..."
                value={formData.description}
                onChange={handleInputChange}
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <div className="input-group">
                <label>Scanner Severity</label>
                <select name="severity" className="glass-input" value={formData.severity} onChange={handleInputChange}>
                  <option value="Low">Low</option>
                  <option value="Medium">Medium</option>
                  <option value="High">High</option>
                  <option value="Critical">Critical</option>
                </select>
              </div>

              <div className="input-group">
                <label>Affected Asset</label>
                <input 
                  type="text" 
                  name="affected_asset"
                  className="glass-input" 
                  placeholder="e.g., Payment Gateway"
                  value={formData.affected_asset}
                  onChange={handleInputChange}
                />
              </div>
            </div>

            <button type="submit" className="btn btn-primary" disabled={loading}>
              <Cpu size={20} />
              {loading ? 'Analyzing with AI...' : 'Generate AI Advisory'}
            </button>
          </form>

          {error && (
            <div style={{ marginTop: '1rem', padding: '1rem', background: 'rgba(239, 68, 68, 0.2)', border: '1px solid var(--color-critical)', borderRadius: '8px', color: '#fca5a5' }}>
              <AlertTriangle className="inline-icon" size={18} style={{ marginRight: '8px' }}/>
              {error}
            </div>
          )}
        </div>

        {/* Right Column: Results */}
        <div className="glass-panel results-panel" style={{ minHeight: '600px' }}>
          {!loading && !result && (
            <div className="scanning-state" style={{ color: 'var(--text-muted)' }}>
              <Database size={48} opacity={0.5} />
              <p>Submit a finding to generate an AI advisory.</p>
            </div>
          )}

          {loading && (
            <div className="scanning-state">
              <Activity className="scan-icon" />
              <h3>Processing via Local LLM...</h3>
              <p style={{ color: 'var(--text-muted)' }}>Analyzing risk, applying policies, and generating remediation...</p>
            </div>
          )}

          {result && !loading && (
            <>
              <div className="risk-header">
                <div>
                  <h2 style={{ fontSize: '1.8rem', marginBottom: '0.5rem' }}>Advisory Generated</h2>
                  <div className="model-tag"><Cpu size={14}/> {result.model_used || "phi3:mini"}</div>
                </div>
                
                <div className="risk-score-circle">
                  <span className="score-num">{result.risk_assessment.risk_score}</span>
                  <span className="score-label">Risk Score</span>
                </div>
              </div>

              <div className="result-section">
                <h3><ShieldAlert size={18}/> Status & Severity</h3>
                <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', marginTop: '0.5rem' }}>
                  <span className={`criticality-badge criticality-${result.risk_assessment.risk_level}`}>
                    {result.risk_assessment.risk_level}
                  </span>
                  <span style={{ color: 'var(--text-muted)' }}>SLA: <strong style={{ color: 'var(--text-main)' }}>{result.risk_assessment.sla}</strong></span>
                </div>
              </div>

              <div className="result-section">
                <h3><Activity size={18}/> Business Impact</h3>
                <p>{result.advisory.business_impact}</p>
              </div>

              <div className="result-section">
                <h3><CheckCircle2 size={18}/> Remediation Steps</h3>
                <ul className="remediation-list">
                  {result.advisory.remediation_steps.map((step, idx) => (
                    <li key={idx}>{step}</li>
                  ))}
                </ul>
              </div>

              <div className="raw-json-toggle">
                <button 
                  type="button" 
                  className="btn btn-secondary" 
                  onClick={() => setShowRaw(!showRaw)}
                  style={{ padding: '0.5rem 1rem', fontSize: '0.85rem' }}
                >
                  <TerminalSquare size={16} />
                  {showRaw ? 'Hide Raw JSON' : 'View API Response'}
                </button>
              </div>

              {showRaw && (
                <div className="raw-json" style={{ animation: 'fadeInDown 0.3s ease-out' }}>
                  <pre>{JSON.stringify(result, null, 2)}</pre>
                </div>
              )}
            </>
          )}
        </div>
      </main>
    </div>
  );
}

export default App;
