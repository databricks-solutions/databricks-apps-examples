import React, { useEffect, useState } from 'react';
import axios from "axios";
import { alpha } from '@mui/material/styles';
import { CssBaseline, Box, Stack } from '@mui/material';
import AppNavbar from '../components/AppNavbar';
import Header from '../components/Header';
import SideMenu from '../components/SideMenu';
import AppTheme from '../theme/AppTheme';
import { useAuth } from '../context/AuthContext';
import { DatabricksDashboard } from '@databricks/aibi-client'

export default function Analytics() {
  const { user } = useAuth();

  const [dashboardConfig, setDashboardConfig] = useState(null);
  const [token, setToken] = useState(null);

  // Retrieve environment variable
  const REACT_APP_API_BASE_URL = process.env.REACT_APP_API_BASE_URL;

  useEffect(() => {
    // Fetch dashboard configuration
    fetchConfig();
    // Fetch initial token
    fetchToken();
  }, []);

  const fetchConfig = async () => {
    const response = await axios.post(
    `${REACT_APP_API_BASE_URL}/api/dashboard/config`);
    const data = await response.data;
    console.log(data);
    setDashboardConfig(data);
  }
  const fetchToken = async () => {
    const response = await axios.post(
      `${REACT_APP_API_BASE_URL}/api/dashboard/get_token`,
      {
        external_data: user.company,
        external_viewer_id: user.email,
        dashboard_name: 'defects'
      });
    const data = await response.data;
    console.log(data);
    setToken(data);
  };

  useEffect(() => {
    if (dashboardConfig && token) {
      const dashboardContainer = document.getElementById("dashboard-container");
      if (dashboardContainer && !dashboardContainer.hasChildNodes()) {  //CHECK HERE
        const dashboard = new DatabricksDashboard({
          instanceUrl: dashboardConfig.instance_url,
          workspaceId: dashboardConfig.workspace_id,
          dashboardId: dashboardConfig.dashboard_id,
          token: token,
          container: dashboardContainer,
          getNewToken: fetchToken
        });

        dashboard.initialize();
      }
    }
  }, [dashboardConfig, token]);

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
                <>Analyze 📈</>
                 
              </Stack>
              <Box
                sx={{
                  alignItems: 'center',
                  mx: 3,
                  pb: 5,
                  mt: { xs: 8, md: 0 },
                }}>
                <style jsx>
                  {`
                    #dashboard-container {
                      width: 100%;
                      border: none;
                    }

                    #dashboard-container > iframe {
                      width: 100%;
                      height: 100vh;
                      border: none;
                    }
                  `}
                </style>

                <Box id="dashboard-container"></Box>
              </Box>
            </Box>
          </Box>
        </AppTheme>
    
      )
    };