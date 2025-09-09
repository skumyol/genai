import React from 'react';
import { Badge, styled } from '@mui/material';
import { NPCStatus } from '../../types/enums';

interface StatusBadgeProps {
  status: NPCStatus;
  children: React.ReactNode;
}

const StyledBadge = styled(Badge)<{ status: NPCStatus }>(({ theme, status }) => ({
  '& .MuiBadge-badge': {
    backgroundColor: 
      status === NPCStatus.ONLINE ? theme.palette.success.main :
      status === NPCStatus.BUSY ? theme.palette.warning.main :
      theme.palette.error.main,
    color: 
      status === NPCStatus.ONLINE ? theme.palette.success.main :
      status === NPCStatus.BUSY ? theme.palette.warning.main :
      theme.palette.error.main,
    boxShadow: `0 0 0 2px ${theme.palette.background.paper}`,
    '&::after': {
      position: 'absolute',
      top: 0,
      left: 0,
      width: '100%',
      height: '100%',
      borderRadius: '50%',
      animation: status === NPCStatus.ONLINE ? 'ripple 1.2s infinite ease-in-out' : 'none',
      border: '1px solid currentColor',
      content: '""',
    },
  },
  '@keyframes ripple': {
    '0%': {
      transform: 'scale(.8)',
      opacity: 1,
    },
    '100%': {
      transform: 'scale(2.4)',
      opacity: 0,
    },
  },
}));

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, children }) => {
  return (
    <StyledBadge
      status={status}
      overlap="circular"
      anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      variant="dot"
    >
      {children}
    </StyledBadge>
  );
};