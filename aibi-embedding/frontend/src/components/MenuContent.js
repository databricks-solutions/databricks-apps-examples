import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { 
  List, 
  ListItem, 
  ListItemButton, 
  ListItemIcon, 
  ListItemText, 
  Stack 
} from '@mui/material';
import HomeRoundedIcon from '@mui/icons-material/HomeRounded';
import AnalyticsRoundedIcon from '@mui/icons-material/AnalyticsRounded';
import PeopleRoundedIcon from '@mui/icons-material/PeopleRounded';
import SettingsRoundedIcon from '@mui/icons-material/SettingsRounded';
import InfoRoundedIcon from '@mui/icons-material/InfoRounded';
import HelpRoundedIcon from '@mui/icons-material/HelpRounded';

export default function MenuContent() {
  const navigate = useNavigate();
  const location = useLocation();

  const mainListItems = [
    { text: 'Home', icon: <HomeRoundedIcon /> },
    { text: 'Analytics', icon: <AnalyticsRoundedIcon /> },
    { text: 'Genie', icon: <PeopleRoundedIcon /> }
  ];
  
  const secondaryListItems = [
    { text: 'Settings', icon: <SettingsRoundedIcon /> },
    { text: 'About', icon: <InfoRoundedIcon /> },
    { text: 'Feedback', icon: <HelpRoundedIcon /> },
  ];

  const handleClick = (event) => {
    navigate('/'+event.text.toLowerCase());
  };

  return (
    <Stack sx={{ flexGrow: 1, p: 1, justifyContent: 'space-between' }}>
      <List dense>
        {mainListItems.map((item, index) => (
          <ListItem key={index} disablePadding sx={{ display: 'block' }}>
            <ListItemButton selected={'/'+item.text.toLowerCase() === location.pathname.toLowerCase()} onClick={() => handleClick(item)}>
              <ListItemIcon>{item.icon}</ListItemIcon>
              <ListItemText primary={item.text} />
            </ListItemButton>
            
          </ListItem>
        ))}
        
      </List>
      <List dense>
        {secondaryListItems.map((item, index) => (
          <ListItem key={index} disablePadding sx={{ display: 'block' }}>
            <ListItemButton>
              <ListItemIcon>{item.icon}</ListItemIcon>
              <ListItemText primary={item.text} />
            </ListItemButton>
          </ListItem>
        ))}
      </List>
    </Stack>
  );
}