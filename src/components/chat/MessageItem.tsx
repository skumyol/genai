import React from 'react';
import { ListItem, ListItemAvatar, ListItemText, Avatar, Typography, Chip, Stack } from '@mui/material';
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
      <ListItem className="flex justify-center py-4">
        <Chip 
          label={message.content}
          color="secondary"
          variant="outlined"
          className="text-center"
        />
      </ListItem>
    );
  }

  return (
    <ListItem 
      className={`flex ${isUserMessage ? 'justify-end' : 'justify-start'} py-2`}
      alignItems="flex-start"
    >
      <div className={`flex ${isUserMessage ? 'flex-row-reverse' : 'flex-row'} items-start space-x-3 max-w-[80%]`}>
        {!isUserMessage && (
          <ListItemAvatar className="mt-1">
            <Avatar className="w-8 h-8">
              {message.npcName?.charAt(0) || 'N'}
            </Avatar>
          </ListItemAvatar>
        )}
        
        <div className={`${isUserMessage ? 'mr-3' : 'ml-0'}`}>
          <div 
            className={`rounded-lg p-3 ${
              isUserMessage 
                ? 'bg-primary-main text-primary-contrastText ml-auto' 
                : 'bg-grey-800 text-text-primary'
            }`}
            style={{
              // Ensure long content wraps and never forces horizontal scroll
              overflowWrap: 'anywhere',
              wordBreak: 'break-word',
              maxWidth: '100%'
            }}
          >
            {!isUserMessage && message.npcName && (
              <Typography variant="caption" className="font-semibold block mb-1">
                {message.npcName}
              </Typography>
            )}
            <Typography 
              variant="body1"
              sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', overflowWrap: 'anywhere' }}
            >
              {message.content}
            </Typography>
          </div>
          
          <Stack direction="row" spacing={1} className={`mt-1 ${isUserMessage ? 'justify-end' : 'justify-start'}`}>
            <Typography variant="caption" color="text.secondary">
              {formatMessageTime(message.timestamp)}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Day {message.day} • {formatTimePeriod(message.timePeriod)}
            </Typography>
          </Stack>
        </div>
      </div>
    </ListItem>
  );
};
