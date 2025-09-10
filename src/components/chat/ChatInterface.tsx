import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Card, CardHeader, CardContent, List, TextField, IconButton, Stack, Typography, Divider, Fab } from '@mui/material';
import SendOutlinedIcon from '@mui/icons-material/SendOutlined';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import { MessageItem } from './MessageItem';
import { Message, NPC } from '../../types/schema';

interface ChatInterfaceProps {
  messages: Message[];
  selectedNPC: NPC | null;
  onSendMessage: (content: string, keystrokes?: number, approxTokens?: number) => void;
  isLoading: boolean;
}

export const ChatInterface: React.FC<ChatInterfaceProps> = ({ 
  messages, 
  selectedNPC, 
  onSendMessage, 
  isLoading 
}) => {
  const [messageInput, setMessageInput] = useState('');
  const [keystrokes, setKeystrokes] = useState(0);
  const [autoScroll, setAutoScroll] = useState(true);
  const [lastMessagesLength, setLastMessagesLength] = useState(0);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const keystrokeCountRef = useRef(0);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // Only auto-scroll if user is near bottom and new messages are added
  useEffect(() => {
    if (messages.length > lastMessagesLength && autoScroll) {
      scrollToBottom();
    }
    setLastMessagesLength(messages.length);
  }, [messages, autoScroll, lastMessagesLength]);

  // Check if user is near bottom when they scroll
  const handleScroll = (event: React.UIEvent<HTMLDivElement>) => {
    const { scrollTop, scrollHeight, clientHeight } = event.currentTarget;
    const isNearBottom = scrollTop + clientHeight >= scrollHeight - 100;
    setAutoScroll(isNearBottom);
  };

  const estimateTokens = (text: string) => Math.ceil(text.trim().split(/\s+/).filter(Boolean).length * 1.3);

  const handleSendMessage = useCallback(() => {
    if (messageInput.trim() && selectedNPC) {
      const approxTokens = estimateTokens(messageInput.trim());
      onSendMessage(messageInput.trim(), keystrokeCountRef.current || undefined, approxTokens);
      setMessageInput('');
      setKeystrokes(0);
      keystrokeCountRef.current = 0;
    }
  }, [messageInput, selectedNPC, onSendMessage]);

  const handleKeyPress = useCallback((event: React.KeyboardEvent) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSendMessage();
    }
  }, [handleSendMessage]);

  // Use a ref to track keystrokes without causing re-renders
  const handleKeyDown = useCallback(() => {
    keystrokeCountRef.current += 1;
    // Update state less frequently - only every 10 keystrokes for UI feedback
    if (keystrokeCountRef.current % 10 === 0) {
      setKeystrokes(keystrokeCountRef.current);
    }
  }, []);

  return (
    <Card 
      className="flex flex-col overflow-hidden relative"
      sx={{ 
        height: '100%',
        maxHeight: '100%',
        display: 'flex',
        flexDirection: 'column'
      }}
    >
      <CardHeader 
        title={
          <Typography variant="h3" className="text-center">
            {selectedNPC ? `Chat with ${selectedNPC.name}` : 'Chat History'}
          </Typography>
        }
        subheader={
          selectedNPC && (
            <Typography variant="body2" color="text.secondary" className="text-center">
              {selectedNPC.description}
            </Typography>
          )
        }
        sx={{ flexShrink: 0 }}
      />
      <Divider />
      
      <CardContent 
        className="flex-1 p-0 flex flex-col overflow-hidden"
        sx={{ 
          flex: 1, 
          display: 'flex', 
          flexDirection: 'column', 
          minHeight: 0 
        }}
      >
        <div 
          className="flex-1 overflow-auto medieval-scroll"
          ref={messagesContainerRef}
          onScroll={handleScroll}
          style={{ flex: 1, minHeight: 0 }}
        >
          {messages.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <Typography variant="body1" color="text.secondary" className="text-center">
                {selectedNPC ? 'Start a conversation...' : 'Select an NPC to start chatting'}
              </Typography>
            </div>
          ) : (
            <List className="py-2">
              {messages.map((message) => (
                <MessageItem key={message.id} message={message} />
              ))}
              <div ref={messagesEndRef} />
            </List>
          )}
        </div>

        <Divider />
        
        <div className="p-4" style={{ flexShrink: 0 }}>
          <Stack direction="row" spacing={2} alignItems="flex-end">
            <TextField
              fullWidth
              multiline
              maxRows={3}
              placeholder={selectedNPC ? "Type your message..." : "Select an NPC to start chatting"}
              value={messageInput}
              onChange={(e) => setMessageInput(e.target.value)}
              onKeyDown={handleKeyDown}
              onKeyPress={handleKeyPress}
              disabled={!selectedNPC || isLoading}
              variant="outlined"
              size="small"
            />
            <IconButton
              onClick={handleSendMessage}
              disabled={!messageInput.trim() || !selectedNPC || isLoading}
              color="primary"
              className="p-3"
            >
              <SendOutlinedIcon />
            </IconButton>
          </Stack>
        </div>
      </CardContent>

      {/* Scroll to bottom button - only show when not auto-scrolling */}
      {!autoScroll && (
        <Fab
          size="small"
          color="primary"
          onClick={() => {
            setAutoScroll(true);
            scrollToBottom();
          }}
          sx={{
            position: 'absolute',
            bottom: 80,
            right: 16,
            zIndex: 1
          }}
        >
          <KeyboardArrowDownIcon />
        </Fab>
      )}
    </Card>
  );
};
