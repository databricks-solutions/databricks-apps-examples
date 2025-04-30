import React from 'react';
import { BrowserRouter as Router, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import Home from './pages/Home';
import Login from './pages/Login';
import Analytics from './pages/Analytics';
import Genie from './pages/Genie';
import PrivateRoute from './components/PrivateRoute';

function App() {
  return (
    
    <AuthProvider>
      <Router>
        <Routes>
          <Route path="/" element={<Login/>} />
          <Route path="/login" element={<Login/>} />
          <Route element={<PrivateRoute />}>
            <Route path="/" element={<Home/>} />
            <Route path="/home" element={<Home/>} />
            <Route path="/analytics" element={<Analytics/>} />
            <Route path="/genie" element={<Genie/>} />
          </Route>
        </Routes>
      </Router>
    </AuthProvider> 
  );
}

export default App;