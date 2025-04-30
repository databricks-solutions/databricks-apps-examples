import React, { useState, useRef, useEffect } from "react";
import axios from "axios";
import { alpha } from "@mui/material/styles";
import {
  CssBaseline,
  Box,
  Stack,
  Paper,
  TextField,
  IconButton,
  LinearProgress,
  InputAdornment
} from "@mui/material";
import SendIcon from "@mui/icons-material/Send";
import AppNavbar from "../components/AppNavbar";
import Header from "../components/Header";
import SideMenu from "../components/SideMenu";
import AppTheme from "../theme/AppTheme";
import ChatMessage from "../components/ChatMessage";
import { useAuth } from "../context/AuthContext";

export default function Genie() {
  const { user } = useAuth();

  const initialMessage = { type: "bot", content: `Hi ${user.first_name}! 👋 Welcome to your personal data assistant. I’m here to help you explore and understand your data. Feel free to ask me anything related to ${user.company}'s sales on Brickstore — what can I assist you with today?` };

  const [messages, setMessages] = useState([initialMessage]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState("");

  // Make sure chatbot scrolls down to bottom of message
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };
  
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Retrieve environment variable
  const REACT_APP_API_BASE_URL = process.env.REACT_APP_API_BASE_URL;


  const handleSend = async () => {
    if (input.trim() === "") return;

    const userMessage = { type: "user", content: input };
    setMessages([...messages, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      let response;
      if (conversationId.length === 0) {
        response = await axios.post(
          `${REACT_APP_API_BASE_URL}/api/genie/start_conversation`,
          {
            databricks_token: user.databricks_token,
            question: input,
            user_company: user.company
          }
        );
        setConversationId(response.data.conversation_id);
      }
      else {
        response = await axios.post(
          `${REACT_APP_API_BASE_URL}/api/genie/continue_conversation`,
          {
            databricks_token: user.databricks_token,
            question: input,
            conversation_id: conversationId,
            user_company: user.company
          }
        );
      }

      let data;
      let content;
      if ("query_result" in response.data) {
        data = JSON.parse(response.data.query_result);
        content = response.data.description;
      } else {
        data = null;
        content = response.data.content;
      }
      const botMessage = { type: "bot", content: content, table: data };
      setMessages((prevMessages) => [...prevMessages, botMessage]);
    } catch (error) {
      console.error("Error fetching response:", error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AppTheme>
      <CssBaseline enableColorScheme />
      <Box sx={{ display: "flex" }}>
        <SideMenu />
        <AppNavbar />

        <Box
          component="main"
          sx={(theme) => ({
            flexGrow: 1,
            backgroundColor: theme.vars
              ? `rgba(${theme.vars.palette.background.defaultChannel} / 1)`
              : alpha(theme.palette.background.default, 1),
            overflow: "auto",
          })}
        >
          <Stack
            spacing={2}
            sx={{
              alignItems: "center",
              mx: 3,
              pb: 5,
              mt: { xs: 8, md: 0 },
            }}
          >
            <Header />
            {user ? <>Ask Genie 💡</> : null}

            <Box sx={{ maxWidth: 1000, margin: "auto", mt: 4 }}>
              <Paper
                elevation={3}
                sx={{ minWidth: 1000, height: 700, overflow: "auto", p: 2, mb: 2 ,boxShadow: 'none'}}
              >
                {messages.map((message, index) => (
                  <ChatMessage key={index} message={message} />
                ))}
                {isLoading && <LinearProgress sx={{height: 3}}/>}

                <div ref={messagesEndRef} />
              </Paper>
              <Box sx={{ display: "flex", alignItems: "center" }}>
              <TextField
            fullWidth
            variant="outlined"
            placeholder="Ask a question..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => e.key === "Enter" && handleSend()}
            disabled={isLoading}
            InputProps={{
              endAdornment: (
                <InputAdornment position="end">
                <IconButton
                  onClick={handleSend}
                  disabled={isLoading}
                  sx={{
                    color: 'primary.main',
                    border: 'none',
                        '&:hover': {
      backgroundColor: 'transparent',
    },
                  }}
                >
                  <SendIcon />
                </IconButton>
              </InputAdornment>
              ),
            }}
          />
              </Box>
            </Box>
            
          </Stack>
        </Box>
      </Box>
    </AppTheme>
  );
}
