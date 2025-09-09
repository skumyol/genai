import React, { useEffect, useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  List,
  ListItemButton,
  ListItemText,
  Stack,
  IconButton,
  Typography,
  CircularProgress
} from '@mui/material';
import RefreshOutlinedIcon from '@mui/icons-material/RefreshOutlined';
import HistoryOutlinedIcon from '@mui/icons-material/HistoryOutlined';
import { ensureUserId, switchUserDataset, listSessions, createSession, saveSession, getUserTestSession, setActiveSession } from '../../api/client';

interface LoadSessionModalProps {
  open: boolean;
  onClose: () => void;
  onLoad: (sessionId: string) => void | Promise<void>;
}

export const LoadSessionModal: React.FC<LoadSessionModalProps> = ({ open, onClose, onLoad }) => {
  const [sessions, setSessions] = useState<any[]>([]);
  // No longer surface self-run scenarios here; use header Quick Tests instead
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const userId = await ensureUserId();
      const data = await listSessions(userId);
      setSessions(data);
    } catch (e: any) {
      setError(e?.message || 'Failed to load sessions');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!open) return;
    fetchData();
  }, [open]);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        <Stack direction="row" alignItems="center" justifyContent="space-between">
          <Stack direction="row" alignItems="center" spacing={1}>
            <HistoryOutlinedIcon />
            <Typography variant="h6">Load Session</Typography>
          </Stack>
          <IconButton onClick={fetchData} disabled={loading} size="small" title="Refresh">
            <RefreshOutlinedIcon />
          </IconButton>
        </Stack>
      </DialogTitle>
      <DialogContent dividers sx={{ minHeight: 260 }}>
        {/* Experiment selection first */}
        <Stack spacing={2} sx={{ mb: 2 }}>
          <Typography variant="subtitle1">Create Your Session (Fresh World)</Typography>
          <Stack spacing={1}>
            <Button
              variant="contained"
              size="small"
              onClick={async () => {
                try {
                  setLoading(true);
                  const userId = await ensureUserId();
                  try { await switchUserDataset(userId); } catch {}
                  // Create or get Test 0 session
                  const test0SessionId = await getUserTestSession(userId, 0);
                  await setActiveSession(userId, test0SessionId);
                  await onLoad(test0SessionId);
                  onClose();
                } catch (e) {
                  setError('Failed to start Test 0');
                } finally {
                  setLoading(false);
                }
              }}
            >
              Test 0 — Fresh World
            </Button>
          </Stack>
        </Stack>

        {/* Base experiments from checkpoints (4 sessions) */}
        <Stack spacing={2} sx={{ mb: 2 }}>
          <Typography variant="subtitle1">Use Base Experiments (Clone to Your Session)</Typography>
          <Typography variant="body2" color="text.secondary">
            These scenarios are cloned from the frozen checkpoints database into your personal session.
          </Typography>
          <Stack direction="row" spacing={1} flexWrap="wrap">
            {[
              { label: 'GPT‑5 — Rep ON', sid: 'exp_gpt5_all_gpt5_rep_on', idx: 1 },
              { label: 'GPT‑5 — Rep OFF', sid: 'exp_gpt5_all_gpt5_rep_off', idx: 2 },
              { label: 'Qwen8B — Rep ON', sid: 'exp_qwen8b_all_qwen8b_rep_on', idx: 3 },
              { label: 'Qwen8B — Rep OFF', sid: 'exp_qwen8b_all_qwen8b_rep_off', idx: 4 },
            ].map((opt) => (
              <Button
                key={opt.sid}
                variant="outlined"
                size="small"
                disabled={loading}
                onClick={async () => {
                  try {
                    setLoading(true);
                    setError(null);
                    const userId = await ensureUserId();
                    const targetId = await getUserTestSession(userId, opt.idx, opt.sid);
                    await setActiveSession(userId, targetId);
                    await onLoad(targetId);
                    onClose();
                  } catch (e) {
                    setError(`Failed to load ${opt.label}`);
                  } finally {
                    setLoading(false);
                  }
                }}
              >
                {opt.label}
              </Button>
            ))}
          </Stack>
        </Stack>

        {loading ? (
          <Stack alignItems="center" justifyContent="center" sx={{ py: 6 }}>
            <CircularProgress size={24} />
          </Stack>
        ) : error ? (
          <Typography color="error" variant="body2">{error}</Typography>
        ) : sessions.length > 0 ? (
          <List>
            {sessions.map((s) => {
              const id = s.session_id ?? s.id;
              const updated = s.last_updated ?? s.updated_at;
              const day = s.current_day ?? s.day ?? 1;
              const period = String(s.current_time_period ?? s.time_period ?? 'morning');
              const title = s.session_summary || s.name || id;
              const status = s.status || 'stopped';
              return (
                <ListItemButton key={id} onClick={() => onLoad(id)}>
                  <ListItemText
                    primary={title}
                    secondary={`Updated: ${updated ? new Date(updated).toLocaleString() : 'n/a'} • Day ${day} • ${period}` + (status ? ` • ${status}` : '')}
                  />
                </ListItemButton>
              );
            })}
          </List>
        ) : null}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} color="secondary">Close</Button>
      </DialogActions>
    </Dialog>
  );
};
