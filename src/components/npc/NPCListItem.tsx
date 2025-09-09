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
        className="rounded-lg mb-2 transition-all hover:scale-[1.02] hover:shadow-lg"
      >
        <ListItemAvatar>
          <StatusBadge status={npc.status}>
            <Avatar 
              src={npc.avatar} 
              alt={npc.name}
              sx={{ width: 40, height: 40 }}
            />
          </StatusBadge>
        </ListItemAvatar>
        <ListItemText
          primary={
            <Typography variant="body1" className="font-semibold">
              {npc.name}
            </Typography>
          }
          primaryTypographyProps={{ component: 'span' }}
          secondary={
            <div className="space-y-1">
              <Typography variant="body2" color="text.secondary">
                {npc.description}
              </Typography>
              <Typography 
                variant="caption" 
                color={
                  npc.status === 'online' ? 'success.main' :
                  npc.status === 'busy' ? 'warning.main' : 'error.main'
                }
                className="font-medium"
              >
                {formatNPCStatus(npc.status)}
              </Typography>
              <Stack direction="row" spacing={1} className="mt-1">
                <Button size="small" variant={isPlayer ? 'contained' : 'outlined'} onClick={(e) => { e.stopPropagation(); onPlayAs?.(npc); }}>Play as</Button>
                <Button size="small" variant={isTalkTarget ? 'contained' : 'outlined'} disabled={!activePlayerNpcId || activePlayerNpcId === npc.id} onClick={(e) => { e.stopPropagation(); onTalk?.(npc); }}>Talk</Button>
              </Stack>
            </div>
          }
          secondaryTypographyProps={{ component: 'div' }}
        />
      </ListItemButton>
    </ListItem>
  );
};
