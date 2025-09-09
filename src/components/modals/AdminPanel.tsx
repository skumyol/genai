import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  Stack,
  IconButton,
  Typography,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Box
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import useMediaQuery from '@mui/material/useMediaQuery';
import MenuItem from '@mui/material/MenuItem';
import CloseOutlinedIcon from '@mui/icons-material/CloseOutlined';
import SettingsOutlinedIcon from '@mui/icons-material/SettingsOutlined';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { NetworkDiagram } from '../admin/NetworkDiagram';
import { AgentNetworkBuilder } from '../agent/AgentNetworkBuilder';
import { NPC, AgentNetwork, NetworkValidation } from '../../types/schema';
import { mockAgentLibrary, mockAgentNetwork } from '../../data/agentNetworkMockData';
import { getNetwork, saveNetwork, resetSettings, fetchSettings, saveSettings, fetchExperiments, applyExperiment, ensureUserId, listSessionsFiltered, listBaseSessionsFiltered, cloneSessionForUser, listMetrics, fetchMetricsSummary, reinitDatabase } from '../../api/client';

interface AdminPanelProps {
  open: boolean;
  onClose: () => void;
  npcs?: NPC[];
}

export const AdminPanel: React.FC<AdminPanelProps> = ({ open, onClose, npcs = [] }) => {
  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down('md'));

  const [prompts, setPrompts] = useState({
    systemPrompt: 'You are a helpful NPC in a medieval fantasy world. Respond in character and be engaging.',
    npcPersonalities: {
      'npc-1': 'You are Sir Gareth, a noble and brave knight. Speak with honor and courage.',
      'npc-2': 'You are Morgana, a wise and mysterious sorceress. Speak with ancient wisdom.',
      'npc-3': 'You are Finn, a cheerful merchant. Be friendly and business-minded.'
    },
    experimentGuide: 'Welcome to the experiment. Use Play as and Talk to interact. You can load tests from the header.' ,
    gameRules: 'The game takes place in a medieval fantasy setting. NPCs should respond appropriately to the time period and setting.'
  });

  const [expandedPanel, setExpandedPanel] = useState<string | false>(() => {
    if (typeof window === 'undefined') return 'agent-network';
    const saved = localStorage.getItem('adminPanelExpanded');
    if (saved === null) return 'agent-network';
    return saved === 'false' ? false : saved;
  });

  const [network, setNetwork] = useState<AgentNetwork | null>(null);
  const [loadingNetwork, setLoadingNetwork] = useState(false);
  const [savingNetwork, setSavingNetwork] = useState(false);
  const [experiments, setExperiments] = useState<any | null>(null);
  const [applyingVariant, setApplyingVariant] = useState<string | null>(null);
  const [rawSettings, setRawSettings] = useState<string>('');
  const [settingsError, setSettingsError] = useState<string | null>(null);
  const [userId, setUserId] = useState<string>('');
  const [userExpNo, setUserExpNo] = useState<string>('');
  const [userSessions, setUserSessions] = useState<any[]>([]);
  const [selfRuns, setSelfRuns] = useState<any[]>([]);
  const [metricsList, setMetricsList] = useState<any[]>([]);
  const [metricsSummary, setMetricsSummary] = useState<any | null>(null);
  const [quickTests, setQuickTests] = useState<Array<{ label: string; source_session_id?: string; variant_id?: string }>>([]);
  const [allSessions, setAllSessions] = useState<any[]>([]);
  const [dbInfo, setDbInfo] = useState<{ paths?: any, counts?: any } | null>(null);
  const [switchUserId, setSwitchUserId] = useState<string>("");
  const [userStats, setUserStats] = useState<any | null>(null);

  // Load current network and prompts when panel opens
  useEffect(() => {
    let mounted = true;
    if (!open) return;
    (async () => {
      try {
        setLoadingNetwork(true);
        const net = await getNetwork();
        if (mounted) setNetwork(net as AgentNetwork);
      } catch (e) {
        console.warn('Failed to load network, using mock:', e);
        if (mounted) setNetwork(mockAgentNetwork as unknown as AgentNetwork);
      } finally {
        setLoadingNetwork(false);
      }
      // Load prompts from settings if present
      try {
        const res = await fetchSettings();
        const p = (res as any)?.settings?.prompts;
        if (mounted && p && typeof p === 'object') {
          setPrompts(prev => ({
            systemPrompt: p.systemPrompt ?? prev.systemPrompt,
            npcPersonalities: { ...prev.npcPersonalities, ...(p.npcPersonalities || {}) },
            gameRules: p.gameRules ?? prev.gameRules,
            experimentGuide: p.experimentGuide ?? prev.experimentGuide,
          }));
        }
        // Load quick tests from settings
        const qt = ((res as any)?.settings?.ui?.quick_tests || []) as any[];
        if (mounted && Array.isArray(qt)) {
          setQuickTests(qt.map((x: any) => ({ label: String(x.label || 'Test'), source_session_id: x.source_session_id, variant_id: x.variant_id })));
        }
        // Keep a raw JSON editor in sync for advanced settings
        if (mounted) {
          try {
            setRawSettings(JSON.stringify((res as any)?.settings ?? {}, null, 2));
          } catch {}
        }
      } catch (e) {
        console.warn('Failed to load prompts from settings:', e);
      }
      // Load experiments config
      try {
        const exp = await fetchExperiments();
        if (mounted) setExperiments(exp);
      } catch (e) {
        console.warn('Failed to load experiments config:', e);
      }

      // Load user id and sessions
      try {
        const uid = await ensureUserId();
        if (mounted) setUserId(uid);
        const us = await listSessionsFiltered({ user_id: uid, exp_type: 'user' });
        if (mounted) setUserSessions(Array.isArray(us) ? us : []);
        const sr = await listSessionsFiltered({ exp_type: 'self' });
        if (mounted) setSelfRuns(Array.isArray(sr) ? sr : []);
        // All sessions for admin dropdown: use base dataset (frozen)
        const all = await listBaseSessionsFiltered({ role: 'admin', exp_type: 'self' });
        if (mounted) setAllSessions(Array.isArray(all) ? all : []);
      } catch (e) {
        console.warn('Failed to load sessions:', e);
      }
      // Load metrics list (optional)
      try {
        const ml = await listMetrics();
        if (mounted) setMetricsList(Array.isArray(ml) ? ml : []);
      } catch (e) {
        console.warn('Failed to load metrics list:', e);
      }

      // Admin DB info (main/checkpoint paths + counts)
      try {
        const res = await fetch('/api/admin/db_info');
        const info = await res.json();
        if (mounted) setDbInfo(info);
      } catch (e) {
        console.warn('Failed to get db info', e);
      }

      // User stats
      try {
        const res = await fetch('/api/user/stats');
        const stats = await res.json();
        if (mounted) setUserStats(stats);
      } catch (e) {
        console.warn('Failed to fetch user stats', e);
      }
    })();
    return () => { mounted = false; };
  }, [open]);

  const handlePromptChange = (category: string, value: string, npcId?: string) => {
    if (npcId) {
      setPrompts(prev => ({
        ...prev,
        npcPersonalities: {
          ...prev.npcPersonalities,
          [npcId]: value
        }
      }));
    } else {
      setPrompts(prev => ({
        ...prev,
        [category]: value
      }));
    }
  };

  const handlePanelChange = (panel: string) => (
    _: React.SyntheticEvent,
    isExpanded: boolean
  ) => {
    const next = isExpanded ? panel : false;
    setExpandedPanel(next);
    try {
      localStorage.setItem('adminPanelExpanded', String(next));
    } catch {}
  };

  const handleSave = async () => {
    try {
      // Fetch current settings, merge prompts, and save
      const res = await fetchSettings();
      const current = (res as any)?.settings || {};
      const next = { ...current, prompts: { ...(current.prompts || {}), ...prompts }, ui: { ...(current.ui || {}), quick_tests: quickTests } };
      await saveSettings(next);
      console.log('Prompts saved to backend settings');
      onClose();
    } catch (e) {
      console.warn('Failed to save prompts:', e);
    }
  };

  const handleSendNetworkToServer = async (networkData: any) => {
    try {
      setSavingNetwork(true);
      await saveNetwork(networkData);
      console.log('Network saved to backend');
    } catch (e) {
      console.warn('Failed to save network:', e);
    } finally {
      setSavingNetwork(false);
    }
  };

  const handleAgentNetworkChange = (network: AgentNetwork) => {
    setNetwork(network);
    console.log('Agent network changed:', network);
  };

  const handleAgentNetworkExport = async (network: AgentNetwork) => {
    console.log('Exporting agent network:', network);
    try {
      setSavingNetwork(true);
      await saveNetwork(network);
      console.log('Agent network configuration sent to server');
    } catch (e) {
      console.warn('Failed to export network:', e);
    } finally {
      setSavingNetwork(false);
    }
  };

  const handleValidationChange = (validation: NetworkValidation) => {
    console.log('Network validation changed:', validation);
  };

  return (
    <Dialog 
      open={open} 
      onClose={onClose}
      maxWidth="xl"
      fullWidth
      scroll="paper"
      fullScreen={fullScreen}
      className="backdrop-blur-sm"
    >
      <DialogTitle sx={{ position: 'sticky', top: 0, zIndex: 1, bgcolor: 'background.paper' }}>
        <Stack direction="row" alignItems="center" justifyContent="space-between">
          <Stack direction="row" alignItems="center" spacing={1}>
            <SettingsOutlinedIcon />
            <Typography variant="h2">
              Admin Panel
            </Typography>
          </Stack>
          <IconButton onClick={onClose} size="small">
            <CloseOutlinedIcon />
          </IconButton>
        </Stack>
      </DialogTitle>

      <DialogContent sx={{ maxHeight: { xs: '80vh', md: '75vh' }, overflow: 'auto' }}>
        <Stack spacing={2} className="mt-2">
          {/* Hierarchical Agent Network Builder */}
          <Accordion 
            expanded={expandedPanel === 'agent-network'} 
            onChange={handlePanelChange('agent-network')}
            sx={{ mb: 2 }}
          >
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="h6">Hierarchical Agent Network</Typography>
            </AccordionSummary>
            <AccordionDetails sx={{ p: 0, overflow: 'hidden' }}>
              <Box 
                sx={{ 
                  height: { xs: 420, sm: 520, md: 600, lg: 720 },
                  position: 'relative',
                  overflow: 'hidden',
                }}
              >
                <AgentNetworkBuilder
                  initialNetwork={network || (mockAgentNetwork as unknown as AgentNetwork)}
                  availableTemplates={mockAgentLibrary}
                  onNetworkChange={handleAgentNetworkChange}
                  onExportNetwork={handleAgentNetworkExport}
                  onValidationChange={handleValidationChange}
                  maxAgents={20}
                  maxConnections={50}
                />
              </Box>
            </AccordionDetails>
          </Accordion>

          {/* Quick Tests (Header Buttons) */}
          <Accordion
            expanded={expandedPanel === 'quick-tests'}
            onChange={handlePanelChange('quick-tests')}
          >
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="h6">Quick Tests (Header Buttons)</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Stack spacing={1}>
                <Typography variant="body2">Auto-populate from frozen base sessions:</Typography>
                <Stack direction="row" spacing={1} alignItems="center">
                  <TextField size="small" label="Experiment name contains" sx={{ width: 240 }} id="qt-expname-filter" />
                  <TextField size="small" label="Variant contains" sx={{ width: 220 }} id="qt-variant-filter" />
                  <Button size="small" variant="outlined" onClick={async () => {
                    try {
                      const expName = (document.getElementById('qt-expname-filter') as HTMLInputElement)?.value || '';
                      const variant = (document.getElementById('qt-variant-filter') as HTMLInputElement)?.value || '';
                      // Fetch frozen sessions and build quick tests
                      const frozen = await listBaseSessionsFiltered({ role: 'admin', exp_type: 'self', experiment_name: expName || undefined, variant_id: variant || undefined });
                      const tests = (Array.isArray(frozen) ? frozen : []).slice(0, 8).map((s: any, i: number) => ({
                        label: s?.experiment?.variant_id ? `${s.experiment.variant_id}` : `Test ${i + 1}`,
                        source_session_id: s.session_id
                      }));
                      setQuickTests(tests);
                    } catch (e) {
                      console.warn('Auto-populate Quick Tests failed', e);
                    }
                  }}>Populate</Button>
                </Stack>
                {quickTests.map((t, idx) => (
                  <Stack key={idx} direction="row" spacing={1} alignItems="center">
                    <TextField size="small" label="Label" value={t.label}
                      onChange={(e) => setQuickTests(prev => prev.map((p, i) => i === idx ? { ...p, label: e.target.value } : p))}
                      sx={{ width: 180 }}
                    />
                    <TextField size="small" label="Source Session" select value={t.source_session_id || ''}
                      onChange={(e) => setQuickTests(prev => prev.map((p, i) => i === idx ? { ...p, source_session_id: e.target.value } : p))}
                      sx={{ flex: 1 }}
                    >
                      {allSessions.map((s: any) => (
                        <MenuItem key={s.session_id} value={s.session_id}>
                          {s.session_id}
                        </MenuItem>
                      ))}
                    </TextField>
                    <IconButton size="small" onClick={() => setQuickTests(prev => prev.filter((_, i) => i !== idx))}>
                      <CloseOutlinedIcon fontSize="small" />
                    </IconButton>
                  </Stack>
                ))}
                <Button size="small" variant="outlined" onClick={() => setQuickTests(prev => [...prev, { label: `Test ${prev.length + 1}`, source_session_id: '' }])}>Add Test</Button>
                <Typography variant="caption" color="text.secondary">Provide a label and a source session ID to clone when clicked. Save to persist.</Typography>
              </Stack>
            </AccordionDetails>
          </Accordion>

          {/* Experiment Guide Editor */}
          <Accordion
            expanded={expandedPanel === 'experiment-guide'}
            onChange={handlePanelChange('experiment-guide')}
            sx={{ mb: 2 }}
          >
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="h6">Experiment Guide</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <TextField
                label="Guide Content"
                value={prompts.experimentGuide}
                onChange={(e) => handlePromptChange('experimentGuide', e.target.value)}
                fullWidth
                multiline
                minRows={6}
              />
              <Typography variant="caption" color="text.secondary">
                This content appears in the user-facing guide modal.
              </Typography>
            </AccordionDetails>
          </Accordion>

          {/* Legacy NPC Network Diagram */}
          <Accordion 
            expanded={expandedPanel === 'npc-network'} 
            onChange={handlePanelChange('npc-network')}
          >
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="h6">NPC Connection Overview</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <NetworkDiagram 
                npcs={npcs} 
                onSendToServer={handleSendNetworkToServer}
              />
            </AccordionDetails>
          </Accordion>

          {/* System Prompt */}
          <Accordion 
            expanded={expandedPanel === 'system'} 
            onChange={handlePanelChange('system')}
          >
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="h6">System Prompt</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <TextField
                label="System Prompt"
                value={prompts.systemPrompt}
                onChange={(e) => handlePromptChange('systemPrompt', e.target.value)}
                fullWidth
                multiline
                rows={4}
                helperText="Base instructions for all NPCs"
              />
            </AccordionDetails>
          </Accordion>

          {/* NPC Personalities */}
          <Accordion 
            expanded={expandedPanel === 'npcs'} 
            onChange={handlePanelChange('npcs')}
          >
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="h6">NPC Personalities</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Stack spacing={3}>
                {Object.entries(prompts.npcPersonalities).map(([npcId, prompt]) => (
                  <div key={npcId}>
                    <Typography variant="subtitle2" className="mb-2">
                      {npcId === 'npc-1' ? 'Sir Gareth the Bold' :
                       npcId === 'npc-2' ? 'Morgana the Wise' :
                       npcId === 'npc-3' ? 'Finn the Merchant' : npcId}
                    </Typography>
                    <TextField
                      value={prompt}
                      onChange={(e) => handlePromptChange('npcPersonalities', e.target.value, npcId)}
                      fullWidth
                      multiline
                      rows={3}
                      placeholder="Define this NPC's personality and speaking style..."
                    />
                  </div>
                ))}
              </Stack>
            </AccordionDetails>
          </Accordion>

          {/* Game Rules */}
          <Accordion 
            expanded={expandedPanel === 'rules'} 
            onChange={handlePanelChange('rules')}
          >
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="h6">Game Rules & Setting</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <TextField
                label="Game Rules"
                value={prompts.gameRules}
                onChange={(e) => handlePromptChange('gameRules', e.target.value)}
                fullWidth
                multiline
                rows={4}
                helperText="Define the game world, rules, and setting constraints"
              />
            </AccordionDetails>
          </Accordion>

          {/* Experiments */}
          <Accordion 
            expanded={expandedPanel === 'experiments'} 
            onChange={handlePanelChange('experiments')}
          >
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="h6">Experiments</Typography>
            </AccordionSummary>
            <AccordionDetails>
              {!experiments ? (
                <Typography variant="body2">Loading experiments…</Typography>
              ) : (
                <Stack spacing={2}>
                  {Object.entries<any>(experiments.experiments || {}).map(([key, exp]) => (
                    <Box key={key} sx={{ p: 1, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
                      <Typography variant="subtitle1">{exp.name}</Typography>
                      <Typography variant="body2" color="text.secondary">{exp.description}</Typography>
                      <Stack direction="row" spacing={1} sx={{ mt: 1, flexWrap: 'wrap' }}>
                        {(exp.variants || []).map((v: any) => (
                          <Button 
                            key={v.id}
                            size="small"
                            variant="outlined"
                            disabled={applyingVariant === v.id}
                            onClick={async () => {
                              try {
                                setApplyingVariant(v.id);
                                await applyExperiment(v.id);
                              } catch (e) {
                                console.warn('Apply experiment failed', e);
                              } finally {
                                setApplyingVariant(null);
                              }
                            }}
                          >
                            Apply: {v.name}
                          </Button>
                        ))}
                      </Stack>
                    </Box>
                  ))}
                </Stack>
              )}
            </AccordionDetails>
          </Accordion>

          {/* User Sessions (Read-Only) */}
          <Accordion
            expanded={expandedPanel === 'user-sessions-ro'}
            onChange={handlePanelChange('user-sessions-ro')}
          >
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="h6">User Sessions (Current DB)</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Stack spacing={1}>
                {userSessions.length === 0 ? (
                  <Typography variant="body2">No user sessions in current dataset.</Typography>
                ) : (
                  userSessions.slice(0, 25).map((s: any) => (
                    <Typography key={`ro-${s.session_id}`} variant="body2">
                      {s.session_id} • Day {s.current_day} • {String(s.current_time_period).toLowerCase()} • exp {s?.experiment?.experiment_no ?? '-'}
                    </Typography>
                  ))
                )}
              </Stack>
            </AccordionDetails>
          </Accordion>

          {/* Dataset */}
          <Accordion
            expanded={expandedPanel === 'dataset'}
            onChange={handlePanelChange('dataset')}
          >
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="h6">Dataset</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Stack spacing={1}>
                <Typography variant="body2">Main DB (active): {dbInfo?.paths?.main || 'unknown'}</Typography>
                {dbInfo?.paths && (
                  <>
                    <Typography variant="body2">Checkpoint DB (read-only): {dbInfo.paths.checkpoints}</Typography>
                    <Typography variant="caption" color="text.secondary">Tables: {Object.entries(dbInfo.counts || {}).map(([k,v]) => `${k}:${v}`).join(' • ')}</Typography>
                  </>
                )}
                <Typography variant="caption" color="text.secondary">Centralized main DB in use. Per-user dataset switching is disabled.</Typography>
              </Stack>
            </AccordionDetails>
          </Accordion>

          {/* Game Settings (Raw JSON) */}
          <Accordion 
            expanded={expandedPanel === 'settings-raw'} 
            onChange={handlePanelChange('settings-raw')}
          >
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="h6">Game Settings (Raw)</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Stack spacing={1}>
                {settingsError && <Typography color="error" variant="body2">{settingsError}</Typography>}
                <TextField
                  label="Settings JSON"
                  value={rawSettings}
                  onChange={(e) => setRawSettings(e.target.value)}
                  fullWidth
                  multiline
                  minRows={8}
                />
                <Stack direction="row" spacing={1}>
                  <Button onClick={async () => {
                    try {
                      setSettingsError(null);
                      const parsed = JSON.parse(rawSettings || '{}');
                      await saveSettings(parsed);
                    } catch (e: any) {
                      setSettingsError(e?.message || 'Invalid JSON');
                    }
                  }} variant="contained">Save Settings</Button>
                  <Button onClick={async () => {
                    try {
                      const res = await fetchSettings();
                      setRawSettings(JSON.stringify((res as any)?.settings ?? {}, null, 2));
                      setSettingsError(null);
                    } catch (e) {
                      setSettingsError('Failed to reload settings');
                    }
                  }}>Reload</Button>
                </Stack>
              </Stack>
            </AccordionDetails>
          </Accordion>

          {/* User Experiments */}
          <Accordion 
            expanded={expandedPanel === 'user-experiments'} 
            onChange={handlePanelChange('user-experiments')}
          >
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="h6">User Experiments</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Stack spacing={2}>
                <Typography variant="body2">User ID: {userId || 'n/a'}</Typography>
                <Stack direction="row" spacing={1} alignItems="center">
                  <TextField
                    label="Experiment No (filter)"
                    value={userExpNo}
                    onChange={(e) => setUserExpNo(e.target.value)}
                    size="small"
                    sx={{ width: 220 }}
                  />
                  <Button size="small" onClick={async () => {
                    try {
                      const uid = userId || await ensureUserId();
                      const exp_no = userExpNo.trim() ? Number(userExpNo) : undefined;
                      const us = await listSessionsFiltered({ user_id: uid, exp_type: 'user', experiment_no: exp_no });
                      setUserSessions(Array.isArray(us) ? us : []);
                    } catch (e) {
                      console.warn('Reload user sessions failed', e);
                    }
                  }}>Reload</Button>
                </Stack>
                <Stack spacing={1}>
                  {userSessions.length === 0 ? (
                    <Typography variant="body2">No user experiment sessions.</Typography>
                  ) : userSessions.map((s: any) => (
                    <Stack key={s.session_id} direction="row" spacing={1} alignItems="center" justifyContent="space-between">
                      <Typography variant="body2">
                        {s.session_id} • Day {s.current_day} • {String(s.current_time_period).toLowerCase()} • exp {s?.experiment?.experiment_no ?? '-'}
                      </Typography>
                      <Button size="small" variant="outlined" onClick={() => {
                        try {
                          localStorage.setItem('session_id', s.session_id);
                          onClose();
                          window.location.reload();
                        } catch (e) { console.warn('Open session failed', e); }
                      }}>Use</Button>
                    </Stack>
                  ))}
                </Stack>
              </Stack>
            </AccordionDetails>
          </Accordion>

          {/* Scenarios (Self-Run Sessions) */}
          <Accordion 
            expanded={expandedPanel === 'self-runs'} 
            onChange={handlePanelChange('self-runs')}
          >
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="h6">Scenarios (Self-Run)</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Stack spacing={1}>
                {selfRuns.length === 0 ? (
                  <Typography variant="body2">No self-run sessions found.</Typography>
                ) : selfRuns.map((s: any, idx: number) => (
                  <Stack key={s.session_id} direction="row" spacing={1} alignItems="center" justifyContent="space-between">
                    <Typography variant="body2">
                      {s.session_id} • Day {s.current_day} • {String(s.current_time_period).toLowerCase()} • {s?.experiment?.variant_id ?? ''}
                    </Typography>
                    <Stack direction="row" spacing={1}>
                      <TextField size="small" label="Exp No" sx={{ width: 100 }}
                        value={userExpNo}
                        onChange={(e) => setUserExpNo(e.target.value)}
                      />
                      <Button size="small" variant="outlined" onClick={async () => {
                        try {
                          const uid = userId || await ensureUserId();
                          const expNo = Number(userExpNo || (idx + 1));
                          const res = await cloneSessionForUser(s.session_id, uid, expNo);
                          if (res?.session_id) {
                            localStorage.setItem('session_id', res.session_id);
                            onClose();
                            window.location.reload();
                          }
                        } catch (e) { console.warn('Clone to user failed', e); }
                      }}>Clone as User</Button>
                    </Stack>
                  </Stack>
                ))}
              </Stack>
            </AccordionDetails>
          </Accordion>

          {/* Metrics */}
          <Accordion 
            expanded={expandedPanel === 'metrics'} 
            onChange={handlePanelChange('metrics')}
          >
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="h6">Metrics</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Stack spacing={2}>
                {metricsList.length === 0 ? (
                  <Typography variant="body2">No metrics found.</Typography>
                ) : (
                  metricsList.slice(0, 20).map((m: any) => (
                    <Stack key={m.file} direction="row" spacing={1} alignItems="center" justifyContent="space-between">
                      <Typography variant="body2">
                        {m.type.toUpperCase()} • {m.experiment_id}_{m.session_id} • {new Date(m.modified * 1000).toLocaleString()}
                      </Typography>
                      {m.type === 'json' && (
                        <Button size="small" variant="outlined" onClick={async () => {
                          try {
                            const sum = await fetchMetricsSummary(m.experiment_id, m.session_id);
                            setMetricsSummary(sum);
                          } catch (e) { console.warn('Fetch metrics summary failed', e); }
                        }}>Summary</Button>
                      )}
                    </Stack>
                  ))
                )}
                {metricsSummary && (
                  <Box sx={{ p: 1, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
                    <Typography variant="subtitle2">Summary ({metricsSummary.experiment_id}_{metricsSummary.session_id})</Typography>
                    <Typography variant="body2">{JSON.stringify(metricsSummary.summary)}</Typography>
                    <Typography variant="caption" color="text.secondary">Last 10 metrics: {metricsSummary.last_metrics?.length || 0}</Typography>
                  </Box>
                )}
              </Stack>
            </AccordionDetails>
          </Accordion>

          {/* User Stats */}
          <Accordion
            expanded={expandedPanel === 'user-stats'}
            onChange={handlePanelChange('user-stats')}
          >
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="h6">User Stats</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Stack spacing={1}>
                <Stack direction="row" spacing={1} alignItems="center">
                  <Button size="small" variant="outlined" onClick={async () => {
                    try {
                      const res = await fetch('/api/user/stats');
                      const stats = await res.json();
                      setUserStats(stats);
                    } catch (e) { console.warn('Reload stats failed', e); }
                  }}>Reload</Button>
                  <Button size="small" variant="outlined" onClick={() => {
                    window.open('/api/user/stats_csv?view=session', '_blank');
                  }}>Export Sessions CSV</Button>
                  <Button size="small" variant="outlined" onClick={() => {
                    window.open('/api/user/stats_csv?view=checkpoint', '_blank');
                  }}>Export Checkpoints CSV</Button>
                </Stack>
                {userStats ? (
                  <>
                    <Typography variant="subtitle2">Sessions</Typography>
                    <Stack spacing={0.5}>
                      {Object.entries<any>(userStats.sessions || {}).slice(0, 10).map(([sid, s]) => (
                        <Typography key={sid} variant="body2">
                          {sid} • time {Math.round((s.total_time_ms||0)/1000)}s • user msgs {s.num_user_messages||0} • npc msgs {s.num_npc_messages||0} • keys {s.num_keystrokes||0} • inTok {s.approx_tokens_in||0} • outTok {s.approx_tokens_out||0}
                        </Typography>
                      ))}
                    </Stack>
                    <Typography variant="subtitle2" sx={{ mt: 1 }}>Recent Events</Typography>
                    <Stack spacing={0.5}>
                      {(userStats.events || []).slice(-10).reverse().map((e: any, idx: number) => (
                        <Typography key={idx} variant="caption" color="text.secondary">
                          {e.time} • {e.type} • {e.session_id || e.target_session_id || ''}
                        </Typography>
                      ))}
                    </Stack>
                  </>
                ) : (
                  <Typography variant="body2">No stats available.</Typography>
                )}
              </Stack>
            </AccordionDetails>
          </Accordion>
        </Stack>
      </DialogContent>

    <DialogActions className="p-6">
      <Button onClick={onClose} color="secondary">
        Cancel
      </Button>
      <Button 
        onClick={async () => {
          try {
            await resetSettings();
            // reload network after reset
            const net = await getNetwork();
            setNetwork(net as AgentNetwork);
            console.log('Settings reset to defaults');
          } catch (e) {
            console.warn('Failed to reset settings:', e);
          }
        }}
        color="warning"
      >
        Reset Defaults
      </Button>
      <Button
        onClick={async () => {
          try {
            const res = await reinitDatabase();
            console.log('DB reinitialized', res);
            alert('Database cleared. Reload the page and create a fresh session.');
          } catch (e) {
            console.warn('Failed to reinitialize DB:', e);
          }
        }}
        color="error"
      >
        Reinit Database
      </Button>
      <Button 
        onClick={handleSave}
        variant="contained"
        color="primary"
      >
        Save Prompts
      </Button>
    </DialogActions>
  </Dialog>
);
};
