// src/components/PrivateRoute.js
import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { CircularProgress, Box, Typography } from '@mui/material';

const PrivateRoute = ({ component: Component, ...rest }) => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <Box
        display="flex"
        flexDirection="column"
        alignItems="center"
        justifyContent="center"
        height="100vh"
      >
        <CircularProgress size={60} />
        <Typography variant="h6" style={{ marginTop: '16px' }}>
          Loading
        </Typography>
      </Box>
    );
  }

  return (
    isAuthenticated ? <Outlet /> : <Navigate to="/login" />
  );
};

export default PrivateRoute;
