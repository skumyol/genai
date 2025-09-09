import React from 'react';
import { Dialog, DialogTitle, DialogContent, DialogActions, Button, Typography } from '@mui/material';

interface ExperimentGuideModalProps {
  open: boolean;
  onClose: () => void;
  content?: string;
}

export const ExperimentGuideModal: React.FC<ExperimentGuideModalProps> = ({ open, onClose, content }) => {
  const text = (content && content.trim().length > 0)
    ? content
    : `Welcome to the experiment.

Instructions:
1) Click 'Play as' on a character.
2) Click 'Talk' on another NPC to set your target.
3) Use the chat to send a message and observe the NPC’s response.

You can also load predefined test sessions using the header buttons.`;

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Experiment Guide</DialogTitle>
      <DialogContent>
        <Typography variant="body1" whiteSpace="pre-wrap">
          {text}
        </Typography>
      </DialogContent>
      <DialogActions>
        <Button variant="contained" onClick={onClose}>Got it</Button>
      </DialogActions>
    </Dialog>
  );
};

