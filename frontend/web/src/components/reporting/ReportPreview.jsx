import { useState, useEffect } from 'react';

const API = '/api';

export default function ReportPreview({ reportId, onClose }) {
  const [loading, setLoading] = useState(true);
  const [url, setUrl]         = useState('');

  useEffect(() => {
    if (!reportId) return;
    const token = localStorage.getItem('token');
    setUrl(`${API}/reports/download/${reportId}?token=${token}`);
    setLoading(false);
  }, [reportId]);

  if (!reportId) return null;

  return (
    <div style={s.overlay}>
      <div style={s.modal}>
        <div style={s.toolbar}>
          <span style={s.toolbarTitle}>📋 Aperçu du rapport</span>
          <div style={{ display: 'flex', gap: 8 }}>
            <a href={url} download style={s.downloadBtn}>⬇ Télécharger</a>
            <button onClick={onClose} style={s.closeBtn}>✕</button>
          </div>
        </div>
        {loading ? (
          <div style={s.loading}>Chargement…</div>
        ) : (
          <iframe src={url} style={s.frame} title="Report Preview" />
        )}
      </div>
    </div>
  );
}

const s = {
  overlay: { position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)', zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center' },
  modal: { width: '90vw', height: '90vh', background: '#1a1a2e', borderRadius: 14, border: '1px solid #1e293b', display: 'flex', flexDirection: 'column', overflow: 'hidden' },
  toolbar: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', borderBottom: '1px solid #1e293b' },
  toolbarTitle: { color: '#00d4ff', fontWeight: 700, fontFamily: 'monospace', fontSize: 14 },
  downloadBtn: { padding: '6px 14px', background: '#00d4ff', color: '#0a0a0f', borderRadius: 6, fontSize: 12, fontWeight: 700, textDecoration: 'none' },
  closeBtn: { padding: '6px 14px', background: '#1e293b', border: '1px solid #334155', color: '#94a3b8', borderRadius: 6, cursor: 'pointer', fontSize: 14 },
  loading: { flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#64748b', fontFamily: 'monospace' },
  frame: { flex: 1, border: 'none', background: '#fff' },
};
