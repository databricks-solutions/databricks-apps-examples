// src/context/AuthContext.js
import React, { createContext, useState, useContext, useEffect } from 'react';
import axios from 'axios';

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState();
  const [isLoading, setIsLoading] = useState(true);
  
  useEffect(() => {
    const storedUser = localStorage.getItem("user");
    if (storedUser) {
      setUser(JSON.parse(storedUser));
    }
    setIsLoading(false);
  }, []);

  // Retrieve environment variable
  const REACT_APP_API_BASE_URL = process.env.REACT_APP_API_BASE_URL;

  const login = async (email, password) => {
    setIsLoading(true);
    try {
      const response = await axios.post(`${REACT_APP_API_BASE_URL}/api/login`, {
        email,
        password
      });
      localStorage.setItem("user", JSON.stringify(response.data));   
      setUser(response.data);

    } catch (error) {
      console.error("Login failed:", error);
    }
    setIsLoading(false);
  };

  const logout = () => {
    // Implement logout logic here
    localStorage.removeItem("user");
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, isAuthenticated: !!user, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
};

export const useAuth = () => useContext(AuthContext);
