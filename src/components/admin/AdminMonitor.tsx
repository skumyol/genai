import React, { useEffect, useMemo, useState } from 'react';
import {
  AppBar,
  Box,
  Button,
  CircularProgress,
  Container,
  Divider,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Tab,
  Tabs,
  Toolbar,
  Typography,
  Paper,
} from '@mui/material';
import { ensureUserId, listSessions, getSession } from '../../api/client';

// Lightweight admin monitor to visualize session database state
// Access via: http://localhost:5173/#admin

type SessionSummary = {
  id?: string;
  session_id?: string;
  name?: string;
  status?: string;
  current_day?: number;
  time_period?: string;
  game_state?: string;
  created_at?: string;
  updated_at?: string;
  [k: string]: any;
};

const Section: React.FC<{ title: string; children?: React.ReactNode }> = ({ title, children }) => (
  <Paper variant="outlined" sx={{ p: 2 }}>
    <Typography variant="h6" gutterBottom>{title}</Typography>
    <Divider sx={{ mb: 2 }} />
    {children}
  </Paper>
);

const PrettyJson: React.FC<{ value: any }> = ({ value }) => (
  <Box component="pre" sx={{
    p: 2,
    bgcolor: 'background.paper',
    borderRadius: 1,
    overflow: 'auto',
    maxHeight: 480,
    fontSize: 12,
  }}>
    {JSON.stringify(value, null, 2)}
  </Box>
);

export const AdminMonitor: React.FC = () => {
  const [userId, setUserId] = useState<string>('');
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string>('');
  const [sessionData, setSessionData] = useState<any | null>(null);
  const [tab, setTab] = useState(0);
  const [loading, setLoading] = useState(false);

  // bootstrap user id and sessions
  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const uid = await ensureUserId();
        if (!mounted) return;
        setUserId(uid);
        const list = await listSessions(uid);
        if (!mounted) return;
        setSessions(list || []);
        // auto-select last session
        if (list && list.length) {
          const last = (list[list.length - 1] as any);
          const sid = String(last.session_id || last.id || '');
          setSelectedSessionId(sid);
        }
      } catch (e) {
        console.warn('AdminMonitor bootstrap failed:', e);
      }
    })();
    return () => { mounted = false; };
  }, []);

  const loadSession = async (sid: string) => {
    if (!sid) return;
    setLoading(true);
    try {
      const data = await getSession(sid);
      setSessionData(data);
    } catch (e) {
      console.warn('Failed to load session', sid, e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (selectedSessionId) {
      loadSession(selectedSessionId);
    }
  }, [selectedSessionId]);

  const overview = useMemo(() => {
    const d = sessionData || {};
    return {
      session_id: d.session_id ?? d.id,
      name: d.name,
      status: d.status ?? d.game_state,
      current_day: d.current_day,
      time_period: d.time_period || d.current_time_period,
      updated_at: d.updated_at || d.timestamp || null,
      num_messages: Array.isArray(d.messages) ? d.messages.length : 0,
      character: d.character || null,
    };
  }, [sessionData]);

  return (
    <Box sx={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <AppBar position="static" color="primary">
        <Toolbar>
          <Typography variant="h6" sx={{ flex: 1 }}>Admin Monitor</Typography>
          <Stack direction="row" spacing={1}>
            <Button color="inherit" onClick={() => selectedSessionId && loadSession(selectedSessionId)} disabled={!selectedSessionId || loading}>
              Refresh
            </Button>
          </Stack>
        </Toolbar>
      </AppBar>

      <Container sx={{ py: 2, flex: 1, display: 'flex', flexDirection: 'column', gap: 2, overflow: 'hidden' }}>
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} alignItems={{ xs: 'stretch', md: 'center' }}>
          <FormControl size="small" sx={{ minWidth: 280 }}>
            <InputLabel id="session-select-label">Session</InputLabel>
            <Select
              labelId="session-select-label"
              label="Session"
              value={selectedSessionId}
              onChange={(e) => setSelectedSessionId(String(e.target.value))}
            >
              {sessions.map((s: any) => {
                const sid = String(s.session_id || s.id);
                const name = s.name || sid;
                return <MenuItem key={sid} value={sid}>{name}</MenuItem>;
              })}
            </Select>
          </FormControl>
          <Box sx={{ flex: 1 }} />
          {loading && (
            <Stack direction="row" alignItems="center" spacing={1}>
              <CircularProgress size={18} />
              <Typography variant="body2">Loading…</Typography>
            </Stack>
          )}
        </Stack>

        <Paper variant="outlined" sx={{ flex: 1, minHeight: 400, display: 'flex', flexDirection: 'column' }}>
          <Tabs value={tab} onChange={(_, v) => setTab(v)} variant="scrollable" allowScrollButtonsMobile>
            <Tab label="Overview" />
            <Tab label="Dialogues" />
            <Tab label="NPC Memories" />
            <Tab label="Raw JSON" />
          </Tabs>
          <Divider />
          <Box sx={{ p: 2, flex: 1, overflow: 'auto' }}>
            {tab === 0 && (
              <Stack spacing={2}>
                <Section title="Session Overview">
                  <PrettyJson value={overview} />
                </Section>
                {sessionData?.game_state && (
                  <Section title="Game State">
                    <PrettyJson value={sessionData.game_state} />
                  </Section>
                )}
              </Stack>
            )}
            {tab === 1 && (
              <Stack spacing={2}>
                <Section title="Dialogues">
                  {Array.isArray(sessionData?.dialogues) ? (
                    <PrettyJson value={sessionData.dialogues} />
                  ) : (
                    <Typography variant="body2">No dialogues available on this endpoint. You may need to expand the backend response or add a specific dialogues fetch.</Typography>
                  )}
                </Section>
              </Stack>
            )}
            {tab === 2 && (
              <Stack spacing={2}>
                <Section title="NPC Memories">
                  {Array.isArray(sessionData?.npc_memories) || sessionData?.npc_memory ? (
                    <PrettyJson value={sessionData.npc_memories || sessionData.npc_memory} />
                  ) : (
                    <Typography variant="body2">No NPC memory data in the current response. You may need to fetch per-NPC memory via dedicated endpoints.</Typography>
                  )}
                </Section>
              </Stack>
            )}
            {tab === 3 && (
              <PrettyJson value={sessionData ?? { note: 'Select a session to view raw JSON.' }} />
            )}
          </Box>
        </Paper>
      </Container>
    </Box>
  );
};
