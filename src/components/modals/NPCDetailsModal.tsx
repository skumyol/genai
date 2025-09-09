import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Stack,
  IconButton,
  Typography,
  Avatar,
  Card,
  CardContent,
  Chip,
  Box
} from '@mui/material';
import CloseOutlinedIcon from '@mui/icons-material/CloseOutlined';
import ShieldOutlinedIcon from '@mui/icons-material/ShieldOutlined';
import SportsEsportsOutlinedIcon from '@mui/icons-material/SportsEsportsOutlined';
import { NPC } from '../../types/schema';
import { StatusBadge } from '../common/StatusBadge';
import { formatNPCStatus } from '../../utils/formatters';

interface NPCDetailsModalProps {
  open: boolean;
  onClose: () => void;
  npc: NPC | null;
  onStartChat?: (npcId: string) => void;
}

export const NPCDetailsModal: React.FC<NPCDetailsModalProps> = ({ 
  open, 
  onClose, 
  npc,
  onStartChat 
}) => {
  if (!npc) return null;

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'online':
        return 'success';
      case 'busy':
        return 'warning';
      default:
        return 'error';
    }
  };

  const handleStartChat = () => {
    if (onStartChat && npc.status === 'online') {
      onStartChat(npc.id);
      onClose();
    }
  };

  // Parse role and story from npc.description (format produced in settings mapping: "Role: <role> — <story>")
  const parseRoleAndStory = (desc?: string): { role?: string; story?: string } => {
    if (!desc) return {};
    const parts = desc.split(' — ');
    let role: string | undefined;
    let story: string | undefined;
    if (parts.length) {
      const first = parts[0].trim();
      if (first.toLowerCase().startsWith('role:')) {
        role = first.split(':').slice(1).join(':').trim();
        story = parts.slice(1).join(' — ').trim() || undefined;
      } else {
        story = desc.trim();
      }
    }
    return { role, story };
  };
  const { role, story } = parseRoleAndStory(npc.description);

  return (
    <Dialog 
      open={open} 
      onClose={onClose}
      maxWidth="sm"
      fullWidth
      className="backdrop-blur-sm"
      PaperProps={{
        className: "medieval-shadow retro-border"
      }}
    >
      <DialogTitle>
        <Stack direction="row" alignItems="center" justifyContent="space-between">
          <Stack direction="row" alignItems="center" spacing={2}>
            <ShieldOutlinedIcon className="text-secondary-main" />
            <Typography variant="h2">
              Character Details
            </Typography>
          </Stack>
          <IconButton onClick={onClose} size="small">
            <CloseOutlinedIcon />
          </IconButton>
        </Stack>
      </DialogTitle>

      <DialogContent>
        <Stack spacing={3} className="mt-2">
          {/* Character Header */}
          <Card className="medieval-shadow">
            <CardContent>
              <Stack direction="row" spacing={3} alignItems="center">
                <StatusBadge status={npc.status}>
                  <Avatar 
                    src={npc.avatar} 
                    alt={npc.name}
                    className="w-20 h-20"
                  />
                </StatusBadge>
                <Box className="flex-1">
                  <Typography variant="h3" className="mb-2">
                    {npc.name}
                  </Typography>
                  <Typography variant="body1" color="text.secondary" className="mb-2">
                    {npc.description}
                  </Typography>
                  <Stack direction="row" spacing={1} alignItems="center">
                    <Chip
                      label={formatNPCStatus(npc.status)}
                      color={getStatusColor(npc.status)}
                      size="small"
                      className="pulse-glow"
                    />
                    {role && (
                      <Chip
                        label={`Role: ${role}`}
                        variant="outlined"
                        size="small"
                      />
                    )}
                  </Stack>
                </Box>
              </Stack>
            </CardContent>
          </Card>

          {/* Profile (backend-aligned: Role and Story parsed from description) */}
          {(role || story) && (
            <Card className="medieval-shadow">
              <CardContent>
                <Typography variant="h6" className="mb-2">
                  Profile
                </Typography>
                <Stack spacing={1.5}>
                  {role && (
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        Role
                      </Typography>
                      <Typography variant="body2" className="font-semibold">
                        {role}
                      </Typography>
                    </Box>
                  )}
                  {story && (
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        Story
                      </Typography>
                      <Typography variant="body2">
                        {story}
                      </Typography>
                    </Box>
                  )}
                </Stack>
              </CardContent>
            </Card>
          )}

          {/* Interaction Tips */}
          {npc.status === 'online' && (
            <Card className="bg-success-main/10 border border-success-main/30">
              <CardContent>
                <Typography variant="body2" color="success.main" className="font-semibold mb-1">
                  💬 Ready to Chat
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  This character is available for conversation and may have quests or valuable information to share.
                </Typography>
              </CardContent>
            </Card>
          )}

          {npc.status === 'busy' && (
            <Card className="bg-warning-main/10 border border-warning-main/30">
              <CardContent>
                <Typography variant="body2" color="warning.main" className="font-semibold mb-1">
                  ⏳ Currently Busy
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  This character is occupied with other tasks. Try again later.
                </Typography>
              </CardContent>
            </Card>
          )}

          {npc.status === 'offline' && (
            <Card className="bg-error-main/10 border border-error-main/30">
              <CardContent>
                <Typography variant="body2" color="error.main" className="font-semibold mb-1">
                  💤 Offline
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  This character is not available right now. They may return later.
                </Typography>
              </CardContent>
            </Card>
          )}
        </Stack>
      </DialogContent>

      <DialogActions className="p-6">
        <Button onClick={onClose} color="secondary">
          Close
        </Button>
        {npc.status === 'online' && onStartChat && (
          <Button 
            onClick={handleStartChat}
            variant="contained"
            color="primary"
            startIcon={<SportsEsportsOutlinedIcon />}
          >
            Start Chat
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
};