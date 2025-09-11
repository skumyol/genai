import React from 'react';
import { ListItem, ListItemAvatar, ListItemText, Avatar, Typography, Chip, Stack, Box } from '@mui/material';
import { Message } from '../../types/schema';
import { MessageType } from '../../types/enums';
import { formatMessageTime, formatTimePeriod } from '../../utils/formatters';

interface MessageItemProps {
  message: Message;
}

export const MessageItem: React.FC<MessageItemProps> = ({ message }) => {
  const isUserMessage = message.type === MessageType.USER;
  const isSystemMessage = message.type === MessageType.SYSTEM;

  if (isSystemMessage) {
    return (
      <ListItem 
        className="flex justify-center"
        sx={{ py: { xs: 2, sm: 4 } }}
      >
        <Chip 
          label={message.content}
          color="secondary"
          variant="outlined"
          className="text-center"
          size="small"
          sx={{
            fontSize: { xs: '0.75rem', sm: '0.875rem' },
            maxWidth: '90%',
            '& .MuiChip-label': {
              px: { xs: 1, sm: 1.5 },
              whiteSpace: 'normal',
              wordBreak: 'break-word'
            }
          }}
        />
      </ListItem>
    );
  }

  return (
    <ListItem 
      className={`flex ${isUserMessage ? 'justify-end' : 'justify-start'}`}
      alignItems="flex-start"
      sx={{ 
        py: { xs: 1, sm: 2 },
        px: { xs: 1, sm: 2 }
      }}
    >
      <div className={`flex ${isUserMessage ? 'flex-row-reverse' : 'flex-row'} items-start space-x-3`} style={{ maxWidth: '85%' }}>
        {!isUserMessage && (
          <ListItemAvatar className="mt-1">
            <Avatar 
              sx={{ 
                width: { xs: 28, sm: 32 }, 
                height: { xs: 28, sm: 32 },
                fontSize: { xs: '0.875rem', sm: '1rem' }
              }}
            >
              {message.npcName?.charAt(0) || 'N'}
            </Avatar>
          </ListItemAvatar>
        )}
        
        <div className={`${isUserMessage ? 'mr-2 sm:mr-3' : 'ml-0'}`}>
          <Box 
            className="rounded-lg"
            sx={{
              // Ensure long content wraps and never forces horizontal scroll
              overflowWrap: 'anywhere',
              wordBreak: 'break-word',
              maxWidth: '100%',
              p: { xs: 1, sm: 1.5, md: 2 },
              backgroundColor: isUserMessage ? 'primary.main' : 'grey.800',
              color: isUserMessage ? 'primary.contrastText' : 'text.primary',
              ml: isUserMessage ? 'auto' : 0,
              border: '1px solid',
              borderColor: isUserMessage ? 'primary.main' : 'grey.700'
            }}
          >
            {!isUserMessage && message.npcName && (
              <Typography 
                variant="caption" 
                className="font-semibold block mb-1"
                sx={{ fontSize: { xs: '0.75rem', sm: '0.875rem' } }}
              >
                {message.npcName}
              </Typography>
            )}
            <Typography 
              variant="body1"
              sx={{ 
                whiteSpace: 'pre-wrap', 
                wordBreak: 'break-word', 
                overflowWrap: 'anywhere',
                fontSize: { xs: '0.875rem', sm: '1rem' },
                lineHeight: { xs: 1.4, sm: 1.5 }
              }}
            >
              {message.content}
            </Typography>
          </Box>
          
          <Stack 
            direction="row" 
            spacing={{ xs: 0.5, sm: 1 }} 
            className={`mt-1 ${isUserMessage ? 'justify-end' : 'justify-start'}`}
          >
            <Typography 
              variant="caption" 
              color="text.secondary"
              sx={{ fontSize: { xs: '0.625rem', sm: '0.75rem' } }}
            >
              {formatMessageTime(message.timestamp)}
            </Typography>
            <Typography 
              variant="caption" 
              color="text.secondary"
              sx={{ 
                fontSize: { xs: '0.625rem', sm: '0.75rem' },
                display: { xs: 'none', sm: 'block' }
              }}
            >
              Day {message.day} • {formatTimePeriod(message.timePeriod)}
            </Typography>
          </Stack>
        </div>
      </div>
    </ListItem>
  );
};
