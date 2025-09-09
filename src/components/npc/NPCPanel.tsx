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
          <Typography variant="h3" className="text-center">
            Available NPCs
          </Typography>
        }
      />
      <Divider />
      <CardContent className="p-0 flex-1 overflow-auto medieval-scroll">
        <div className="p-4 space-y-4">
          {onlineNPCs.length > 0 && (
            <div>
              <Typography variant="h6" color="success.main" className="mb-2 px-2">
                Online ({onlineNPCs.length})
              </Typography>
              <List dense>
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
              <Typography variant="h6" color="warning.main" className="mb-2 px-2">
                Busy ({busyNPCs.length})
              </Typography>
              <List dense>
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
              <Typography variant="h6" color="error.main" className="mb-2 px-2">
                Offline ({offlineNPCs.length})
              </Typography>
              <List dense>
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
