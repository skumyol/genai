import React from 'react';
import { ListItem, ListItemButton, ListItemAvatar, ListItemText, Avatar, Typography, Stack, Button } from '@mui/material';
import { NPC } from '../../types/schema';
import { StatusBadge } from '../common/StatusBadge';
import { formatNPCStatus } from '../../utils/formatters';

interface NPCListItemProps {
  npc: NPC;
  isSelected: boolean;
  onSelect: (npcId: string) => void;
  onDoubleClick?: (npc: NPC) => void;
  onPlayAs?: (npc: NPC) => void;
  onTalk?: (npc: NPC) => void;
  activePlayerNpcId?: string | null;
  activeTalkTargetId?: string | null;
}

export const NPCListItem: React.FC<NPCListItemProps> = ({ 
  npc, 
  isSelected, 
  onSelect, 
  onDoubleClick,
  onPlayAs,
  onTalk,
  activePlayerNpcId,
  activeTalkTargetId,
}) => {
  const isPlayer = activePlayerNpcId === npc.id;
  const isTalkTarget = activeTalkTargetId === npc.id;
  return (
    <ListItem disablePadding>
      <ListItemButton 
        selected={isSelected}
        onClick={() => onSelect(npc.id)}
        onDoubleClick={() => onDoubleClick?.(npc)}
        className="rounded-lg transition-all hover:scale-[1.02] hover:shadow-lg"
        sx={{
          mb: { xs: 1, sm: 2 },
          py: { xs: 1, sm: 1.5 },
          px: { xs: 1, sm: 2 },
          minHeight: { xs: '60px', sm: '80px' }
        }}
      >
        <ListItemAvatar sx={{ mr: { xs: 1, sm: 2 } }}>
          <StatusBadge status={npc.status}>
            <Avatar 
              src={npc.avatar} 
              alt={npc.name}
              sx={{ 
                width: { xs: 32, sm: 40 }, 
                height: { xs: 32, sm: 40 },
                fontSize: { xs: '0.875rem', sm: '1rem' }
              }}
            />
          </StatusBadge>
        </ListItemAvatar>
        <ListItemText
          primary={
            <Typography 
              variant="body1" 
              className="font-semibold"
              sx={{ 
                fontSize: { xs: '0.875rem', sm: '1rem' },
                fontWeight: { xs: 600, sm: 700 }
              }}
            >
              {npc.name}
            </Typography>
          }
          primaryTypographyProps={{ component: 'span' }}
          secondary={
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <Typography 
                variant="body2" 
                color="text.secondary"
                sx={{ 
                  fontSize: { xs: '0.75rem', sm: '0.875rem' },
                  lineHeight: 1.3,
                  display: '-webkit-box',
                  WebkitLineClamp: { xs: 2, sm: 3 },
                  WebkitBoxOrient: 'vertical',
                  overflow: 'hidden'
                }}
              >
                {npc.description}
              </Typography>
              <Typography 
                variant="caption" 
                color={
                  npc.status === 'online' ? 'success.main' :
                  npc.status === 'busy' ? 'warning.main' : 'error.main'
                }
                className="font-medium"
                sx={{ 
                  fontSize: { xs: '0.625rem', sm: '0.75rem' },
                  display: { xs: 'none', sm: 'block' }
                }}
              >
                {formatNPCStatus(npc.status)}
              </Typography>
              <Stack 
                direction="row" 
                spacing={{ xs: 0.5, sm: 1 }} 
                className="mt-1"
              >
                <Button 
                  size="small" 
                  variant={isPlayer ? 'contained' : 'outlined'} 
                  onClick={(e) => { e.stopPropagation(); onPlayAs?.(npc); }}
                  sx={{
                    fontSize: { xs: '0.625rem', sm: '0.75rem' },
                    minWidth: { xs: '50px', sm: '64px' },
                    py: { xs: 0.25, sm: 0.5 },
                    px: { xs: 0.75, sm: 1 }
                  }}
                >
                  Play as
                </Button>
                <Button 
                  size="small" 
                  variant={isTalkTarget ? 'contained' : 'outlined'} 
                  disabled={!activePlayerNpcId || activePlayerNpcId === npc.id} 
                  onClick={(e) => { e.stopPropagation(); onTalk?.(npc); }}
                  sx={{
                    fontSize: { xs: '0.625rem', sm: '0.75rem' },
                    minWidth: { xs: '40px', sm: '64px' },
                    py: { xs: 0.25, sm: 0.5 },
                    px: { xs: 0.75, sm: 1 }
                  }}
                >
                  Talk
                </Button>
              </Stack>
            </div>
          }
          secondaryTypographyProps={{ component: 'div' }}
        />
      </ListItemButton>
    </ListItem>
  );
};
