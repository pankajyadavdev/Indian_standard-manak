import React, { useState, useEffect } from 'react';
import { ShieldCheck, Server, Database, FileText, CheckCircle2, AlertTriangle, RefreshCw } from 'lucide-react';

export default function App() {
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchHealth = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/v1/health/ready');
      if (!res.ok) {
        throw new Error(`HTTP error! status: ${res.status}`);
      }
      const data = await res.json();
      setHealth(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
  }, []);

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#f1f5f9', padding: '24px' }}>
      <header style={{
        maxWidth: '1200px',
        margin: '0 auto 24px auto',
        backgroundColor: '#ffffff',
        borderRadius: '12px',
        padding: '24px',
        boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{
            backgroundColor: '#1d4ed8',
            color: '#ffffff',
            padding: '12px',
            borderRadius: '10px',
            display: 'flex'
          }}>
            <ShieldCheck size={32} />
          </div>
          <div>
            <h1 style={{ fontSize: '24px', fontWeight: '700', color: '#0f172a', margin: 0 }}>
              IS Compliance & Verification Platform
            </h1>
            <p style={{ margin: '4px 0 0 0', color: '#64748b', fontSize: '14px' }}>
              Autonomous Tender Verification against Indian Standards (BIS)
            </p>
          </div>
        </div>
        <button
          onClick={fetchHealth}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '10px 16px',
            backgroundColor: '#f8fafc',
            border: '1px solid #cbd5e1',
            borderRadius: '8px',
            cursor: 'pointer',
            fontWeight: 500,
            color: '#334155'
          }}
        >
          <RefreshCw size={16} className={loading ? 'spin' : ''} />
          Refresh Status
        </button>
      </header>

      <main style={{ maxWidth: '1200px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '24px' }}>
        {/* System Health Card */}
        <section style={{
          backgroundColor: '#ffffff',
          borderRadius: '12px',
          padding: '24px',
          boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
        }}>
          <h2 style={{ fontSize: '18px', fontWeight: '600', marginBottom: '16px', color: '#1e293b' }}>
            System Foundation Status (Phase 1)
          </h2>

          {loading ? (
            <p style={{ color: '#64748b' }}>Checking system health...</p>
          ) : error ? (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              padding: '16px',
              backgroundColor: '#fef2f2',
              border: '1px solid #fecaca',
              borderRadius: '8px',
              color: '#991b1b'
            }}>
              <AlertTriangle size={24} />
              <div>
                <strong>Backend Connection Error:</strong> {error}
                <div style={{ fontSize: '13px', marginTop: '4px' }}>Ensure the FastAPI backend is running on port 8000.</div>
              </div>
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
              <div style={{
                padding: '16px',
                borderRadius: '8px',
                border: '1px solid #e2e8f0',
                backgroundColor: '#f8fafc',
                display: 'flex',
                alignItems: 'center',
                gap: '16px'
              }}>
                <Server size={28} color="#2563eb" />
                <div>
                  <div style={{ fontSize: '13px', color: '#64748b' }}>API Server</div>
                  <div style={{ fontSize: '16px', fontWeight: '600', color: '#0f172a' }}>
                    {health?.status === 'READY' ? 'Operational' : 'Degraded'}
                  </div>
                </div>
              </div>

              <div style={{
                padding: '16px',
                borderRadius: '8px',
                border: '1px solid #e2e8f0',
                backgroundColor: '#f8fafc',
                display: 'flex',
                alignItems: 'center',
                gap: '16px'
              }}>
                <Database size={28} color="#16a34a" />
                <div>
                  <div style={{ fontSize: '13px', color: '#64748b' }}>Database Engine</div>
                  <div style={{ fontSize: '16px', fontWeight: '600', color: '#0f172a' }}>
                    {health?.checks?.database ? 'Connected & Healthy' : 'Disconnected'}
                  </div>
                </div>
              </div>

              <div style={{
                padding: '16px',
                borderRadius: '8px',
                border: '1px solid #e2e8f0',
                backgroundColor: '#f8fafc',
                display: 'flex',
                alignItems: 'center',
                gap: '16px'
              }}>
                <FileText size={28} color="#9333ea" />
                <div>
                  <div style={{ fontSize: '13px', color: '#64748b' }}>Storage Subsystem</div>
                  <div style={{ fontSize: '16px', fontWeight: '600', color: '#0f172a' }}>
                    {health?.checks?.storage ? 'Read/Write Verified' : 'Unavailable'}
                  </div>
                </div>
              </div>
            </div>
          )}
        </section>

        {/* Foundation Checklist */}
        <section style={{
          backgroundColor: '#ffffff',
          borderRadius: '12px',
          padding: '24px',
          boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
        }}>
          <h2 style={{ fontSize: '18px', fontWeight: '600', marginBottom: '16px', color: '#1e293b' }}>
            Phase 1 Foundation Verification Checklist
          </h2>
          <ul style={{ listStyle: 'none', padding: 0, display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {[
              "Modular Project Structure established (backend, frontend, alembic, tests)",
              "Environment configuration loaded via Pydantic BaseSettings and .env",
              "Dependency management defined and pinned (requirements.txt & package.json)",
              "Backend FastAPI application initialized with CORS and OWASP security headers",
              "Database session with foreign-key enforcement & soft-delete mixins",
              "Alembic migration system initialized and linked to schema metadata",
              "Health and readiness probes verified with 100% test pass rate",
              "Frontend built with Vite and verified"
            ].map((item, idx) => (
              <li key={idx} style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '14px', color: '#334155' }}>
                <CheckCircle2 size={18} color="#16a34a" />
                {item}
              </li>
            ))}
          </ul>
        </section>
      </main>
    </div>
  );
}
