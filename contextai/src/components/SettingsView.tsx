import { useState, useEffect } from 'react';
import { Eye, EyeOff, ChevronDown, ChevronUp, Zap, Check, Loader2, AlertTriangle, RefreshCw } from 'lucide-react';
import { useAppStore } from '../stores/appStore';
import { updateProvider, testProvider, fetchOllamaModels } from '../lib/api';

export function SettingsView() {
  const providers = useAppStore((s) => s.providers);
  const toggleProvider = useAppStore((s) => s.toggleProvider);
  const updateProviderKey = useAppStore((s) => s.updateProviderKey);
  const updateProviderModel = useAppStore((s) => s.updateProviderModel);
  const setOllamaModels = useAppStore((s) => s.setOllamaModels);
  const backendReady = useAppStore((s) => s.backendReady);

  const [expandedProvider, setExpandedProvider] = useState<string | null>(null);
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});
  const [testResults, setTestResults] = useState<Record<string, { status: string; message?: string; response?: string }>>({});
  const [testing, setTesting] = useState<string | null>(null);
  const [refreshingOllama, setRefreshingOllama] = useState(false);

  const toggleShowKey = (id: string) => {
    setShowKeys((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const toggleExpand = (id: string) => {
    setExpandedProvider((prev) => (prev === id ? null : id));
  };

  const handleToggleProvider = async (id: string) => {
    toggleProvider(id);
    const provider = providers.find((p) => p.id === id);
    if (provider && backendReady) {
      await updateProvider(id, { enabled: !provider.enabled });
    }
  };

  const handleKeyChange = async (id: string, key: string) => {
    updateProviderKey(id, key);
  };

  const handleKeyBlur = async (id: string) => {
    const provider = providers.find((p) => p.id === id);
    if (provider && backendReady && provider.apiKey) {
      await updateProvider(id, { api_key: provider.apiKey, model: provider.model });
    }
  };

  const handleModelChange = async (id: string, model: string) => {
    updateProviderModel(id, model);
    if (backendReady) {
      await updateProvider(id, { model });
    }
  };

  const handleRefreshOllama = async () => {
    setRefreshingOllama(true);
    const result = await fetchOllamaModels();
    if (result.available && result.models.length > 0) {
      const modelNames = result.models.map((m) => m.name);
      setOllamaModels(modelNames);
    }
    setRefreshingOllama(false);
  };

  const handleTestProvider = async (id: string) => {
    if (testing) return;
    setTesting(id);
    setTestResults((prev) => ({ ...prev, [id]: { status: 'testing' } }));

    // Ensure key + model are synced first
    const provider = providers.find((p) => p.id === id);
    if (provider && backendReady) {
      await updateProvider(id, {
        enabled: provider.enabled,
        api_key: provider.apiKey,
        model: provider.model,
      });
    }

    const result = await testProvider(id);
    setTestResults((prev) => ({ ...prev, [id]: result }));
    setTesting(null);
  };

  const ollamaProvider = providers.find((p) => p.id === 'ollama');

  return (
    <div className="settings-view">
      <div className="settings-section">
        <h3 className="settings-section__title">LLM Providers</h3>

        {providers.map((provider) => {
          const test = testResults[provider.id];
          const isOllama = provider.id === 'ollama';
          const hasModels = isOllama && (provider.availableModels?.length ?? 0) > 0;

          return (
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
                    <div className="setting-row__sublabel">
                      {provider.model || (isOllama ? 'No models detected' : 'Not configured')}
                      {test?.status === 'ok' && <span style={{ color: 'var(--success)', marginLeft: '6px' }}>✓ connected</span>}
                      {test?.status === 'error' && <span style={{ color: 'var(--error)', marginLeft: '6px' }}>✗ failed</span>}
                    </div>
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <button
                    className={`toggle ${provider.enabled ? 'toggle--active' : ''}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleToggleProvider(provider.id);
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
                  {isOllama ? (
                    <>
                      <div style={{ fontSize: '12px', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                        Ollama runs locally — no API key needed. Ensure Ollama is running on{' '}
                        <code style={{ color: 'var(--accent)', fontFamily: 'var(--font-mono)' }}>localhost:11434</code>.
                      </div>

                      {/* Ollama Model Picker */}
                      <div>
                        <label style={{
                          fontSize: '11px', fontWeight: 600, color: 'var(--text-secondary)',
                          marginBottom: '4px', display: 'block', textTransform: 'uppercase', letterSpacing: '0.5px',
                        }}>
                          Model
                        </label>
                        <div style={{ display: 'flex', gap: '6px' }}>
                          <select
                            className="input-field"
                            value={provider.model}
                            onChange={(e) => handleModelChange(provider.id, e.target.value)}
                            onClick={(e) => e.stopPropagation()}
                            style={{
                              flex: 1,
                              cursor: 'pointer',
                              appearance: 'auto',
                            }}
                          >
                            {!hasModels && (
                              <option value="">No models detected</option>
                            )}
                            {provider.availableModels?.map((m) => (
                              <option key={m} value={m}>{m}</option>
                            ))}
                          </select>
                          <button
                            className="title-bar__btn"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleRefreshOllama();
                            }}
                            title="Refresh models"
                            style={{ flexShrink: 0 }}
                            disabled={refreshingOllama}
                          >
                            <RefreshCw size={14} style={{
                              animation: refreshingOllama ? 'spin 1s linear infinite' : 'none',
                            }} />
                          </button>
                        </div>

                        {hasModels && (
                          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
                            {provider.availableModels!.length} model{provider.availableModels!.length !== 1 ? 's' : ''} detected
                          </div>
                        )}
                        {!hasModels && backendReady && (
                          <div style={{ fontSize: '11px', color: 'var(--warning, orange)', marginTop: '4px' }}>
                            No models found. Install one with: <code style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent)' }}>ollama pull gemma4</code>
                          </div>
                        )}
                      </div>
                    </>
                  ) : (
                    <>
                      <div>
                        <label style={{
                          fontSize: '11px', fontWeight: 600, color: 'var(--text-secondary)',
                          marginBottom: '4px', display: 'block', textTransform: 'uppercase', letterSpacing: '0.5px',
                        }}>
                          API Key
                        </label>
                        <div style={{ display: 'flex', gap: '6px' }}>
                          <input
                            className="input-field"
                            type={showKeys[provider.id] ? 'text' : 'password'}
                            placeholder={`Enter ${provider.name} API key`}
                            value={provider.apiKey}
                            onChange={(e) => handleKeyChange(provider.id, e.target.value)}
                            onBlur={() => handleKeyBlur(provider.id)}
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

                      {/* Model name for cloud providers */}
                      <div>
                        <label style={{
                          fontSize: '11px', fontWeight: 600, color: 'var(--text-secondary)',
                          marginBottom: '4px', display: 'block', textTransform: 'uppercase', letterSpacing: '0.5px',
                        }}>
                          Model
                        </label>
                        <input
                          className="input-field"
                          type="text"
                          placeholder={`e.g., ${provider.model}`}
                          value={provider.model}
                          onChange={(e) => handleModelChange(provider.id, e.target.value)}
                          onClick={(e) => e.stopPropagation()}
                        />
                      </div>
                    </>
                  )}

                  {/* Test connection button */}
                  <button
                    className="btn-primary"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleTestProvider(provider.id);
                    }}
                    disabled={
                      testing === provider.id ||
                      (!provider.apiKey && !isOllama) ||
                      (isOllama && !provider.model) ||
                      !backendReady
                    }
                    style={{ alignSelf: 'flex-start', gap: '6px' }}
                  >
                    {testing === provider.id ? (
                      <><Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} /> Testing...</>
                    ) : (
                      <><Check size={12} /> Test Connection</>
                    )}
                  </button>

                  {test?.status === 'error' && (
                    <div style={{
                      display: 'flex', alignItems: 'flex-start', gap: '6px',
                      fontSize: '11px', color: 'var(--error)', lineHeight: 1.4,
                      padding: '6px 8px', background: 'rgba(248, 113, 113, 0.08)', borderRadius: 'var(--radius-sm)',
                    }}>
                      <AlertTriangle size={12} style={{ flexShrink: 0, marginTop: '1px' }} />
                      {test.message}
                    </div>
                  )}

                  {test?.status === 'ok' && (
                    <div style={{
                      display: 'flex', alignItems: 'center', gap: '6px',
                      fontSize: '11px', color: 'var(--success)',
                      padding: '6px 8px', background: 'rgba(52, 211, 153, 0.08)', borderRadius: 'var(--radius-sm)',
                    }}>
                      <Check size={12} /> {test.response || 'Provider connected successfully'}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
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
              <div className="setting-row__sublabel">Open-source · MIT · Ctrl+Shift+Space</div>
            </div>
          </div>
          <div className={`status-dot ${backendReady ? 'status-dot--connected' : 'status-dot--disconnected'}`} title={backendReady ? 'Backend connected' : 'Backend offline'} />
        </div>
      </div>
    </div>
  );
}
