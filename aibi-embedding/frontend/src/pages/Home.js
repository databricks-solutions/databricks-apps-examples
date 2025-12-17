// src/pages/Home.js
import React from 'react';
import { alpha } from '@mui/material/styles';
import { 
  CssBaseline, 
  Box, 
  Stack, 
  Typography, 
  Container 
} from '@mui/material';
import AppNavbar from '../components/AppNavbar';
import MainContent from '../components/MainContent';
import Header from '../components/Header';
import SideMenu from '../components/SideMenu';
import AppTheme from '../theme/AppTheme';
import { useAuth } from '../context/AuthContext';


export default function Home() {
    const { user } = useAuth();

    return (
        <AppTheme  >
          <CssBaseline enableColorScheme />
          <Box sx={{ display: 'flex' }}>
            <SideMenu />
            <AppNavbar />
            <Box
              component="main"
              sx={(theme) => ({
                flexGrow: 1,
                backgroundColor: theme.vars
                  ? `rgba(${theme.vars.palette.background.defaultChannel} / 1)`
                  : alpha(theme.palette.background.default, 1),
                overflow: 'auto',
              })}
            >
              <Stack
                spacing={2}
                sx={{
                  alignItems: 'center',
                  mx: 3,
                  pb: 5,
                  mt: { xs: 8, md: 0 },
                }}
              >

                          <Header />
            {user ? (
              <Typography variant="h4" sx={{ textAlign: 'center', mt: 2 }}>
                Welcome back, {user.first_name} from {user.company}! 👋
              </Typography>
            ) : (
              <Typography variant="h4" sx={{ textAlign: 'center', mt: 2 }}>
                Welcome to Brickstore! The ultimate platform for selling bricks.
              </Typography>
            )}

            {/* Description Section */}
            <Typography variant="body1" sx={{ textAlign: 'center', maxWidth: '600px' }}>
            At Brickstore, we connect 🤝 retailers with a wide variety of high-quality bricks 🧱. Whether you're a small business or a large construction company, we make it easy for you to find and sell the perfect bricks for your projects.

            </Typography>
            <Container
        maxWidth="lg"
        component="main"
        sx={{ display: 'flex', flexDirection: 'column', my: 16, gap: 4 }}
      >
        <MainContent />
      </Container>

          </Stack>
            </Box>
          </Box>
        </AppTheme>
      )
    };