import { useState } from 'react';
import { Eye, EyeOff, ChevronDown, ChevronUp, Zap } from 'lucide-react';
import { useAppStore } from '../stores/appStore';

export function SettingsView() {
  const providers = useAppStore((s) => s.providers);
  const toggleProvider = useAppStore((s) => s.toggleProvider);
  const updateProviderKey = useAppStore((s) => s.updateProviderKey);

  const [expandedProvider, setExpandedProvider] = useState<string | null>(null);
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});

  const toggleShowKey = (id: string) => {
    setShowKeys((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const toggleExpand = (id: string) => {
    setExpandedProvider((prev) => (prev === id ? null : id));
  };

  return (
    <div className="settings-view">
      <div className="settings-section">
        <h3 className="settings-section__title">LLM Providers</h3>
        
        {providers.map((provider) => (
          <div key={provider.id}>
            <div className="setting-row" style={{ cursor: 'pointer' }} onClick={() => toggleExpand(provider.id)}>
              <div className="setting-row__left">
                <div
                  className="setting-row__icon"
                  style={{ background: provider.color + '20', color: provider.color }}
                >
                  <Zap size={14} />
                </div>
                <div>
                  <div className="setting-row__label">{provider.name}</div>
                  <div className="setting-row__sublabel">{provider.model}</div>
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <button
                  className={`toggle ${provider.enabled ? 'toggle--active' : ''}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleProvider(provider.id);
                  }}
                />
                {expandedProvider === provider.id ? (
                  <ChevronUp size={14} style={{ color: 'var(--text-muted)' }} />
                ) : (
                  <ChevronDown size={14} style={{ color: 'var(--text-muted)' }} />
                )}
              </div>
            </div>

            {expandedProvider === provider.id && (
              <div style={{
                padding: '12px',
                background: 'var(--bg-tertiary)',
                borderRadius: '0 0 var(--radius-md) var(--radius-md)',
                borderLeft: '1px solid var(--border)',
                borderRight: '1px solid var(--border)',
                borderBottom: '1px solid var(--border)',
                marginTop: '-1px',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
              }}>
                {provider.id !== 'ollama' && (
                  <div>
                    <label className="settings-section__title" style={{ marginBottom: '4px', display: 'block' }}>
                      API Key
                    </label>
                    <div style={{ display: 'flex', gap: '6px' }}>
                      <input
                        className="input-field"
                        type={showKeys[provider.id] ? 'text' : 'password'}
                        placeholder={`Enter ${provider.name} API key`}
                        value={provider.apiKey}
                        onChange={(e) => updateProviderKey(provider.id, e.target.value)}
                        onClick={(e) => e.stopPropagation()}
                      />
                      <button
                        className="title-bar__btn"
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleShowKey(provider.id);
                        }}
                        style={{ flexShrink: 0 }}
                      >
                        {showKeys[provider.id] ? <EyeOff size={14} /> : <Eye size={14} />}
                      </button>
                    </div>
                  </div>
                )}
                {provider.id === 'ollama' && (
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                    Ollama runs locally — no API key needed. Make sure Ollama is installed and running on <code style={{ color: 'var(--accent)', fontFamily: 'var(--font-mono)' }}>localhost:11434</code>.
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="settings-section">
        <h3 className="settings-section__title">Privacy</h3>
        <div className="setting-row">
          <div className="setting-row__left">
            <div>
              <div className="setting-row__label">Screen Context Capture</div>
              <div className="setting-row__sublabel">Capture text from active window</div>
            </div>
          </div>
          <button className="toggle" />
        </div>
        <div className="setting-row">
          <div className="setting-row__left">
            <div>
              <div className="setting-row__label">Clipboard Monitoring</div>
              <div className="setting-row__sublabel">Auto-detect copied text</div>
            </div>
          </div>
          <button className="toggle" />
        </div>
      </div>

      <div className="settings-section">
        <h3 className="settings-section__title">About</h3>
        <div className="setting-row">
          <div className="setting-row__left">
            <div>
              <div className="setting-row__label">ContextAI v0.1.0</div>
              <div className="setting-row__sublabel">Open-source · MIT License · Ctrl+Shift+Space</div>
            </div>
          </div>
          <div className="status-dot status-dot--connected" title="Backend connected" />
        </div>
      </div>
    </div>
  );
}
