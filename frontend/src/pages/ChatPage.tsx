import { useState } from 'react';
import {
  Box,
  TextField,
  Button,
  Paper,
  Typography,
  List,
  ListItem,
  ListItemText,
  IconButton,
  Divider,
  useTheme,
  CircularProgress,
} from '@mui/material';
import {
  Fullscreen as FullscreenIcon,
  FullscreenExit as FullscreenExitIcon,
} from '@mui/icons-material';
import { GeminiService, LLMResponse } from '../services/llmService';

interface Message {
  text: string;
  isUser: boolean;
  timestamp: Date;
}

const ChatPage = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const theme = useTheme();

  // Initialize Gemini service with API key from environment variables
  const llmService = new GeminiService(import.meta.env.VITE_GEMINI_API_KEY);

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return;

    // Add user message
    const userMessage: Message = {
      text: inputMessage,
      isUser: true,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);

    try {
      // Get AI response using the LLM service
      const response: LLMResponse = await llmService.sendMessage(inputMessage);
      
      const aiMessage: Message = {
        text: response.text,
        isUser: false,
        timestamp: response.timestamp,
      };

      setMessages((prev) => [...prev, aiMessage]);
    } catch (error) {
      console.error('Error getting AI response:', error);
      // Add error message to chat
      const errorMessage: Message = {
        text: "I apologize, but I'm having trouble processing your request right now. Please try again later.",
        isUser: false,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Box
      sx={{
        height: '100vh',
        width: '100vw',
        display: 'flex',
        bgcolor: 'background.default',
      }}
    >
      {/* Chat Section */}
      <Box
        sx={{
          width: isFullscreen ? '100%' : '50%',
          display: 'flex',
          flexDirection: 'column',
          transition: 'width 0.3s ease-in-out',
          borderRight: isFullscreen ? 'none' : `1px solid ${theme.palette.divider}`,
        }}
      >
        {/* Header */}
        <Paper
          elevation={2}
          sx={{
            p: 2,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            bgcolor: 'background.paper',
          }}
        >
          <Typography variant="h5" sx={{ fontWeight: 'bold' }}>
            Chat with Your AI Assistant
          </Typography>
          <IconButton
            onClick={() => setIsFullscreen(!isFullscreen)}
            color="primary"
            sx={{ ml: 2 }}
          >
            {isFullscreen ? <FullscreenExitIcon /> : <FullscreenIcon />}
          </IconButton>
        </Paper>

        {/* Chat Messages */}
        <Box
          sx={{
            flex: 1,
            overflow: 'auto',
            p: 2,
            display: 'flex',
            flexDirection: 'column',
            gap: 2,
            bgcolor: 'background.default',
          }}
        >
          {messages.map((message, index) => (
            <ListItem
              key={index}
              sx={{
                flexDirection: 'column',
                alignItems: message.isUser ? 'flex-end' : 'flex-start',
                px: 2,
              }}
            >
              <Paper
                elevation={1}
                sx={{
                  p: 2,
                  maxWidth: '80%',
                  backgroundColor: message.isUser ? 'primary.light' : 'grey.100',
                  borderRadius: 2,
                  position: 'relative',
                  '&:hover': {
                    boxShadow: 2,
                  },
                }}
              >
                <ListItemText
                  primary={message.text}
                  secondary={message.timestamp.toLocaleTimeString()}
                />
              </Paper>
            </ListItem>
          ))}
        </Box>

        {/* Input Area */}
        <Paper
          elevation={2}
          sx={{
            p: 2,
            bgcolor: 'background.paper',
          }}
        >
          <Box sx={{ display: 'flex', gap: 1 }}>
            <TextField
              fullWidth
              variant="outlined"
              placeholder="Type your message..."
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
              disabled={isLoading}
            />
            <Button
              variant="contained"
              onClick={handleSendMessage}
              disabled={!inputMessage.trim() || isLoading}
              sx={{ minWidth: '100px' }}
            >
              {isLoading ? <CircularProgress size={24} /> : 'Send'}
            </Button>
          </Box>
        </Paper>
      </Box>

      {/* Content Display Section */}
      {!isFullscreen && (
        <Box
          sx={{
            width: '50%',
            display: 'flex',
            flexDirection: 'column',
            bgcolor: 'background.paper',
          }}
        >
          {/* Content Header */}
          <Paper
            elevation={2}
            sx={{
              p: 2,
              bgcolor: 'background.paper',
            }}
          >
            <Typography variant="h5" sx={{ fontWeight: 'bold' }}>
              Generated Content
            </Typography>
          </Paper>

          {/* Content Area */}
          <Box
            sx={{
              flex: 1,
              overflow: 'auto',
              p: 3,
              bgcolor: 'background.default',
            }}
          >
            {/* TODO: Replace with actual content display */}
            <Typography variant="body1" color="text.secondary" align="center">
              Your personalized meal plans and nutritional advice will appear here
            </Typography>
          </Box>
        </Box>
      )}
    </Box>
  );
};

export default ChatPage; 