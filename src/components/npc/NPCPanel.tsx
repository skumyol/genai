import React from 'react';
import { Card, CardHeader, CardContent, List, Typography, Divider } from '@mui/material';
import { NPCListItem } from './NPCListItem';
import { NPC } from '../../types/schema';

interface NPCPanelProps {
  npcs: NPC[];
  selectedNPCId: string | null;
  onNPCSelect: (npcId: string) => void;
  onNPCDoubleClick?: (npc: NPC) => void;
  onPlayAs?: (npc: NPC) => void;
  onTalk?: (npc: NPC) => void;
  activePlayerNpcId?: string | null;
  activeTalkTargetId?: string | null;
}

export const NPCPanel: React.FC<NPCPanelProps> = ({ 
  npcs, 
  selectedNPCId, 
  onNPCSelect, 
  onNPCDoubleClick,
  onPlayAs,
  onTalk,
  activePlayerNpcId,
  activeTalkTargetId,
}) => {
  const onlineNPCs = npcs.filter(npc => npc.status === 'online');
  const busyNPCs = npcs.filter(npc => npc.status === 'busy');
  const offlineNPCs = npcs.filter(npc => npc.status === 'offline');

  return (
    <Card className="h-full flex flex-col overflow-hidden">
      <CardHeader 
        title={
          <Typography 
            variant="h3" 
            className="text-center"
            sx={{ 
              fontSize: { xs: '1.1rem', sm: '1.25rem', md: '1.5rem' },
              fontWeight: { xs: 600, sm: 700 }
            }}
          >
            Available NPCs
          </Typography>
        }
        sx={{ 
          py: { xs: 1.5, sm: 2 },
          pb: { xs: 1, sm: 1.5 }
        }}
      />
      <Divider />
      <CardContent 
        className="p-0 flex-1 overflow-auto medieval-scroll"
        sx={{ 
          p: 0,
          '&:last-child': { pb: 0 }
        }}
      >
        <div 
          className="space-y-4"
          style={{ 
            padding: window.innerWidth < 600 ? '8px 16px' : '16px' 
          }}
        >
          {onlineNPCs.length > 0 && (
            <div>
              <Typography 
                variant="h6" 
                color="success.main" 
                className="mb-2 px-2"
                sx={{ 
                  fontSize: { xs: '0.875rem', sm: '1rem', md: '1.125rem' },
                  fontWeight: { xs: 500, sm: 600 }
                }}
              >
                Online ({onlineNPCs.length})
              </Typography>
              <List 
                dense
                sx={{ 
                  py: { xs: 0.5, sm: 1 }
                }}
              >
                {onlineNPCs.map((npc) => (
                  <NPCListItem
                    key={npc.id}
                    npc={npc}
                    isSelected={selectedNPCId === npc.id}
                    onSelect={onNPCSelect}
                    onDoubleClick={onNPCDoubleClick}
                    onPlayAs={onPlayAs}
                    onTalk={onTalk}
                    activePlayerNpcId={activePlayerNpcId}
                    activeTalkTargetId={activeTalkTargetId}
                  />
                ))}
              </List>
            </div>
          )}

          {busyNPCs.length > 0 && (
            <div>
              <Typography 
                variant="h6" 
                color="warning.main" 
                className="mb-2 px-2"
                sx={{ 
                  fontSize: { xs: '0.875rem', sm: '1rem', md: '1.125rem' },
                  fontWeight: { xs: 500, sm: 600 }
                }}
              >
                Busy ({busyNPCs.length})
              </Typography>
              <List 
                dense
                sx={{ 
                  py: { xs: 0.5, sm: 1 }
                }}
              >
                {busyNPCs.map((npc) => (
                  <NPCListItem
                    key={npc.id}
                    npc={npc}
                    isSelected={selectedNPCId === npc.id}
                    onSelect={onNPCSelect}
                    onDoubleClick={onNPCDoubleClick}
                    onPlayAs={onPlayAs}
                    onTalk={onTalk}
                    activePlayerNpcId={activePlayerNpcId}
                    activeTalkTargetId={activeTalkTargetId}
                  />
                ))}
              </List>
            </div>
          )}

          {offlineNPCs.length > 0 && (
            <div>
              <Typography 
                variant="h6" 
                color="error.main" 
                className="mb-2 px-2"
                sx={{ 
                  fontSize: { xs: '0.875rem', sm: '1rem', md: '1.125rem' },
                  fontWeight: { xs: 500, sm: 600 }
                }}
              >
                Offline ({offlineNPCs.length})
              </Typography>
              <List 
                dense
                sx={{ 
                  py: { xs: 0.5, sm: 1 }
                }}
              >
                {offlineNPCs.map((npc) => (
                  <NPCListItem
                    key={npc.id}
                    npc={npc}
                    isSelected={selectedNPCId === npc.id}
                    onSelect={onNPCSelect}
                    onDoubleClick={onNPCDoubleClick}
                    onPlayAs={onPlayAs}
                    onTalk={onTalk}
                    activePlayerNpcId={activePlayerNpcId}
                    activeTalkTargetId={activeTalkTargetId}
                  />
                ))}
              </List>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};
